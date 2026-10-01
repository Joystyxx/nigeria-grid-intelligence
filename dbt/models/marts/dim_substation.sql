{{ config(materialized='table') }}

-- One row per substation. Nigerian substations appear at multiple
-- voltage tiers in the source data (330/132/33/11 kV). We collapse
-- to one row per substation_id with:
--   - primary_voltage_kv = highest tier (transmission-side)
--   - voltage_tiers = list of all observed tiers
--   - voltage_class = 'transmission' if primary >= 132, else 'distribution'

with voltage_agg as (
    select
        disco,
        substation_id,
        max(voltage_level_kv)                              as primary_voltage_kv,
        array_agg(distinct voltage_level_kv order by voltage_level_kv desc)
                                                           as voltage_tiers,
        count(distinct voltage_level_kv)                   as num_voltage_tiers
    from {{ ref('stg_grid_load') }}
    group by 1, 2
),

sensor_coverage as (
    select
        substation_id,
        count(distinct device_id)   as num_iot_devices,
        count(distinct metric)      as num_metrics
    from {{ ref('stg_smart_grid_iot') }}
    group by 1
),

geo as (
    select
        split_part(feeder_id, '-FD', 1) as substation_id,
        avg(latitude)   as latitude,
        avg(longitude)  as longitude
    from {{ ref('stg_outages') }}
    where latitude is not null
    group by 1
)

select
    {{ dbt_utils.generate_surrogate_key(['v.substation_id']) }} as substation_key,
    v.substation_id,
    v.disco,
    v.primary_voltage_kv,
    v.voltage_tiers,
    v.num_voltage_tiers,
    coalesce(sc.num_iot_devices, 0)     as num_iot_devices,
    coalesce(sc.num_metrics, 0)         as num_metrics,
    g.latitude,
    g.longitude,
    case
        when v.primary_voltage_kv >= 132 then 'transmission'
        else 'distribution'
    end as voltage_class
from voltage_agg v
left join sensor_coverage sc on v.substation_id = sc.substation_id
left join geo g on v.substation_id = g.substation_id