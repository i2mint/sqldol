"""``query`` and ``setup`` no longer escape a wrapped store (i2mint/sqldol#3, i2mint/dol#83).

``dol`` wrappers serve a persister's public attributes unchanged, in the persister's
coordinates: ``SQLAlchemyTupleStore.query`` returned ORM rows and ``setup`` repointed the
whole store at another table. Both are now off the method surface; ``sqldol.ops.query`` is
the explicit way to the persister's ``Query``. In-memory/file SQLite only.
"""

import sqlite3

import pytest
import sqlalchemy
from dol import KeyCodecs, filt_iter

from sqldol import SQLAlchemyPersister, SQLAlchemyStore, SQLAlchemyTupleStore, ops
from sqldol.ops import WrappedStoreError

KEY_FIELDS = {"id": SQLAlchemyPersister.TYPE_STRING}
DATA_FIELDS = {"data": SQLAlchemyPersister.TYPE_STRING}


def _mk(cls, tmp_path, table="tbl", db="a.db"):
    return cls(
        f"sqlite:///{tmp_path / db}",
        table,
        key_fields=KEY_FIELDS,
        data_fields=DATA_FIELDS,
    )


def test_query_is_not_a_method_of_persister_or_wrappers(tmp_path):
    for store in (
        _mk(SQLAlchemyPersister, tmp_path),
        _mk(SQLAlchemyStore, tmp_path, "t2"),
        _mk(SQLAlchemyTupleStore, tmp_path, "t3"),
    ):
        with pytest.raises(AttributeError, match=r"sqldol\.ops\.query"):
            store.query


def test_setup_is_not_a_method_and_cannot_rebind_a_wrapped_store(tmp_path):
    store = _mk(SQLAlchemyTupleStore, tmp_path)
    store[("a",)] = ("one",)
    with pytest.raises(AttributeError, match="setup was removed"):
        store.setup(f"sqlite:///{tmp_path / 'b.db'}", "other_tbl")
    assert list(store) == [("a",)]  # still the same database and table
    assert store.store._uri.endswith("a.db")
    assert not (tmp_path / "b.db").exists()


def test_ops_query_on_bare_persister_is_the_store_coordinates(tmp_path):
    p = _mk(SQLAlchemyPersister, tmp_path)
    p[{"id": "a"}] = {"data": "one"}
    rows = list(ops.query(p).filter_by(id="a"))
    assert [(r.id, r.data) for r in rows] == [("a", "one")]


@pytest.mark.parametrize(
    "wrap",
    [
        lambda s: s,  # a SQLAlchemyTupleStore is itself a wrapper
        KeyCodecs.prefixed("u/"),
        filt_iter(filt=lambda k: True),
    ],
)
def test_ops_query_refuses_a_wrapped_store_unless_leaf_coordinates(tmp_path, wrap):
    store = wrap(_mk(SQLAlchemyTupleStore, tmp_path))
    with pytest.raises(WrappedStoreError, match="leaf_coordinates=True"):
        ops.query(store)
    store_rows = ops.query(store, leaf_coordinates=True)
    assert store_rows.count() == 0


def test_ops_query_leaf_coordinates_gives_orm_rows_not_store_values(tmp_path):
    store = _mk(SQLAlchemyTupleStore, tmp_path)
    store[("a",)] = ("one",)
    assert list(store) == [("a",)]
    (row,) = ops.query(store, leaf_coordinates=True)
    assert (row.id, row.data) == ("a", "one")


def test_ops_query_needs_a_persister_underneath():
    with pytest.raises(TypeError, match="does not wrap"):
        ops.query({})


def test_teardown_drops_nothing(tmp_path):
    store = _mk(SQLAlchemyTupleStore, tmp_path)
    store[("a",)] = ("one",)
    store.teardown()
    con = sqlite3.connect(tmp_path / "a.db")
    assert con.execute(
        "select name from sqlite_master where type='table'"
    ).fetchall() == [("tbl",)]
    con.close()
