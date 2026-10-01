{{ config(materialized='view') }}

-- Aggregate IoT telemetry by substation, day, and metric.
-- The raw data is long-format (metric name + value), so we pivot
-- into per-substation daily summaries.

with base as (
    select
        reading_ts,
        date_trunc('day', reading_ts)   as day_ts,
        disco,
        substation_id,
        device_id,
        device_type,
        metric,
        metric_value,
        unit,
        device_status
    from {{ ref('stg_smart_grid_iot') }}
),

-- Flag anomalous readings
flagged as (
    select
        *,
        case
            when metric ilike '%frequency%' and (metric_value < 49.5 or metric_value > 50.5) then 1
            when metric ilike '%voltage%'   and metric_value <= 0 then 1
            when device_status is not null and device_status ilike '%error%' then 1
            when device_status is not null and device_status ilike '%fail%' then 1
            else 0
        end as is_anomaly
    from base
),

-- Daily per-substation-per-metric summary
daily_metric as (
    select
        day_ts,
        disco,
        substation_id,
        metric,
        count(*)                as num_readings,
        avg(metric_value)       as avg_value,
        min(metric_value)       as min_value,
        max(metric_value)       as max_value,
        stddev(metric_value)    as stddev_value,
        sum(is_anomaly)         as anomaly_count
    from flagged
    group by 1, 2, 3, 4
),

-- Daily per-substation rollup (across all metrics)
daily_substation as (
    select
        day_ts,
        disco,
        substation_id,
        sum(num_readings)                                       as total_readings,
        sum(anomaly_count)                                      as total_anomalies,
        sum(anomaly_count)::numeric / nullif(sum(num_readings), 0) * 100 as anomaly_pct,
        count(distinct metric)                                  as num_metrics
    from daily_metric
    group by 1, 2, 3
),

-- Distinct device count per substation per day (separate aggregation)
device_counts as (
    select
        day_ts,
        substation_id,
        count(distinct device_id)   as num_devices
    from base
    group by 1, 2
)

select
    s.day_ts,
    s.disco,
    s.substation_id,
    s.num_metrics,
    coalesce(d.num_devices, 0)      as num_devices,
    s.total_readings,
    s.total_anomalies,
    s.anomaly_pct
from daily_substation s
left join device_counts d
    on s.day_ts = d.day_ts
    and s.substation_id = d.substation_id