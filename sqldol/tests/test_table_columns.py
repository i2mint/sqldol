"""``SQLAlchemyPersister.table_columns`` lists column names on any dialect (i2mint/sqldol#14)."""

from sqldol.sql_base import SQLAlchemyPersister


def test_table_columns_lists_column_names_on_sqlite():
    with SQLAlchemyPersister("sqlite:///:memory:", "things") as store:
        columns = store.table_columns()
    assert isinstance(columns, list) and columns
    assert all(isinstance(name, str) for name in columns)
