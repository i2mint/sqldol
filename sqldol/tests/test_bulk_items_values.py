"""``items()``/``values()`` read the table in one query, not one per key (i2mint/sqldol#11).

Uses in-memory SQLite only -- no external service, no credentials.
"""

import pytest
from dol import Pipe, filt_iter, wrap_kvs
from sqlalchemy import event

from sqldol import SQLAlchemyPersister, SQLAlchemyStore, SQLAlchemyTupleStore

N = 50
KEY_FIELDS = {"id": SQLAlchemyPersister.TYPE_STRING}
DATA_FIELDS = {"doc": SQLAlchemyPersister.TYPE_TEXT}


def _mk(cls, name):
    s = cls(
        uri="sqlite:///:memory:",
        collection_name=name,
        key_fields=KEY_FIELDS,
        data_fields=DATA_FIELDS,
    )
    persister = getattr(s, "store", s)
    for i in range(N):
        persister[{"id": f"k{i:03d}"}] = {"doc": f"v{i}"}
    return s


class Counter:
    """Counts the SQL statements an engine executes."""

    def __init__(self, store):
        self.n = 0
        persister = getattr(store, "store", store)
        event.listen(persister.session.bind, "before_cursor_execute", self._inc)

    def _inc(self, *args, **kwargs):
        self.n += 1


@pytest.mark.parametrize("cls", [SQLAlchemyPersister, SQLAlchemyStore])
def test_items_and_values_use_a_constant_number_of_queries(cls):
    store = _mk(cls, "bulk_" + cls.__name__)
    per_key = {k["id"]: store[k].doc for k in store}  # one query per key
    counter = Counter(store)

    items = {k["id"]: v.doc for k, v in store.items()}
    n_items = counter.n
    values = sorted(v.doc for v in store.values())

    assert items == per_key and values == sorted(per_key.values())
    assert len(items) == N and n_items <= 3 and counter.n <= 6 < N


def test_tuple_store_bulk_items_apply_codecs():
    store = _mk(SQLAlchemyTupleStore, "bulk_tuple")
    counter = Counter(store)
    items = dict(store.items())
    assert items[("k007",)] == ("v7",) and len(items) == N and counter.n <= 3
    assert sorted(store.values())[0] == ("v0",)


def test_filt_iter_scope_and_key_codec_still_apply():
    persister = _mk(SQLAlchemyPersister, "bulk_scope")
    view = Pipe(
        filt_iter(filt=lambda k: k["id"] < "k005"),
        wrap_kvs(key_of_id=lambda k: k["id"], id_of_key=lambda k: {"id": k}),
    )(persister)
    counter = Counter(persister)
    assert sorted(k for k, _ in view.items()) == [f"k00{i}" for i in range(5)]
    assert len(list(view.values())) == 5 and counter.n <= 6


def test_lookups_after_iteration_hit_the_database_again():
    store = _mk(SQLAlchemyPersister, "bulk_fresh")
    list(store.items())
    store[{"id": "new"}] = {"doc": "n"}
    assert store[{"id": "new"}].doc == "n"
    assert store._prefetches == []


def test_writes_and_deletes_during_iteration():
    store = _mk(SQLAlchemyPersister, "bulk_mutate")
    for key, row in store.items():
        if key["id"].endswith("0"):
            del store[key]
        else:
            store[key] = {"doc": row.doc + "!"}
    assert len(store) == N - N // 10
    assert all(r.doc.endswith("!") for r in store.values())


def test_partial_and_interleaved_iterations_leave_no_state_behind():
    store = _mk(SQLAlchemyPersister, "bulk_interleave")
    a, b = iter(store.items()), iter(store.values())
    next(a), next(b), next(a)
    b.close()
    del a
    assert store._prefetches == []
    assert store[{"id": "k001"}].doc == "v1"
