"""Ingest Nigerian outage and fault logs.

Primary source: Hugging Face electricsheepafrica/nigerian_energy_and_utilities_outage_fault_logs
Fallback: synthetic_fallback.generate_outage_logs()
"""
from __future__ import annotations

from grid_intelligence.db import write_df
from grid_intelligence.ingestion import synthetic_fallback
from grid_intelligence.utils.logging import get_logger

log = get_logger(__name__)

HF_DATASET = "electricsheepafrica/nigerian_energy_and_utilities_outage_fault_logs"


def _try_huggingface():
    try:
        from datasets import load_dataset

        ds = load_dataset(HF_DATASET, split="train")
        df = ds.to_pandas()
        log.info("ingest_outage_logs: source=huggingface rows=%d", len(df))
        return df
    except Exception as exc:  # noqa: BLE001
        log.warning("ingest_outage_logs: huggingface unavailable (%s)", exc)
        return None


def run() -> int:
    df = _try_huggingface()
    if df is None:
        log.info("ingest_outage_logs: fallback=synthetic")
        df = synthetic_fallback.generate_outage_logs()

    rows = write_df(df, "raw", "outage_logs")
    log.info("ingest_outage_logs: wrote %d rows to raw.outage_logs", rows)
    return rows


if __name__ == "__main__":
    run()