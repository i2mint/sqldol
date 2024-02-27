"""WIP on postgres dol -- but really will generalize to any sqlalchemy store."""

from typing import Mapping, Sized, Iterable, Union, MutableMapping
from sqlalchemy import (
    create_engine,
    Table,
    MetaData,
    select,
    Engine,
    Column,
    Integer,
    String,
    Float,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session


def ensure_engine(engine: Union[Engine, str]) -> Engine:
    if isinstance(engine, str):
        return create_engine(engine)
    return engine


from typing import Callable

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


from sqlalchemy import Table


class TableColumnsDol(Mapping):
    def __init__(self, table: Table):
        self.table = table

    def __getitem__(self, key):
        return self.table.c[key]

    def __iter__(self):
        return iter(self.table.c)

    def __len__(self):
        return len(self.table.c)


from sqlalchemy import select, Table, Engine
from contextlib import contextmanager


@contextmanager
def rows_iter(table: Table, filt=None, *, engine: Engine = None):
    if engine is None:
        engine = table.bind
        if not engine:
            raise ValueError(
                f"You didn't specify an engine, and your table ({table.name})"
                " is not bound to an engine or connection."
            )

    query = select(table)
    if filt is not None:
        query = query.where(filt)

    try:
        # Open a connection
        connection = engine.connect()
        # Execute the query and yield the result for iteration
        result = connection.execute(query)
        yield result
    finally:
        # Ensure the connection is closed after iteration
        connection.close()


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
