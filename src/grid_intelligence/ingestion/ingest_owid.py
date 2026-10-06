"""Ingest Our World in Data energy dataset, filtered to Nigeria.

Primary source: OWID energy CSV (https://ourworldindata.org/energy)
Fallback: synthetic placeholder (minimal, Nigeria context only).
"""
from __future__ import annotations

import io

import pandas as pd
import requests

from grid_intelligence.db import write_df
from grid_intelligence.utils.logging import get_logger

log = get_logger(__name__)

OWID_URL = "https://raw.githubusercontent.com/owid/energy-data/master/owid-energy-data.csv"


def _try_owid() -> pd.DataFrame | None:
    try:
        log.info("ingest_owid: downloading OWID energy CSV")
        r = requests.get(OWID_URL, timeout=60)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        ng = df[df["country"] == "Nigeria"].copy()
        if ng.empty:
            log.warning("ingest_owid: Nigeria not found in OWID dataset")
            return None
        log.info("ingest_owid: source=owid rows=%d", len(ng))
        return ng
    except Exception as exc:  # noqa: BLE001
        log.warning("ingest_owid: OWID unavailable (%s)", exc)
        return None


def _synthetic() -> pd.DataFrame:
    """Minimal Nigeria energy context — only if OWID fully fails."""
    log.warning("ingest_owid: using synthetic placeholder")
    years = list(range(2000, 2024))
    rows = []
    for y in years:
        rows.append({
            "country": "Nigeria",
            "year": y,
            "primary_energy_consumption": 4.5 + (y - 2000) * 0.05,
            "electricity_generation": 25.0 + (y - 2000) * 0.4,
            "solar_consumption": 0.01 + (y - 2015) * 0.02 if y >= 2015 else 0.0,
            "gas_electricity": 20.0 + (y - 2000) * 0.25,
            "hydro_electricity": 5.0 + (y - 2000) * 0.05,
        })
    return pd.DataFrame(rows)


def run() -> int:
    df = _try_owid()
    if df is None:
        df = _synthetic()
        log.info("ingest_owid: source=synthetic rows=%d", len(df))

    rows = write_df(df, "raw", "owid")
    log.info("ingest_owid: wrote %d rows to raw.owid", rows)
    return rows


if __name__ == "__main__":
    run()
