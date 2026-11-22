"""Regression tests for i2mint/sqldol#19: list-valued fields and portable table listing."""

import sqlalchemy as sa

from sqldol import SQLAlchemyTupleStore, SqlDbReader


def test_tuple_store_accepts_list_valued_fields():
    store = SQLAlchemyTupleStore(
        uri='sqlite:///:memory:',
        collection_name='coordinates',
        key_fields=['x', 'y'],
        data_fields=['label', 'value'],
    )
    store[('10', '20')] = ('Point A', '42.0')
    assert store[('10', '20')] == ('Point A', '42.0')


def test_tuple_store_typed_fields_round_trip_numbers():
    store = SQLAlchemyTupleStore(
        uri='sqlite:///:memory:',
        collection_name='coordinates',
        key_fields={'x': sa.Integer, 'y': sa.Integer},
        data_fields={'label': sa.String, 'value': sa.Float},
    )
    store[(10, 20)] = ('Point A', 42.0)
    assert store[(10, 20)] == ('Point A', 42.0)


def test_db_reader_lists_tables_on_sqlite():
    connection = sa.create_engine('sqlite:///:memory:').connect()
    connection.execute(sa.text('create table users (id integer)'))
    assert list(SqlDbReader(connection)) == ['users']
