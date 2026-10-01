{{ config(materialized='table') }}

-- One row per settlement with a 0-100 viability score.
-- Weighted: Solar 30% | Pop density 25% | Grid distance 20%
--           Economic activity 15% | Accessibility 10%
--
-- Each sub-score is min-max normalised to 0-100 across all settlements.
-- Tiers are PERCENTILE-BASED (top 5% = A) to adapt to actual data
-- distribution; absolute thresholds would leave A empty.

with base as (
    select
        settlement_id,
        settlement_name,
        state,
        lga,
        latitude,
        longitude,
        population,
        area_km2,
        num_buildings,
        building_density_pct,
        dist_main_road_km,
        has_main_road,
        dist_transmission_km,
        dist_gridlight_km,
        solar_pv_value,
        wealth_index,
        has_nightlight,
        ag_value_ngn,
        num_education_facilities,
        num_health_facilities,
        security_risk,
        demand_kwh,
        num_connections
    from {{ ref('stg_dre_atlas') }}
),

normalised as (
    select
        *,
        case
            when max(solar_pv_value) over () = min(solar_pv_value) over () then 50
            else (solar_pv_value - min(solar_pv_value) over ())
                 / nullif(max(solar_pv_value) over () - min(solar_pv_value) over (), 0) * 100
        end as solar_score,
        case
            when max(population / nullif(area_km2, 0)) over () = min(population / nullif(area_km2, 0)) over () then 50
            else least(100,
                (population / nullif(area_km2, 0) - min(population / nullif(area_km2, 0)) over ())
                / nullif(max(population / nullif(area_km2, 0)) over () - min(population / nullif(area_km2, 0)) over (), 0) * 100
            )
        end as pop_density_score,
        case
            when max(dist_transmission_km) over () = min(dist_transmission_km) over () then 50
            else (dist_transmission_km - min(dist_transmission_km) over ())
                 / nullif(max(dist_transmission_km) over () - min(dist_transmission_km) over (), 0) * 100
        end as grid_distance_score,
        case
            when max(wealth_index) over () = min(wealth_index) over () then 50
            else (wealth_index - min(wealth_index) over ())
                 / nullif(max(wealth_index) over () - min(wealth_index) over (), 0) * 100
        end as economic_score,
        case
            when max(dist_main_road_km) over () = min(dist_main_road_km) over () then 50
            else (1 - (dist_main_road_km - min(dist_main_road_km) over ())
                    / nullif(max(dist_main_road_km) over () - min(dist_main_road_km) over (), 0)) * 100
        end as accessibility_score
    from base
),

scored as (
    select
        {{ dbt_utils.generate_surrogate_key(['settlement_id']) }} as viability_key,
        settlement_id,
        settlement_name,
        state,
        lga,
        latitude,
        longitude,
        population,
        area_km2,
        num_buildings,
        dist_transmission_km,
        solar_pv_value,
        wealth_index,
        has_nightlight,
        has_main_road,
        num_education_facilities,
        num_health_facilities,
        security_risk,
        demand_kwh,
        num_connections,
        round(solar_score, 2)         as solar_score,
        round(pop_density_score, 2)   as pop_density_score,
        round(grid_distance_score, 2) as grid_distance_score,
        round(economic_score, 2)      as economic_score,
        round(accessibility_score, 2) as accessibility_score,
        round(
            0.30 * solar_score
          + 0.25 * pop_density_score
          + 0.20 * grid_distance_score
          + 0.15 * economic_score
          + 0.10 * accessibility_score,
          2
        ) as viability_score
    from normalised
),

ranked as (
    select
        *,
        percent_rank() over (order by viability_score desc) as viability_pctile
    from scored
)

select
    *,
    case
        when viability_pctile <= 0.05 then 'A_highly_viable'
        when viability_pctile <= 0.20 then 'B_viable'
        when viability_pctile <= 0.50 then 'C_borderline'
        else 'D_not_viable'
    end as viability_tier
from ranked