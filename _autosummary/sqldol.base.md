# sqldol.base

Base objects for sqldol

### Functions

| `ensure_table_and_engine`(table, engine)   |    |
|--------------------------------------------|----|

### Classes

| [`PostgresBaseColumnsReader`](#sqldol.base.PostgresBaseColumnsReader)(engine, table_name)   | Here, keys are column names and values are column values                                                      |
|--------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| [`SqlBaseKvReader`](#sqldol.base.SqlBaseKvReader)(engine, table_name[, ...])      | A mapping view of a table, where keys are values from a key column and values are values from a value column. |
| [`SqlBaseKvStore`](#sqldol.base.SqlBaseKvStore)(engine, table_name[, ...])       |                                                                                                               |
| [`SqlKvStore`](#sqldol.base.SqlKvStore)                                      |                                                                                                               |
| [`TableColumnsDol`](#sqldol.base.TableColumnsDol)(table)                          |                                                                                                               |
| `TableRows`(table[, filt, engine])                                                               |                                                                                                               |
| [`TablesDol`](#sqldol.base.TablesDol)(engine[, metadata])                   |                                                                                                               |

### *class* sqldol.base.PostgresBaseColumnsReader(engine, table_name)

Bases: [`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)

Here, keys are column names and values are column values

### *class* sqldol.base.SqlBaseKvReader(engine, table_name, key_columns=None, value_columns=None, filt=None, , missing_key_policy='empty')

Bases: [`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)

A mapping view of a table,
where keys are values from a key column and values are values from a value column.
There’s also a filter function that can be used to filter the rows.

The `missing_key_policy` keyword decides what a lookup of an absent key does:

- `'empty'` (the default) returns an empty result. This is the historical
  behavior, kept as the default for backwards compatibility, but note that it
  makes the inherited `__contains__` and `get(key, default)` lie: because
  `Mapping` implements both in terms of `__getitem__` raising `KeyError`,
  every key looks present and `get` never returns its default.
- `'raise'` raises `KeyError`, which is what `collections.abc.Mapping`
  requires and what makes `in` and `get` truthful.

### *class* sqldol.base.SqlBaseKvStore(engine, table_name, key_columns=None, value_columns=None, filt=None, , missing_key_policy='empty')

Bases: [`SqlBaseKvReader`](#sqldol.base.SqlBaseKvReader), [`MutableMapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.MutableMapping)

### sqldol.base.SqlKvStore

alias of [`SqlBaseKvStore`](#sqldol.base.SqlBaseKvStore)

### *class* sqldol.base.TableColumnsDol(table)

Bases: [`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)

### *class* sqldol.base.TablesDol(engine, metadata=None)

Bases: [`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)
