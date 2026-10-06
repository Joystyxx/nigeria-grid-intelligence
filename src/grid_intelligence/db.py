"""Database helpers shared across the project.

Exposes a SQLAlchemy engine and a helper to write DataFrames
into the raw schema idempotently.
"""
from __future__ import annotations

from collections.abc import Iterable

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from grid_intelligence.config import DATABASE_URL

_engine: Engine | None = None


def get_engine() -> Engine:
    """Return a singleton SQLAlchemy engine for the project database."""
    global _engine
    if _engine is None:
        _engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
    return _engine


def write_df(
    df: pd.DataFrame,
    schema: str,
    table: str,
    if_exists: str = "replace",
) -> int:
    """Write a DataFrame to <schema>.<table> and return the row count.

    if_exists='replace' makes ingestion idempotent: re-running the same
    script overwrites the table rather than appending duplicates.
    """
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    df.to_sql(table, engine, schema=schema, if_exists=if_exists, index=False)
    return len(df)


def read_df(query: str, params: dict | None = None) -> pd.DataFrame:
    """Run a SQL query and return the result as a DataFrame."""
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(query), conn, params=params or {})


def table_exists(schema: str, table: str) -> bool:
    """Check if a table exists in the given schema."""
    engine = get_engine()
    sql = text(
        "SELECT EXISTS ("
        "  SELECT 1 FROM information_schema.tables "
        "  WHERE table_schema = :schema AND table_name = :table"
        ")"
    )
    with engine.connect() as conn:
        return bool(conn.execute(sql, {"schema": schema, "table": table}).scalar())


def list_tables(schema: str) -> Iterable[str]:
    """List table names in a schema."""
    engine = get_engine()
    sql = text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = :schema ORDER BY table_name"
    )
    with engine.connect() as conn:
        return [row[0] for row in conn.execute(sql, {"schema": schema})]
