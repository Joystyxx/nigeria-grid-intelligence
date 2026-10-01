"""Ingest Nigerian AI grid optimisation runs.

Primary source: Hugging Face electricsheepafrica/nigerian_energy_and_utilities_ai_grid_optimization
Fallback: synthetic_fallback.generate_ai_optimization()
"""
from __future__ import annotations

from grid_intelligence.db import write_df
from grid_intelligence.ingestion import synthetic_fallback
from grid_intelligence.utils.logging import get_logger

log = get_logger(__name__)

HF_DATASET = "electricsheepafrica/nigerian_energy_and_utilities_ai_grid_optimization"


def _try_huggingface():
    try:
        from datasets import load_dataset

        ds = load_dataset(HF_DATASET, split="train")
        df = ds.to_pandas()
        log.info("ingest_ai_optimization: source=huggingface rows=%d", len(df))
        return df
    except Exception as exc:  # noqa: BLE001
        log.warning("ingest_ai_optimization: huggingface unavailable (%s)", exc)
        return None


def run() -> int:
    df = _try_huggingface()
    if df is None:
        log.info("ingest_ai_optimization: fallback=synthetic")
        df = synthetic_fallback.generate_ai_optimization()

    rows = write_df(df, "raw", "ai_optimization")
    log.info("ingest_ai_optimization: wrote %d rows to raw.ai_optimization", rows)
    return rows


if __name__ == "__main__":
    run()