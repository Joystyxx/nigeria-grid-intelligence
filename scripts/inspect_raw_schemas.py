"""Print column names and types for the remaining raw tables."""
from grid_intelligence.db import read_df

TABLES = ["ai_optimization", "pvgis", "owid", "dre_atlas"]

for t in TABLES:
    print(f"\n=== raw.{t} ===")
    df = read_df(
        "SELECT column_name, data_type FROM information_schema.columns "
        f"WHERE table_schema='raw' AND table_name='{t}' "
        "ORDER BY ordinal_position"
    )
    print(df.to_string(index=False))
