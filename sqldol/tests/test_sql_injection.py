"""Regression tests: keys and table names are never spliced into SQL text.

``SqlBaseKvStore`` (and so ``SqlDictStore``) used to build the ``WHERE`` clause of
``__setitem__`` / ``__delitem__`` by string formatting, so a key containing a quote
broke the query and a key could rewrite it. The legacy raw-SQL paths of
``sqldol.sql_base`` wrote table names into SQL text unchecked.

Every key here holds SQL metacharacters (quotes, semicolons, ``--``). Each test
writes it, reads it back, and checks that no other row was touched.

Uses in-memory SQLite only -- no external service, no credentials.
"""

import sqlite3

import pytest
from sqlalchemy import create_engine, text

from sqldol.base import SqlBaseKvStore
from sqldol.sql_base import SqlTableRowsCollection, iter_rows, validate_sql_identifier
from sqldol.stores import SqlDictStore

TABLE_NAME = "t"
KEY_COLUMN = "k"
ORIGINAL_ROWS = {"a": "1", "b": "2"}

TRICKY_KEYS = [
    "it's",
    'say "hi"',
    "a; DROP TABLE t; --",
    "x' OR '1'='1",
    "x' OR '1'='1' --",
    "k -- comment",
    "';",
    "--",
    "\\'",
]


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


def _all_rows(engine):
    with engine.connect() as connection:
        rows = connection.execute(text(f"SELECT k, v FROM {TABLE_NAME}")).fetchall()
    return sorted(map(tuple, rows))


def _original_rows():
    return sorted(ORIGINAL_ROWS.items())


@pytest.mark.parametrize("key", TRICKY_KEYS)
def test_tricky_key_insert_then_read_back(engine, key):
    store = SqlDictStore(engine, TABLE_NAME, key_columns=KEY_COLUMN)

    store[key] = {"k": key, "v": "new"}

    assert store[key] == {"k": key, "v": "new"}
    assert _all_rows(engine) == sorted(_original_rows() + [(key, "new")])


@pytest.mark.parametrize("key", TRICKY_KEYS)
def test_tricky_key_overwrite_updates_only_that_row(engine, key):
    store = SqlDictStore(engine, TABLE_NAME, key_columns=KEY_COLUMN)
    store[key] = {"k": key, "v": "first"}

    store[key] = {"k": key, "v": "second"}

    assert store[key] == {"k": key, "v": "second"}
    assert _all_rows(engine) == sorted(_original_rows() + [(key, "second")])


@pytest.mark.parametrize("key", TRICKY_KEYS)
def test_deleting_an_absent_tricky_key_touches_no_row(engine, key):
    """With interpolation, ``x' OR '1'='1`` as a key emptied the whole table."""
    store = SqlDictStore(engine, TABLE_NAME, key_columns=KEY_COLUMN)

    del store[key]

    assert _all_rows(engine) == _original_rows()


@pytest.mark.parametrize("key", TRICKY_KEYS)
def test_deleting_a_present_tricky_key_removes_only_that_row(engine, key):
    store = SqlDictStore(engine, TABLE_NAME, key_columns=KEY_COLUMN)
    store[key] = {"k": key, "v": "new"}

    del store[key]

    assert store[key] is None
    assert _all_rows(engine) == _original_rows()


@pytest.mark.parametrize("key", TRICKY_KEYS)
def test_tricky_values_in_a_mapping_key_are_bound(engine, key):
    store = SqlBaseKvStore(engine, TABLE_NAME, key_columns=KEY_COLUMN)
    store[key] = {"k": key, "v": key}

    store[{"k": key, "v": key}] = {"v": "updated"}
    assert _all_rows(engine) == sorted(_original_rows() + [(key, "updated")])

    del store[{"k": key, "v": "updated"}]
    assert _all_rows(engine) == _original_rows()


def test_normal_keys_behave_as_before(engine):
    """Guard for existing callers: plain str and int keys, and dict keys."""
    store = SqlDictStore(engine, TABLE_NAME, key_columns=KEY_COLUMN)

    store["a"] = {"k": "a", "v": "10"}
    store["c"] = {"k": "c", "v": "3"}
    assert store["a"] == {"k": "a", "v": "10"}
    assert store["c"] == {"k": "c", "v": "3"}

    base = SqlBaseKvStore(engine, TABLE_NAME, key_columns=KEY_COLUMN)
    del base[{"k": "c"}]
    del store["b"]
    assert _all_rows(engine) == [("a", "10")]


def test_int_keys_on_an_integer_key_column(engine):
    with engine.connect() as connection:
        connection.execute(text("CREATE TABLE n (id INTEGER, v TEXT)"))
        connection.execute(text("INSERT INTO n VALUES (1, 'one'), (2, 'two')"))
        connection.commit()
    store = SqlDictStore(engine, "n", key_columns="id")

    store[1] = {"id": 1, "v": "uno"}
    store[3] = {"id": 3, "v": "tres"}
    del store[2]

    assert store[1] == {"id": 1, "v": "uno"}
    assert sorted(store) == [1, 3]


def test_mapping_key_of_ints_on_integer_columns(engine):
    """The shape of a known dependent's call: ``del store[{"app_id": 1, "user_id": 7}]``
    on an integer-keyed permission table, with ``value_columns`` naming a subset."""
    with engine.connect() as connection:
        connection.execute(text("CREATE TABLE perm (app_id INTEGER, user_id INTEGER)"))
        connection.execute(text("INSERT INTO perm VALUES (1, 7), (1, 8), (2, 7)"))
        connection.commit()
    store = SqlDictStore(
        engine, "perm", key_columns="app_id", value_columns=["user_id", "app_id"]
    )

    store[3] = {"app_id": 3, "user_id": 9}
    del store[{"app_id": 1, "user_id": 7}]

    with engine.connect() as connection:
        rows = connection.execute(text("SELECT app_id, user_id FROM perm")).fetchall()
    assert sorted(map(tuple, rows)) == [(1, 8), (2, 7), (3, 9)]
    assert store[3] == {"user_id": 9, "app_id": 3}


def test_mapping_key_with_an_unknown_column_is_rejected(engine):
    store = SqlBaseKvStore(engine, TABLE_NAME, key_columns=KEY_COLUMN)
    with pytest.raises(KeyError, match="not a column"):
        del store[{"k = 'a' OR 1=1 --": "a"}]
    assert _all_rows(engine) == _original_rows()


def test_empty_mapping_key_is_rejected(engine):
    store = SqlBaseKvStore(engine, TABLE_NAME, key_columns=KEY_COLUMN)
    with pytest.raises(ValueError):
        del store[{}]
    assert _all_rows(engine) == _original_rows()


# Legacy raw-SQL paths (sqldol.sql_base) ------------------------------------------


@pytest.mark.parametrize("name", ["t", "_t2", "my_schema.t", "t$1"])
def test_valid_identifiers_pass(name):
    assert validate_sql_identifier(name) == name


@pytest.mark.parametrize(
    "name",
    ["t; DROP TABLE t", "t --", "t'", 't"', "1t", "", "a.b.c", "t t", None, 3],
)
def test_invalid_identifiers_are_rejected(name):
    with pytest.raises(ValueError, match="Not a valid SQL table name"):
        validate_sql_identifier(name)


@pytest.fixture
def dbapi_connection():
    """A raw ``sqlite3`` connection: the kind these legacy paths can still execute on."""
    connection = sqlite3.connect(":memory:")
    connection.execute(f"CREATE TABLE {TABLE_NAME} (k TEXT, v TEXT)")
    connection.execute(f"INSERT INTO {TABLE_NAME} VALUES ('a', '1'), ('b', '2')")
    connection.commit()
    yield connection
    connection.close()


def test_raw_sql_collection_rejects_a_table_name_carrying_sql(dbapi_connection):
    with pytest.raises(ValueError):
        SqlTableRowsCollection(dbapi_connection, "t; DELETE FROM t; --")
    rows = dbapi_connection.execute(f"SELECT k, v FROM {TABLE_NAME}").fetchall()
    assert sorted(rows) == _original_rows()


def test_raw_sql_paths_still_read_a_plain_table(dbapi_connection):
    SqlTableRowsCollection(dbapi_connection, TABLE_NAME)  # accepted
    # Note: a single bounded batch, because on a DB-API cursor whose SELECT rowcount
    # is -1 (sqlite3), iter_rows does not detect the end of the table by itself.
    rows = iter_rows(dbapi_connection, TABLE_NAME, batch_size=10, limit=10)
    assert sorted(rows) == _original_rows()


def test_iter_rows_rejects_non_integer_limits(dbapi_connection):
    with pytest.raises(TypeError):
        list(iter_rows(dbapi_connection, TABLE_NAME, limit="1; DELETE FROM t"))
