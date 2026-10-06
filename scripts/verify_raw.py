"""Verify all raw schema tables exist with expected row counts."""
from grid_intelligence.db import read_df

TABLES = [
    "grid_load",
    "demand_forecast",
    "smart_grid_iot",
    "outage_logs",
    "ai_optimization",
    "pvgis",
    "owid",
    "dre_atlas",
]

sql = " UNION ALL ".join(
    f"SELECT '{t}' AS tbl, COUNT(*) AS rows FROM raw.{t}" for t in TABLES
)
df = read_df(sql)
print(df.to_string(index=False))
