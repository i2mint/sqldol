"""Making test data for sqldol tests."""


def mk_simple_4_by_3_table(engine, table_name='sqldol_test_table'):
    from sqlalchemy import Column, Integer, JSON
    from sqldol.util import get_or_create_table, ensure_engine
    from sqldol.base import SqlKvStore

    engine = ensure_engine(engine)

    example_data = {
        'name': ['Alice', 'Bob', 'Charlie', 'Diana'],
        'age': [30, 25, 35, 28],
        'extras': [
            {'hobby': 'cycling', 'pet': 'cat'},
            {'hobby': 'hiking', 'pet': 'dog'},
            {'hobby': 'swimming', 'pet': 'fish'},
            {'hobby': 'reading'},
        ],
    }
    example_data_with_name_key = {
        x[0]: dict(zip(['age', 'extras'], x[1:])) for x in zip(*example_data.values())
    }
    assert example_data_with_name_key == {
        'Alice': {'age': 30, 'extras': {'hobby': 'cycling', 'pet': 'cat'}},
        'Bob': {'age': 25, 'extras': {'hobby': 'hiking', 'pet': 'dog'}},
        'Charlie': {'age': 35, 'extras': {'hobby': 'swimming', 'pet': 'fish'}},
        'Diana': {'age': 28, 'extras': {'hobby': 'reading'}},
    }

    get_or_create_table(
        engine,
        'sqldol_test_table',
        ['name', Column('age', Integer), Column('extras', JSON)],
    )

    test_store = SqlKvStore(engine, table_name, 'name', ['age', 'extras'])

    test_store.update(example_data_with_name_key)
