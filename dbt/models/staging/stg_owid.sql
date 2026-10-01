{{ config(materialized='view') }}

with source as (
    select * from {{ source('raw', 'owid') }}
),

selected as (
    select
        cast(country as varchar)                  as country,
        cast(iso_code as varchar)                 as iso_code,
        cast(year as integer)                     as year,
        cast(population as bigint)                as population,
        cast(gdp as numeric(18,2))                as gdp,

        -- Consumption & generation
        cast(primary_energy_consumption as numeric(12,3)) as primary_energy_twh,
        cast(electricity_generation as numeric(12,3))     as electricity_generation_twh,
        cast(electricity_demand as numeric(12,3))         as electricity_demand_twh,
        cast(per_capita_electricity as numeric(10,3))     as electricity_per_capita_kwh,
        cast(energy_per_capita as numeric(12,3))          as energy_per_capita_kwh,

        -- Generation by source
        cast(fossil_electricity as numeric(12,3))    as fossil_electricity_twh,
        cast(gas_electricity as numeric(12,3))       as gas_electricity_twh,
        cast(coal_electricity as numeric(12,3))      as coal_electricity_twh,
        cast(oil_electricity as numeric(12,3))       as oil_electricity_twh,
        cast(hydro_electricity as numeric(12,3))     as hydro_electricity_twh,
        cast(solar_electricity as numeric(12,3))     as solar_electricity_twh,
        cast(wind_electricity as numeric(12,3))      as wind_electricity_twh,
        cast(renewables_electricity as numeric(12,3)) as renewables_electricity_twh,
        cast(low_carbon_electricity as numeric(12,3)) as low_carbon_electricity_twh,

        -- Shares
        cast(fossil_share_elec as numeric(6,2))      as fossil_share_elec_pct,
        cast(gas_share_elec as numeric(6,2))         as gas_share_elec_pct,
        cast(hydro_share_elec as numeric(6,2))       as hydro_share_elec_pct,
        cast(solar_share_elec as numeric(6,2))       as solar_share_elec_pct,
        cast(renewables_share_elec as numeric(6,2))  as renewables_share_elec_pct,

        -- Emissions
        cast(carbon_intensity_elec as numeric(10,3))      as carbon_intensity_elec_gco2_kwh,
        cast(greenhouse_gas_emissions as numeric(12,3))   as ghg_emissions_mtco2e

    from source
    where year is not null
      and country is not null
)

select * from selected