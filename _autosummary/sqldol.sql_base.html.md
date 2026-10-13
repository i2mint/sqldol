# sqldol.sql_base

Independent legacy DOLs
sql with a simple (dict-like or list-like) interface

### Module Attributes

| [`SQL_IDENTIFIER_PATTERN`](#sqldol.sql_base.SQL_IDENTIFIER_PATTERN)   | letters (Unicode included), digits, `_` or `$`, not all digits (MySQL allows e.g. `2020_sales`), optionally qualified by a schema (`schema.table`).   |
|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------|

### Functions

| [`iter_rows`](#sqldol.sql_base.iter_rows)(connection, table_name[, ...])     | Iterate over the rows of a table, fetching `batch_size` rows per query.          |
|-----------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------|
| [`validate_sql_identifier`](#sqldol.sql_base.validate_sql_identifier)(name, \*[, pattern]) | Return `name` if it is safe to write into raw SQL text, else raise `ValueError`. |

### Classes

| [`DfSqlDbReader`](#sqldol.sql_base.DfSqlDbReader)(connection)                         |                                                                                                 |
|----------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| [`RowKey`](#sqldol.sql_base.RowKey)                                            | A hashable, immutable `{key_field: value}` dict: the key of one row of a `SQLAlchemyPersister`. |
| [`SQLAlchemyPersister`](#sqldol.sql_base.SQLAlchemyPersister)([uri, collection_name, ...])  |                                                                                                 |
| [`SQLAlchemyStore`](#sqldol.sql_base.SQLAlchemyStore)([uri, collection_name, ...])      |                                                                                                 |
| [`SQLAlchemyTupleStore`](#sqldol.sql_base.SQLAlchemyTupleStore)([uri, collection_name, ...]) |                                                                                                 |
| [`SqlAlchemyDatabaseCollection`](#sqldol.sql_base.SqlAlchemyDatabaseCollection)                      |                                                                                                 |
| [`SqlAlchemyReader`](#sqldol.sql_base.SqlAlchemyReader)                                  |                                                                                                 |
| [`SqlDbCollection`](#sqldol.sql_base.SqlDbCollection)(connection)                       | A collection of sql tables names.                                                               |
| [`SqlDbReader`](#sqldol.sql_base.SqlDbReader)(connection)                           | A KvReader of sql tables.                                                                       |
| [`SqlTableRowsCollection`](#sqldol.sql_base.SqlTableRowsCollection)(connection, table_name)    | Base class wrapping an sql table.                                                               |
| [`SqlTableRowsSequence`](#sqldol.sql_base.SqlTableRowsSequence)(connection, table_name)      |                                                                                                 |

### *class* sqldol.sql_base.DfSqlDbReader(connection)

Bases: [`SqlDbReader`](#sqldol.sql_base.SqlDbReader)

### *class* sqldol.sql_base.RowKey

Bases: [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

A hashable, immutable `{key_field: value}` dict: the key of one row of a `SQLAlchemyPersister`.

It *is* a `dict` (so it works anywhere the persister takes a key – `store[key]`,
`key in store` – and equals the plain dict with the same items), but, unlike a plain
dict, it is hashable, as a `Mapping` key must be (`set(store)`, `dict(store)`,
`store.keys() & other`), and so cannot be mutated. Key fields can also be read as
attributes (`key.id`), so code written for the ORM rows that `__iter__` used to yield
(`row.id`) keeps working.

```pycon
>>> k = RowKey(id='a')
>>> k == {'id': 'a'}, hash(k) == hash(RowKey(id='a')), {k: 1}[RowKey(id='a')], k.id
(True, True, 1, 'a')
>>> k['id'] = 'b'
Traceback (most recent call last):
  ...
TypeError: RowKey is immutable (it is hashable): build a new one
```

#### clear() → None.  Remove all items from D.

#### pop(k) → v, remove specified key and return the corresponding value.

If the key is not found, return the default if given; otherwise,
raise a KeyError.

#### popitem(\*args, \*\*kwargs)

Remove and return a (key, value) pair as a 2-tuple.

Pairs are returned in LIFO (last-in, first-out) order.
Raises KeyError if the dict is empty.

#### setdefault(\*args, \*\*kwargs)

Insert key with a value of default if key is not in the dictionary.

Return the value for key if key is in the dictionary, else default.

#### update(\*\*F) → None.  Update D from mapping/iterable E and F.

If E is present and has a .keys() method, then does:  for k in E.keys(): D[k] = E[k]
If E is present and lacks a .keys() method, then does:  for k, v in E: D[k] = v
In either case, this is followed by: for k in F:  D[k] = F[k]

### *class* sqldol.sql_base.SQLAlchemyPersister(uri='sqlite:///my_sqlite.db', collection_name='dol_default_table', \*, key_fields={'_id': <class 'sqlalchemy.sql.sqltypes.INTEGER'>}, data_fields={'data': <class 'sqlalchemy.sql.sqltypes.String'>}, autocommit=True, \*\*db_kwargs)

Bases: `KvPersister`

#### TYPE_BLOB

alias of `BLOB`

#### TYPE_BOOLEAN

alias of `BOOLEAN`

#### TYPE_INTEGER

alias of `INTEGER`

#### TYPE_STRING

alias of `String`

#### TYPE_TEXT

A basic SQL DB persister written with SQLAlchemy.

alias of `TEXT`

#### iter_rows()

Iterate the ORM row objects (what `__iter__` used to yield).

### *class* sqldol.sql_base.SQLAlchemyStore(uri='sqlite:///my_sqlite.db', collection_name='dol_default_table', \*, key_fields={'_id': <class 'sqlalchemy.sql.sqltypes.INTEGER'>}, data_fields={'data': <class 'sqlalchemy.sql.sqltypes.String'>}, autocommit=True, \*\*db_kwargs)

Bases: `Store`

### *class* sqldol.sql_base.SQLAlchemyTupleStore(uri='sqlite:///my_sqlite.db', collection_name='dol_default_table', \*, key_fields={'_id': <class 'sqlalchemy.sql.sqltypes.INTEGER'>}, data_fields={'data': <class 'sqlalchemy.sql.sqltypes.String'>}, autocommit=True, \*\*db_kwargs)

Bases: [`SQLAlchemyStore`](#sqldol.sql_base.SQLAlchemyStore)

### sqldol.sql_base.SQL_IDENTIFIER_PATTERN *= re.compile('(?=[\\\\w$]\*[^\\\\W\\\\d])[\\\\w$]+(\\\\.(?=[\\\\w$]\*[^\\\\W\\\\d])[\\\\w$]+)?')*

letters
(Unicode included), digits, `_` or `$`, not all digits (MySQL allows e.g.
`2020_sales`), optionally qualified by a schema (`schema.table`). None of these
characters can end an identifier or start a new SQL token.

* **Type:**
  What a table name may look like where it is written into raw SQL text

### sqldol.sql_base.SqlAlchemyDatabaseCollection

alias of [`SqlDbCollection`](#sqldol.sql_base.SqlDbCollection)

### sqldol.sql_base.SqlAlchemyReader

alias of [`SqlDbReader`](#sqldol.sql_base.SqlDbReader)

### *class* sqldol.sql_base.SqlDbCollection(connection)

Bases: `Collection`

A collection of sql tables names.

### *class* sqldol.sql_base.SqlDbReader(connection)

Bases: [`SqlDbCollection`](#sqldol.sql_base.SqlDbCollection), `KvReader`

A KvReader of sql tables. Keys are table names and values are SqlTable objects

### *class* sqldol.sql_base.SqlTableRowsCollection(connection, table_name, batch_size=2000, limit=10000000000000000)

Bases: `Collection`

Base class wrapping an sql table.
It is Iterable (yields rows (as tuples)) and Sized (i.e. you can call len on it).
It’s also a container, but brute-forced: should probably subclass if you want to perform `row in table` efficiently.

#### NOTE
Be aware of how this object works if you’re (1) talking to a table whose contents are changing dynamically.

* count_rows() will return the current count every time
* len returns the value of the \_row_count lazyprop
* \_row_count returns the length of the \_rows cache if it exists, and if not, will return the live count_rows
* if len (therefore \_row_count) is called before the object listed the rows (therefore filling it’s cache),
  : it will return the current number of rows, but if at the time of listing rows, the number of different,
    the number of rows will be updated to match number of rows cached.
* column_names is a cached property

### *class* sqldol.sql_base.SqlTableRowsSequence(connection, table_name, batch_size=2000, limit=10000000000000000)

Bases: [`SqlTableRowsCollection`](#sqldol.sql_base.SqlTableRowsCollection), [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)

### sqldol.sql_base.iter_rows(connection, table_name, batch_size=1000, offset=0, limit=1000000000000)

Iterate over the rows of a table, fetching `batch_size` rows per query.

Yields at most `limit` rows, starting at row `offset` (like SQL’s
`LIMIT`/`OFFSET`), and stops at the end of the table: a page shorter than
the one requested means there is nothing after it.

`table_name` must pass [`validate_sql_identifier()`](#sqldol.sql_base.validate_sql_identifier), and `batch_size`,
`offset` and `limit` must be integers, because they are written into the SQL text
(`batch_size` positive, `offset` and `limit` non-negative). Invalid arguments
raise `ValueError` at call time, before any row is requested.

```pycon
>>> import sqlite3
>>> con = sqlite3.connect(":memory:")
>>> _ = con.execute("CREATE TABLE t (x INTEGER)")
>>> _ = con.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(5)])
>>> list(iter_rows(con, "t", batch_size=2))
[(0,), (1,), (2,), (3,), (4,)]
>>> list(iter_rows(con, "t", batch_size=2, offset=1, limit=3))
[(1,), (2,), (3,)]
```

### sqldol.sql_base.validate_sql_identifier(name, , pattern=re.compile('(?=[\\\\w$]\*[^\\\\W\\\\d])[\\\\w$]+(\\\\.(?=[\\\\w$]\*[^\\\\W\\\\d])[\\\\w$]+)?'))

Return `name` if it is safe to write into raw SQL text, else raise `ValueError`.

The raw-SQL paths of this module cannot bind a table name as a parameter (no SQL
dialect allows that), and they may be handed a plain DB-API connection that has no
quoting helper, so they only accept names matching an allowlist.

```pycon
>>> validate_sql_identifier("my_table")
'my_table'
>>> validate_sql_identifier("my_schema.my_table")
'my_schema.my_table'
>>> validate_sql_identifier("t; SELECT 1")
Traceback (most recent call last):
    ...
ValueError: Not a valid SQL table name: 't; SELECT 1'. ...
```
