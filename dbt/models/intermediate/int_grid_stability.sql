{{ config(materialized='view') }}

-- Join grid load with outages by substation and 6-hour window.
-- Outages are aggregated to substation-hour grain BEFORE joining,
-- so multiple feeders under one substation don't fan out rows.

with load_base as (
    select
        reading_ts,
        disco,
        substation_id,
        load_mw,
        forecast_mw,
        (load_mw - forecast_mw)             as forecast_error_mw,
        frequency_hz,
        abs(frequency_hz - 50.0)            as frequency_deviation_hz,
        temp_c,
        humidity
    from {{ ref('stg_grid_load') }}
),

hourly as (
    select
        date_trunc('hour', reading_ts)      as hour_ts,
        disco,
        substation_id,
        avg(load_mw)                        as avg_load_mw,
        max(load_mw)                        as peak_load_mw,
        avg(forecast_mw)                    as avg_forecast_mw,
        avg(frequency_hz)                   as avg_frequency_hz,
        avg(frequency_deviation_hz)         as avg_freq_dev_hz,
        avg(temp_c)                         as avg_temp_c,
        avg(humidity)                       as avg_humidity
    from load_base
    group by 1, 2, 3
),

with_rolling as (
    select
        *,
        avg(avg_load_mw) over w6           as load_avg_6h,
        stddev(avg_load_mw) over w6        as load_std_6h,
        avg(avg_load_mw) over w24          as load_avg_24h,
        stddev(avg_load_mw) over w24       as load_std_24h
    from hourly
    window
        w6 as (partition by substation_id order by hour_ts rows between 5 preceding and current row),
        w24 as (partition by substation_id order by hour_ts rows between 23 preceding and current row)
),

-- Aggregate outages to SUBSTATION-hour grain (not feeder-hour)
-- so joins don't fan out when a substation has multiple feeders.
-- Two severity tiers: any outage, and severe (>1000 customers affected).
outage_hourly as (
    select
        date_trunc('hour', started_ts)                              as hour_ts,
        split_part(feeder_id, '-FD', 1)                             as substation_id,
        count(*)                                                    as outage_count,
        sum(duration_minutes)                                       as total_outage_minutes,
        sum(customers_affected)                                     as total_customers_affected,
        count(*) filter (where customers_affected > 1000)           as severe_outage_count,
        case when count(*) filter (where customers_affected > 1000) > 0
             then 1 else 0 end                                      as had_severe_outage
    from {{ ref('stg_outages') }}
    group by 1, 2
),

joined as (
    select
        w.*,
        coalesce(o.outage_count, 0)              as outage_count_this_hour,
        coalesce(o.total_outage_minutes, 0)      as outage_minutes_this_hour,
        coalesce(o.total_customers_affected, 0)  as customers_affected_this_hour,
        coalesce(o.severe_outage_count, 0)       as severe_outage_count_this_hour,
        coalesce(o.had_severe_outage, 0)         as had_severe_outage
    from with_rolling w
    left join outage_hourly o
        on w.hour_ts = o.hour_ts
        and w.substation_id = o.substation_id
)

select * from joined