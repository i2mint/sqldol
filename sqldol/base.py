"""Base objects for sqldol"""

from typing import Iterable, Iterable, Mapping, Sized
from sqlalchemy import (
    Table,
    MetaData,
    select,
    Engine,
    Column,
)

from sqlalchemy import Table, Column, MetaData
from sqldol.util import ensure_engine, rows_iter

PostgresBaseKvReader: Mapping


class TablesDol(Mapping):
    def __init__(self, engine, metadata=None):
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


class PostgresBaseKvReader(Mapping):
    """A mapping view of a table,
    where keys are values from a key column and values are values from a value column.
    There's also a filter function that can be used to filter the rows.
    """

    def __init__(
        self,
        engine,
        table_name,
        key_column: str = None,
        value_column: str = None,
        filt=None,
    ):
        self.engine = engine
        self.table_name = table_name
        self.metadata = MetaData()
        self.table = Table(self.table_name, self.metadata, autoload_with=self.engine)
        self.key_column = key_column
        self.value_column = value_column
        self.filt = filt

    def __iter__(self):
        query = select(self.table)
        with self.engine.connect() as connection:
            result = connection.execute(query)
            for row in result:
                yield row[self.key_column], row[self.value_column]

    def __len__(self):
        query = select(self.table)
        with self.engine.connect() as connection:
            result = connection.execute(query)
            return result.rowcount

    def __getitem__(self, key):
        query = select(self.table).where(self.table.c[self.key_column] == key)
        with self.engine.connect() as connection:
            result = connection.execute(query)
            return result.fetchall()
