{{ config(materialized='view') }}

with source as (
    select * from {{ source('raw', 'smart_grid_iot') }}
),

renamed as (
    select
        cast(timestamp as timestamp)        as reading_ts,
        cast(disco as varchar)              as disco,
        cast(substation_id as varchar)      as substation_id,
        cast(device_id as varchar)          as device_id,
        cast(device_type as varchar)        as device_type,
        cast(metric as varchar)             as metric,
        cast(value as numeric(12,4))        as metric_value,
        cast(unit as varchar)               as unit,
        cast(status as varchar)             as device_status
    from source
    where timestamp is not null
      and substation_id is not null
)

select * from renamed