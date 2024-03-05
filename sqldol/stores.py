"""Higher level stores for sql data"""

from typing import List, Iterable
from sqldol.base import SqlBaseKvReader
from dol import wrap_kvs

# TODO: Extend value wrappers to contain data_of_obj to be able to wrap SqlBaseKvStore
list_values = wrap_kvs(obj_of_data=list)


def _first_value(iterable):
    """
    Get the first element of an iterable.

    >>> _get_first([1, 2])
    1

    """
    return next(iter(iterable))


first_value = wrap_kvs(obj_of_data=_first_value)

there_are_no_more = object()


def _get_first_and_assert_there_are_no_more(iterable):
    """
    Get the first element of an iterable, and assert that there are no more elements.

    >>> _get_first_and_assert_there_are_no_more([1])
    1
    >>> _get_first_and_assert_there_are_no_more([1, 2])
    Traceback (most recent call last):
        ...
    ValueError: iterable has more than one element
    """
    it = iter(iterable)
    first = next(it)
    next_one = next(it, there_are_no_more)
    if next_one is there_are_no_more:
        return first
    else:
        raise ValueError("iterable has more than one element")


get_first_and_assert_there_are_no_more = wrap_kvs(
    obj_of_data=_get_first_and_assert_there_are_no_more
)

Row = List


def _dictionarize_row(self, row: Row):
    """
    Convert row (list) to a dictionary using the value_columns as keys.

    >>> from types import SimpleNamespace
    >>> self = SimpleNamespace(value_columns=['a', 'b'])
    >>> self.value_columns
    ['a', 'b']
    >>> row = [1, 'one']
    >>> _dictionarize_row(self, [1, 'one'])
    {'a': 1, 'b': 'one'}

    """
    return dict(zip(self.value_columns, row))


def _dictionarize_rows(self, rows: Iterable[Row]):
    """
    Convert an iterable of rows to list of dictionaries using the value_columns as keys.
    """
    return [_dictionarize_row(self, row) for row in rows]


def _dictionarize_first_row(self, rows: Iterable[Row]):
    return dict(zip(self.value_columns, _first_value(rows)))


dictionarize_rows = wrap_kvs(obj_of_data=_dictionarize_rows)
dictionarize_first_row = wrap_kvs(obj_of_data=_dictionarize_first_row)


@list_values
class SqlRowsReader(SqlBaseKvReader):
    """SqlBaseKvReader whose values are lists of rows (lists)."""


@first_value
class SqlRowReader(SqlBaseKvReader):
    """SqlBaseKvReader whose values are single rows (the first one matchig the key)."""


@dictionarize_rows
class SqlDictsReader(SqlBaseKvReader):
    """SqlBaseKvReader whose values are lists of dicts."""


@dictionarize_first_row
class SqlDictReader(SqlBaseKvReader):
    """SqlBaseKvReader whose values are single dicts (the first one matchig the key)."""
