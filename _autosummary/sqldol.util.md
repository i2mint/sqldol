# sqldol.util

Utils for sqldol

### Functions

| [`create_table_from_dict`](#sqldol.util.create_table_from_dict)(data, \*, engine[, ...])   | Create a table from a dictionary of data.   |
|----------------------------------------------------------------------------------------------------|---------------------------------------------|
| `ensure_engine`(engine)                                                                            |                                             |
| `get_engine_insert_func`(engine)                                                                   |                                             |
| [`get_or_create_table`](#sqldol.util.get_or_create_table)(engine, table_name[, ...])    | Get or create a table in the database.      |
| `rows_iter`(table[, filt, engine])                                                                 |                                             |

### sqldol.util.create_table_from_dict(data, \*, engine, table_name='sqldol_test_table_2', delete_table_before_create_if_same_columns=True, type_mapping=((<class 'str'>, <class 'sqlalchemy.sql.sqltypes.Text'>), (<class 'int'>, <class 'sqlalchemy.sql.sqltypes.Integer'>), (<class 'float'>, <class 'sqlalchemy.sql.sqltypes.Float'>), (<class 'bool'>, <class 'sqlalchemy.sql.sqltypes.Boolean'>), (<class 'datetime.date'>, <class 'sqlalchemy.sql.sqltypes.Date'>), (<class 'datetime.datetime'>, <class 'sqlalchemy.sql.sqltypes.DateTime'>), (<class 'bytes'>, <class 'sqlalchemy.sql.sqltypes.LargeBinary'>), (<class 'bytearray'>, <class 'sqlalchemy.sql.sqltypes.LargeBinary'>), (<class 'decimal.Decimal'>, <class 'sqlalchemy.sql.sqltypes.Float'>), (<class 'dict'>, <class 'sqlalchemy.sql.sqltypes.JSON'>), (<class 'collections.abc.Sequence'>, <class 'sqlalchemy.sql.sqltypes.JSON'>), (<class 'set'>, <class 'sqlalchemy.sql.sqltypes.JSON'>), (<class 'collections.abc.Iterable'>, <class 'sqlalchemy.sql.sqltypes.JSON'>)))

Create a table from a dictionary of data.

### sqldol.util.get_or_create_table(engine, table_name, columns=None)

Get or create a table in the database.

If the table does not exist, it will be created with the specified columns.

* **Parameters:**
  * **engine** (`Union`[`Engine`, [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]) – The SQLAlchemy engine or a URI string
  * **table_name** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The name of the table
  * **columns** – An iterable of column names or Column objects, used if the table
    does not exist and needs to be created
