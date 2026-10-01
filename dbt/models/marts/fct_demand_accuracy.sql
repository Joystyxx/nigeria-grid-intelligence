{{ config(materialized='table') }}

-- Daily forecast accuracy fact per region. Feeds Dashboard Page 2.

with daily as (
    select * from {{ ref('int_demand_accuracy') }}
),

-- Rolling 7-day MAE per region
with_rolling as (
    select
        *,
        avg(mae_mw) over (
            partition by region
            order by day_ts
            rows between 6 preceding and current row
        ) as mae_mw_7d_avg
    from daily
),

-- Per-region average MAE for ranking
region_avg as (
    select
        region,
        avg(mae_mw) as region_avg_mae_mw
    from daily
    group by 1
),

enriched as (
    select
        {{ dbt_utils.generate_surrogate_key(['w.region', 'w.day_ts']) }} as accuracy_key,
        w.day_ts,
        w.region,
        w.num_readings,
        w.avg_actual_mw,
        w.avg_forecast_mw,
        w.bias_mw,
        w.mae_mw,
        w.mape_pct,
        w.max_abs_error_mw,
        w.worst_mae_rank,
        w.mae_mw_7d_avg,
        rank() over (order by r.region_avg_mae_mw desc) as region_mae_rank
    from with_rolling w
    left join region_avg r on w.region = r.region
)

select * from enriched