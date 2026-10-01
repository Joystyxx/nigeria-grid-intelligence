"""Verify grid_load and demand_forecast are distinct datasets."""
from grid_intelligence.db import read_df

print("=== COLUMNS ===")
for t in ["grid_load", "demand_forecast"]:
    cols = read_df(
        f"SELECT column_name, data_type FROM information_schema.columns "
        f"WHERE table_schema='raw' AND table_name='{t}' ORDER BY ordinal_position"
    )
    print(f"\n{t}:")
    print(cols.to_string(index=False))

print("\n=== SAMPLE ROWS (first 3 of each) ===")
for t in ["grid_load", "demand_forecast"]:
    print(f"\n{t}:")
    df = read_df(f"SELECT * FROM raw.{t} LIMIT 3")
    print(df.to_string(index=False))