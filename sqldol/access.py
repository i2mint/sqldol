"""Read Microsoft Access files (``.mdb``, ``.accdb``: Jet3, Jet4, ACE) as Mappings and as engines.

There is no SQLAlchemy dialect for Access off Windows, so this module bridges into the seam the
rest of sqldol already has (``engine``):

- :class:`AccessReader` ``(path)`` is a ``Mapping`` of table name to rows (a list of dicts).
  No SQL involved.
- :func:`access_engine` ``(path)`` copies the tables into SQLite (in memory unless you give a
  ``sqlite_path``) and returns a SQLAlchemy ``Engine``, so every sqldol store works on an Access
  file: ``TablesDol(engine)``, ``SqlDictReader(engine, 'Items', key_columns='ID')``, ...
  It is a **snapshot**: writes through that engine change the copy, never the Access file.
- :func:`check_requirements` says which backends this machine has, and how to get one.

The file is read by a **backend**, chosen at runtime. None is a hard dependency:

- ``'access_parser'``: pure Python, ``pip install "sqldol[access]"`` (Apache-2.0). Default.
- ``'mdbtools'``: the mdbtools command-line programs, if they are on ``PATH``
  (``brew install mdbtools``, ``apt install mdbtools``). Called as programs, not linked.

``backend=None`` takes the first available one, in that order. A backend can also be any callable
``backend(path)`` returning an object with ``table_names()``, ``column_names(table)`` and
``rows(table)`` (an iterable of dicts); that is the escape hatch for Windows ODBC or UCanAccess.

The two shipped backends agree on text (Jet3 files are read as cp1252, as Access wrote them)
and on GUIDs (``'{0B339502-3145-11D2-8D45-0080C6FD2CAA}'``, Access's display form), which this
module normalises. Where they differ:

- dates: ``datetime`` from ``access_parser``, ``'YYYY-MM-DD HH:MM:SS'`` strings from
  ``mdbtools``; in the SQLite copy both are that string.
- Jet3 text holding UTF-8 bytes (text pasted into the database already encoded): ``mdbtools``
  shows it as Access does (``'â€”'``); ``access_parser`` tries UTF-8 first and gives the
  intended ``'—'``.

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
from functools import cached_property

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    Integer,
    LargeBinary,
    MetaData,
    Numeric,
    Table,
    Text,
    create_engine,
)
from sqlalchemy.pool import StaticPool

__all__ = [
    "AccessReader",
    "access_engine",
    "check_requirements",
    "MissingAccessBackendError",
    "BACKENDS",
]


class MissingAccessBackendError(ImportError):
    """No backend that can read Access files is available (or the one asked for is not)."""


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


class AccessParserSource:
    """Reads an Access file with the pure-Python ``access_parser`` package."""

    name = "access_parser"
    install_hint = 'pip install "sqldol[access]"   (or: pip install access-parser)'

    @staticmethod
    def is_available() -> bool:
        return importlib.util.find_spec("access_parser") is not None

    def __init__(self, path):
        from access_parser import AccessParser

        with _quiet_logger("access_parser"):
            self._db = AccessParser(os.fspath(path))

    def table_names(self) -> list[str]:
        return [name for name in self._db.catalog if not name.startswith("MSys")]

    def column_names(self, table: str) -> list[str]:
        with _quiet_logger("access_parser"):
            columns = self._db.get_table(table).columns
        # keyed by the column's position in the table definition
        return [columns[i].col_name_str for i in sorted(columns)]

    def rows(self, table: str) -> Iterator[dict]:
        with _quiet_logger("access_parser"):
            access_table = self._db.get_table(table)
            data = access_table.parse()
        columns = [access_table.columns[i] for i in sorted(access_table.columns)]
        fixes = {c.col_name_str: self._fix_for(c.type) for c in columns}
        names = list(fixes)
        n_rows = len(data[names[0]]) if names else 0
        for i in range(n_rows):
            yield {name: fixes[name](data[name][i]) for name in names}

    def _fix_for(self, column_type):
        """access_parser 0.0.6 decodes Jet3 text as latin-1 (not the cp1252 Jet3 files use)
        and formats GUIDs from their raw little-endian bytes; undo both."""
        if column_type == _ACCESS_PARSER_TYPE_GUID:
            return _guid_from_access_parser
        if column_type in _ACCESS_PARSER_TEXT_TYPES and self._db.version == 3:
            return _cp1252_from_latin1
        return _identity


class MdbtoolsSource:
    """Reads an Access file with the mdbtools programs (``mdb-tables``, ``mdb-schema``,
    ``mdb-json``)."""

    name = "mdbtools"
    install_hint = (
        "brew install mdbtools   (macOS)  |  sudo apt-get install mdbtools   (Debian/Ubuntu)"
        "  |  https://github.com/mdbtools/mdbtools"
    )
    programs = ("mdb-tables", "mdb-schema", "mdb-json")
    datetime_format = "%Y-%m-%d %H:%M:%S"
    date_format = "%Y-%m-%d"

    @classmethod
    def is_available(cls) -> bool:
        return all(shutil.which(program) for program in cls.programs)

    def __init__(self, path):
        self.path = os.fspath(path)

    def _run(self, *args) -> str:
        return subprocess.run(
            args, capture_output=True, check=True, text=True, encoding="utf-8"
        ).stdout

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
        columns = self._columns(table)
        out = self._run(
            "mdb-json", "-D", self.date_format, "-T", self.datetime_format, self.path, table
        )
        for line in out.splitlines():
            if line:
                record = json.loads(line)  # mdb-json leaves out the null fields
                yield {
                    name: _from_mdb_json(record.get(name), access_type)
                    for name, access_type in columns
                }


def _from_mdb_json(value, access_type: str):
    """mdb-json writes binary values (GUIDs among them) as ``{"$binary": <base64>, ...}``."""
    if isinstance(value, dict) and "$binary" in value:
        raw = base64.b64decode(value["$binary"])
        if access_type == "Replication ID":  # libmdb's text form of the GUID
            return _canonical_guid(uuid.UUID(raw.decode("ascii").strip("{}")))
        return raw
    return value


def _canonical_guid(guid: uuid.UUID) -> str:
    """Access's own display form of a GUID.

    >>> _canonical_guid(uuid.UUID('0b339502-3145-11d2-8d45-0080c6fd2caa'))
    '{0B339502-3145-11D2-8D45-0080C6FD2CAA}'
    """
    return "{" + str(guid).upper() + "}"


_ACCESS_PARSER_TYPE_GUID = 15  # access_parser.utils.TYPE_GUID
_ACCESS_PARSER_TEXT_TYPES = (10, 12)  # TYPE_TEXT, TYPE_MEMO


def _identity(value):
    return value


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


BACKENDS = {source.name: source for source in (AccessParserSource, MdbtoolsSource)}
"""Shipped backends, in the order ``backend=None`` tries them."""

BackendSpec = None | str | Callable


def _resolve_backend(backend: BackendSpec) -> Callable:
    if callable(backend):
        return backend
    if backend is None:
        for source in BACKENDS.values():
            if source.is_available():
                return source
        hints = "\n".join(f"  - {name}: {s.install_hint}" for name, s in BACKENDS.items())
        raise MissingAccessBackendError(
            f"No backend to read Access files is available. Install one of:\n{hints}"
        )
    if backend not in BACKENDS:
        raise ValueError(f"Unknown Access backend {backend!r}. Known: {list(BACKENDS)}")
    source = BACKENDS[backend]
    if not source.is_available():
        raise MissingAccessBackendError(
            f"The {backend!r} Access backend is not available. {source.install_hint}"
        )
    return source


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

    ``backend`` is ``None`` (first available), a name in :data:`BACKENDS`, or a callable
    ``backend(path)`` returning a source (see the module docstring).
    System tables (``MSys*``) are not listed.
    """

    def __init__(self, path, *, backend: BackendSpec = None):
        self.path = path
        self.source = _resolve_backend(backend)(path)

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

    def column_names(self, table: str) -> list[str]:
        """The table's column names, in definition order."""
        if table not in self:
            raise KeyError(table)
        return list(self.source.column_names(table))

    def __repr__(self):
        return f"{type(self).__name__}({self.path!r}, backend={getattr(self.source, 'name', self.source)!r})"


def _sqlite_value(value):
    if isinstance(value, datetime.datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, datetime.date):
        return value.isoformat()
    return value


def _column_type(values: Iterable):
    """The SQLAlchemy type for a column, from its first non-null value."""
    first = next((v for v in values if v is not None), None)
    if isinstance(first, bool):
        return Boolean
    if isinstance(first, int):
        return Integer
    if isinstance(first, float):
        return Float
    if isinstance(first, decimal.Decimal):
        return Numeric
    if isinstance(first, (bytes, bytearray)):
        return LargeBinary
    return Text


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
        writes a SQLite file there (tables of the same name in it are replaced).
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
        engine = create_engine(f"sqlite:///{os.fspath(sqlite_path)}")

    metadata = MetaData()
    for name in reader if tables is None else tables:
        names = reader.column_names(name)
        rows = [{c: _sqlite_value(row.get(c)) for c in names} for row in reader[name]]
        table = Table(
            name,
            metadata,
            *(Column(c, _column_type(row[c] for row in rows)) for c in names),
        )
        table.drop(engine, checkfirst=True)
        table.create(engine)
        if rows:
            with engine.begin() as connection:
                connection.execute(table.insert(), rows)
    return engine


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
