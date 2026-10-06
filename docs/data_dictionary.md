# Data Dictionary

Reference for the platform's key tables. Schemas: `raw` (untouched source data), `dbt_dev_marts` (business tables), `ml` (model and optimisation outputs).

---

## raw Schema

Untouched data written by ingestion scripts. Column names match the source exactly.

| Table | Rows | Description |
|---|---|---|
| raw.grid_load | 200,000 | Per-substation load MW, forecast, sensor readings (HF electricsheepafrica) |
| raw.demand_forecast | 200,000 | Per-region actual vs forecast demand with error (HF) |
| raw.smart_grid_iot | 250,000 | 5-min substation telemetry: voltage, frequency, current, temperature (HF) |
| raw.outage_logs | 60,000 | Outage events with cause, duration, customers affected (HF) |
| raw.ai_optimization | 80,000 | Pre-computed grid optimisation runs (HF) |
| raw.pvgis | 36 | Monthly solar irradiation for Lagos, Abuja, Kano (EU JRC) |
| raw.owid | 126 | Historical Nigerian energy mix and consumption (OWID) |
| raw.dre_atlas | 154,319 | Nigerian settlements for mini-grid planning (World Bank) |

---

## dbt_dev_marts Schema

Business-ready tables. What the dashboard and ML models read.

### dim_substation

One row per substation. 23 rows.

| Column | Type | Description |
|---|---|---|
| substation_key | text | Surrogate key (hash of substation_id) |
| substation_id | text | Natural ID, e.g. IKJ-SS-001 |
| disco | text | Distribution company (Ikeja, Eko, Abuja, Kano, etc.) |
| primary_voltage_kv | int | Highest voltage tier observed (11, 33, 132, 330) |
| voltage_tiers | array | All voltage tiers seen for this substation |
| num_iot_devices | int | Distinct IoT devices reporting |
| latitude | numeric | Substation latitude |
| longitude | numeric | Substation longitude |
| voltage_class | text | transmission if primary >= 132 kV, else distribution |

### fct_grid_events

One row per substation-hour. The ML feature table. 125,381 rows.

| Column | Description |
|---|---|
| event_key | Surrogate key (substation_id + hour) |
| event_ts | Hour timestamp (UTC) |
| disco, substation_id | Foreign keys |
| avg_load_mw, peak_load_mw | Hourly load stats |
| forecast_error_mw | avg_load_mw minus avg_forecast_mw |
| load_avg_6h, load_std_6h | Rolling 6-hour mean and stddev of load |
| load_avg_24h, load_std_24h | Rolling 24-hour mean and stddev |
| avg_frequency_hz, avg_freq_dev_hz | Average frequency and deviation from 50 Hz |
| sensor_anomalies, sensor_anomaly_pct | Anomaly count and rate from IoT telemetry |
| outage_count_this_hour | Number of outage events in this hour |
| severe_outage_count_this_hour | Count of outages affecting >1,000 customers |
| had_outage, had_severe_outage | Binary flags (0/1) |

### fct_demand_accuracy

Daily forecast accuracy per region. 2,190 rows.

| Column | Description |
|---|---|
| accuracy_key | Surrogate key (region + day) |
| day_ts, region | Date and region |
| num_readings | Number of forecast/actual pairs |
| avg_actual_mw, avg_forecast_mw | Daily means |
| bias_mw | Signed error mean |
| mae_mw | Mean absolute error |
| mape_pct | Mean absolute percentage error |
| mae_mw_7d_avg | Rolling 7-day MAE |
| worst_mae_rank, region_mae_rank | Rankings |

### fct_bess_optimization

Pre-computed optimisation runs. 80,000 rows.

| Column | Description |
|---|---|
| optimization_key | Surrogate key |
| run_id, run_ts, disco | Run metadata |
| baseline_loss_mw, optimized_loss_mw | Loss before and after optimisation |
| baseline_cost_ngn, optimized_cost_ngn | Cost before and after |
| cost_savings_ngn | Baseline minus optimised |
| improvement_pct | Percentage improvement |
| constraint_violations | Number of LP constraint breaches |
| constraint_status | clean, minor_violations, or violated |

### fct_minigrid_viability

One row per Nigerian settlement. 154,319 rows.

| Column | Description |
|---|---|
| viability_key | Surrogate key |
| settlement_id, settlement_name, state, lga | Settlement identifiers |
| latitude, longitude | Location |
| population, area_km2, num_buildings | Demographics |
| solar_pv_value | Solar resource value |
| wealth_index | Relative wealth index |
| dist_transmission_km | Distance to nearest transmission line |
| solar_score, pop_density_score, grid_distance_score, economic_score, accessibility_score | 0-100 sub-scores |
| viability_score | Weighted composite (solar 30%, density 25%, grid distance 20%, economic 15%, accessibility 10%) |
| viability_pctile | Percentile rank |
| viability_tier | A_highly_viable (top 5%), B_viable (next 15%), C_borderline (next 30%), D_not_viable (bottom 50%) |

### fct_state_summary

One row per Nigerian state. 37 rows.

| Column | Description |
|---|---|
| state | State name |
| viable_settlements | Count of A + B tier settlements |
| total_population, households_served | Population covered |
| solar_capacity_mw_needed | Estimated solar capacity (MW) |
| bess_capacity_mwh_needed | Estimated battery storage (MWh) |
| capex_estimate_m_ngn | Estimated capital expenditure (millions of naira) |
| tco2_avoided_per_year | Annual CO2 avoided vs diesel (tonnes) |
| avg_viability_score | Mean score across the state's viable settlements |
| viability_rank | State ranking by viable settlement count |

---

## ml Schema

Model outputs and optimisation results.

### ml.grid_instability_predictions

Latest predictions per substation-hour. 552 rows.

| Column | Description |
|---|---|
| predicted_at | Timestamp of prediction run |
| event_ts, disco, substation_id | Row identity |
| outage_probability | XGBoost outage model output (0 to 1) |
| outage_predicted | Binary flag (probability >= 0.5) |
| load_spike_probability | XGBoost load spike model output |
| load_percentile | Load percentile rank within snapshot |
| freq_deviation_score | Frequency deviation percentile |
| sensor_anomaly_score | Sensor anomaly percentile |
| stress_score | Composite 0 to 100 |
| stress_tier | low, moderate, high, or critical |

### ml.bess_optimization_results

Summary for the 12 BESS scenarios.

| Column | Description |
|---|---|
| scenario_id, region, mode | Scenario identity |
| total_cost_ngn, baseline_cost_ngn, savings_ngn, savings_pct | Cost metrics |
| emissions_kg, baseline_emissions_kg, emissions_saved_kg | CO2 metrics |
| solver_status | Optimal or Infeasible |

### ml.bess_dispatch_hourly

24 hourly rows per scenario.

| Column | Description |
|---|---|
| scenario_id, region, mode, hour | Row identity |
| demand_mw | Demand to meet |
| grid_import_mw, solar_gen_mw, diesel_gen_mw | Sources used |
| charge_mw, discharge_mw | Battery activity |
| soc_mwh | Battery state of charge |

### ml.bess_sensitivity

54-cell sensitivity grid.

| Column | Description |
|---|---|
| region, charging_source | Region and charge source (grid_charge or solar_charge) |
| diesel_price_ngn_per_kwh | Varied: 500, 600, 800 |
| battery_capacity_mwh | Varied: 100, 250, 500 |
| savings_ngn, savings_pct, emissions_saved_kg | Output metrics |
| solver_status | Optimal or Infeasible |

### ml.bess_multiyear

Multi-year economic comparison.

| Column | Description |
|---|---|
| year | 2024, 2025, or 2026 |
| region | Lagos, Kano, Abuja |
| grid_price, diesel_price, solar_price | Prices used for that year |
| savings_ngn, savings_pct, emissions_saved_kg | Output metrics |

---

## Configuration

### config/energy_prices.yaml

Nigerian energy price reference, versioned in git. Sources documented inline.

| Section | Contents |
|---|---|
| grid | Band A tariff (N225/kWh) and weighted average |
| diesel | Pump price (N3,277/L), generation cost (N600/kWh) |
| solar | C&I LCOE (N120/kWh) |
| historical | Per-year prices for 2024, 2025, 2026 |
| metadata | Last verified date, next review due |

To update prices: edit this file and re-run the BESS scripts. No code changes needed.

---

## GeoJSON Exports

### docs/minigrid_viability_top50.geojson

Top 50 viable settlements per state. ~1,667 features, 0.6 MB. Used by the dashboard map.

### docs/minigrid_viability_full.geojson

All A + B tier settlements. 30,913 features, 10.6 MB. Available for download and offline analysis in QGIS or similar tools.

Both files use the standard GeoJSON FeatureCollection format with point geometries and settlement attributes in the properties object.