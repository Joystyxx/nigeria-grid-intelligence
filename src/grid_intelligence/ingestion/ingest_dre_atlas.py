"""Ingest DRE Atlas settlement-level data for Nigeria.

Primary source: VIDA / World Bank DRE Atlas via source.coop
Direct GeoParquet: https://data.source.coop/vida/dre-atlas/by_country/country_iso=NGA/NGA.parquet
License: CC-BY-4.0
Publisher: VIDA for ESMAP / World Bank / IFC

Contains 154,319 Nigerian settlements with 50+ planning attributes:
population, grid distance, road access, solar potential, wealth, etc.

Fallback: synthetic settlement generator (12 states x 40 settlements).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import requests

from grid_intelligence.db import write_df
from grid_intelligence.utils.logging import get_logger

log = get_logger(__name__)

DRE_ATLAS_URL = (
    "https://data.source.coop/vida/dre-atlas/"
    "by_country/country_iso=NGA/NGA.parquet"
)

STATES = [
    ("Lagos", 6.5244, 3.3792, 0.85),
    ("Kano", 12.0022, 8.5920, 0.90),
    ("Kaduna", 10.5222, 7.4383, 0.82),
    ("Katsina", 12.9908, 7.6018, 0.88),
    ("Oyo", 7.8500, 3.9333, 0.78),
    ("Rivers", 4.8156, 7.0498, 0.72),
    ("Borno", 11.8333, 13.1500, 0.70),
    ("Anambra", 6.2109, 6.9372, 0.75),
    ("Delta", 5.8904, 5.6790, 0.68),
    ("Niger", 9.6139, 6.5473, 0.65),
    ("Bauchi", 10.3142, 9.8442, 0.72),
    ("Sokoto", 13.0059, 5.2476, 0.80),
]


def _try_dre_atlas() -> pd.DataFrame | None:
    """Download the Nigeria GeoParquet from source.coop.

    source.coop serves S3-backed files without User-Agent blocking,
    unlike energydata.info which returns 403 for programmatic clients.
    """
    try:
        log.info("ingest_dre_atlas: downloading GeoParquet from source.coop")
        r = requests.get(DRE_ATLAS_URL, timeout=180, stream=True)
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        log.info("ingest_dre_atlas: file size %.1f MB", total / 1e6)

        # Stream to temp file to avoid loading 100+ MB into memory twice
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                tmp.write(chunk)
            tmp_path = Path(tmp.name)

        df = pd.read_parquet(tmp_path)
        tmp_path.unlink()  # cleanup

        # Drop columns that Postgres can't store directly
        # geometry: WKB binary; bbox: nested dict
        for col in ["geometry", "bbox"]:
            if col in df.columns:
                df = df.drop(columns=[col])

        # Safety net: stringify any remaining dict/list columns
        for col in df.columns:
            if df[col].apply(lambda x: isinstance(x, (dict, list))).any():
                log.warning("ingest_dre_atlas: stringifying dict/list column %s", col)
                df[col] = df[col].astype(str)

        df["source"] = "dre_atlas"

        log.info("ingest_dre_atlas: source=dre_atlas rows=%d", len(df))
        return df
    except Exception as exc:  # noqa: BLE001
        log.warning("ingest_dre_atlas: source.coop failed (%s)", exc)
        return None


def _synthetic_settlements(n_per_state: int = 40) -> pd.DataFrame:
    """Generate realistic Nigerian settlement records (fallback only)."""
    rng = np.random.default_rng(42)
    rows = []
    for state, lat0, lon0, electrification in STATES:
        for i in range(n_per_state):
            lat = lat0 + rng.normal(0, 0.6)
            lon = lon0 + rng.normal(0, 0.6)
            population = int(np.clip(rng.lognormal(7.5, 1.1), 200, 50000))
            grid_dist_km = max(0.5, rng.exponential(scale=25 * (1 - electrification) + 5))
            road_access = bool(rng.random() < 0.55 + 0.3 * electrification)
            has_diesel = bool(rng.random() < 0.25)
            diesel_capacity_kw = float(rng.uniform(20, 500)) if has_diesel else 0.0

            rows.append({
                "settlement_id": f"{state[:3].upper()}-{i:04d}",
                "settlement_name": f"{state} Settlement {i+1}",
                "state": state,
                "latitude": round(lat, 5),
                "longitude": round(lon, 5),
                "population": population,
                "households": int(population / 4.5),
                "distance_to_grid_km": round(grid_dist_km, 2),
                "road_access": road_access,
                "has_diesel": has_diesel,
                "diesel_capacity_kw": round(diesel_capacity_kw, 1),
                "source": "synthetic",
            })
    return pd.DataFrame(rows)


def run() -> int:
    df = _try_dre_atlas()
    if df is None:
        log.info("ingest_dre_atlas: fallback=synthetic")
        df = _synthetic_settlements()
        log.info("ingest_dre_atlas: source=synthetic rows=%d", len(df))

    rows = write_df(df, "raw", "dre_atlas")
    log.info("ingest_dre_atlas: wrote %d rows to raw.dre_atlas", rows)
    return rows


if __name__ == "__main__":
    run()