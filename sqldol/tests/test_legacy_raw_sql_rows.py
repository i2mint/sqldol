"""The legacy raw-SQL row readers (``sqldol.sql_base``) on a plain DB-API connection.

``iter_rows`` used to decide whether a page had rows from the cursor's
``rowcount``, which is -1 (truthy) for a SELECT on sqlite3, so without a small
``limit`` it kept requesting empty pages. It also over-yielded when ``limit``
spanned several pages. ``SqlTableRowsCollection.count_rows`` called ``.first()``,
a SQLAlchemy result method that a DB-API cursor does not have.
"""

import math
import sqlite3

import pytest

from sqldol.sql_base import SqlTableRowsCollection, SqlTableRowsSequence, iter_rows

TABLE = "t"
N_ROWS = 7


class CountingConnection:
    """A sqlite3 connection that counts queries and refuses to run forever."""

    def __init__(self, connection, *, max_queries=100):
        self._connection = connection
        self.max_queries = max_queries
        self.queries = 0

    def execute(self, sql, *args):
        self.queries += 1
        if self.queries > self.max_queries:
            raise AssertionError(f"{self.queries} queries: the end was never detected")
        return self._connection.execute(sql, *args)


@pytest.fixture
def connection():
    con = sqlite3.connect(":memory:")
    con.execute(f"CREATE TABLE {TABLE} (x INTEGER)")
    con.executemany(f"INSERT INTO {TABLE} VALUES (?)", [(i,) for i in range(N_ROWS)])
    con.commit()
    yield CountingConnection(con)
    con.close()


ALL_ROWS = [(i,) for i in range(N_ROWS)]


@pytest.mark.parametrize("batch_size", [1, 2, 3, N_ROWS, N_ROWS + 5])
def test_iter_rows_stops_at_the_end_of_the_table(connection, batch_size):
    assert list(iter_rows(connection, TABLE, batch_size=batch_size)) == ALL_ROWS
    # One query per full page, plus the short (possibly empty) one that ends it.
    assert connection.queries == N_ROWS // batch_size + 1


def test_iter_rows_on_an_empty_table_makes_one_query(connection):
    connection.execute(f"DELETE FROM {TABLE}")
    assert list(iter_rows(connection, TABLE, batch_size=3)) == []
    assert connection.queries == 2  # the DELETE, then one SELECT


@pytest.mark.parametrize("batch_size", [1, 2, 3, 10])
@pytest.mark.parametrize(
    "offset, limit", [(0, 0), (0, 1), (0, 5), (2, 3), (2, 100), (6, 4), (7, 2), (9, 1)]
)
def test_iter_rows_offset_and_limit_act_like_a_slice(
    connection, batch_size, offset, limit
):
    rows = list(
        iter_rows(connection, TABLE, batch_size=batch_size, offset=offset, limit=limit)
    )
    assert rows == ALL_ROWS[offset : offset + limit]
    assert connection.queries <= math.ceil(limit / batch_size) + 1


@pytest.mark.parametrize(
    "kwargs, match",
    [
        (dict(batch_size=0), "batch_size"),
        (dict(batch_size=-1), "batch_size"),
        (dict(offset=-1), "non-negative"),
        (dict(limit=-1), "non-negative"),
    ],
)
def test_iter_rows_rejects_bad_arguments_when_called(connection, kwargs, match):
    with pytest.raises(ValueError, match=match):
        iter_rows(connection, TABLE, **kwargs)  # not even iterated
    assert connection.queries == 0


def test_rows_collection_counts_iterates_and_slices(connection):
    rows = SqlTableRowsCollection(connection, TABLE, batch_size=3)
    assert rows.count_rows() == N_ROWS
    assert len(rows) == N_ROWS
    assert list(rows) == ALL_ROWS
    assert list(rows[2:5]) == ALL_ROWS[2:5]
    assert list(rows[4:]) == ALL_ROWS[4:]
    assert list(rows[3]) == [ALL_ROWS[3]]
    assert list(rows[2:2]) == []
    assert list(rows[:0]) == []


def test_rows_sequence_indexes_like_a_list(connection):
    rows = SqlTableRowsSequence(connection, TABLE, batch_size=2)
    assert rows[1:6] == ALL_ROWS[1:6]
    assert len(rows) == N_ROWS
