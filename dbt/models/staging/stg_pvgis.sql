{{ config(materialized='view') }}

with source as (
    select * from {{ source('raw', 'pvgis') }}
),

renamed as (
    select
        cast(month as integer)              as month_num,
        cast("E_d" as numeric(8,3))         as daily_energy_kwh,
        cast("E_m" as numeric(10,3))        as monthly_energy_kwh,
        cast("H(i)_d" as numeric(8,3))      as daily_irradiance_kwh_m2,
        cast("H(i)_m" as numeric(10,3))     as monthly_irradiance_kwh_m2,
        cast("SD_m" as numeric(10,3))       as monthly_std_kwh,
        cast(city as varchar)               as city,
        cast(lat as numeric(10,6))          as latitude,
        cast(lon as numeric(10,6))          as longitude,
        cast(source as varchar)             as source
    from source
    where month is not null
      and city is not null
)

select * from renamed