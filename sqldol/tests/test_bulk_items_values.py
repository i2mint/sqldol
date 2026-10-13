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
    assert store._prefetch is None


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
    assert store._prefetch is None
    assert store[{"id": "k001"}].doc == "v1"


# ---- the prefetched rows never outlive the view's own lookup (review of PR #12) --------


def _file_persister(tmp_path, name="t"):
    return SQLAlchemyPersister(
        uri=f"sqlite:///{tmp_path}/db.sqlite",
        collection_name=name,
        key_fields=KEY_FIELDS,
        data_fields=DATA_FIELDS,
    )


def _filled(tmp_path, n=20):
    p = _file_persister(tmp_path)
    for i in range(n):
        p[{"id": f"k{i:03d}"}] = {"doc": f"v{i}"}
    return p


def test_row_deleted_by_the_session_then_rewritten_in_the_loop_is_reinserted(tmp_path):
    p = _filled(tmp_path)
    for key, row in p.items():
        if key["id"] == "k003":
            p.session.delete(row)
            p.session.commit()
            p[key] = {"doc": "recreated"}
    assert len(p) == 20 and p[{"id": "k003"}].doc == "recreated"


def test_write_after_session_close_in_the_loop_lands(tmp_path):
    p = _filled(tmp_path)
    for key, _ in p.items():
        if key["id"] == "k005":
            p.session.close()
            p[key] = {"doc": "after-close"}
    assert p[{"id": "k005"}].doc == "after-close"


def test_changed_primary_key_in_the_loop_is_not_served_stale(tmp_path):
    p = _filled(tmp_path)
    for key, _ in p.items():
        if key["id"] == "k001":
            p[key] = {"id": "zzz", "doc": "moved"}
    with pytest.raises(KeyError):
        p[{"id": "k001"}]
    assert p[{"id": "zzz"}].doc == "moved"


def test_paused_view_does_not_change_lookups_elsewhere(tmp_path):
    a, b = _filled(tmp_path), _file_persister(tmp_path)
    it = iter(a.items())
    next(it)
    del b[{"id": "k005"}]
    assert {"id": "k005"} not in a
    with pytest.raises(KeyError):
        a[{"id": "k005"}]
    a[{"id": "k005"}] = {"doc": "again"}  # inserts, as without a paused view
    assert a[{"id": "k005"}].doc == "again"


def test_row_deleted_behind_the_views_back_raises_like_a_plain_lookup(tmp_path):
    a, b = _filled(tmp_path), _file_persister(tmp_path)
    seen = []
    with pytest.raises(KeyError):
        for key, row in a.items():
            seen.append(key["id"])
            if len(seen) == 1:
                a.session.query(a.table).filter_by(id="k004").delete()
                a.session.commit()
    assert "k004" not in seen


def test_rows_are_read_in_batches_not_all_at_once(tmp_path):
    p = _filled(tmp_path, 30)
    p._prefetch_batch = 10
    counter = Counter(p)
    assert len(dict(p.items())) == 30
    assert counter.n <= 1 + 3 + 1  # keys + one query per batch
    counter.n = 0
    from itertools import islice

    assert len(list(islice(p.items(), 3))) == 3
    assert counter.n <= 2


@pytest.mark.parametrize("change", ["delete", "rekey"])
def test_uncommitted_change_in_the_loop_is_seen_like_a_plain_lookup(tmp_path, change):
    """The batch must not yield a row the session has deleted or re-keyed (unflushed)."""
    p = _filled(tmp_path)
    p.autocommit = False
    seen = []
    with pytest.raises(KeyError):  # what the plain per-key lookup does
        for key, row in p.items():
            seen.append(key["id"])
            if key["id"] == "k001":
                if change == "delete":
                    del p[{"id": "k005"}]
                else:
                    p[{"id": "k005"}] = {"id": "zzz", "doc": "moved"}
    assert "k005" not in seen


def test_expired_row_deleted_elsewhere_raises_keyerror_not_objectdeleted(tmp_path):
    a, b = _filled(tmp_path), _file_persister(tmp_path)
    with pytest.raises(KeyError):
        for key, _ in a.items():
            if key["id"] == "k001":
                a[{"id": "k002"}] = {"doc": "x"}  # commit: expires every row
                del b[{"id": "k005"}]


def test_primary_key_bulk_update_then_commit_in_the_loop(tmp_path):
    p = _filled(tmp_path)
    with pytest.raises(KeyError):
        for key, _ in p.items():
            if key["id"] == "k001":
                p.session.query(p.table).filter_by(id="k005").update({"id": "zzz"})
                p.session.commit()


def test_unhashable_key_value_falls_back_to_a_plain_lookup(tmp_path):
    p = _filled(tmp_path, 3)
    assert p._load_rows([{"id": ["not", "hashable"]}]) == {}
