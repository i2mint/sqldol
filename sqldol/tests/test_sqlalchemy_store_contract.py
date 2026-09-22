"""Tests that ``k in store`` agrees with ``store[k]`` for the SQLAlchemy stores.

``SQLAlchemyPersister.__iter__`` yields ORM row objects rather than keys, so the
brute-force ``__contains__`` inherited from ``dol.base.Collection`` compared a key
against a row and answered ``False`` for every key. ``SQLAlchemyStore`` and
``SQLAlchemyTupleStore`` inherited that answer through ``dol.base.Store``.

Uses in-memory SQLite only -- no external service, no credentials.
"""

import pytest

from sqldol import SQLAlchemyPersister, SQLAlchemyStore, SQLAlchemyTupleStore

SQLITE_DB_URI = 'sqlite:///:memory:'
KEY_FIELDS = {'id': SQLAlchemyPersister.TYPE_STRING}
DATA_FIELDS = {'doc': SQLAlchemyPersister.TYPE_TEXT}


def _mk(cls, collection_name):
    return cls(
        uri=SQLITE_DB_URI,
        collection_name=collection_name,
        key_fields=KEY_FIELDS,
        data_fields=DATA_FIELDS,
    )


def test_persister_contains_agrees_with_getitem():
    persister = _mk(SQLAlchemyPersister, 'persister_contains')
    persister[{'id': 'a'}] = {'doc': 'x'}

    assert {'id': 'a'} in persister
    assert {'id': 'zzz'} not in persister
    assert persister[{'id': 'a'}] is not None
    assert len(persister) == 1


def test_store_contains_agrees_with_getitem():
    store = _mk(SQLAlchemyStore, 'store_contains')
    store[{'id': 'a'}] = {'doc': 'x'}

    assert {'id': 'a'} in store
    assert {'id': 'zzz'} not in store
    assert store[{'id': 'a'}] is not None
    assert len(store) == 1


def test_tuple_store_contains_agrees_with_getitem():
    store = _mk(SQLAlchemyTupleStore, 'tuple_store_contains')
    store[('a',)] = ('x',)

    assert ('a',) in store
    assert ('zzz',) not in store
    assert store[('a',)] == ('x',)
    assert len(store) == 1


def test_tuple_store_iteration_still_yields_keys():
    """Pins that ``__iter__`` was deliberately left alone.

    Making the persister's ``__iter__`` yield keys instead of ORM rows is a
    separate, not-backwards-compatible change: ``SQLAlchemyTupleStore._key_of_id``
    does ``getattr(obj, field)`` on whatever is yielded, and at least one known
    consumer wraps the row-yielding behaviour.
    """
    store = _mk(SQLAlchemyTupleStore, 'tuple_store_iter')
    store[('a',)] = ('x',)

    assert list(store) == [('a',)]


def test_contains_does_not_raise_on_a_key_it_cannot_query():
    """``in`` must answer, not explode, for keys that can't name a row.

    ``Container.__contains__`` returned False for these before, so keeping them
    False (rather than propagating a SQLAlchemy/TypeError) preserves behaviour.
    """
    persister = _mk(SQLAlchemyPersister, 'persister_bad_key')
    persister[{'id': 'a'}] = {'doc': 'x'}

    assert 'not-a-dict' not in persister
    assert {'no_such_column': 'a'} not in persister
