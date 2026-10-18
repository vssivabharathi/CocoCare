"""CocoCare Stage 1 hybrid dataset generator.
NASA POWER weather + provisional modelled water-balance outputs.
Model outputs are not field observations or independently validated stress labels.
"""
from pathlib import Path
import json, math, os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ---------------- Configuration ----------------
SCRIPT_DIR = Path(__file__).resolve().parent
OUT_DIR = Path(os.environ.get(
    "COCOCARE_OUTPUT_DIR",
    str(SCRIPT_DIR / "data" / "cococare_stage1_outputs"),
)).expanduser().resolve()
OUT_DIR.mkdir(exist_ok=True)

LATITUDE, LONGITUDE, ELEVATION_M = 10.7460, 77.0976, 286.0
START_DATE, END_DATE = "2023-01-01", "2023-12-31"
VARIETY, PALM_AGE_MONTHS = "East Coast Tall", 18
LOCATION = "Pollachi, Tamil Nadu, India"

NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
NASA_PARAMS = ["PRECTOTCORR", "T2M_MAX", "T2M_MIN",
               "ALLSKY_SFC_SW_DWN", "RH2M", "WS2M"]
TNAU_IRRIGATION_URL = "https://www.agritech.tnau.ac.in/expert_system/coconut/coconut/coconut_irrigation_management.html"
TNAU_NUTRIENT_URL = "https://agritech.tnau.ac.in/expert_system/coconut/coconut/coconut_nutrient_management.html"
FAO56_ET0_URL = "https://www.fao.org/4/X0490E/x0490e0b.htm"

# All parameters below are provisional placeholders pending evidence/calibration.
KC_PROVISIONAL = 0.70
SOIL = {
    "root_zone_depth_m": 0.45,
    "field_capacity_vwc_m3_m3": 0.23,
    "wilting_point_vwc_m3_m3": 0.10,
    "initial_available_water_fraction": 0.70,
    "runoff_fraction_of_rainfall": 0.05,
}
DEPLETION_TRIGGER = 0.50  # Illustrative only; not a validated stress threshold.

# ---------------- Download weather ----------------
def fetch_nasa_power_daily(start_date, end_date, latitude=LATITUDE, longitude=LONGITUDE):
    # Keep frozen-snapshot reproduction independent of the optional HTTP client.
    import requests
    params = {
        "parameters": ",".join(NASA_PARAMS), "community": "AG",
        "longitude": longitude, "latitude": latitude,
        "start": pd.to_datetime(start_date).strftime("%Y%m%d"),
        "end": pd.to_datetime(end_date).strftime("%Y%m%d"), "format": "JSON",
    }
    response = requests.get(NASA_POWER_URL, params=params, timeout=90)
    response.raise_for_status()
    parameters = response.json()["properties"]["parameter"]
    date_keys = sorted(parameters[NASA_PARAMS[0]].keys())
    rows = []
    for date_key in date_keys:
        row = {"date": pd.to_datetime(date_key, format="%Y%m%d")}
        for parameter in NASA_PARAMS:
            raw = parameters.get(parameter, {}).get(date_key)
            row[parameter] = np.nan if raw is None or float(raw) <= -900 else float(raw)
        rows.append(row)
    weather = pd.DataFrame(rows).rename(columns={
        "PRECTOTCORR": "rainfall_mm", "T2M_MAX": "tmax_c",
        "T2M_MIN": "tmin_c", "ALLSKY_SFC_SW_DWN": "solar_radiation_mj_m2_day",
        "RH2M": "relative_humidity_pct", "WS2M": "wind_speed_m_s",
    })
    weather["weather_source"] = "NASA_POWER_daily_point"
    weather["weather_source_url"] = "https://power.larc.nasa.gov/docs/services/api/temporal/daily/"
    return weather

def load_weather_input(start_date, end_date):
    """Fetch NASA POWER or reuse a supplied, previously downloaded daily snapshot.

    COCOCARE_WEATHER_CSV makes runs reproducible without silently changing the
    external weather input.  It must contain the generator's canonical weather
    columns and is still subjected to the same completeness checks below.
    """
    snapshot = os.environ.get("COCOCARE_WEATHER_CSV")
    if not snapshot:
        return fetch_nasa_power_daily(start_date, end_date)
    weather_path = Path(snapshot).expanduser().resolve()
    if not weather_path.exists():
        raise FileNotFoundError(f"COCOCARE_WEATHER_CSV does not exist: {weather_path}")
    weather = pd.read_csv(weather_path)
    required = ["date", "rainfall_mm", "tmax_c", "tmin_c",
                "solar_radiation_mj_m2_day", "relative_humidity_pct", "wind_speed_m_s"]
    missing = [column for column in required if column not in weather.columns]
    if missing:
        raise ValueError(f"Weather snapshot missing required columns: {missing}")
    weather["date"] = pd.to_datetime(weather["date"], errors="coerce")
    for column in required[1:]:
        weather[column] = pd.to_numeric(weather[column], errors="coerce")
    weather["weather_source"] = weather.get("weather_source", "NASA_POWER_daily_point_snapshot")
    weather["weather_source_url"] = weather.get("weather_source_url", NASA_POWER_URL)
    return weather

weather = load_weather_input(START_DATE, END_DATE)
expected_dates = pd.date_range(START_DATE, END_DATE, freq="D")
observed_dates = pd.DatetimeIndex(weather["date"].dt.normalize().unique())
missing_dates = expected_dates.difference(observed_dates)
if weather["date"].duplicated().any():
    raise ValueError("Duplicate weather dates found.")
if len(missing_dates):
    raise ValueError(f"{len(missing_dates)} calendar dates are missing: {missing_dates[:10]}")
required_weather = ["rainfall_mm", "tmax_c", "tmin_c", "solar_radiation_mj_m2_day",
                    "relative_humidity_pct", "wind_speed_m_s"]
if weather[required_weather].isna().any().any():
    raise ValueError("Missing required weather values; inspect before continuing.")
weather.to_csv(OUT_DIR / "coimbatore_nasa_power_weather.csv", index=False)
print("Weather rows:", len(weather), "| period:", weather.date.min(), "to", weather.date.max())

# ---------------- FAO-56 ET0 approximation ----------------
def saturation_vapour_pressure_kpa(temp_c):
    return 0.6108 * np.exp((17.27 * temp_c) / (temp_c + 237.3))

def fao56_et0_daily(row, latitude_deg=LATITUDE, elevation_m=ELEVATION_M):
    required = ["tmax_c", "tmin_c", "relative_humidity_pct",
                "wind_speed_m_s", "solar_radiation_mj_m2_day"]
    if any(pd.isna(row[k]) for k in required):
        return np.nan
    tmax, tmin = float(row["tmax_c"]), float(row["tmin_c"])
    rh = float(np.clip(row["relative_humidity_pct"], 0, 100))
    u2 = max(0.0, float(row["wind_speed_m_s"]))
    rs = max(0.0, float(row["solar_radiation_mj_m2_day"]))
    tmean = (tmax + tmin) / 2
    es = (saturation_vapour_pressure_kpa(tmax) +
          saturation_vapour_pressure_kpa(tmin)) / 2
    # Approximation: daily mean RH used to estimate actual vapour pressure.
    ea = (rh / 100) * es
    delta = 4098 * saturation_vapour_pressure_kpa(tmean) / (tmean + 237.3)**2
    pressure = 101.3 * (((293 - 0.0065 * elevation_m) / 293)**5.26)
    gamma = 0.000665 * pressure
    doy = pd.Timestamp(row["date"]).dayofyear
    phi = math.radians(latitude_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi / 365 * doy)
    decl = 0.409 * math.sin(2 * math.pi / 365 * doy - 1.39)
    sunset_arg = float(np.clip(-math.tan(phi) * math.tan(decl), -1, 1))
    ws = math.acos(sunset_arg)
    ra = (24 * 60 / math.pi) * 0.0820 * dr * (
        ws * math.sin(phi) * math.sin(decl) +
        math.cos(phi) * math.cos(decl) * math.sin(ws))
    rso = (0.75 + 2e-5 * elevation_m) * ra
    rns = (1 - 0.23) * rs
    ratio = np.clip(rs / rso, 0, 1) if rso > 0 else 0
    rnl = 4.903e-9 * (((tmax + 273.16)**4 + (tmin + 273.16)**4) / 2) * (
        0.34 - 0.14 * math.sqrt(max(0, ea))) * (1.35 * ratio - 0.35)
    rn, g = rns - rnl, 0.0
    numerator = 0.408 * delta * (rn - g) + gamma * (900 / (tmean + 273)) * u2 * (es - ea)
    denominator = delta + gamma * (1 + 0.34 * u2)
    return max(0.0, numerator / denominator) if denominator > 0 else np.nan

weather["et0_mm_day"] = weather.apply(fao56_et0_daily, axis=1)
if weather["et0_mm_day"].isna().any():
    raise ValueError("ET0 contains missing values.")
weather["etc_potential_mm_day_modelled"] = KC_PROVISIONAL * weather["et0_mm_day"]

# ---------------- Soil water model ----------------
fc = SOIL["field_capacity_vwc_m3_m3"]
wp = SOIL["wilting_point_vwc_m3_m3"]
zr = SOIL["root_zone_depth_m"]
if fc <= wp or zr <= 0:
    raise ValueError("Invalid soil configuration: FC must exceed WP and root depth must be positive.")
TAW_MM = (fc - wp) * zr * 1000

def simulate_scenario(weather_df, scenario="weather_only"):
    df = weather_df.sort_values("date").copy()
    storage = TAW_MM * SOIL["initial_available_water_fraction"]
    rows = []
    for _, row in df.iterrows():
        if pd.isna(row["rainfall_mm"]) or pd.isna(row["et0_mm_day"]):
            raise ValueError(f"Missing weather on {row['date']}; no row silently skipped.")
        rain = max(0.0, float(row["rainfall_mm"]))
        runoff = rain * SOIL["runoff_fraction_of_rainfall"]
        effective_rain = max(0.0, rain - runoff)
        irrigation = 0.0
        # Optional illustrative scenario only; not an operational recommendation.
        if scenario == "irrigation_response" and storage < TAW_MM * (1 - DEPLETION_TRIGGER):
            irrigation = min(12.0, max(0.0, TAW_MM - storage - effective_rain))
        etc = float(row["etc_potential_mm_day_modelled"])
        relative_available = np.clip(storage / TAW_MM, 0, 1)
        ks = np.clip(relative_available / max(0.01, 1 - DEPLETION_TRIGGER), 0, 1)
        actual_et = etc * ks
        # Runoff is already deducted in effective_rain; do NOT subtract it again.
        pre_drainage = storage + effective_rain + irrigation - actual_et
        # Close the bucket exactly: any water above TAW leaves as drainage.
        # A partial-drainage factor combined with clipping creates unreported
        # loss and violates mass balance.  Infiltration/runoff parameterisation
        # remains provisional and is deliberately not changed here.
        drainage = max(0.0, pre_drainage - TAW_MM)
        storage = float(np.clip(pre_drainage - drainage, 0, TAW_MM))
        depletion = 1 - storage / TAW_MM
        stress = "low" if depletion < 0.30 else ("moderate" if depletion < DEPLETION_TRIGGER else "high")
        action = ("continue_monitoring" if stress == "low" else
                  "recheck_soil_and_weather" if stress == "moderate" else
                  "consider_irrigation_if_field_conditions_confirm")
        simulated_vwc = wp + (storage / TAW_MM) * (fc - wp)
        rows.append({
            **row.to_dict(), "scenario": scenario,
            "effective_rainfall_mm_modelled": effective_rain,
            "runoff_mm_modelled": runoff,
            "irrigation_mm_simulated": irrigation,
            "actual_et_mm_day_modelled": actual_et,
            "drainage_mm_modelled": drainage,
            "soil_water_storage_mm_modelled": storage,
            "depletion_fraction_modelled": depletion,
            "soil_moisture_vwc_pct_simulated": simulated_vwc * 100,
            "water_stress_rule_derived": stress,
            "recommended_action_simulated": action,
            "model_status": "computed_using_provisional_parameters",
        })
    result = pd.DataFrame(rows)
    result["location"] = LOCATION
    result["latitude"] = LATITUDE
    result["longitude"] = LONGITUDE
    result["variety"] = VARIETY
    result["palm_age_months"] = PALM_AGE_MONTHS
    result["data_class"] = "NASA_POWER_weather_plus_modelled_outputs"
    result["stress_label_status"] = "rule_derived_not_ground_truth"
    return result

model_df = simulate_scenario(weather, scenario="weather_only")
if len(model_df) != len(expected_dates) or model_df["date"].duplicated().any():
    raise ValueError("Output row count/date validation failed.")
dataset_path = OUT_DIR / "stage1_hybrid_dataset.csv"
model_df.to_csv(dataset_path, index=False)

# ---------------- TNAU source-reference template ----------------
tnau_rules = pd.DataFrame([
    {"topic": "young_palm_irrigation",
     "age_category": "first two years after planting",
     "recommendation_summary": "TNAU page summary: 45 L/seedling once every 4 days during dry summer months; verify official page and local applicability.",
     "numeric_value": 45, "unit": "L/seedling/application",
     "conditions": "dry summer months; verify method and local applicability",
     "source_url": TNAU_IRRIGATION_URL, "source_type": "official_extension_guidance",
     "status": "source_summary_to_verify_before_use"},
    {"topic": "second_year_compost",
     "age_category": "second year after planting",
     "recommendation_summary": "TNAU table summary for second-year compost; verify exact table.",
     "numeric_value": 20, "unit": "kg/palm/year",
     "conditions": "verify exact table and management context",
     "source_url": TNAU_NUTRIENT_URL, "source_type": "official_extension_guidance",
     "status": "source_summary_to_verify_before_use"},
])
tnau_rules.to_csv(OUT_DIR / "tnau_reference_rules.csv", index=False)

# ---------------- Metadata ----------------
metadata = {
    "project": "CocoCare", "stage": "Stage 1", "variety": VARIETY,
    "palm_age_months": PALM_AGE_MONTHS, "location": LOCATION,
    "coordinates": {"latitude": LATITUDE, "longitude": LONGITUDE,
                    "elevation_m_approx": ELEVATION_M},
    "weather_source": "NASA POWER daily point API",
    "weather_source_url": "https://power.larc.nasa.gov/docs/services/api/temporal/daily/",
    "weather_period": {"start": START_DATE, "end": END_DATE},
    "agronomic_sources": {"TNAU irrigation": TNAU_IRRIGATION_URL,
                          "TNAU nutrient management": TNAU_NUTRIENT_URL,
                          "FAO-56 ET0": FAO56_ET0_URL},
    "formulas": {
        "ETc": "ETc = Kc * ET0 (crop coefficient approach)",
        "TAW": "TAW_mm = (field_capacity_vwc - wilting_point_vwc) * root_zone_depth_m * 1000",
        "effective_rainfall": "effective_rainfall = max(0, rainfall - runoff)",
        "water_balance": "storage_t = storage_(t-1) + effective_rainfall + irrigation - actual_ET - drainage; drainage = max(0, pre_drainage - TAW); storage is therefore bounded in [0, TAW] without unreported clipping loss",
        "actual_ET": "actual_ET = potential_ETc * Ks; Ks is a simplified provisional storage-based stress factor",
    },
    "provisional_parameters": {
        **SOIL, "kc_provisional": KC_PROVISIONAL,
        "depletion_trigger_fraction": DEPLETION_TRIGGER,
        "total_available_water_mm_calculated": float(TAW_MM),
        "status": "Prototype assumptions; require literature support, soil data, or field calibration.",
    },
    "validation": {
        "weather_period": "one calendar year; prototype/debugging period",
        "weather_quality": "Required weather inputs checked for missing values and duplicate dates during generation.",
        "water_balance_arithmetic": "Storage equation uses effective rainfall, which already excludes runoff; runoff is not subtracted a second time. Drainage removes the complete amount above bucket capacity, so the reported fluxes close the bucket.",
        "agronomic_validation": "not_yet_performed",
        "independent_field_validation": "not_available",
    },
    "limitations": [
        "NASA POWER is gridded weather data, not on-farm sensor measurements.",
        "ET0 implementation approximates actual vapour pressure from daily mean relative humidity.",
        "Kc, root-zone depth, FC, WP, runoff, drainage, initial storage and stress threshold are provisional.",
        "The weather_only scenario applies zero irrigation.",
        "Modelled moisture and stress labels are not ground truth.",
        "Stress labels are generated by the same model being evaluated.",
        "No agronomic accuracy claim is justified without independent field validation.",
        "TNAU source summaries must be verified against current official pages before operational use.",
    ],
}
metadata_path = OUT_DIR / "stage1_metadata.json"
metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

print("Saved dataset:", dataset_path.resolve())
print("Saved metadata:", metadata_path.resolve())
print("Saved TNAU reference rules:", (OUT_DIR / "tnau_reference_rules.csv").resolve())
print("Dataset shape:", model_df.shape)
print("Missing values:", int(model_df.isna().sum().sum()))
print("\nStress labels:\n", model_df["water_stress_rule_derived"].value_counts())

# Quick visual checks
fig, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True)
axes[0].plot(model_df["date"], model_df["rainfall_mm"])
axes[0].set_ylabel("Rain (mm/day)")
axes[0].set_title("NASA POWER daily rainfall estimate")
axes[1].plot(model_df["date"], model_df["et0_mm_day"], label="ET0")
axes[1].plot(model_df["date"], model_df["etc_potential_mm_day_modelled"], label="Potential ETc")
axes[1].set_ylabel("ET (mm/day)")
axes[1].legend()
axes[2].plot(model_df["date"], model_df["soil_water_storage_mm_modelled"], label="Modelled storage")
axes[2].axhline(TAW_MM, linestyle="--", label="Assumed TAW")
axes[2].set_ylabel("Storage (mm)")
axes[2].legend()
for ax in axes:
    ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()

print("Generation complete. Prototype only; not field-validated.")
