"""Ingest Nigerian grid load data.

Primary source: Hugging Face electricsheepafrica/nigerian_energy_and_utilities_grid_load
Fallback: synthetic_fallback.generate_grid_load()

Raw schema preserves the source's original column names. Renaming to
snake_case happens in dbt staging models (Day 2).
"""
from __future__ import annotations

from grid_intelligence.db import write_df
from grid_intelligence.ingestion import synthetic_fallback
from grid_intelligence.utils.logging import get_logger

log = get_logger(__name__)

HF_DATASET = "electricsheepafrica/nigerian_energy_and_utilities_grid_load"


def _try_huggingface():
    try:
        from datasets import load_dataset

        ds = load_dataset(HF_DATASET, split="train")
        df = ds.to_pandas()
        log.info("ingest_grid_load: source=huggingface rows=%d", len(df))
        return df
    except Exception as exc:  # noqa: BLE001
        log.warning("ingest_grid_load: huggingface unavailable (%s)", exc)
        return None


def run() -> int:
    df = _try_huggingface()
    if df is None:
        log.info("ingest_grid_load: fallback=synthetic")
        df = synthetic_fallback.generate_grid_load()

    rows = write_df(df, "raw", "grid_load")
    log.info("ingest_grid_load: wrote %d rows to raw.grid_load", rows)
    return rows


if __name__ == "__main__":
    run()