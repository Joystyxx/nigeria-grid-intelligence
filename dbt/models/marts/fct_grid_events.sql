{{ config(materialized='table') }}

-- One row per substation-hour grid event. Joins load, sensor health,
-- and outage signals into a single ML-ready feature table.

with stability as (
    select * from {{ ref('int_grid_stability') }}
),

sensor as (
    select
        day_ts,
        substation_id,
        total_anomalies,
        anomaly_pct
    from {{ ref('int_sensor_health') }}
),

joined as (
    select
        {{ dbt_utils.generate_surrogate_key(['s.substation_id', 's.hour_ts']) }} as event_key,
        s.hour_ts                               as event_ts,
        s.disco,
        s.substation_id,

        -- Load features
        s.avg_load_mw,
        s.peak_load_mw,
        s.avg_forecast_mw,
        (s.avg_load_mw - s.avg_forecast_mw)     as forecast_error_mw,
        s.load_avg_6h,
        s.load_std_6h,
        s.load_avg_24h,
        s.load_std_24h,

        -- Frequency / sensor
        s.avg_frequency_hz,
        s.avg_freq_dev_hz,
        s.avg_temp_c,
        s.avg_humidity,
        coalesce(se.total_anomalies, 0)         as sensor_anomalies,
        coalesce(se.anomaly_pct, 0)             as sensor_anomaly_pct,

        -- Outage flags
        s.outage_count_this_hour,
        s.outage_minutes_this_hour,
        s.customers_affected_this_hour,
        case when s.outage_count_this_hour > 0 then 1 else 0 end as had_outage
    from stability s
    left join sensor se
        on s.substation_id = se.substation_id
        and date_trunc('day', s.hour_ts) = se.day_ts
)

select * from joined