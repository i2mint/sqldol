"""Tests for the ``Mapping`` contract of ``SqlBaseKvReader`` and its subclasses.

Covers ``__len__`` (which must return a real, non-negative row count) and the
``missing_key_policy`` that decides what an absent key does: return an empty
result (the legacy default) or raise ``KeyError`` (which is what makes the
inherited ``__contains__`` and ``.get(key, default)`` truthful).

Uses in-memory SQLite only -- no external service, no credentials.
"""

import pytest
from sqlalchemy import create_engine, text

from sqldol import SqlDictsReader, SqlDictReader, SqlRowReader, SqlRowsReader

TABLE_NAME = 't'
KEY_COLUMN = 'k'


@pytest.fixture
def engine():
    """An in-memory SQLite engine holding ``t(k, v)`` with rows a/1 and b/2."""
    engine = create_engine('sqlite:///:memory:')
    with engine.connect() as connection:
        connection.execute(text(f'CREATE TABLE {TABLE_NAME} (k TEXT, v TEXT)'))
        connection.execute(text(f"INSERT INTO {TABLE_NAME} VALUES ('a', '1'), ('b', '2')"))
        connection.commit()
    return engine


@pytest.mark.parametrize(
    'cls', [SqlRowsReader, SqlRowReader, SqlDictsReader, SqlDictReader]
)
def test_len_is_a_real_row_count(engine, cls):
    """``__len__`` must count rows, not return a SELECT's ``rowcount``.

    Before the fix every one of these raised
    ``ValueError: __len__() should return >= 0``, because a SELECT reports
    ``rowcount == -1`` on SQLite (and any other driver that does not
    pre-buffer results).
    """
    store = cls(engine, TABLE_NAME, key_columns=KEY_COLUMN)
    assert len(store) == 2


@pytest.mark.parametrize(
    'cls', [SqlRowsReader, SqlRowReader, SqlDictsReader, SqlDictReader]
)
def test_list_of_store_yields_the_keys(engine, cls):
    """``list(store)`` used to die on the ``__len__`` length hint, though
    ``iter(store)`` worked fine."""
    store = cls(engine, TABLE_NAME, key_columns=KEY_COLUMN)
    assert sorted(store) == ['a', 'b']
    assert sorted(list(store)) == ['a', 'b']


def test_values_of_present_keys_are_unchanged(engine):
    """Guard that nothing about the happy path moved."""
    assert SqlDictsReader(engine, TABLE_NAME, key_columns=KEY_COLUMN)['a'] == [
        {'k': 'a', 'v': '1'}
    ]
    assert SqlRowsReader(engine, TABLE_NAME, key_columns=KEY_COLUMN)['a'] == [
        ['a', '1']
    ]
    assert SqlRowReader(engine, TABLE_NAME, key_columns=KEY_COLUMN)['a'] == ['a', '1']
    assert SqlDictReader(engine, TABLE_NAME, key_columns=KEY_COLUMN)['a'] == {
        'k': 'a',
        'v': '1',
    }


@pytest.mark.parametrize(
    'cls', [SqlRowsReader, SqlRowReader, SqlDictsReader, SqlDictReader]
)
def test_missing_key_policy_raise_makes_the_mapping_contract_truthful(engine, cls):
    """With ``missing_key_policy='raise'``, ``in`` and ``.get`` stop lying.

    Before the fix ``'zzz' in store`` was ``True`` for every store (because
    ``Mapping.__contains__`` is getitem-based and getitem never raised), and
    ``.get('zzz', default)`` returned an empty result instead of ``default``.
    """
    store = cls(engine, TABLE_NAME, key_columns=KEY_COLUMN, missing_key_policy='raise')

    with pytest.raises(KeyError):
        store['zzz']

    assert 'zzz' not in store
    assert 'a' in store
    assert store.get('zzz', 'DEFAULT') == 'DEFAULT'
    assert store.get('a') is not None


def test_missing_key_policy_defaults_to_the_legacy_empty_behavior(engine):
    """Regression guard: the default must keep 2024-era callers working.

    Existing consumers branch on ``SqlDictReader[missing] is None``, so the
    ``KeyError`` behaviour has to stay opt-in.
    """
    assert SqlDictReader(engine, TABLE_NAME, key_columns=KEY_COLUMN)['zzz'] is None
    assert SqlDictsReader(engine, TABLE_NAME, key_columns=KEY_COLUMN)['zzz'] == []
    assert SqlRowsReader(engine, TABLE_NAME, key_columns=KEY_COLUMN)['zzz'] == []
    with pytest.raises(StopIteration):
        SqlRowReader(engine, TABLE_NAME, key_columns=KEY_COLUMN)['zzz']


def test_unknown_missing_key_policy_is_rejected_at_construction(engine):
    """A typo must fail loudly, and at construction time, not at lookup time."""
    with pytest.raises(ValueError):
        SqlDictsReader(
            engine, TABLE_NAME, key_columns=KEY_COLUMN, missing_key_policy='nope'
        )
