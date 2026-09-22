# sqldol.stores

Higher level stores for sql data

### Classes

| [`SqlDictReader`](#sqldol.stores.SqlDictReader)(engine, table_name[, ...])   | SqlBaseKvReader whose values are single dicts (the first one matchig the key).   |
|---------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------|
| [`SqlDictStore`](#sqldol.stores.SqlDictStore)(engine, table_name[, ...])    | SqlDictStore whose values are lists of dicts.                                    |
| [`SqlDictsReader`](#sqldol.stores.SqlDictsReader)(engine, table_name[, ...])  | SqlBaseKvReader whose values are lists of dicts.                                 |
| [`SqlRowReader`](#sqldol.stores.SqlRowReader)(engine, table_name[, ...])    | SqlBaseKvReader whose values are single rows (the first one matchig the key).    |
| [`SqlRowsReader`](#sqldol.stores.SqlRowsReader)(engine, table_name[, ...])   | SqlBaseKvReader whose values are lists of rows (lists).                          |

### *class* sqldol.stores.SqlDictReader(engine, table_name, key_columns=None, value_columns=None, filt=None, , missing_key_policy='empty')

Bases: `Store`

SqlBaseKvReader whose values are single dicts (the first one matchig the key).

### *class* sqldol.stores.SqlDictStore(engine, table_name, key_columns=None, value_columns=None, filt=None, , missing_key_policy='empty')

Bases: `Store`

SqlDictStore whose values are lists of dicts.

### *class* sqldol.stores.SqlDictsReader(engine, table_name, key_columns=None, value_columns=None, filt=None, , missing_key_policy='empty')

Bases: `Store`

SqlBaseKvReader whose values are lists of dicts.

### *class* sqldol.stores.SqlRowReader(engine, table_name, key_columns=None, value_columns=None, filt=None, , missing_key_policy='empty')

Bases: `Store`

SqlBaseKvReader whose values are single rows (the first one matchig the key).

### *class* sqldol.stores.SqlRowsReader(engine, table_name, key_columns=None, value_columns=None, filt=None, , missing_key_policy='empty')

Bases: `Store`

SqlBaseKvReader whose values are lists of rows (lists).
