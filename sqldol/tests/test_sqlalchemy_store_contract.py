"""Tests that ``k in store`` agrees with ``store[k]`` for the SQLAlchemy stores.

``SQLAlchemyPersister.__iter__`` yields ORM row objects rather than keys, so the
brute-force ``__contains__`` inherited from ``dol.base.Collection`` compared a key
against a row and answered ``False`` for every key. ``SQLAlchemyStore`` and
``SQLAlchemyTupleStore`` inherited that answer through ``dol.base.Store``.

Uses in-memory SQLite only -- no external service, no credentials.
"""

import pytest

from sqldol import SQLAlchemyPersister, SQLAlchemyStore, SQLAlchemyTupleStore
from sqldol.sql_base import RowKey

SQLITE_DB_URI = "sqlite:///:memory:"
KEY_FIELDS = {"id": SQLAlchemyPersister.TYPE_STRING}
DATA_FIELDS = {"doc": SQLAlchemyPersister.TYPE_TEXT}


def _mk(cls, collection_name):
    return cls(
        uri=SQLITE_DB_URI,
        collection_name=collection_name,
        key_fields=KEY_FIELDS,
        data_fields=DATA_FIELDS,
    )


def test_persister_contains_agrees_with_getitem():
    persister = _mk(SQLAlchemyPersister, "persister_contains")
    persister[{"id": "a"}] = {"doc": "x"}

    assert {"id": "a"} in persister
    assert {"id": "zzz"} not in persister
    assert persister[{"id": "a"}] is not None
    assert len(persister) == 1


def test_store_contains_agrees_with_getitem():
    store = _mk(SQLAlchemyStore, "store_contains")
    store[{"id": "a"}] = {"doc": "x"}

    assert {"id": "a"} in store
    assert {"id": "zzz"} not in store
    assert store[{"id": "a"}] is not None
    assert len(store) == 1


def test_tuple_store_contains_agrees_with_getitem():
    store = _mk(SQLAlchemyTupleStore, "tuple_store_contains")
    store[("a",)] = ("x",)

    assert ("a",) in store
    assert ("zzz",) not in store
    assert store[("a",)] == ("x",)
    assert len(store) == 1


def test_tuple_store_iteration_yields_keys():
    """``SQLAlchemyTupleStore`` maps the persister's keys to tuples."""
    store = _mk(SQLAlchemyTupleStore, "tuple_store_iter")
    store[("a",)] = ("x",)

    assert list(store) == [("a",)]
    assert dict(store) == {("a",): ("x",)}


def test_contains_does_not_raise_on_a_key_it_cannot_query():
    """``in`` must answer, not explode, for keys that can't name a row.

    ``Container.__contains__`` returned False for these before, so keeping them
    False (rather than propagating a SQLAlchemy/TypeError) preserves behaviour.
    """
    persister = _mk(SQLAlchemyPersister, "persister_bad_key")
    persister[{"id": "a"}] = {"doc": "x"}

    assert "not-a-dict" not in persister
    assert {"no_such_column": "a"} not in persister


# ---- __iter__ yields keys, not ORM rows (i2mint/sqldol#2) --------------------------


def test_persister_iter_yields_hashable_keys_that_round_trip():
    store = _mk(SQLAlchemyStore, "iter_keys")
    store[{"id": "a"}] = {"doc": "x"}
    store[{"id": "b"}] = {"doc": "y"}

    keys = list(store)
    assert sorted(k["id"] for k in keys) == ["a", "b"]
    assert all(isinstance(k, dict) for k in keys)  # still dict keys (compat)
    assert set(keys) == {RowKey(id="a"), RowKey(id="b")}  # hashable
    assert RowKey(id="a") == {"id": "a"}
    for k in keys:  # every iterated key works with every Mapping method
        assert k in store
        assert store[k].doc in {"x", "y"}
    assert len(keys) == len(store) == 2


def test_persister_mapping_protocol_over_keys():
    persister = _mk(SQLAlchemyPersister, "iter_protocol")
    persister[{"id": "a"}] = {"doc": "x"}

    assert [(k, v.doc) for k, v in persister.items()] == [({"id": "a"}, "x")]
    assert len(persister.keys()) == 1
    assert {"id": "a"} in persister.keys()
    del persister[next(iter(persister))]
    assert list(persister) == []


def test_multi_field_keys():
    store = SQLAlchemyStore(
        uri=SQLITE_DB_URI,
        collection_name="iter_multi",
        key_fields={"a": SQLAlchemyPersister.TYPE_STRING, "n": SQLAlchemyPersister.TYPE_INTEGER},
        data_fields=DATA_FIELDS,
    )
    store[{"a": "x", "n": 1}] = {"doc": "d"}
    assert list(store) == [{"a": "x", "n": 1}]


def test_iter_rows_still_gives_orm_rows():
    persister = _mk(SQLAlchemyPersister, "iter_rows")
    persister[{"id": "a"}] = {"doc": "x"}
    [row] = list(persister.iter_rows())
    assert (row.id, row.doc) == ("a", "x")


def test_consumer_key_of_id_written_for_dict_or_row_still_works():
    """lacing's catalog: ``key_of_id`` handles the key dict on writes and a row on iteration."""
    from dol import wrap_kvs

    def key_of_id(row_or_key):
        if isinstance(row_or_key, dict):
            return row_or_key["id"]
        return row_or_key.id

    raw = _mk(SQLAlchemyStore, "iter_lacing")
    store = wrap_kvs(raw, key_of_id=key_of_id, id_of_key=lambda k: {"id": k})
    store["a"] = {"doc": "x"}
    assert list(store) == ["a"] and "a" in store


def test_rowkey_is_immutable_and_attribute_readable():
    k = RowKey(id="a")
    for mutate in (
        lambda: k.__setitem__("id", "b"),
        lambda: k.__delitem__("id"),
        lambda: k.update(id="b"),
        lambda: k.pop("id"),
        lambda: k.setdefault("x", 1),
        lambda: k.clear(),
        lambda: k.__ior__({"id": "b"}),
    ):
        with pytest.raises(TypeError, match="immutable"):
            mutate()
    assert k == {"id": "a"} and k.id == "a"
    with pytest.raises(AttributeError):
        k.nope


def test_consumer_written_for_orm_rows_keeps_working():
    from dol import wrap_kvs

    raw = _mk(SQLAlchemyStore, "iter_row_attr")
    store = wrap_kvs(raw, key_of_id=lambda row: row.id, id_of_key=lambda k: {"id": k})
    store["a"] = {"doc": "x"}
    assert list(store) == ["a"]


def test_rowkey_survives_pickle_and_copy():
    import copy
    import pickle

    k = RowKey(id="a", n=1)
    for clone in (pickle.loads(pickle.dumps(k)), copy.copy(k), copy.deepcopy(k)):
        assert clone == k and type(clone) is RowKey and hash(clone) == hash(k)
