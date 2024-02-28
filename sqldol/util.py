"""Utils for sqldol"""

from typing import Iterable, Union, Sequence, Iterable
import json
import datetime
import decimal
from contextlib import contextmanager

from sqlalchemy import create_engine, Table, MetaData, Engine, Column, select
from sqlalchemy import (
    Integer,
    Float,
    Boolean,
    Date,
    DateTime,
    LargeBinary,
    Text,
    JSON,
)


def ensure_engine(engine: Union[Engine, str]) -> Engine:
    if isinstance(engine, str):
        return create_engine(engine)
    return engine


DFLT_URI = 'sqlite:///:memory:'


def get_engine_insert_func(engine):
    # choose which dialect to use according to the dialect of the engine
    # from sqlalchemy.dialects.mysql import insert
    # from sqlalchemy.dialects.postgresql import insert
    # from sqlalchemy.dialects.sqlite import insert
    engine_dialect = engine.dialect.name
    import importlib

    try:
        return importlib.import_module(f'sqlalchemy.dialects.{engine_dialect}').insert
    except ImportError:
        raise ValueError(f"Unsupported engine dialect: {engine_dialect}")


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


dflt_type_mapping = tuple(
    {
        # Mpte" For large text fields, you might want to distinguish based on your use case
        # e.g., descriptions or textual data that exceeds the typical length of a String type
        str: Text,  # or String (but requires size in some databases, so Text more flexible
        int: Integer,
        float: Float,
        bool: Boolean,
        datetime.date: Date,
        datetime.datetime: DateTime,
        bytes: LargeBinary,
        bytearray: LargeBinary,
        decimal.Decimal: Float,
        dict: JSON,
        Sequence: JSON,  # Assuming you want to store lists, tuples etc. as JSON
        set: JSON,
        Iterable: JSON,  # Precedence: Iterable must come after any other iterables (str...)
        # Note: For `dict` and `list`, we use the JSON type, assuming you want to
        # serialize these Python types to JSON.
        # This is a common approach for storing structured data in a single database column.
    }.items()
)


def create_table_from_dict(
    data,
    *,
    table_name: str = "temp_table",
    uri: str,
    delete_table_before_create_if_same_columns: bool = True,
    type_mapping=dflt_type_mapping,
):
    """Create a table from a dictionary of data."""
    type_mapping = dict(type_mapping)
    engine = create_engine(uri)
    metadata = MetaData()

    columns = []
    for col_name, values in data.items():
        # Determine the SQLAlchemy column type based on the first value of each column
        col_type = type_mapping.get(type(values[0]))
        if col_type is None:
            raise ValueError(f"Unsupported data type for column {col_name}")
        columns.append(Column(col_name, col_type))

    column_names = [col.name for col in columns]

    if delete_table_before_create_if_same_columns:
        # Delete the table if it exists and has the same columns
        metadata.reflect(engine)
        if table_name in metadata.tables:
            existing_table = metadata.tables[table_name]
            if existing_table.columns.keys() == column_names:
                existing_table.drop(engine)

    # Define and create the table
    table = Table(table_name, metadata, *columns)
    table.create(engine)
    insert = get_engine_insert_func(engine)

    # Insert data into the table
    with engine.connect() as conn:
        for i in range(
            len(next(iter(data.values())))
        ):  # Assuming all columns have the same length
            row = {
                col: (
                    json.dumps(values[i]) if isinstance(values[i], dict) else values[i]
                )
                for col, values in data.items()
            }
            # Correct way to execute the insert statement
            conn.execute(insert(table).values(row))

    return table
