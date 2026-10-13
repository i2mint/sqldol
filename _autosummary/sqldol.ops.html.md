# sqldol.ops

Leaf-level operations, as free functions over the caller’s (possibly wrapped) store.

`dol` wraps stores by delegation, so a public *attribute* of a persister is served by every
wrapper above it unchanged, in the persister’s own coordinates (i2mint/sqldol#3, i2mint/dol#83).
`SQLAlchemyPersister.query` was such an attribute: on a `SQLAlchemyTupleStore` (which speaks
tuples) it handed back ORM rows, and anything filtered through it was in a different coordinate
system than the store, with nothing raising. A free function is handed the caller’s store itself,
so it can tell whether wrappers sit between the caller and the persister, and say so.

- [`query()`](#sqldol.ops.query) `(store)` is the SQLAlchemy `Query` over the persister’s table. On a bare
  persister that is the store’s own coordinates. Under a wrapper it is not, so it is refused
  with [`WrappedStoreError`](#sqldol.ops.WrappedStoreError) unless `leaf_coordinates=True` states that you want the
  persister’s rows and keys.

The removed `SQLAlchemyPersister.query` property and `SQLAlchemyPersister.setup` method
raise an `AttributeError` naming their replacement (`setup`, a whole-store rebind that no
wrapper could veto, has none: build a new store). The same design as cosmodol.ops, sshdol.ops
and s3dol’s ADR-0011.

`table`, `session` and `connection` are still plain attributes of the persister (they are
the SQLAlchemy objects it is built on). Through a wrapper they too are the persister’s, not the
store’s: treat them as leaf escape hatches.

```pycon
>>> import sqlalchemy
>>> from sqldol import SQLAlchemyTupleStore
>>> store = SQLAlchemyTupleStore(
...     "sqlite:///:memory:", "t",
...     key_fields={"id": sqlalchemy.String}, data_fields={"data": sqlalchemy.String},
... )
>>> store[("a",)] = ("one",)
>>> list(store)
[('a',)]
>>> query(store)
Traceback (most recent call last):
  ...
sqldol.ops.WrappedStoreError: SQLAlchemyTupleStore is not a bare SQLAlchemyPersister...
>>> [(row.id, row.data) for row in query(store, leaf_coordinates=True)]
[('a', 'one')]
```

### Functions

| [`query`](#sqldol.ops.query)(store, \*[, leaf_coordinates])   | The SQLAlchemy `Query` over the table of `store`'s persister (rows are ORM objects).   |
|-----------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------|

### Exceptions

| [`WrappedStoreError`](#sqldol.ops.WrappedStoreError)   | An operation that answers in the persister's coordinates was given a wrapped store (i2mint/sqldol#3).   |
|----------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------|

### *exception* sqldol.ops.WrappedStoreError

Bases: [`ValueError`](https://docs.python.org/3/builtins/exceptions.html#ValueError)

An operation that answers in the persister’s coordinates was given a wrapped store (i2mint/sqldol#3).

### sqldol.ops.query(store, , leaf_coordinates=False)

The SQLAlchemy `Query` over the table of `store`’s persister (rows are ORM objects).

The rows are the persister’s: their keys and values are *not* mapped by any `dol`
wrapper between you and the persister. If `store` is such a wrapper (a
`SQLAlchemyTupleStore`, a key codec, a `filt_iter` view…), a `Query` could neither
honour its scope nor speak its keys, so `WrappedStoreError` is raised unless you pass
`leaf_coordinates=True`, which says you know.

A *subclass* of `SQLAlchemyPersister` counts as bare, even if it maps keys or values
itself: `query` cannot know.

* **Parameters:**
  * **store** – a `SQLAlchemyPersister`, wrapped or not
  * **leaf_coordinates** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – accept a wrapped `store` and return the persister’s query
* **Raises:**
  [**WrappedStoreError**](#sqldol.ops.WrappedStoreError) – if `store` is wrapped and `leaf_coordinates` is not set
