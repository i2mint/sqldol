"""Read Microsoft Access files (``.mdb``, ``.accdb``: Jet3, Jet4, ACE) as Mappings and as engines.

There is no SQLAlchemy dialect for Access off Windows, so this module bridges into the seam the
rest of sqldol already has (``engine``):

- :class:`AccessReader` ``(path)`` is a ``Mapping`` of table name to rows (a list of dicts).
  No SQL involved. :class:`AccessColumns` ``(path_or_reader)`` is its sibling: table name to
  column names, in definition order.
- :func:`access_engine` ``(path)`` copies the tables into SQLite (in memory unless you give a
  ``sqlite_path``) and returns a SQLAlchemy ``Engine``, so every sqldol store works on an Access
  file: ``TablesDol(engine)``, ``SqlDictReader(engine, 'Items', key_columns='ID')``, ...
  It is a **snapshot**: writes through that engine change the copy, never the Access file.
- :func:`check_requirements` says which backends this machine has, and how to get one.

The file is read by a **backend**, chosen at runtime. None is a hard dependency:

- ``'mdbtools'``: the mdbtools command-line programs, if they are on ``PATH``
  (``brew install mdbtools``, ``apt install mdbtools``). Called as programs, not linked.
  Reads Jet3, Jet4 and ACE, with Access's own column types.
- ``'access_parser'``: pure Python, ``pip install "sqldol[access]"`` (Apache-2.0). Needs
  nothing else, but cannot open some files (ACE ``.accdb`` files written by Jackcess, some
  long memo layouts).

``backend=None`` tries the available ones in that order and takes the first that opens the
file. A backend can also be any callable ``backend(path)`` returning an object with
``table_names()``, ``column_names(table)`` and ``rows(table)`` (an iterable of dicts); UCanAccess
would fit there. A *live* Windows ODBC engine would not: it would be its own function, since
``access_engine``'s contract is that it never writes to the Access file.

Values are normalised so the two backends agree: text is ``str`` (Jet3 read as cp1252),
Currency and Numeric are ``decimal.Decimal``, Yes/No is ``bool``, Replication ID (GUID) is
``'{0B339502-3145-11D2-8D45-0080C6FD2CAA}'``, binary is ``bytes``, and date/times are
``'YYYY-MM-DD HH:MM:SS'`` strings. Known differences that remain:

- Jet3 text holding UTF-8 bytes (text pasted into the database already encoded): ``mdbtools``
  shows it as Access does (``'â€”'``); ``access_parser`` tries UTF-8 first and gives the
  intended ``'—'``.
- ``access_parser`` returns a Currency field that has a Format property as the formatted
  string (``'$1,234.57'``), which cannot be turned back into the exact amount.

Each table is read into memory whole (``reader[table]``, and one table at a time by
``access_engine``).

>>> reader = AccessReader('some.mdb', backend=_DictSource.factory({
...     'Items': [{'ID': 1, 'Title': 'alpha'}, {'ID': 2, 'Title': 'beta'}],
... }))
>>> list(reader)
['Items']
>>> reader['Items'][1]
{'ID': 2, 'Title': 'beta'}
>>> from sqldol import SqlDictReader
>>> engine = access_engine(reader)
>>> SqlDictReader(engine, 'Items', key_columns='ID')[2]
{'ID': 2, 'Title': 'beta'}

(``_DictSource`` stands in for a real file here; with one, write ``AccessReader('songs.mdb')``.)
"""

# extraction candidate: an ``mdbdol`` package, once Access-specific concerns beyond tables
# appear (write-back, saved queries, relationships, more backends). See i2mint/sqldol#15.

import base64
import datetime
import decimal
import importlib.util
import json
import logging
import os
import re
import shutil
import subprocess
import uuid
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from functools import cached_property, partial

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    Integer,
    LargeBinary,
    MetaData,
    Table,
    Text,
    create_engine,
)
from sqlalchemy import event
from sqlalchemy.engine import URL
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import UserDefinedType

__all__ = [
    "AccessReader",
    "AccessColumns",
    "access_engine",
    "check_requirements",
    "MissingAccessBackendError",
    "AccessReadError",
    "BACKENDS",
]


class MissingAccessBackendError(ImportError):
    """No backend that can read Access files is available (or the one asked for is not)."""


class AccessReadError(RuntimeError):
    """A backend could not read the file (or one of its tables)."""


# --------------------------------------------------------------------------------------
# Backends


@contextmanager
def _quiet_logger(name, level=logging.CRITICAL):
    """Raise a logger's level for the duration (access_parser logs recoverable chunk errors)."""
    logger = logging.getLogger(name)
    previous = logger.level
    logger.setLevel(level)
    try:
        yield
    finally:
        logger.setLevel(previous)


class MdbtoolsSource:
    """Reads an Access file with the mdbtools programs (``mdb-ver``, ``mdb-tables``,
    ``mdb-schema``, ``mdb-json``)."""

    name = "mdbtools"
    install_hint = (
        "brew install mdbtools   (macOS)  |  sudo apt-get install mdbtools   (Debian/Ubuntu)"
        "  |  https://github.com/mdbtools/mdbtools"
    )
    programs = ("mdb-ver", "mdb-tables", "mdb-schema", "mdb-json")
    datetime_format = "%Y-%m-%d %H:%M:%S"
    date_format = "%Y-%m-%d"

    @classmethod
    def is_available(cls) -> bool:
        return all(shutil.which(program) for program in cls.programs)

    def __init__(self, path):
        self.path = os.fspath(path)
        if not os.path.exists(self.path):
            raise FileNotFoundError(self.path)
        self.version = self._run("mdb-ver", self.path).strip()  # fails early on a non-Access file

    def _run(self, *args) -> str:
        try:
            return subprocess.run(
                args, capture_output=True, check=True, text=True, encoding="utf-8"
            ).stdout
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or "").strip() or f"exit status {error.returncode}"
            raise AccessReadError(f"{args[0]} could not read {self.path!r}: {detail}") from error
        except UnicodeDecodeError as error:
            raise AccessReadError(
                f"{args[0]} wrote non-UTF-8 output for {self.path!r} (an mdbtools built "
                f"without iconv?): {error}"
            ) from error

    def table_names(self) -> list[str]:
        return [line for line in self._run("mdb-tables", "-1", self.path).splitlines() if line]

    def _columns(self, table: str) -> list[tuple[str, str]]:
        ddl = self._run(
            "mdb-schema", "-T", table, "--no-indexes", "--no-relations", self.path, "access"
        )
        return _columns_of_create_table(ddl)

    def column_names(self, table: str) -> list[str]:
        return [name for name, _ in self._columns(table)]

    def rows(self, table: str) -> Iterator[dict]:
        columns = [(name, _mdbtools_converter(t)) for name, t in self._columns(table)]
        out = self._run(
            "mdb-json", "-D", self.date_format, "-T", self.datetime_format, self.path, table
        )
        for line in out.splitlines():
            if line:
                # Decimal, not float, so Currency/Numeric keep every digit; mdb-json leaves out
                # the null fields
                record = json.loads(line, parse_float=decimal.Decimal)
                yield {name: convert(record.get(name)) for name, convert in columns}


def _mdbtools_converter(access_type: str) -> Callable:
    """How to normalise an ``mdb-json`` value, given the column's Access type."""
    if access_type == "Replication ID":
        return _guid_from_mdb_json
    if access_type.startswith(("Currency", "Numeric")):
        return _decimal
    if access_type.startswith("Boolean"):
        return _bool
    return _plain_from_mdb_json


def _plain_from_mdb_json(value):
    """Binaries to bytes; the other non-integers (Double, Single) back to float."""
    if isinstance(value, decimal.Decimal):
        return float(value)
    return _decoded_binary(value)


def _decoded_binary(value):
    """mdb-json writes binary values as ``{"$binary": <base64>, "$type": ...}``."""
    if isinstance(value, dict) and "$binary" in value:
        return base64.b64decode(value["$binary"])
    return value


def _guid_from_mdb_json(value):
    """mdb-json writes a GUID as libmdb's text form of it, base64'd as a binary."""
    raw = _decoded_binary(value)
    if isinstance(raw, bytes):
        return _canonical_guid(uuid.UUID(raw.decode("ascii").strip("{}")))
    return raw


def _decimal(value):
    """Currency and Numeric, exactly (``str`` first, so a float's repr is kept, not its binary).

    >>> _decimal(1234.5678), _decimal('123456789012345678.'), _decimal(None)
    (Decimal('1234.5678'), Decimal('123456789012345678'), None)
    """
    if value is None or isinstance(value, decimal.Decimal):
        return value
    return decimal.Decimal(str(value))


def _bool(value):
    return value if value is None else bool(value)


def _canonical_guid(guid: uuid.UUID) -> str:
    """Access's own display form of a GUID.

    >>> _canonical_guid(uuid.UUID('0b339502-3145-11d2-8d45-0080c6fd2caa'))
    '{0B339502-3145-11D2-8D45-0080C6FD2CAA}'
    """
    return "{" + str(guid).upper() + "}"


# Access forbids brackets in names, so the bracketed form is unambiguous.
_DDL_COLUMN = re.compile(r"^\s*\[([^\]]+)\]\s+(.*?),?\s*$", re.MULTILINE)


def _columns_of_create_table(ddl: str) -> list[tuple[str, str]]:
    """``(name, Access type)`` pairs, in order, from ``mdb-schema -T <t> <file> access``.

    >>> _columns_of_create_table(
    ...     'CREATE TABLE [T]\\n (\\n\\t[ID]\\t\\t\\tLong Integer, \\n\\t[My Name]\\t\\t\\tText (50)\\n);'
    ... )
    [('ID', 'Long Integer'), ('My Name', 'Text (50)')]
    """
    body = ddl[ddl.index("(") + 1 :] if "(" in ddl else ""
    return _DDL_COLUMN.findall(body)


class AccessParserSource:
    """Reads an Access file with the pure-Python ``access_parser`` package."""

    name = "access_parser"
    install_hint = 'pip install "sqldol[access]"   (or: pip install access-parser)'

    @staticmethod
    def is_available() -> bool:
        return importlib.util.find_spec("access_parser") is not None

    def __init__(self, path):
        from access_parser import AccessParser

        try:
            with _quiet_logger("access_parser"):
                self._db = AccessParser(os.fspath(path))
        except FileNotFoundError:
            raise
        except Exception as error:  # it raises KeyError, struct.error, ... on files it can't parse
            raise AccessReadError(
                f"access_parser could not open {os.fspath(path)!r}: "
                f"{type(error).__name__}: {error}. Try backend='mdbtools'."
            ) from error

    def table_names(self) -> list[str]:
        return [name for name in self._db.catalog if not name.startswith("MSys")]

    def _columns(self, table: str) -> list:
        with _quiet_logger("access_parser"):
            columns = self._db.get_table(table).columns
        # keyed by the column's position in the table definition
        return [columns[i] for i in sorted(columns)]

    def column_names(self, table: str) -> list[str]:
        return [column.col_name_str for column in self._columns(table)]

    def rows(self, table: str) -> Iterator[dict]:
        try:
            with _quiet_logger("access_parser"):
                data = self._db.get_table(table).parse()
        except Exception as error:
            raise AccessReadError(
                f"access_parser could not read table {table!r}: {type(error).__name__}: "
                f"{error}. Try backend='mdbtools'."
            ) from error
        fixes = {c.col_name_str: self._fix_for(c) for c in self._columns(table)}
        names = list(fixes)
        n_rows = len(data[names[0]]) if names else 0
        for i in range(n_rows):
            yield {name: fixes[name](data[name][i]) for name in names}

    def _fix_for(self, column) -> Callable:
        """Undo what access_parser 0.0.6 gets wrong: Jet3 text decoded as latin-1 (Jet3 is
        cp1252), GUIDs formatted from their little-endian bytes, Currency as an int scaled by
        10**4, Numeric as a string that loses its decimal point when the digits are fewer
        than the scale."""
        column_type = column.type
        if column_type == _ACCESS_PARSER_TYPE_GUID:
            return _guid_from_access_parser
        if column_type == _ACCESS_PARSER_TYPE_MONEY:
            return _money_from_access_parser
        if column_type == _ACCESS_PARSER_TYPE_NUMERIC:
            scale = (column.get("various") or {}).get("scale", 0)
            return partial(_numeric_from_access_parser, scale=scale)
        if column_type in _ACCESS_PARSER_TEXT_TYPES and self._db.version == 3:
            return _cp1252_from_latin1
        return _identity


# access_parser.utils type codes
_ACCESS_PARSER_TYPE_MONEY = 5
_ACCESS_PARSER_TYPE_GUID = 15
_ACCESS_PARSER_TYPE_NUMERIC = 16
_ACCESS_PARSER_TEXT_TYPES = (10, 12)  # TYPE_TEXT, TYPE_MEMO


def _identity(value):
    return value


def _money_from_access_parser(value):
    """Currency is stored as an integer count of 1/10000ths.

    >>> _money_from_access_parser(12345678), _money_from_access_parser('$1,234.57')
    (Decimal('1234.5678'), '$1,234.57')
    """
    if isinstance(value, int) and not isinstance(value, bool):
        return decimal.Decimal(value).scaleb(-4)
    return value  # None, or the formatted string it returns when the field has a Format


def _numeric_from_access_parser(value, *, scale: int):
    """access_parser writes the digits, and puts the point in only when they outnumber the scale.

    >>> _numeric_from_access_parser('10000000000000000001', scale=20)
    Decimal('0.10000000000000000001')
    >>> _numeric_from_access_parser('-12.50', scale=2), _numeric_from_access_parser('7.', scale=0)
    (Decimal('-12.50'), Decimal('7'))
    """
    if not isinstance(value, str):
        return value
    if "." in value or not scale:
        return decimal.Decimal(value.rstrip("."))
    return decimal.Decimal(value).scaleb(-scale)


def _guid_from_access_parser(value):
    """access_parser 0.0.6 builds the UUID from the bytes as stored (little-endian fields).

    >>> _guid_from_access_parser('0295330b-4531-d211-8d45-0080c6fd2caa')
    '{0B339502-3145-11D2-8D45-0080C6FD2CAA}'
    """
    if not isinstance(value, str):
        return value
    return _canonical_guid(uuid.UUID(bytes_le=uuid.UUID(value).bytes))


_C1_CONTROLS = re.compile("[\x80-\x9f]")


def _cp1252_from_latin1(value):
    """Re-decode Jet3 text that was decoded as latin-1, when it shows it (C1 control chars).

    >>> _cp1252_from_latin1('haven\x92t')
    'haven’t'
    >>> _cp1252_from_latin1('café')
    'café'
    """
    if not isinstance(value, str) or not _C1_CONTROLS.search(value):
        return value
    try:
        return value.encode("latin-1").decode("cp1252")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


BACKENDS = {source.name: source for source in (MdbtoolsSource, AccessParserSource)}
"""Shipped backends, in the order ``backend=None`` tries them."""

BackendSpec = None | str | Callable


def _open_source(path, backend: BackendSpec):
    """The source for ``path``: the one asked for, or the first available one that opens it."""
    if callable(backend):
        return backend(path)
    if backend is not None:
        if backend not in BACKENDS:
            raise ValueError(f"Unknown Access backend {backend!r}. Known: {list(BACKENDS)}")
        source = BACKENDS[backend]
        if not source.is_available():
            raise MissingAccessBackendError(
                f"The {backend!r} Access backend is not available. {source.install_hint}"
            )
        return source(path)
    available = [source for source in BACKENDS.values() if source.is_available()]
    if not available:
        hints = "\n".join(f"  - {name}: {s.install_hint}" for name, s in BACKENDS.items())
        raise MissingAccessBackendError(
            f"No backend to read Access files is available. Install one of:\n{hints}"
        )
    failures = []
    for source in available:
        try:
            return source(path)
        except AccessReadError as error:
            failures.append(f"  - {source.name}: {error}")
    raise AccessReadError(f"No available backend could open {path!r}:\n" + "\n".join(failures))


def check_requirements(*, verbose: bool = True) -> dict[str, bool]:
    """Which Access backends this machine has; prints how to get the missing ones.

    >>> sorted(check_requirements(verbose=False))
    ['access_parser', 'mdbtools']
    """
    available = {name: source.is_available() for name, source in BACKENDS.items()}
    if verbose:
        for name, ok in available.items():
            status = "available" if ok else f"missing: {BACKENDS[name].install_hint}"
            print(f"{name:14} {status}")
        if not any(available.values()):
            print("No Access backend: AccessReader and access_engine cannot read files yet.")
    return available


# --------------------------------------------------------------------------------------
# The Mapping and the engine


class AccessReader(Mapping):
    """A ``Mapping`` of an Access file's table names to their rows (lists of dicts).

    ``backend`` is ``None`` (the first available one that opens the file), a name in
    :data:`BACKENDS`, or a callable ``backend(path)`` returning a source (see the module
    docstring). System tables (``MSys*``) are not listed.
    """

    def __init__(self, path, *, backend: BackendSpec = None):
        self.path = path
        self.source = _open_source(path, backend)

    @cached_property
    def _table_names(self) -> tuple[str, ...]:
        return tuple(self.source.table_names())

    def __iter__(self) -> Iterator[str]:
        return iter(self._table_names)

    def __len__(self) -> int:
        return len(self._table_names)

    def __contains__(self, table) -> bool:
        return table in self._table_names

    def __getitem__(self, table: str) -> list[dict]:
        if table not in self:
            raise KeyError(table)
        return list(self.source.rows(table))

    def __repr__(self):
        backend = getattr(self.source, "name", type(self.source).__name__)
        return f"{type(self).__name__}({self.path!r}, backend={backend!r})"


class AccessColumns(Mapping):
    """A ``Mapping`` of an Access file's table names to their column names (definition order).

    The sibling of :class:`AccessReader` over the same keys, rather than a
    ``reader.column_names(table)`` method: dol wrappers map keys only through the Mapping
    methods, so a key-taking method would be handed unmapped keys (i2mint/dol#83).
    Pass a reader to share its open source, or a path (and ``backend``) to open one.
    """

    def __init__(self, path_or_reader, *, backend: BackendSpec = None):
        if isinstance(path_or_reader, AccessReader):
            self._reader = path_or_reader
        else:
            self._reader = AccessReader(path_or_reader, backend=backend)

    def __iter__(self) -> Iterator[str]:
        return iter(self._reader)

    def __len__(self) -> int:
        return len(self._reader)

    def __contains__(self, table) -> bool:
        return table in self._reader

    def __getitem__(self, table: str) -> list[str]:
        if table not in self._reader:
            raise KeyError(table)
        return list(self._reader.source.column_names(table))


_INT64 = range(-(2**63), 2**63)


def _sqlite_value(value):
    """A value SQLite stores without loss of meaning (exactness is lost only for non-integral
    Decimals, stored as float)."""
    if isinstance(value, datetime.datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, (datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        if value == value.to_integral_value() and int(value) in _INT64:
            return int(value)
        return float(value)
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, int) and not isinstance(value, bool) and value not in _INT64:
        return str(value)
    return value


class _Untyped(UserDefinedType):
    """A column with no declared type: SQLite stores each value as it is."""

    cache_ok = True

    def get_col_spec(self, **kw):
        return ""


def _column_type(values: Iterable):
    """The SQLAlchemy type for a column, from the kinds of its non-null values. Mixed kinds
    get no declared type, so SQLite stores each value as it is."""
    kinds = {type(v) for v in values if v is not None}
    if not kinds or kinds == {str}:
        return Text
    if kinds == {bool}:
        return Boolean
    if kinds <= {int, bool}:
        return Integer
    if kinds <= {int, bool, float}:
        return Float
    if kinds == {bytes}:
        return LargeBinary
    return _Untyped


def access_engine(
    path_or_reader,
    *,
    sqlite_path=None,
    backend: BackendSpec = None,
    tables: Iterable[str] | None = None,
):
    """Copy an Access file's tables into SQLite and return the SQLAlchemy ``Engine``.

    :param path_or_reader: the Access file, or an :class:`AccessReader` already open on it.
    :param sqlite_path: where the copy lives. ``None`` (default) keeps it in memory; a path
        writes a SQLite file there. A table of the same name already in it is replaced, in one
        transaction (a failed copy leaves it as it was).
    :param backend: as in :class:`AccessReader` (ignored if a reader is given).
    :param tables: the tables to copy (default: all of them).

    The engine is a snapshot: writing through it changes the copy, never the Access file.
    """
    if isinstance(path_or_reader, AccessReader):
        reader = path_or_reader
    else:
        reader = AccessReader(path_or_reader, backend=backend)
    if sqlite_path is None:
        engine = create_engine(
            "sqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
    else:
        engine = create_engine(URL.create("sqlite", database=os.fspath(sqlite_path)))
    _make_ddl_transactional(engine)

    columns_of = AccessColumns(reader)
    for name in dict.fromkeys(reader if tables is None else tables):
        names = columns_of[name]
        rows = [{c: _sqlite_value(row.get(c)) for c in names} for row in reader[name]]
        columns = [Column(c, _column_type(row[c] for row in rows)) for c in names]
        _replace_table(engine, name, columns, rows)
    return engine


def _make_ddl_transactional(engine):
    """Let a transaction hold DDL too (pysqlite otherwise commits around CREATE/DROP).

    The SQLAlchemy recipe for pysqlite: turn off the driver's own transaction handling and
    emit BEGIN ourselves (https://docs.sqlalchemy.org/en/20/dialects/sqlite.html, "Serializable
    isolation / Savepoints / Transactional DDL").
    """

    @event.listens_for(engine, "connect")
    def _no_driver_transactions(dbapi_connection, connection_record):
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def _begin(connection):
        connection.exec_driver_sql("BEGIN")


def _replace_table(engine, name, columns, rows):
    """Drop, create and fill ``name`` in one transaction: on any failure the old table stays."""
    table = Table(name, MetaData(), *columns)
    with engine.begin() as connection:
        table.drop(connection, checkfirst=True)
        table.create(connection)
        if rows:
            connection.execute(table.insert(), rows)


class _DictSource:
    """An in-memory source (``{table: [row_dict, ...]}``), for doctests and tests."""

    name = "dict"

    def __init__(self, tables: Mapping[str, list[dict]], columns=()):
        self._tables = tables
        self._columns = dict(columns)  # {table: [column, ...]}, for tables without rows

    @classmethod
    def factory(cls, tables, columns=()):
        return lambda path: cls(tables, columns)

    def table_names(self):
        return list(self._tables)

    def column_names(self, table):
        if table in self._columns:
            return list(self._columns[table])
        rows = self._tables[table]
        return list(dict.fromkeys(k for row in rows for k in row))

    def rows(self, table):
        return iter(self._tables[table])
