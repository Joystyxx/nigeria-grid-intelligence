{{ config(materialized='view') }}

with source as (
    select * from {{ source('raw', 'ai_optimization') }}
),

renamed as (
    select
        cast(run_id as varchar)                    as run_id,
        cast(timestamp as timestamp)               as run_ts,
        cast(disco as varchar)                     as disco,
        cast(objective as varchar)                 as objective,
        cast(baseline_loss_mw as numeric(10,3))    as baseline_loss_mw,
        cast(optimized_loss_mw as numeric(10,3))   as optimized_loss_mw,
        cast(baseline_cost_ngn as numeric(14,2))   as baseline_cost_ngn,
        cast(optimized_cost_ngn as numeric(14,2))  as optimized_cost_ngn,
        cast(improvement_pct as numeric(6,2))      as improvement_pct,
        cast(constraint_violations as integer)     as constraint_violations,
        cast(solution_time_s as numeric(8,3))      as solution_time_s
    from source
    where run_id is not null
)

select * from renamed