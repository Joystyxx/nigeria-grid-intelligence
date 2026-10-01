"""Export viable Nigerian settlements as GeoJSON — two files.

Light file (for dashboard): top N settlements per state, ~500 KB
Full file (for download):   all A+B tier settlements, ~15-25 MB

Both use the same FeatureCollection schema, so any tool that reads
one can read the other. Light file optimized for browser/Leaflet;
full file optimized for QGIS, Mapbox, or offline analysis.
"""
from __future__ import annotations

import json
from pathlib import Path

from grid_intelligence.config import PROJECT_ROOT
from grid_intelligence.db import read_df
from grid_intelligence.utils.logging import get_logger

log = get_logger(__name__)

DOCS_DIR = PROJECT_ROOT / "docs"
LIGHT_PATH = DOCS_DIR / "minigrid_viability_top50.geojson"
FULL_PATH = DOCS_DIR / "minigrid_viability_full.geojson"

TOP_PER_STATE = 50


def fetch_settlements(top_per_state: int | None) -> list[dict]:
    """Fetch viable settlements; optionally cap per state via row_number()."""
    cap_clause = ""
    if top_per_state is not None:
        cap_clause = f"WHERE rank_in_state <= {top_per_state}"

    sql = f"""
        WITH ranked AS (
            SELECT
                settlement_id,
                settlement_name,
                state,
                lga,
                latitude,
                longitude,
                population,
                num_buildings,
                dist_transmission_km,
                solar_pv_value,
                wealth_index,
                viability_score,
                viability_tier,
                row_number() OVER (
                    PARTITION BY state
                    ORDER BY viability_score DESC, settlement_id
                ) as rank_in_state
            FROM dbt_dev_marts.fct_minigrid_viability
            WHERE viability_tier IN ('A_highly_viable', 'B_viable')
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
        )
        SELECT * FROM ranked
        {cap_clause}
        ORDER BY state, rank_in_state
    """
    df = read_df(sql)
    log.info("geo: fetched %d settlements (cap=%s)", len(df), top_per_state)
    return df.to_dict(orient="records")


def to_geojson(rows: list[dict], description: str) -> dict:
    """Convert settlement rows to a GeoJSON FeatureCollection."""
    features = []
    for r in rows:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(r["longitude"]), float(r["latitude"])],
            },
            "properties": {
                "settlement_id": r["settlement_id"],
                "name": r["settlement_name"],
                "state": r["state"],
                "lga": r["lga"],
                "population": int(r["population"]) if r["population"] else None,
                "num_buildings": int(r["num_buildings"]) if r["num_buildings"] else None,
                "dist_transmission_km": float(r["dist_transmission_km"]) if r["dist_transmission_km"] else None,
                "solar_pv_value": float(r["solar_pv_value"]) if r["solar_pv_value"] else None,
                "wealth_index": float(r["wealth_index"]) if r["wealth_index"] else None,
                "viability_score": float(r["viability_score"]),
                "viability_tier": r["viability_tier"],
                "rank_in_state": int(r["rank_in_state"]),
            },
        })

    return {
        "type": "FeatureCollection",
        "metadata": {
            "source": "Nigeria Grid & Mini-Grid Intelligence Platform",
            "description": description,
            "total_features": len(features),
        },
        "features": features,
    }


def write_geojson(path: Path, features: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(features, separators=(",", ":")))
    size_mb = path.stat().st_size / (1024 * 1024)
    log.info("geo: wrote %d features to %s (%.2f MB)", len(features["features"]), path.name, size_mb)


def run() -> None:
    # Light file — for dashboard
    log.info("geo: building light file (top %d per state)", TOP_PER_STATE)
    light_rows = fetch_settlements(TOP_PER_STATE)
    light_gj = to_geojson(light_rows, f"Top {TOP_PER_STATE} viable settlements per state")
    write_geojson(LIGHT_PATH, light_gj)

    # Full file — for download
    log.info("geo: building full file (all A+B tier)")
    full_rows = fetch_settlements(None)
    full_gj = to_geojson(full_rows, "All A+B tier viable settlements")
    write_geojson(FULL_PATH, full_gj)


if __name__ == "__main__":
    run()

    import collections

    print("\n=== Output files ===")
    for p in [LIGHT_PATH, FULL_PATH]:
        if p.exists():
            size_mb = p.stat().st_size / (1024 * 1024)
            print(f"  {p.name:45s} {size_mb:>8.2f} MB")

    print("\n=== Light file — top 10 states ===")
    gj = json.loads(LIGHT_PATH.read_text())
    states = collections.Counter(f["properties"]["state"] for f in gj["features"])
    for state, n in states.most_common(10):
        print(f"  {state:20s} {n}")

    print("\n=== Full file — top 10 states by viable settlement count ===")
    gj = json.loads(FULL_PATH.read_text())
    states = collections.Counter(f["properties"]["state"] for f in gj["features"])
    for state, n in states.most_common(10):
        print(f"  {state:20s} {n}")