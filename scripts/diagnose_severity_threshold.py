"""Test positive rate for outage_within_6h at different severity thresholds.

Optimised: pre-aggregate outages to (substation, hour) grain first, then
compute forward-looking 6h target using a LEAD-based window function.
"""
from grid_intelligence.db import read_df

# Pre-aggregate once — this is the expensive part, do it a single time.
print("Pre-aggregating outages at substation-hour grain...")
agg = read_df("""
    SELECT
        split_part(feeder_id, '-FD', 1)         AS substation_id,
        date_trunc('hour', start_time::timestamp) AS hour_ts,
        MAX(customers_affected)                 AS max_customers,
        MAX(duration_min)                       AS max_duration
    FROM raw.outage_logs
    GROUP BY 1, 2
""")
print(f"Aggregated outage rows: {len(agg)}")

print("\nLoading grid events...")
events = read_df("""
    SELECT DISTINCT substation_id, event_ts::timestamp AS hour_ts
    FROM dbt_dev_marts.fct_grid_events
""")
print(f"Grid event rows: {len(events)}")


# Merge events with outage info (left join on substation + hour)
merged = events.merge(agg, on=["substation_id", "hour_ts"], how="left")
merged = merged.sort_values(["substation_id", "hour_ts"]).reset_index(drop=True)

# Forward-looking 6h window: for each row, is there any outage in the next 6 hours?
# We use a rolling max on the shifted series (shift -1 to look forward).
def forward_6h_flag(series):
    s = series.fillna(False).astype(int)
    # reverse look: shift so we look at next 6 rows
    return s.shift(-1).rolling(6, min_periods=1).max().fillna(0).astype(int)

print("\n=== Target rate by customer-affected threshold ===")
for label, mask in [
    ("any outage", merged["max_customers"].notna()),
    ("customers > 500", merged["max_customers"].fillna(0) > 500),
    ("customers > 1000", merged["max_customers"].fillna(0) > 1000),
    ("customers > 2000", merged["max_customers"].fillna(0) > 2000),
    ("customers > 5000", merged["max_customers"].fillna(0) > 5000),
]:
    flagged = merged.assign(signal=mask)
    flagged["target"] = flagged.groupby("substation_id")["signal"].transform(forward_6h_flag)
    rate = flagged["target"].mean() * 100
    n_pos = int(flagged["target"].sum())
    print(f"  {label:25s}  positives={n_pos:>7d}  rate={rate:>6.2f}%")

print("\n=== Target rate by duration threshold ===")
for label, mask in [
    ("duration > 60 min", merged["max_duration"].fillna(0) > 60),
    ("duration > 120 min", merged["max_duration"].fillna(0) > 120),
    ("duration > 240 min", merged["max_duration"].fillna(0) > 240),
]:
    flagged = merged.assign(signal=mask)
    flagged["target"] = flagged.groupby("substation_id")["signal"].transform(forward_6h_flag)
    rate = flagged["target"].mean() * 100
    n_pos = int(flagged["target"].sum())
    print(f"  {label:25s}  positives={n_pos:>7d}  rate={rate:>6.2f}%")
