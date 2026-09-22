# sqldol.sql_base

Independent legacy DOLs
sql with a simple (dict-like or list-like) interface

### Functions

| [`iter_rows`](#sqldol.sql_base.iter_rows)(connection, table_name[, ...])   | Iterate the over the rows of a table.   |
|---------------------------------------------------------------------------------------------|-----------------------------------------|

### Classes

| [`DfSqlDbReader`](#sqldol.sql_base.DfSqlDbReader)(connection)                         |                                   |
|----------------------------------------------------------------------------------------------------|-----------------------------------|
| [`SQLAlchemyPersister`](#sqldol.sql_base.SQLAlchemyPersister)([uri, collection_name, ...])  |                                   |
| [`SQLAlchemyStore`](#sqldol.sql_base.SQLAlchemyStore)([uri, collection_name, ...])      |                                   |
| [`SQLAlchemyTupleStore`](#sqldol.sql_base.SQLAlchemyTupleStore)([uri, collection_name, ...]) |                                   |
| [`SqlAlchemyDatabaseCollection`](#sqldol.sql_base.SqlAlchemyDatabaseCollection)                      |                                   |
| [`SqlAlchemyReader`](#sqldol.sql_base.SqlAlchemyReader)                                  |                                   |
| [`SqlDbCollection`](#sqldol.sql_base.SqlDbCollection)(connection)                       | A collection of sql tables names. |
| [`SqlDbReader`](#sqldol.sql_base.SqlDbReader)(connection)                           | A KvReader of sql tables.         |
| [`SqlTableRowsCollection`](#sqldol.sql_base.SqlTableRowsCollection)(connection, table_name)    | Base class wrapping an sql table. |
| [`SqlTableRowsSequence`](#sqldol.sql_base.SqlTableRowsSequence)(connection, table_name)      |                                   |

### *class* sqldol.sql_base.DfSqlDbReader(connection)

Bases: [`SqlDbReader`](#sqldol.sql_base.SqlDbReader)

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

### *class* sqldol.sql_base.SQLAlchemyStore(uri='sqlite:///my_sqlite.db', collection_name='dol_default_table', \*, key_fields={'_id': <class 'sqlalchemy.sql.sqltypes.INTEGER'>}, data_fields={'data': <class 'sqlalchemy.sql.sqltypes.String'>}, autocommit=True, \*\*db_kwargs)

Bases: `Store`

### *class* sqldol.sql_base.SQLAlchemyTupleStore(uri='sqlite:///my_sqlite.db', collection_name='dol_default_table', \*, key_fields={'_id': <class 'sqlalchemy.sql.sqltypes.INTEGER'>}, data_fields={'data': <class 'sqlalchemy.sql.sqltypes.String'>}, autocommit=True, \*\*db_kwargs)

Bases: [`SQLAlchemyStore`](#sqldol.sql_base.SQLAlchemyStore)

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

Iterate the over the rows of a table.
The limit argument is mostly there to avoid an infinite loop, but can also be used to get ranges.
