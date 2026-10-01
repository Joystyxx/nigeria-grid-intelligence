"""Inspect values behind the 4 failing dbt tests."""
from grid_intelligence.db import read_df

print("=== 1. Distinct disco values in dim_substation ===")
df = read_df("SELECT disco, COUNT(*) AS n FROM dbt_dev_marts.dim_substation GROUP BY 1 ORDER BY 1")
print(df.to_string(index=False))

print("\n=== 2. Duplicated substation_ids in dim_substation ===")
df = read_df("""
    SELECT substation_id, COUNT(*) AS n
    FROM dbt_dev_marts.dim_substation
    GROUP BY 1 HAVING COUNT(*) > 1
    ORDER BY n DESC LIMIT 10
""")
print(df.to_string(index=False))

print("\n=== 3. Sample of a duplicated substation_id ===")
df = read_df("""
    SELECT * FROM dbt_dev_marts.dim_substation
    WHERE substation_id IN (
        SELECT substation_id FROM dbt_dev_marts.dim_substation
        GROUP BY 1 HAVING COUNT(*) > 1 LIMIT 1
    )
""")
print(df.to_string(index=False))

print("\n=== 4. Duplicated event_keys in fct_grid_events ===")
df = read_df("""
    SELECT event_ts, substation_id, COUNT(*) AS n
    FROM dbt_dev_marts.fct_grid_events
    GROUP BY 1, 2 HAVING COUNT(*) > 1
    ORDER BY n DESC LIMIT 5
""")
print(df.to_string(index=False))