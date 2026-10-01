{{ config(materialized='view') }}

-- Aggregate forecast accuracy by region and day.
-- Mean absolute error (MAE) is the headline metric for DisCo comparison.

with base as (
    select
        reading_ts,
        region,
        actual_mw,
        forecast_mw,
        error_mw,
        abs(error_mw)                   as abs_error_mw,
        case
            when actual_mw = 0 then null
            else abs(error_mw) / nullif(actual_mw, 0) * 100
        end                             as abs_error_pct
    from {{ ref('stg_demand_forecast') }}
),

daily as (
    select
        date_trunc('day', reading_ts)   as day_ts,
        region,
        count(*)                        as num_readings,
        avg(actual_mw)                  as avg_actual_mw,
        avg(forecast_mw)                as avg_forecast_mw,
        avg(error_mw)                   as bias_mw,
        avg(abs_error_mw)               as mae_mw,
        avg(abs_error_pct)              as mape_pct,
        max(abs_error_mw)               as max_abs_error_mw
    from base
    group by 1, 2
),

ranked as (
    select
        *,
        rank() over (partition by day_ts order by mae_mw desc) as worst_mae_rank
    from daily
)

select * from ranked