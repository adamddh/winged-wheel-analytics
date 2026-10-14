import duckdb
import pytest

from wings.warehouse.build import SQL_DIR


@pytest.fixture
def con():
    """In-memory DuckDB with the warehouse macros loaded."""
    c = duckdb.connect()
    for schema in ("bronze", "silver", "gold", "meta"):
        c.execute(f"create schema {schema}")
    c.execute((SQL_DIR / "macros.sql").read_text())
    yield c
    c.close()
