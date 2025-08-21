# sqldol

SQL (through SQLAlchemy) with a simple (dict-like or list-like) interface

## Installation

```bash
pip install sqldol
```

## Overview

`sqldol` provides a pythonic, dict-like interface to SQL databases using SQLAlchemy under the hood. It allows you to interact with SQL tables as if they were Python dictionaries or lists, making database operations more intuitive and less verbose.

## Key Features

- **Dict-like interface**: Access SQL tables like Python dictionaries
- **Multiple store types**: Choose from various store implementations based on your needs
- **SQLAlchemy integration**: Built on top of SQLAlchemy for robust database support
- **Flexible data formats**: Work with rows as tuples, dictionaries, or raw data
- **Simple CRUD operations**: Create, read, update, and delete with familiar Python syntax

## Quick Start

### Basic Usage with SQLAlchemyStore

```python
from sqldol import SQLAlchemyStore

# Connect to an in-memory SQLite database
store = SQLAlchemyStore(
    uri='sqlite:///:memory:',
    collection_name='users',
    key_fields={'user_id': SQLAlchemyStore.TYPE_INTEGER},
    data_fields={'name': SQLAlchemyStore.TYPE_STRING, 'email': SQLAlchemyStore.TYPE_STRING}
)

# Create
store[{'user_id': 1}] = {'name': 'Alice', 'email': 'alice@example.com'}

# Read
user = store[{'user_id': 1}]
print(user.name)  # Alice

# Update
store[{'user_id': 1}] = {'name': 'Alice Smith', 'email': 'alice.smith@example.com'}

# Delete
del store[{'user_id': 1}]
```

### Working with Different Store Types

#### SqlDictStore - Dictionary Values

```python
from sqldol import SqlDictStore

# Returns single dictionaries as values
dict_store = SqlDictStore(engine, 'my_table', key_columns=['id'], value_columns=['name', 'age'])

# Access returns a dictionary
user_data = dict_store['user123']  # {'name': 'John', 'age': 30}
```

#### SqlRowsReader - List of Rows

```python
from sqldol import SqlRowsReader

# Returns lists of rows (tuples)
rows_reader = SqlRowsReader(engine, 'my_table', key_columns=['category'], value_columns=['id', 'name'])

# Access returns a list of tuples
items = rows_reader['electronics']  # [('1', 'Phone'), ('2', 'Laptop')]
```

#### SqlRowReader - Single Row

```python
from sqldol import SqlRowReader

# Returns single row (tuple)
row_reader = SqlRowReader(engine, 'my_table', key_columns=['id'], value_columns=['name', 'price'])

# Access returns a tuple
item = row_reader['123']  # ('Widget', 19.99)
```

### Database Connection Examples

#### SQLite

```python
# File-based SQLite
store = SQLAlchemyStore('sqlite:///my_database.db', 'my_table')

# In-memory SQLite
store = SQLAlchemyStore('sqlite:///:memory:', 'my_table')
```

#### PostgreSQL

```python
store = SQLAlchemyStore(
    'postgresql://user:password@localhost:5432/my_db',
    'my_table'
)
```

#### MySQL

```python
store = SQLAlchemyStore(
    'mysql://user:password@localhost/my_db',
    'my_table'
)
```

### Working with Complex Data Types

```python
from sqldol import SQLAlchemyStore
from sqlalchemy import JSON

# Store with JSON field
store = SQLAlchemyStore(
    uri='sqlite:///example.db',
    collection_name='products',
    key_fields={'product_id': SQLAlchemyStore.TYPE_STRING},
    data_fields={
        'name': SQLAlchemyStore.TYPE_STRING,
        'metadata': JSON  # Store complex data as JSON
    }
)

# Store complex data
store[{'product_id': 'PROD001'}] = {
    'name': 'Smartphone',
    'metadata': {
        'specs': {'ram': '8GB', 'storage': '128GB'},
        'tags': ['electronics', 'mobile'],
        'reviews': {'average': 4.5, 'count': 150}
    }
}
```

### Tuple-based Operations

```python
from sqldol import SQLAlchemyTupleStore

# Work with tuples for both keys and values
tuple_store = SQLAlchemyTupleStore(
    uri='sqlite:///:memory:',
    collection_name='coordinates',
    key_fields=['x', 'y'],
    data_fields=['label', 'value']
)

# Keys and values are tuples
tuple_store[(10, 20)] = ('Point A', 42.0)
point_data = tuple_store[(10, 20)]  # ('Point A', 42.0)
```

## Advanced Usage

### Database Collections

```python
from sqldol import SqlDbReader

# Access multiple tables in a database
db = SqlDbReader.from_uri('sqlite:///my_app.db')

# List all tables
tables = list(db)  # ['users', 'products', 'orders']

# Access specific table
users_table = db['users']
all_users = list(users_table)  # List of all user rows
```

### Custom Persisters

```python
from sqldol import SQLAlchemyPersister

# Lower-level access for custom operations
persister = SQLAlchemyPersister(
    uri='sqlite:///custom.db',
    collection_name='events',
    key_fields={'event_id': SQLAlchemyPersister.TYPE_STRING},
    data_fields={'timestamp': SQLAlchemyPersister.TYPE_STRING, 'data': SQLAlchemyPersister.TYPE_TEXT}
)

# Direct access to SQLAlchemy session and query objects
query_result = persister.query.filter_by(event_id='EVT001').first()
```

## Testing

The project includes comprehensive tests. To run them:

```bash
# Install test dependencies
pip install pytest

# Run tests
pytest sqldol/tests/
```

## Supported Data Types

- `TYPE_INTEGER`: Integer values
- `TYPE_STRING`: Variable-length strings
- `TYPE_TEXT`: Long text fields
- `TYPE_BOOLEAN`: Boolean values
- `TYPE_BLOB`: Binary data
- Plus any SQLAlchemy type (JSON, DateTime, etc.)

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## License

[License information would go here]

## Related Projects

- [dol](https://github.com/i2mint/dol) - The underlying framework for dict-like interfaces
- [SQLAlchemy](https://www.sqlalchemy.org/) - The SQL toolkit powering sqldol
