# sqldol.access

Read Microsoft Access files (`.mdb`, `.accdb`: Jet3, Jet4, ACE) as Mappings and as engines.

There is no SQLAlchemy dialect for Access off Windows, so this module bridges into the seam the
rest of sqldol already has (`engine`):

- [`AccessReader`](#sqldol.access.AccessReader) `(path)` is a `Mapping` of table name to rows (a list of dicts).
  No SQL involved. [`AccessColumns`](#sqldol.access.AccessColumns) `(path_or_reader)` is its sibling: table name to
  column names, in definition order.
- [`access_engine()`](#sqldol.access.access_engine) `(path)` copies the tables into SQLite (in memory unless you give a
  `sqlite_path`) and returns a SQLAlchemy `Engine`, so every sqldol store works on an Access
  file: `TablesDol(engine)`, `SqlDictReader(engine, 'Items', key_columns='ID')`, …
  It is a **snapshot**: writes through that engine change the copy, never the Access file.
- [`check_requirements()`](#sqldol.access.check_requirements) says which backends this machine has, and how to get one.

The file is read by a **backend**, chosen at runtime. None is a hard dependency:

- `'mdbtools'`: the mdbtools command-line programs, if they are on `PATH`
  (`brew install mdbtools`, `apt install mdbtools`). Called as programs, not linked.
  Reads Jet3, Jet4 and ACE, with Access’s own column types.
- `'access_parser'`: pure Python, `pip install "sqldol[access]"` (Apache-2.0). Needs
  nothing else, but cannot open some files (ACE `.accdb` files written by Jackcess, some
  long memo layouts).

`backend=None` tries the available ones in that order and takes the first that opens the
file. A backend can also be any callable `backend(path)` returning an object with
`table_names()`, `column_names(table)` and `rows(table)` (an iterable of dicts); UCanAccess
would fit there. A *live* Windows ODBC engine would not: it would be its own function, since
`access_engine`’s contract is that it never writes to the Access file.

Values are normalised so the two backends agree: text is `str` (Jet3 read as cp1252),
Currency and Numeric are `decimal.Decimal`, Yes/No is `bool`, Replication ID (GUID) is
`'{0B339502-3145-11D2-8D45-0080C6FD2CAA}'`, binary is `bytes`, and date/times are
`'YYYY-MM-DD HH:MM:SS'` strings. Known differences that remain:

- Jet3 text holding UTF-8 bytes (text pasted into the database already encoded): `mdbtools`
  shows it as Access does (`'â€”'`); `access_parser` tries UTF-8 first and gives the
  intended `'—'`.
- `access_parser` returns a Currency field that has a Format property as the formatted
  string (`'$1,234.57'`), which cannot be turned back into the exact amount.

Each table is read into memory whole (`reader[table]`, and one table at a time by
`access_engine`).

```pycon
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
```

(`_DictSource` stands in for a real file here; with one, write `AccessReader('songs.mdb')`.)

### Module Attributes

| [`BACKENDS`](#sqldol.access.BACKENDS)   | Shipped backends, in the order `backend=None` tries them.   |
|-------------------------------------------------------------|-------------------------------------------------------------|

### Functions

| [`access_engine`](#sqldol.access.access_engine)(path_or_reader, \*[, ...])   | Copy an Access file's tables into SQLite and return the SQLAlchemy `Engine`.   |
|---------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------|
| [`check_requirements`](#sqldol.access.check_requirements)(\*[, verbose])          | Which Access backends this machine has; prints how to get the missing ones.    |

### Classes

| [`AccessReader`](#sqldol.access.AccessReader)(path, \*[, backend])            | A `Mapping` of an Access file's table names to their rows (lists of dicts).           |
|-----------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------|
| [`AccessColumns`](#sqldol.access.AccessColumns)(path_or_reader, \*[, backend]) | A `Mapping` of an Access file's table names to their column names (definition order). |

### Exceptions

| [`MissingAccessBackendError`](#sqldol.access.MissingAccessBackendError)   | No backend that can read Access files is available (or the one asked for is not).   |
|------------------------------------------------------------------------------|-------------------------------------------------------------------------------------|
| [`AccessReadError`](#sqldol.access.AccessReadError)             | A backend could not read the file (or one of its tables).                           |

### *class* sqldol.access.AccessColumns(path_or_reader, , backend=None)

Bases: [`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)

A `Mapping` of an Access file’s table names to their column names (definition order).

The sibling of [`AccessReader`](#sqldol.access.AccessReader) over the same keys, rather than a
`reader.column_names(table)` method: dol wrappers map keys only through the Mapping
methods, so a key-taking method would be handed unmapped keys (i2mint/dol#83).
Pass a reader to share its open source, or a path (and `backend`) to open one.

### *exception* sqldol.access.AccessReadError

Bases: [`RuntimeError`](https://docs.python.org/3/builtins/exceptions.html#RuntimeError)

A backend could not read the file (or one of its tables).

### *class* sqldol.access.AccessReader(path, , backend=None)

Bases: [`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)

A `Mapping` of an Access file’s table names to their rows (lists of dicts).

`backend` is `None` (the first available one that opens the file), a name in
[`BACKENDS`](#sqldol.access.BACKENDS), or a callable `backend(path)` returning a source (see the module
docstring). System tables (`MSys*`) are not listed.

### sqldol.access.BACKENDS *= {'access_parser': <class 'sqldol.access.AccessParserSource'>, 'mdbtools': <class 'sqldol.access.MdbtoolsSource'>}*

Shipped backends, in the order `backend=None` tries them.

### *exception* sqldol.access.MissingAccessBackendError

Bases: [`ImportError`](https://docs.python.org/3/builtins/exceptions.html#ImportError)

No backend that can read Access files is available (or the one asked for is not).

### sqldol.access.access_engine(path_or_reader, , sqlite_path=None, backend=None, tables=None)

Copy an Access file’s tables into SQLite and return the SQLAlchemy `Engine`.

* **Parameters:**
  * **path_or_reader** – the Access file, or an [`AccessReader`](#sqldol.access.AccessReader) already open on it.
  * **sqlite_path** – where the copy lives. `None` (default) keeps it in memory; a path
    writes a SQLite file there. A table of the same name already in it is replaced, in one
    transaction (a failed copy leaves it as it was).
  * **backend** ([`None`](https://docs.python.org/3/builtins/constants.html#None) | [`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`Callable`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)) – as in [`AccessReader`](#sqldol.access.AccessReader) (ignored if a reader is given).
  * **tables** ([`Iterable`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Iterable)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)] | [`None`](https://docs.python.org/3/builtins/constants.html#None)) – the tables to copy (default: all of them).

The engine is a snapshot: writing through it changes the copy, never the Access file.

### sqldol.access.check_requirements(, verbose=True)

Which Access backends this machine has; prints how to get the missing ones.

```pycon
>>> sorted(check_requirements(verbose=False))
['access_parser', 'mdbtools']
```

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`bool`](https://docs.python.org/3/builtins/functions.html#bool)]
