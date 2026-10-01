{{ config(materialized='view') }}

with source as (
    select * from {{ source('raw', 'demand_forecast') }}
),

renamed as (
    select
        cast(timestamp as timestamp)          as reading_ts,
        cast(region as varchar)               as region,
        cast(hour as integer)                 as hour_of_day,
        cast(weekday as integer)              as weekday,
        cast(temp_c as numeric(6,2))          as temp_c,
        cast(humidity as numeric(6,2))        as humidity,
        cast(holiday as boolean)              as is_holiday,
        cast(y_actual_mw as numeric(10,3))    as actual_mw,
        cast(y_forecast_mw as numeric(10,3))  as forecast_mw,
        cast(error_mw as numeric(10,3))       as error_mw
    from source
    where timestamp is not null
      and region is not null
)

select * from renamed