"""Tests for ``SqlBaseKvStore.__setitem__``: writing an existing key must update it.

Uses in-memory SQLite only -- no external service, no credentials.
"""

import pytest
from sqlalchemy import create_engine, text

from sqldol.stores import SqlDictStore

TABLE_NAME = "t"
KEY_COLUMN = "k"


@pytest.fixture
def engine():
    """An in-memory SQLite engine holding ``t(k, v)`` with rows a/1 and b/2."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as connection:
        connection.execute(text(f"CREATE TABLE {TABLE_NAME} (k TEXT, v TEXT)"))
        connection.execute(
            text(f"INSERT INTO {TABLE_NAME} VALUES ('a', '1'), ('b', '2')")
        )
        connection.commit()
    return engine


def test_setitem_on_an_existing_key_updates_instead_of_duplicating(engine):
    """It used to decide update-vs-insert from a SELECT's ``rowcount``, which is -1
    on SQLite, so it always inserted: ``len`` grew and ``store[k]`` kept returning
    the old value."""
    store = SqlDictStore(engine, TABLE_NAME, key_columns=KEY_COLUMN)

    store["a"] = {"k": "a", "v": "10"}

    assert store["a"] == {"k": "a", "v": "10"}
    assert len(store) == 2
    assert sorted(store) == ["a", "b"]


def test_setitem_on_a_new_key_inserts(engine):
    store = SqlDictStore(engine, TABLE_NAME, key_columns=KEY_COLUMN)

    store["c"] = {"k": "c", "v": "3"}
    store["c"] = {"k": "c", "v": "4"}

    assert store["c"] == {"k": "c", "v": "4"}
    assert len(store) == 3
