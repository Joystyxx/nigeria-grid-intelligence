"""Ingest Nigerian demand forecast data.

Primary source: Hugging Face electricsheepafrica/nigerian-energy-utilities-demand-forecasting
Fallback: synthetic_fallback.generate_demand_forecast()
"""
from __future__ import annotations

from grid_intelligence.db import write_df
from grid_intelligence.ingestion import synthetic_fallback
from grid_intelligence.utils.logging import get_logger

log = get_logger(__name__)

HF_DATASET = "electricsheepafrica/nigerian_energy_and_utilities_demand_forecasting"


def _try_huggingface():
    try:
        from datasets import load_dataset

        ds = load_dataset(HF_DATASET, split="train")
        df = ds.to_pandas()
        log.info("ingest_demand_forecast: source=huggingface rows=%d", len(df))
        return df
    except Exception as exc:  # noqa: BLE001
        log.warning("ingest_demand_forecast: huggingface unavailable (%s)", exc)
        return None


def run() -> int:
    df = _try_huggingface()
    if df is None:
        log.info("ingest_demand_forecast: fallback=synthetic")
        df = synthetic_fallback.generate_demand_forecast()

    rows = write_df(df, "raw", "demand_forecast")
    log.info("ingest_demand_forecast: wrote %d rows to raw.demand_forecast", rows)
    return rows


if __name__ == "__main__":
    run()
