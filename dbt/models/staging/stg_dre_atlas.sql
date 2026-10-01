{{ config(materialized='view') }}

with source as (
    select * from {{ source('raw', 'dre_atlas') }}
),

renamed as (
    select
        cast(geohash as varchar)                              as settlement_id,
        cast(village_name as varchar)                         as settlement_name,
        cast(admin_cgaz_1 as varchar)                         as state,
        cast(admin_cgaz_2 as varchar)                         as lga,
        cast(lat as numeric(10,6))                            as latitude,
        cast(lon as numeric(10,6))                            as longitude,

        cast(population as bigint)                            as population,
        cast(hull_area as numeric(12,3))                      as area_km2,
        cast(num_buildings as integer)                        as num_buildings,
        cast(building_density_percent as numeric(6,2))        as building_density_pct,

        cast(dist_main_road_km as numeric(10,3))              as dist_main_road_km,
        cast(main_road_access as boolean)                     as has_main_road,
        cast(dist_nearest_hub_km as numeric(10,3))            as dist_nearest_hub_km,
        cast(nearest_hub_name as varchar)                     as nearest_hub,

        cast(distance_to_existing_transmission_lines as numeric(10,3))    as dist_transmission_km,
        cast(distance_to_existing_hv_transmission_lines as numeric(10,3)) as dist_hv_transmission_km,
        cast(distance_to_gridlight_targets as numeric(10,3))              as dist_gridlight_km,

        cast(pv_value as numeric(12,3))                       as solar_pv_value,
        cast(mean_rwi as numeric(6,3))                        as wealth_index,
        cast(has_nightlight as boolean)                       as has_nightlight,
        cast(ag_value as numeric(18,2))                       as ag_value_ngn,
        cast(ag_area as numeric(12,3))                        as ag_area_ha,
        cast(ag_yield as numeric(12,3))                       as ag_yield,
        cast(crop_types as varchar)                           as crop_types,

        cast(num_education_facilities as integer)             as num_education_facilities,
        cast(num_health_facilities as integer)                as num_health_facilities,
        cast(total_incidents_50km as integer)                 as incidents_50km,
        cast(security_risk as varchar)                        as security_risk,

        cast(demand as numeric(10,3))                         as demand_kwh,
        cast(demand_connection as numeric(10,3))              as demand_per_connection_kwh,
        cast(num_connections as integer)                      as num_connections,

        cast(country_iso as varchar)                          as country_iso,
        cast(source as varchar)                               as source

    from source
    where geohash is not null
      and admin_cgaz_1 is not null
)

select * from renamed