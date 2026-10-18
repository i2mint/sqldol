"""Tests for sqldol.access: reading Access files as Mappings and as SQLite engines (#15).

The backend-independent logic runs everywhere against an in-memory source. The real backends
run against synthetic fixtures (``test_data/tiny_jet4.mdb.gz``, ``tiny_ace.accdb.gz``, generated
by ``test_data/MkFixture.java``) and are skipped when the backend is not installed.
"""

import datetime
import gzip
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from collections.abc import Mapping

from sqldol import SqlDictReader, TablesDol
from sqldol import access
from sqldol.access import (
    BACKENDS,
    AccessColumns,
    AccessReadError,
    AccessReader,
    MdbtoolsSource,
    MissingAccessBackendError,
    _DictSource,
    access_engine,
    check_requirements,
)

TEST_DATA = Path(__file__).parent / "test_data"

TABLES = {
    "Items": [
        {"ID": 1, "Title": "alpha", "When": datetime.datetime(2001, 2, 3, 4, 5, 6)},
        {"ID": 2, "Title": None, "When": None},
    ],
    "Empty Table": [],
}


def _fake(tables=TABLES):
    return _DictSource.factory(tables, columns={"Empty Table": ["ID", "Name"]})


def test_reader_is_a_mapping_of_tables_to_rows():
    reader = AccessReader("x.mdb", backend=_fake())
    assert list(reader) == ["Items", "Empty Table"]
    assert len(reader) == 2
    assert "Items" in reader and "Nope" not in reader
    assert reader["Items"][0]["Title"] == "alpha"
    assert reader["Empty Table"] == []
    with pytest.raises(KeyError):
        reader["Nope"]
    columns = AccessColumns(reader)
    assert dict(columns) == {"Items": ["ID", "Title", "When"], "Empty Table": ["ID", "Name"]}
    with pytest.raises(KeyError):
        columns["Nope"]
    assert not [m for m in dir(AccessReader) if not m.startswith("_") and m not in dir(Mapping)], (
        "AccessReader has public non-Mapping methods; key-taking ones break under wrappers (dol#83)"
    )


def test_engine_copies_tables_and_sqldol_stores_work_on_it():
    engine = access_engine("x.mdb", backend=_fake())
    assert set(TablesDol(engine)) == {"Items", "Empty Table"}
    assert list(TablesDol(engine)["Empty Table"].columns.keys()) == ["ID", "Name"]
    items = SqlDictReader(engine, "Items", key_columns="ID")
    assert items[1] == {"ID": 1, "Title": "alpha", "When": "2001-02-03 04:05:06"}
    assert items[2] == {"ID": 2, "Title": None, "When": None}


def test_engine_to_a_file_replaces_same_named_tables(tmp_path):
    db = tmp_path / "copy?.sqlite"  # a '?' must not be read as a URL query
    access_engine("x.mdb", backend=_fake(), sqlite_path=db, tables=["Items", "Items"])
    engine = access_engine("x.mdb", backend=_fake(), sqlite_path=db, tables=["Items"])
    assert db.exists()
    assert list(TablesDol(engine)) == ["Items"]
    assert len(list(SqlDictReader(engine, "Items", key_columns="ID"))) == 2


def test_a_failed_copy_leaves_the_existing_table_intact(tmp_path):
    db = tmp_path / "copy.sqlite"
    access_engine("x.mdb", backend=_fake(), sqlite_path=db, tables=["Items"])
    unstorable = {"Items": [{"ID": 9, "Title": {"not": "storable"}, "When": None}]}
    with pytest.raises(Exception):
        access_engine("x.mdb", backend=_fake(unstorable), sqlite_path=db, tables=["Items"])
    engine = access_engine("x.mdb", backend=_fake({}), sqlite_path=db, tables=[])
    assert list(TablesDol(engine)) == ["Items"]
    assert sorted(SqlDictReader(engine, "Items", key_columns="ID")) == [1, 2]


def test_replacing_a_table_that_a_view_depends_on(tmp_path):
    db = tmp_path / "copy.sqlite"
    engine = access_engine("x.mdb", backend=_fake(), sqlite_path=db, tables=["Items"])
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE VIEW titles AS SELECT "Title" FROM "Items"')
    engine = access_engine("x.mdb", backend=_fake(), sqlite_path=db, tables=["Items"])
    with engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM titles").scalar() == 2


def test_mixed_and_wide_values_are_stored():
    tables = {
        "T": [
            {"ID": 1, "V": True, "W": Decimal("1234.5678"), "X": b"\x00", "Y": 2**70},
            {"ID": 2, "V": 2, "W": Decimal("7"), "X": "text", "Y": None},
        ]
    }
    engine = access_engine("x.mdb", backend=_DictSource.factory(tables))
    rows = SqlDictReader(engine, "T", key_columns="ID")
    assert rows[1] == {"ID": 1, "V": 1, "W": 1234.5678, "X": b"\x00", "Y": str(2**70)}
    assert rows[2] == {"ID": 2, "V": 2, "W": 7, "X": "text", "Y": None}


def test_unknown_backend_name_raises_and_never_falls_back():
    with pytest.raises(ValueError, match="Unknown Access backend"):
        AccessReader("x.mdb", backend="acces_parser")


def test_no_backend_available_says_how_to_get_one(monkeypatch):
    for source in BACKENDS.values():
        monkeypatch.setattr(source, "is_available", staticmethod(lambda: False))
    with pytest.raises(MissingAccessBackendError, match="mdbtools"):
        AccessReader("x.mdb")
    assert check_requirements(verbose=False) == {"mdbtools": False, "access_parser": False}


def test_auto_backend_falls_back_when_one_cannot_open_the_file(monkeypatch):
    class Fails:
        name = "fails"
        is_available = staticmethod(lambda: True)

        def __init__(self, path):
            raise AccessReadError("not this one")

    class Opens(_DictSource):
        name = "opens"
        is_available = staticmethod(lambda: True)

        def __init__(self, path):
            super().__init__(TABLES)

    monkeypatch.setattr(access, "BACKENDS", {"fails": Fails, "opens": Opens})
    assert list(AccessReader("x.mdb")) == ["Items", "Empty Table"]

    monkeypatch.setattr(access, "BACKENDS", {"fails": Fails})
    with pytest.raises(AccessReadError, match="fails: not this one"):
        AccessReader("x.mdb")


def test_mdbtools_output_parsing(monkeypatch, tmp_path):
    outputs = {
        "mdb-ver": "JET4\n",
        "mdb-tables": "Items\nCategories\n",
        "mdb-schema": (
            "CREATE TABLE [Items]\n (\n\t[ID]\t\t\tLong Integer, \n\t[My Title]\t\t\tText (50), "
            "\n\t[Key]\t\t\tReplication ID, \n\t[Blob]\t\t\tOLE, \n\t[Amount]\t\t\tCurrency, "
            "\n\t[Flag]\t\t\tBoolean NOT NULL, \n\t[Ratio]\t\t\tDouble\n);\n"
        ),
        "mdb-json": (
            '{"ID":1,"My Title":"alpha","Blob":{"$binary":"AAE=","$type":"00"},'
            '"Key":{"$binary":"ezBCMzM5NTAyLTMxNDUtMTFEMi04RDQ1MDA4MEM2RkQyQ0FBfQ==","$type":"00"},'
            '"Amount":922337203685477.5807,"Flag":1,"Ratio":0.5}\n'
            '{"ID":2,"Flag":0}\n'
        ),
    }
    monkeypatch.setattr(MdbtoolsSource, "_run", lambda self, *args: outputs[args[0]])
    path = tmp_path / "x.mdb"
    path.touch()  # the programs are faked; the file only has to exist
    reader = AccessReader(path, backend=MdbtoolsSource)
    assert list(reader) == ["Items", "Categories"]
    assert AccessColumns(reader)["Items"] == [
        "ID", "My Title", "Key", "Blob", "Amount", "Flag", "Ratio"
    ]
    first, second = reader["Items"]
    assert first == {
        "ID": 1,
        "My Title": "alpha",
        "Key": "{0B339502-3145-11D2-8D45-0080C6FD2CAA}",
        "Blob": b"\x00\x01",
        "Amount": Decimal("922337203685477.5807"),
        "Flag": True,
        "Ratio": 0.5,
    }
    assert second == {
        "ID": 2, "My Title": None, "Key": None, "Blob": None, "Amount": None, "Flag": False,
        "Ratio": None,
    }


# --------------------------------------------------------------------------------------
# Real backends on the synthetic fixtures


def _gunzipped(tmp_path_factory, name):
    path = tmp_path_factory.mktemp("access") / name
    with gzip.open(TEST_DATA / f"{name}.gz") as src, open(path, "wb") as dst:
        shutil.copyfileobj(src, dst)
    return path


@pytest.fixture(scope="module")
def tiny_mdb(tmp_path_factory):
    return _gunzipped(tmp_path_factory, "tiny_jet4.mdb")


@pytest.fixture(scope="module")
def tiny_accdb(tmp_path_factory):
    return _gunzipped(tmp_path_factory, "tiny_ace.accdb")


def _skip_unless_available(backend):
    if not BACKENDS[backend].is_available():
        pytest.skip(f"{backend} backend not installed")


@pytest.mark.parametrize("backend", list(BACKENDS))
def test_real_backend_reads_fixture(backend, tiny_mdb):
    _skip_unless_available(backend)
    reader = AccessReader(tiny_mdb, backend=backend)
    assert sorted(reader) == ["Categories", "Items", "Numbers"]
    assert AccessColumns(reader)["Items"] == ["ID", "Title", "Body", "Price", "Created", "Key"]
    rows = {row["ID"]: row for row in reader["Items"]}
    assert rows[1] == {
        "ID": 1,
        "Title": "alpha",
        "Body": "short memo",
        "Price": 1.5,
        "Created": "2001-02-03 04:05:06",
        "Key": "{0B339502-3145-11D2-8D45-0080C6FD2CAA}",
    }
    assert rows[2]["Title"] == "béta"
    assert rows[2]["Body"].startswith("line 0; ") and rows[2]["Body"].endswith("line 299; ")
    assert rows[3] == {
        "ID": 3, "Title": "gamma", "Body": None, "Price": None, "Created": None, "Key": None
    }
    assert reader["Numbers"] == [
        {
            "ID": 1,
            "Amount": Decimal("1234.5678"),
            "Big": Decimal("123456789012345678"),
            "Flag": True,
            "Small": Decimal("0.10000000000000000001"),
        },
        {"ID": 2, "Amount": Decimal("0.0001"), "Big": Decimal("-7"), "Flag": False,
         "Small": Decimal("-12.5")},
        {"ID": 3, "Amount": None, "Big": None, "Flag": False, "Small": None},
    ]

    engine = access_engine(reader)
    item = SqlDictReader(engine, "Items", key_columns="ID")[1]
    assert item["Created"] == "2001-02-03 04:05:06"
    number = SqlDictReader(engine, "Numbers", key_columns="ID")[1]
    assert number == {
        "ID": 1, "Amount": 1234.5678, "Big": 123456789012345678, "Flag": True, "Small": 0.1
    }


def test_mdbtools_reads_accdb(tiny_accdb):
    _skip_unless_available("mdbtools")
    reader = AccessReader(tiny_accdb, backend="mdbtools")
    assert reader.source.version.startswith("ACE")
    assert [row["Title"] for row in reader["Items"]] == ["alpha", "béta", "gamma"]


def test_auto_backend_opens_an_accdb_access_parser_cannot(tiny_accdb):
    _skip_unless_available("access_parser")
    with pytest.raises(AccessReadError, match="Try backend='mdbtools'"):
        AccessReader(tiny_accdb, backend="access_parser")
    _skip_unless_available("mdbtools")
    assert sorted(AccessReader(tiny_accdb)) == ["Categories", "Items", "Numbers"]


def test_mdbtools_error_says_what_went_wrong(tmp_path):
    _skip_unless_available("mdbtools")
    not_access = tmp_path / "not_access.mdb"
    not_access.write_bytes(b"definitely not a Jet database" * 100)
    with pytest.raises(AccessReadError, match="mdb-ver could not read"):
        AccessReader(not_access, backend="mdbtools")
    with pytest.raises(FileNotFoundError):
        AccessReader(tmp_path / "missing.mdb")
