"""Ingest Nigerian smart-grid IoT telemetry.

Primary source: Hugging Face electricsheepafrica/nigerian-energy-utilities-smart-grid-iot
Fallback: synthetic_fallback.generate_smart_grid_iot()
"""
from __future__ import annotations

from grid_intelligence.db import write_df
from grid_intelligence.ingestion import synthetic_fallback
from grid_intelligence.utils.logging import get_logger

log = get_logger(__name__)

HF_DATASET = "electricsheepafrica/nigerian_energy_and_utilities_smart_grid_iot"


def _try_huggingface():
    try:
        from datasets import load_dataset

        ds = load_dataset(HF_DATASET, split="train")
        df = ds.to_pandas()
        log.info("ingest_smart_grid_iot: source=huggingface rows=%d", len(df))
        return df
    except Exception as exc:  # noqa: BLE001
        log.warning("ingest_smart_grid_iot: huggingface unavailable (%s)", exc)
        return None


def run() -> int:
    df = _try_huggingface()
    if df is None:
        log.info("ingest_smart_grid_iot: fallback=synthetic")
        df = synthetic_fallback.generate_smart_grid_iot()

    rows = write_df(df, "raw", "smart_grid_iot")
    log.info("ingest_smart_grid_iot: wrote %d rows to raw.smart_grid_iot", rows)
    return rows


if __name__ == "__main__":
    run()