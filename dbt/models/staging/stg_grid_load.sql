{{ config(materialized='view') }}

with source as (
    select * from {{ source('raw', 'grid_load') }}
),

renamed as (
    select
        cast(timestamp as timestamp)        as reading_ts,
        cast(disco as varchar)              as disco,
        cast(substation_id as varchar)      as substation_id,
        cast(voltage_level_kv as integer)   as voltage_level_kv,
        cast(load_mw as numeric(10,3))      as load_mw,
        cast(forecast_mw as numeric(10,3))  as forecast_mw,
        cast(temp_c as numeric(6,2))        as temp_c,
        cast(humidity as numeric(6,2))      as humidity,
        cast(frequency_hz as numeric(6,3))  as frequency_hz,
        cast(source as varchar)             as source
    from source
    where timestamp is not null
      and substation_id is not null
)

select * from renamed