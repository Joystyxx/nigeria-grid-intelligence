"""Tests for the ingestion layer.

Verifies that every raw table exists and has the expected row count.
These run against the live Docker Postgres — start it with
`docker compose up -d postgres` before running pytest.
"""
import pytest

from grid_intelligence.db import list_tables, read_df

pytestmark = pytest.mark.requires_db

EXPECTED_TABLES = {
    "grid_load": 200_000,
    "demand_forecast": 200_000,
    "smart_grid_iot": 250_000,
    "outage_logs": 60_000,
    "ai_optimization": 80_000,
    "pvgis": 36,
    "owid": 126,
    "dre_atlas": 154_319,
}


def test_raw_schema_contains_expected_tables():
    tables = set(list_tables("raw"))
    missing = set(EXPECTED_TABLES.keys()) - tables
    assert not missing, f"Missing raw tables: {missing}"


@pytest.mark.parametrize("table,expected_rows", EXPECTED_TABLES.items())
def test_raw_table_row_count(table, expected_rows):
    df = read_df(f"SELECT COUNT(*) AS n FROM raw.{table}")
    actual = int(df["n"].iloc[0])
    assert actual == expected_rows, (
        f"raw.{table} has {actual} rows, expected {expected_rows}"
    )
