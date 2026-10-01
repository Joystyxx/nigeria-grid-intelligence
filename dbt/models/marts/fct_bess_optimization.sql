{{ config(materialized='table') }}

-- One row per AI grid optimisation run (from HF ai_optimization).
-- Quantifies the improvement that optimisation delivers over baseline.

with base as (
    select * from {{ ref('stg_optimization') }}
),

enriched as (
    select
        {{ dbt_utils.generate_surrogate_key(['run_id']) }} as optimization_key,
        run_id,
        run_ts,
        disco,
        objective,
        baseline_loss_mw,
        optimized_loss_mw,
        (baseline_loss_mw - optimized_loss_mw)             as loss_reduction_mw,
        baseline_cost_ngn,
        optimized_cost_ngn,
        (baseline_cost_ngn - optimized_cost_ngn)           as cost_savings_ngn,
        improvement_pct,
        constraint_violations,
        solution_time_s,

        -- Derived KPIs
        case
            when baseline_loss_mw > 0
            then (baseline_loss_mw - optimized_loss_mw) / baseline_loss_mw * 100
            else null
        end                                                as loss_reduction_pct,
        case
            when baseline_cost_ngn > 0
            then (baseline_cost_ngn - optimized_cost_ngn) / baseline_cost_ngn * 100
            else null
        end                                                as cost_reduction_pct,

        -- Annualised savings estimate (assumes hourly run pattern)
        (baseline_cost_ngn - optimized_cost_ngn) * 24 * 365 as annualised_savings_ngn,

        -- Constraint health flag
        case
            when constraint_violations = 0 then 'clean'
            when constraint_violations <= 2 then 'minor_violations'
            else 'violated'
        end                                                as constraint_status
    from base
)

select * from enriched