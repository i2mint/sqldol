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

EngineSpec = Union[Engine, str]


def ensure_engine(engine: EngineSpec) -> Engine:
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
        raise ValueError(f'Unsupported engine dialect: {engine_dialect}')


@contextmanager
def rows_iter(table: Table, filt=None, *, engine: Engine = None):
    if engine is None:
        engine = table.bind
        if not engine:
            raise ValueError(
                f"You didn't specify an engine, and your table ({table.name})"
                ' is not bound to an engine or connection.'
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


from sqlalchemy import create_engine, Table, Column, Integer, MetaData, exc, String


def _prepare_columns(columns):
    assert isinstance(
        columns, Iterable
    ), 'Columns must be an iterable of strings or Column objects'
    # Process columns input to handle both string names and Column objects
    for col in columns:
        if isinstance(col, str):
            # Default to a Column with type String if just a name is provided
            yield Column(col, String)
        elif isinstance(col, Column):
            # If it's a fully formed Column object, use it as is
            yield col
        else:
            raise TypeError('Columns must be either string names or Column objects')


def get_or_create_table(engine: EngineSpec, table_name: str, columns=None):
    """
    Get or create a table in the database.

    If the table does not exist, it will be created with the specified columns.

    :param engine: The SQLAlchemy engine or a URI string
    :param table_name: The name of the table
    :param columns: An iterable of column names or Column objects, used if the table
        does not exist and needs to be created
    """
    engine = ensure_engine(engine)
    metadata = MetaData()

    try:
        # Attempt to reflect the table
        table = Table(table_name, metadata, autoload_with=engine)
        # TODO: Idea -- could use columns to validate the table's schema
    except exc.NoSuchTableError:
        # If the table does not exist, define it with the specified columns and create it
        # Process columns input to handle both string names and Column objects
        processed_columns = list(_prepare_columns(columns))
        table = Table(table_name, metadata, *processed_columns)
        # Create the table in the database
        metadata.create_all(engine)

    return table


def create_table_from_dict(
    data,
    *,
    engine: str,
    table_name: str = 'sqldol_test_table_2',
    delete_table_before_create_if_same_columns: bool = True,
    type_mapping=dflt_type_mapping,
):
    """Create a table from a dictionary of data."""
    type_mapping = dict(type_mapping)
    engine = create_engine(engine)
    metadata = MetaData()

    columns = []
    for col_name, values in data.items():
        # Determine the SQLAlchemy column type based on the first value of each column
        col_type = type_mapping.get(type(values[0]))
        if col_type is None:
            raise ValueError(f'Unsupported data type for column {col_name}')
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
    # table = Table(table_name, metadata, *columns)
    table = get_or_create_table(engine, table_name, columns)
    # table.create(engine)
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

        conn.commit()

    return table
