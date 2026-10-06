"""Diagnose why outage_within_6h has such a high positive rate."""
from grid_intelligence.db import read_df

print("=== 1. Total outage events ===")
print(read_df("SELECT COUNT(*) AS n FROM raw.outage_logs").to_string(index=False))

print("\n=== 2. Outages per substation (top 10) ===")
print(read_df("""
    SELECT split_part(feeder_id, '-FD', 1) AS substation_id,
           COUNT(*) AS outage_events,
           AVG(duration_min) AS avg_duration_min,
           AVG(customers_affected) AS avg_customers
    FROM raw.outage_logs
    GROUP BY 1 ORDER BY outage_events DESC LIMIT 10
""").to_string(index=False))

print("\n=== 3. Distribution of outage durations ===")
print(read_df("""
    SELECT
      CASE
        WHEN duration_min < 30 THEN '<30min'
        WHEN duration_min < 60 THEN '30-60min'
        WHEN duration_min < 240 THEN '1-4h'
        WHEN duration_min < 720 THEN '4-12h'
        ELSE '12h+'
      END AS bucket,
      COUNT(*) AS n
    FROM raw.outage_logs GROUP BY 1 ORDER BY 1
""").to_string(index=False))

print("\n=== 4. fct_grid_events: had_outage distribution ===")
print(read_df("""
    SELECT had_outage, COUNT(*) AS n
    FROM dbt_dev_marts.fct_grid_events
    GROUP BY 1 ORDER BY 1
""").to_string(index=False))

print("\n=== 5. fct_grid_events: outage_count_this_hour distribution ===")
print(read_df("""
    SELECT outage_count_this_hour, COUNT(*) AS n
    FROM dbt_dev_marts.fct_grid_events
    GROUP BY 1 ORDER BY 1 LIMIT 20
""").to_string(index=False))

print("\n=== 6. Unique substation-hours in fct_grid_events ===")
print(read_df("""
    SELECT COUNT(*) AS total_rows,
           COUNT(DISTINCT (substation_id, event_ts)) AS unique_substation_hours,
           COUNT(DISTINCT substation_id) AS num_substations
    FROM dbt_dev_marts.fct_grid_events
""").to_string(index=False))

print("\n=== 7. Outages with severity filter (customers > 500) ===")
print(read_df("""
    SELECT
      COUNT(*) FILTER (WHERE customers_affected > 500) AS major_outages,
      COUNT(*) FILTER (WHERE customers_affected <= 500) AS minor_outages,
      COUNT(*) AS total
    FROM raw.outage_logs
""").to_string(index=False))
