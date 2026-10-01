{{ config(materialized='table') }}

-- One row per Nigerian state with mini-grid deployment aggregates.
-- Answers the investor/policymaker question: "What does deployment
-- look like for state X, and what does it cost?"

with viability as (
    select * from {{ ref('fct_minigrid_viability') }}
),

-- Only A and B tier settlements are considered deployment-ready
viable as (
    select *
    from viability
    where viability_tier in ('A_highly_viable', 'B_viable')
),

-- Per-state aggregates
state_agg as (
    select
        state,

        -- Settlement counts
        count(*)                                                            as viable_settlements,
        sum(population)                                                     as total_population,
        round(sum(population) / 4.5, 0)                                     as households_served,

        -- Capacity estimates (Nigerian mini-grid sizing rules of thumb)
        -- Assume ~0.5 kW per household average, with 25% capacity factor
        round(sum(population) / 4.5 * 0.5 / 1000, 2)                        as solar_capacity_mw_needed,
        -- BESS sized for 4 hours of average demand
        round(sum(population) / 4.5 * 0.5 * 4 / 1000, 2)                    as bess_capacity_mwh_needed,

        -- Investment estimate: ₦400M per MW of solar + BESS combined
        -- (industry benchmark from Nigerian mini-grid developers)
        round(sum(population) / 4.5 * 0.5 / 1000 * 400, 0)                  as capex_estimate_m_ngn,

        -- Diesel displacement benefit (annual)
        -- Assume 2 MWh/household/year displaced, 0.72 kg CO2/kWh
        round(sum(population) / 4.5 * 2 * 0.72, 0)                          as tco2_avoided_per_year,

        -- Average viability metrics for the state
        round(avg(viability_score), 2)                                      as avg_viability_score,
        round(avg(solar_score), 2)                                          as avg_solar_score,
        round(avg(grid_distance_score), 2)                                  as avg_grid_distance_score

    from viable
    group by 1
)

select
    {{ dbt_utils.generate_surrogate_key(['state']) }} as state_key,
    state,
    viable_settlements,
    total_population,
    households_served,
    solar_capacity_mw_needed,
    bess_capacity_mwh_needed,
    capex_estimate_m_ngn,
    tco2_avoided_per_year,
    avg_viability_score,
    avg_solar_score,
    avg_grid_distance_score,
    rank() over (order by viable_settlements desc) as viability_rank
from state_agg
order by viable_settlements desc