"""Leaf-level operations, as free functions over the caller's (possibly wrapped) store.

``dol`` wraps stores by delegation, so a public *attribute* of a persister is served by every
wrapper above it unchanged, in the persister's own coordinates (i2mint/sqldol#3, i2mint/dol#83).
``SQLAlchemyPersister.query`` was such an attribute: on a ``SQLAlchemyTupleStore`` (which speaks
tuples) it handed back ORM rows, and anything filtered through it was in a different coordinate
system than the store, with nothing raising. A free function is handed the caller's store itself,
so it can tell whether wrappers sit between the caller and the persister, and say so.

- :func:`query` ``(store)`` is the SQLAlchemy ``Query`` over the persister's table. On a bare
  persister that is the store's own coordinates. Under a wrapper it is not, so it is refused
  with :class:`WrappedStoreError` unless ``leaf_coordinates=True`` states that you want the
  persister's rows and keys.

The removed ``SQLAlchemyPersister.query`` property and ``SQLAlchemyPersister.setup`` method
raise an ``AttributeError`` naming their replacement (``setup``, a whole-store rebind that no
wrapper could veto, has none: build a new store). The same design as cosmodol.ops, sshdol.ops
and s3dol's ADR-0011.

``table``, ``session`` and ``connection`` are still plain attributes of the persister (they are
the SQLAlchemy objects it is built on). Through a wrapper they too are the persister's, not the
store's: treat them as leaf escape hatches.

>>> import sqlalchemy
>>> from sqldol import SQLAlchemyTupleStore
>>> store = SQLAlchemyTupleStore(
...     "sqlite:///:memory:", "t",
...     key_fields={"id": sqlalchemy.String}, data_fields={"data": sqlalchemy.String},
... )
>>> store[("a",)] = ("one",)
>>> list(store)
[('a',)]
>>> query(store)  # doctest: +ELLIPSIS
Traceback (most recent call last):
  ...
sqldol.ops.WrappedStoreError: SQLAlchemyTupleStore is not a bare SQLAlchemyPersister...
>>> [(row.id, row.data) for row in query(store, leaf_coordinates=True)]
[('a', 'one')]
"""

from __future__ import annotations

from sqldol.sql_base import SQLAlchemyPersister, _leaf_persister


class WrappedStoreError(ValueError):
    """An operation that answers in the persister's coordinates was given a wrapped store (i2mint/sqldol#3)."""


def _persister_of(store) -> SQLAlchemyPersister:
    persister = _leaf_persister(store)
    if persister is None:
        raise TypeError(f"{type(store).__name__} does not wrap a SQLAlchemyPersister")
    return persister


def query(store, *, leaf_coordinates: bool = False):
    """The SQLAlchemy ``Query`` over the table of ``store``'s persister (rows are ORM objects).

    The rows are the persister's: their keys and values are *not* mapped by any ``dol``
    wrapper between you and the persister. If ``store`` is such a wrapper (a
    ``SQLAlchemyTupleStore``, a key codec, a ``filt_iter`` view...), a ``Query`` could neither
    honour its scope nor speak its keys, so ``WrappedStoreError`` is raised unless you pass
    ``leaf_coordinates=True``, which says you know.

    A *subclass* of ``SQLAlchemyPersister`` counts as bare, even if it maps keys or values
    itself: ``query`` cannot know.

    :param store: a ``SQLAlchemyPersister``, wrapped or not
    :param leaf_coordinates: accept a wrapped ``store`` and return the persister's query
    :raises WrappedStoreError: if ``store`` is wrapped and ``leaf_coordinates`` is not set
    """
    persister = _persister_of(store)
    if store is not persister and not leaf_coordinates:
        raise WrappedStoreError(
            f"{type(store).__name__} is not a bare SQLAlchemyPersister (it wraps one): a Query answers in the "
            "persister's coordinates (ORM rows, its own keys), not the store's, and cannot "
            "honour the wrapper's scope. Pass leaf_coordinates=True if that is what you "
            "want (i2mint/sqldol#3)."
        )
    return persister._query
