"""Base objects for sqldol"""

from typing import Iterable, Iterable, Mapping, Sized, Union, List
from sqlalchemy import (
    Table,
    MetaData,
    select,
    insert,
    exists,
    update,
    text,
    Engine,
    Column,
)

from sqlalchemy import Table, Column, MetaData
from sqldol.util import ensure_engine, rows_iter, EngineSpec


class TablesDol(Mapping):
    def __init__(self, engine: EngineSpec, metadata=None):
        self.engine = ensure_engine(engine)
        self.metadata = metadata or MetaData()
        self.metadata.reflect(bind=self.engine)

    def __getitem__(self, key):
        # return PostgresBaseKvReader(self.engine, key)
        # Or do something with this and wrap_kvs, because then it's all ops
        # on self.metadata.tables
        return self.metadata.tables[key]

    def __iter__(self):
        return iter(self.metadata.tables)

    def __len__(self):
        return len(self.metadata.tables)


from sqlalchemy import Table, Column


class TableColumnsDol(Mapping):
    def __init__(self, table: Table):
        self.table = table

    def __iter__(self) -> Iterable[str]:
        """Yields the column names of the table."""
        return (column_obj.name for column_obj in self.table.c)

    def __getitem__(self, column_name: str) -> Column:
        """Returns the column object corresponding to the column_name."""
        return self.table.c[column_name]

    def __len__(self) -> int:
        """Number of columns of the table."""
        return len(self.table.c)

    def __contains__(self, column_name: str) -> bool:
        """Returns True if the column name exists in the table."""
        return column_name in self.table.c


# from sqldol
class TableRows(Sized, Iterable):
    def __init__(self, table: Table, filt=None, *, engine: Engine = None):
        self.table = table
        self.filt = filt
        self.engine = engine or table.bind

    def __iter__(self):
        with rows_iter(self.table, self.filt, engine=self.engine) as result:
            for row in result:
                yield row

    def __len__(self):
        with rows_iter(self.table, self.filt, engine=self.engine) as result:
            return result.rowcount


# TODO: Extend TableRows to TableRowsReader by adding a __getitem__ method?


class PostgresBaseColumnsReader(Mapping):
    """Here, keys are column names and values are column values"""

    def __init__(self, engine, table_name):
        self.engine = ensure_engine(engine)
        self.table_name = table_name
        self.metadata = MetaData()
        self.table = Table(self.table_name, self.metadata, autoload_with=self.engine)

    def __iter__(self):
        return (column_obj.name for column_obj in self.table.columns)

    def __len__(self):
        return len(self.table.columns)

    def __getitem__(self, column_name):
        query = select(self.table).with_only_columns([self.table.c[column_name]])
        with self.engine.connect() as connection:
            result = connection.execute(query)
            return result.fetchall()

        # # TODO: Finish
        # query = select(self.table).with_only_columns([self.table.c[key]])
        # with self.engine.connect() as connection:
        #     result = connection.execute(query)
        #     return result.fetchall()


# TODO: Extend key_columns to be multiple
# TODO: Handle single and multiple key and value columns to avoid 1-tuples
# TODO: Do we waste time opening and closing connections
#       (perhaps we should make the whole SqlBaseKvReader a context manager?)
class SqlBaseKvReader(Mapping):
    """A mapping view of a table,
    where keys are values from a key column and values are values from a value column.
    There's also a filter function that can be used to filter the rows.
    """

    def __init__(
        self,
        engine,
        table_name,
        key_columns: str,
        value_columns: Union[str, List[str]] = None,
        filt=None,
    ):
        self.engine = ensure_engine(engine)
        self.table_name = table_name
        self.metadata = MetaData()
        self.table = Table(self.table_name, self.metadata, autoload_with=self.engine)
        assert isinstance(key_columns, str), 'Must be a single column name'  # for now!
        self.key_columns = key_columns
        self._column_names = [col.name for col in self.table.columns]
        if value_columns is None:
            value_columns = self._column_names
        elif isinstance(value_columns, str):
            value_columns = [value_columns]
        self.value_columns = value_columns
        self.filt = filt
        self._prepare()

    def _prepare(self):
        self._key_index = self._column_names.index(self.key_columns)
        self._value_indices = list(map(self._column_names.index, self.value_columns))

    def _extract_key(self, row):
        return row[self._key_index]

    def _extract_values(self, row):
        return [row[i] for i in self._value_indices]

    def __iter__(self):
        query = select(self.table)
        with self.engine.connect() as connection:
            result = connection.execute(query)
            for row in result:
                yield self._extract_key(row)

    def __len__(self):
        query = select(self.table)
        with self.engine.connect() as connection:
            result = connection.execute(query)
            return result.rowcount

    def __getitem__(self, key):
        query = select(self.table).where(self.table.c[self.key_columns] == key)
        with self.engine.connect() as connection:
            result = connection.execute(query)
            return map(self._extract_values, result.fetchall())

    def __setitem__(self, key, value):
        value[self.key_columns] = key

        if key is str:
            key = f'"{key}"'
        filter = text(f'{self.key_columns} = {key}')

        with self.engine.connect() as connection:
            query = select(self.table).where(filter)
            result = connection.execute(query)

            if result.rowcount == 1:
                query = update(self.table).values(**value).where(filter)
            else:
                query = insert(self.table).values(**value)

            connection.execute(query)
            connection.commit()
