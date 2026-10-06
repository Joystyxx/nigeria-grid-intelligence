"""Ingest solar irradiation data from the EU JRC PVGIS API.

Primary source: PVGIS API (free, no key)
Docs: https://re.jrc.ec.europa.eu/pvg_tools/en/

Fetches monthly solar radiation for three Nigerian cities:
Lagos, Abuja, Kano. Fallback: per-city synthetic placeholder.
"""
from __future__ import annotations

import time

import pandas as pd
import requests

from grid_intelligence.db import write_df
from grid_intelligence.utils.logging import get_logger

log = get_logger(__name__)

PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_2/PVcalc"

CITIES = {
    "Lagos": {"lat": 6.5244, "lon": 3.3792},
    "Abuja": {"lat": 9.0765, "lon": 7.3986},
    "Kano": {"lat": 12.0022, "lon": 8.5920},
}


def _fetch_city(city: str, lat: float, lon: float) -> pd.DataFrame:
    """Fetch monthly PV output for one city from PVGIS with 3 retries."""
    params: dict[str, str | int | float] = {
        "lat": lat,
        "lon": lon,
        "peakpower": 1.0,
        "loss": 14,
        "outputformat": "json",
        "mountingplace": "free",
        "angle": 15,
        "aspect": 0,
    }
    last_exc = None
    r = None
    for attempt in range(3):
        try:
            r = requests.get(PVGIS_URL, params=params, timeout=30)
            r.raise_for_status()
            break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            log.warning(
                "ingest_pvgis: %s attempt %d failed (%s)",
                city,
                attempt + 1,
                exc,
            )
            time.sleep(2)
    if r is None:
        assert last_exc is not None
        raise last_exc  # all 3 attempts failed

    data = r.json()
    monthly = data["outputs"]["monthly"]["fixed"]
    df = pd.DataFrame(monthly)
    df["city"] = city
    df["lat"] = lat
    df["lon"] = lon
    df["source"] = "pvgis"
    return df


def _synthetic_city(city: str, lat: float, lon: float) -> pd.DataFrame:
    """Per-city synthetic fallback with Nigerian solar profile."""
    months = list(range(1, 13))
    rows = []
    base = 5.5 if city == "Kano" else 4.8 if city == "Abuja" else 4.3
    for m in months:
        ghi = base + (0.4 if m in [1, 2, 3, 11, 12] else -0.3)
        rows.append({
            "month": m,
            "city": city,
            "lat": lat,
            "lon": lon,
            "E_m": round(ghi * 30, 2),
            "H_m": round(ghi * 30 / 24, 3),
            "source": "synthetic",
        })
    return pd.DataFrame(rows)


def run() -> int:
    frames = []
    for city, coords in CITIES.items():
        try:
            log.info("ingest_pvgis: fetching %s", city)
            frames.append(_fetch_city(city, coords["lat"], coords["lon"]))
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "ingest_pvgis: %s failed after retries (%s), using synthetic for this city",
                city,
                exc,
            )
            frames.append(_synthetic_city(city, coords["lat"], coords["lon"]))

    df = pd.concat(frames, ignore_index=True)
    sources = df["source"].unique().tolist()
    log.info("ingest_pvgis: sources=%s rows=%d", sources, len(df))

    rows = write_df(df, "raw", "pvgis")
    log.info("ingest_pvgis: wrote %d rows to raw.pvgis", rows)
    return rows


if __name__ == "__main__":
    run()