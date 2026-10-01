{{ config(materialized='view') }}

with source as (
    select * from {{ source('raw', 'outage_logs') }}
),

renamed as (
    select
        cast(outage_id as varchar)            as outage_id,
        cast(disco as varchar)                as disco,
        cast(feeder_id as varchar)            as feeder_id,
        cast(start_time as timestamp)         as started_ts,
        cast(end_time as timestamp)           as ended_ts,
        cast(duration_min as numeric(10,2))   as duration_minutes,
        cast(cause as varchar)                as cause,
        cast(customers_affected as integer)   as customers_affected,
        cast(status as varchar)               as outage_status,
        cast(lat as numeric(10,6))            as latitude,
        cast(lon as numeric(10,6))            as longitude,
        extract(hour from cast(start_time as timestamp))::int  as hour_of_day,
        extract(dow from cast(start_time as timestamp))::int   as day_of_week
    from source
    where outage_id is not null
      and start_time is not null
)

select * from renamed