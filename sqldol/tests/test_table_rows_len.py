"""Tests for ``TableRows.__len__``: it must count rows, not report a SELECT's rowcount.

Uses in-memory SQLite only -- no external service, no credentials.
"""

import pytest
from sqlalchemy import create_engine, text

from sqldol import TableRows

TABLE_NAME = "t"


@pytest.fixture
def engine():
    """An in-memory SQLite engine holding ``t(k, v)`` with three rows."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as connection:
        connection.execute(text(f"CREATE TABLE {TABLE_NAME} (k TEXT, v INTEGER)"))
        connection.execute(
            text(f"INSERT INTO {TABLE_NAME} VALUES ('a', 1), ('b', 2), ('c', 3)")
        )
        connection.commit()
    return engine


def test_len_counts_the_rows(engine):
    """``rowcount`` of a SELECT is -1 on SQLite, so ``len`` used to raise ValueError."""
    rows = TableRows(TABLE_NAME, engine=engine)
    assert len(rows) == 3 == len(list(rows))


def test_len_honours_the_filter(engine):
    rows = TableRows(TABLE_NAME, engine=engine)
    filtered = TableRows(rows.table, rows.table.c.v >= 2, engine=engine)
    assert len(filtered) == 2 == len(list(filtered))
