"""
CocoCare Stage 2 scenario generator
----------------------------------
Creates a separate Stage 2 dataset; it does not modify Stage 1 files.

Inputs:
- NASA POWER daily weather, or a frozen CSV supplied through COCOCARE_WEATHER_CSV
- Provisional FAO-56-style ET0 implementation and a simplified root-zone bucket

Scenarios:
1. weather_only: no irrigation
2. tnau_guided_irrigation: illustrative 45 L/palm every four days ONLY when
   the simulated palm age is 18 to <24 months and the calendar month is in
   DRY_SEASON_MONTHS. This operationalises a summary of TNAU guidance, not a
   complete TNAU irrigation algorithm.

IMPORTANT LIMITATIONS:
- The simulated age clock begins at START_DATE with a palm already 18 months old.
  This is a modelling convention, not a real planting record.
- The default wetted area (1 m²) is a placeholder. Litres are converted to mm
  as L/m²; replace this with a measured/defensible wetted area before interpreting
  irrigation depths.
- TNAU's cited recommendation is for the first two years after planting during
  dry summer months. No TNAU schedule is assumed for age >=24 months.
- Soil temperature is NOT generated: this script has no defensible soil-temperature
  model or soil-temperature observations.
- Water stress, actual ET, soil moisture and drainage are model-derived, not
  field observations or validated labels.
- Parameters require literature support, site soil data and/or field calibration.
"""

from pathlib import Path
import json
import math
import os

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ---------------- Configuration ----------------
SCRIPT_DIR = Path(__file__).resolve().parent
OUT_DIR = Path(os.environ.get(
    "COCOCARE_STAGE2_OUTPUT_DIR",
    str(SCRIPT_DIR / "data" / "cococare_stage2_outputs"),
)).expanduser().resolve()
OUT_DIR.mkdir(parents=True, exist_ok=True)

LATITUDE, LONGITUDE, ELEVATION_M = 10.7460, 77.0976, 286.0
LOCATION = "Pollachi, Tamil Nadu, India"
VARIETY = "East Coast Tall"

# The age clock starts at 18 months on START_DATE and advances daily.
# This period spans approximately 18 through 36 months of simulated palm age.
START_DATE, END_DATE = "2023-01-01", "2024-06-30"

NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
NASA_PARAMS = [
    "PRECTOTCORR", "T2M_MAX", "T2M_MIN",
    "ALLSKY_SFC_SW_DWN", "RH2M", "WS2M"
]
NASA_DOC_URL = "https://power.larc.nasa.gov/docs/services/api/temporal/daily/"
TNAU_IRRIGATION_URL = (
    "https://www.agritech.tnau.ac.in/expert_system/coconut/"
    "coconut/coconut_irrigation_management.html"
)
FAO56_ET0_URL = "https://www.fao.org/4/X0490E/x0490e0b.htm"

START_AGE_MONTHS = 18
# TNAU source summary is limited to dry summer months during the first two years.
# This month list is a project assumption and should be checked for local applicability.
DRY_SEASON_MONTHS = [3, 4, 5]  # March, April, May; provisional local calendar rule
TNAU_LITRES_PER_PALM = 45.0
TNAU_INTERVAL_DAYS = 4
# IMPORTANT: placeholder, not a measured or sourced wetted area.
EFFECTIVE_WETTED_AREA_M2 = 1.0

# Provisional bucket parameters: kept close to Stage 1 for comparability.
KC_PROVISIONAL = 0.70
SOIL = {
    "root_zone_depth_m": 0.45,
    "field_capacity_vwc_m3_m3": 0.23,
    "wilting_point_vwc_m3_m3": 0.10,
    "initial_available_water_fraction": 0.70,
    "runoff_fraction_of_rainfall": 0.05,
}
DEPLETION_TRIGGER = 0.50

# ---------------- Weather input ----------------
def fetch_nasa_power_daily(start_date, end_date):
    import requests

    params = {
        "parameters": ",".join(NASA_PARAMS),
        "community": "AG",
        "longitude": LONGITUDE,
        "latitude": LATITUDE,
        "start": pd.to_datetime(start_date).strftime("%Y%m%d"),
        "end": pd.to_datetime(end_date).strftime("%Y%m%d"),
        "format": "JSON",
    }
    response = requests.get(NASA_POWER_URL, params=params, timeout=120)
    response.raise_for_status()
    parameters = response.json()["properties"]["parameter"]
    date_keys = sorted(parameters[NASA_PARAMS[0]].keys())
    rows = []
    for key in date_keys:
        row = {"date": pd.to_datetime(key, format="%Y%m%d")}
        for param in NASA_PARAMS:
            value = parameters.get(param, {}).get(key)
            row[param] = (
                np.nan if value is None or float(value) <= -900 else float(value)
            )
        rows.append(row)

    weather = pd.DataFrame(rows).rename(columns={
        "PRECTOTCORR": "rainfall_mm",
        "T2M_MAX": "tmax_c",
        "T2M_MIN": "tmin_c",
        "ALLSKY_SFC_SW_DWN": "solar_radiation_mj_m2_day",
        "RH2M": "relative_humidity_pct",
        "WS2M": "wind_speed_m_s",
    })
    weather["weather_source"] = "NASA_POWER_daily_point"
    weather["weather_source_url"] = NASA_DOC_URL
    return weather


def load_weather():
    snapshot = os.environ.get("COCOCARE_WEATHER_CSV")
    required = [
        "date", "rainfall_mm", "tmax_c", "tmin_c",
        "solar_radiation_mj_m2_day", "relative_humidity_pct", "wind_speed_m_s",
    ]
    if not snapshot:
        weather = fetch_nasa_power_daily(START_DATE, END_DATE)
    else:
        path = Path(snapshot).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"COCOCARE_WEATHER_CSV does not exist: {path}")
        weather = pd.read_csv(path)
        missing = [c for c in required if c not in weather.columns]
        if missing:
            raise ValueError(f"Weather CSV missing columns: {missing}")
        weather["date"] = pd.to_datetime(weather["date"], errors="coerce")
        for col in required[1:]:
            weather[col] = pd.to_numeric(weather[col], errors="coerce")
        if "weather_source" not in weather:
            weather["weather_source"] = "provided_weather_snapshot"
        if "weather_source_url" not in weather:
            weather["weather_source_url"] = "user_supplied_snapshot; verify provenance"

    weather["date"] = pd.to_datetime(weather["date"], errors="coerce").dt.normalize()
    if weather["date"].isna().any():
        raise ValueError("Invalid dates in weather input.")
    weather = weather.loc[
        (weather["date"] >= pd.Timestamp(START_DATE)) &
        (weather["date"] <= pd.Timestamp(END_DATE))
    ].copy()
    weather = weather.sort_values("date").reset_index(drop=True)

    expected = pd.date_range(START_DATE, END_DATE, freq="D")
    if weather["date"].duplicated().any():
        raise ValueError("Duplicate weather dates found.")
    missing_dates = expected.difference(pd.DatetimeIndex(weather["date"]))
    if len(missing_dates):
        raise ValueError(
            f"Weather input has {len(missing_dates)} missing dates in configured period. "
            "Supply a complete snapshot or fetch NASA POWER."
        )
    if weather[required[1:]].isna().any().any():
        raise ValueError("Missing required weather values; inspect the weather input.")
    weather["weather_source"] = weather["weather_source"].fillna("unknown_source")
    weather["weather_source_url"] = weather["weather_source_url"].fillna("unknown_url")
    return weather


# ---------------- FAO-56-style ET0 approximation ----------------
def saturation_vapour_pressure_kpa(temp_c):
    return 0.6108 * np.exp((17.27 * temp_c) / (temp_c + 237.3))


def fao56_et0_daily(row):
    tmax, tmin = float(row["tmax_c"]), float(row["tmin_c"])
    rh = float(np.clip(row["relative_humidity_pct"], 0, 100))
    u2 = max(0.0, float(row["wind_speed_m_s"]))
    rs = max(0.0, float(row["solar_radiation_mj_m2_day"]))
    tmean = (tmax + tmin) / 2
    es = (
        saturation_vapour_pressure_kpa(tmax)
        + saturation_vapour_pressure_kpa(tmin)
    ) / 2
    # Approximation: daily mean RH estimates actual vapour pressure.
    ea = (rh / 100) * es
    delta = 4098 * saturation_vapour_pressure_kpa(tmean) / (tmean + 237.3) ** 2
    pressure = 101.3 * (((293 - 0.0065 * ELEVATION_M) / 293) ** 5.26)
    gamma = 0.000665 * pressure
    doy = pd.Timestamp(row["date"]).dayofyear
    phi = math.radians(LATITUDE)
    dr = 1 + 0.033 * math.cos(2 * math.pi / 365 * doy)
    decl = 0.409 * math.sin(2 * math.pi / 365 * doy - 1.39)
    sunset_arg = float(np.clip(-math.tan(phi) * math.tan(decl), -1, 1))
    ws = math.acos(sunset_arg)
    ra = (24 * 60 / math.pi) * 0.0820 * dr * (
        ws * math.sin(phi) * math.sin(decl)
        + math.cos(phi) * math.cos(decl) * math.sin(ws)
    )
    rso = (0.75 + 2e-5 * ELEVATION_M) * ra
    rns = (1 - 0.23) * rs
    ratio = np.clip(rs / rso, 0, 1) if rso > 0 else 0
    rnl = 4.903e-9 * (
        ((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2
    ) * (0.34 - 0.14 * math.sqrt(max(0, ea))) * (1.35 * ratio - 0.35)
    rn = rns - rnl
    numerator = (
        0.408 * delta * rn
        + gamma * (900 / (tmean + 273)) * u2 * (es - ea)
    )
    denominator = delta + gamma * (1 + 0.34 * u2)
    return max(0.0, numerator / denominator) if denominator > 0 else np.nan


# ---------------- Water-balance simulation ----------------
fc = SOIL["field_capacity_vwc_m3_m3"]
wp = SOIL["wilting_point_vwc_m3_m3"]
zr = SOIL["root_zone_depth_m"]
if fc <= wp or zr <= 0:
    raise ValueError("Invalid soil configuration.")
TAW_MM = (fc - wp) * zr * 1000
if EFFECTIVE_WETTED_AREA_M2 <= 0:
    raise ValueError("EFFECTIVE_WETTED_AREA_M2 must be positive.")

def age_months_on_date(date):
    """Approximate age clock: START_DATE represents an 18-month-old palm."""
    elapsed_days = (pd.Timestamp(date) - pd.Timestamp(START_DATE)).days
    return START_AGE_MONTHS + elapsed_days / 30.4375


def tnau_guided_irrigation_litres(date, age_months, day_index):
    """Illustrative schedule only; zero outside source-summary applicability."""
    eligible_age = START_AGE_MONTHS <= age_months < 24.0
    eligible_month = pd.Timestamp(date).month in DRY_SEASON_MONTHS
    if eligible_age and eligible_month and day_index % TNAU_INTERVAL_DAYS == 0:
        return TNAU_LITRES_PER_PALM
    return 0.0


def simulate_scenario(weather, scenario):
    if scenario not in {"weather_only", "tnau_guided_irrigation"}:
        raise ValueError(f"Unknown scenario: {scenario}")
    storage = TAW_MM * SOIL["initial_available_water_fraction"]
    rows = []

    for day_index, (_, row) in enumerate(weather.iterrows()):
        rain = max(0.0, float(row["rainfall_mm"]))
        runoff = rain * SOIL["runoff_fraction_of_rainfall"]
        effective_rain = max(0.0, rain - runoff)
        age = age_months_on_date(row["date"])

        if scenario == "tnau_guided_irrigation":
            irrigation_l = tnau_guided_irrigation_litres(
                row["date"], age, day_index
            )
        else:
            irrigation_l = 0.0

        # 1 L/m² equals 1 mm. Wetted area is provisional and must be calibrated.
        irrigation_mm = irrigation_l / EFFECTIVE_WETTED_AREA_M2
        etc = float(row["etc_potential_mm_day_modelled"])

        relative_available = np.clip(storage / TAW_MM, 0, 1)
        ks = np.clip(
            relative_available / max(0.01, 1 - DEPLETION_TRIGGER), 0, 1
        )
        actual_et = etc * ks

        pre_drainage = storage + effective_rain + irrigation_mm - actual_et
        drainage = max(0.0, pre_drainage - TAW_MM)
        storage = float(np.clip(pre_drainage - drainage, 0, TAW_MM))
        depletion = 1 - storage / TAW_MM
        stress = (
            "low" if depletion < 0.30
            else ("moderate" if depletion < DEPLETION_TRIGGER else "high")
        )
        action = (
            "continue_monitoring" if stress == "low"
            else "recheck_soil_and_weather" if stress == "moderate"
            else "consider_irrigation_if_field_conditions_confirm"
        )
        simulated_vwc = wp + (storage / TAW_MM) * (fc - wp)

        rows.append({
            **row.to_dict(),
            "scenario": scenario,
            "simulated_palm_age_months": age,
            "effective_rainfall_mm_modelled": effective_rain,
            "runoff_mm_modelled": runoff,
            "irrigation_litres_per_palm_simulated": irrigation_l,
            "effective_wetted_area_m2_assumed": EFFECTIVE_WETTED_AREA_M2,
            "irrigation_mm_simulated": irrigation_mm,
            "actual_et_mm_day_modelled": actual_et,
            "drainage_mm_modelled": drainage,
            "soil_water_storage_mm_modelled": storage,
            "depletion_fraction_modelled": depletion,
            "soil_moisture_vwc_pct_simulated": simulated_vwc * 100,
            "water_stress_rule_derived": stress,
            "recommended_action_simulated": action,
            "soil_temperature_c": np.nan,
            "soil_temperature_status": "not_modelled_no_defensible_method_or_measurements",
            "model_status": "prototype_provisional_parameters_not_field_validated",
            "stress_label_status": "rule_derived_not_ground_truth",
        })

    result = pd.DataFrame(rows)
    result["location"] = LOCATION
    result["latitude"] = LATITUDE
    result["longitude"] = LONGITUDE
    result["variety"] = VARIETY
    result["data_class"] = "NASA_POWER_weather_plus_modelled_outputs"
    return result


# ---------------- Generate both scenarios ----------------
weather = load_weather()
weather["et0_mm_day"] = weather.apply(fao56_et0_daily, axis=1)
if weather["et0_mm_day"].isna().any():
    raise ValueError("ET0 contains missing values.")
weather["etc_potential_mm_day_modelled"] = KC_PROVISIONAL * weather["et0_mm_day"]

weather.to_csv(OUT_DIR / "stage2_weather_input.csv", index=False)
weather_only = simulate_scenario(weather, "weather_only")
tnau_guided = simulate_scenario(weather, "tnau_guided_irrigation")

weather_only.to_csv(OUT_DIR / "stage2_weather_only.csv", index=False)
tnau_guided.to_csv(OUT_DIR / "stage2_tnau_guided_irrigation.csv", index=False)
combined = pd.concat([weather_only, tnau_guided], ignore_index=True)
combined.to_csv(OUT_DIR / "stage2_combined_scenarios.csv", index=False)

# ---------------- Scenario comparison ----------------
comparison_rows = []
for name, df in [
    ("weather_only", weather_only),
    ("tnau_guided_irrigation", tnau_guided),
]:
    counts = df["water_stress_rule_derived"].value_counts()
    comparison_rows.append({
        "scenario": name,
        "days": len(df),
        "total_irrigation_litres_per_palm_simulated":
            float(df["irrigation_litres_per_palm_simulated"].sum()),
        "total_irrigation_mm_simulated":
            float(df["irrigation_mm_simulated"].sum()),
        "mean_soil_water_storage_mm_modelled":
            float(df["soil_water_storage_mm_modelled"].mean()),
        "mean_soil_moisture_vwc_pct_simulated":
            float(df["soil_moisture_vwc_pct_simulated"].mean()),
        "low_stress_days_rule_derived": int(counts.get("low", 0)),
        "moderate_stress_days_rule_derived": int(counts.get("moderate", 0)),
        "high_stress_days_rule_derived": int(counts.get("high", 0)),
        "total_drainage_mm_modelled":
            float(df["drainage_mm_modelled"].sum()),
    })
comparison = pd.DataFrame(comparison_rows)
comparison.to_csv(OUT_DIR / "stage2_scenario_comparison.csv", index=False)

# Same-day differences: positive storage difference means more modelled storage
# under the TNAU-guided scenario.
daily_compare = weather_only[[
    "date", "soil_water_storage_mm_modelled",
    "soil_moisture_vwc_pct_simulated", "depletion_fraction_modelled",
    "water_stress_rule_derived"
]].merge(
    tnau_guided[[
        "date", "soil_water_storage_mm_modelled",
        "soil_moisture_vwc_pct_simulated", "depletion_fraction_modelled",
        "water_stress_rule_derived", "irrigation_litres_per_palm_simulated"
    ]],
    on="date", suffixes=("_weather_only", "_tnau_guided"), validate="one_to_one"
)
daily_compare["storage_difference_mm_tnau_minus_weather"] = (
    daily_compare["soil_water_storage_mm_modelled_tnau_guided"]
    - daily_compare["soil_water_storage_mm_modelled_weather_only"]
)
daily_compare.to_csv(OUT_DIR / "stage2_daily_scenario_differences.csv", index=False)

# Basic quality checks and mass-balance arithmetic checks.
expected_dates = pd.date_range(START_DATE, END_DATE, freq="D")
for name, df in [("weather_only", weather_only), ("tnau_guided_irrigation", tnau_guided)]:
    if len(df) != len(expected_dates) or df["date"].duplicated().any():
        raise ValueError(f"{name}: row count/date validation failed.")
    if df["soil_water_storage_mm_modelled"].isna().any():
        raise ValueError(f"{name}: missing storage output.")
    if not df["soil_water_storage_mm_modelled"].between(0, TAW_MM + 1e-9).all():
        raise ValueError(f"{name}: storage outside [0, TAW].")
if not weather_only["date"].equals(tnau_guided["date"]):
    raise ValueError("Scenario dates do not match.")

# ---------------- Metadata ----------------
metadata = {
    "project": "CocoCare",
    "stage": "Stage 2",
    "variety": VARIETY,
    "location": LOCATION,
    "coordinates": {
        "latitude": LATITUDE, "longitude": LONGITUDE,
        "elevation_m_approx": ELEVATION_M,
    },
    "age_convention": (
        "START_DATE is treated as an already-planted 18-month-old palm; "
        "age advances by elapsed days / 30.4375. This is a simulation convention."
    ),
    "weather_period": {"start": START_DATE, "end": END_DATE},
    "weather_source": "NASA POWER daily point API or explicitly supplied snapshot",
    "weather_source_url": NASA_DOC_URL,
    "agronomic_sources": {
        "TNAU irrigation": TNAU_IRRIGATION_URL,
        "FAO-56 ET0": FAO56_ET0_URL,
    },
    "scenarios": {
        "weather_only": "Zero irrigation baseline.",
        "tnau_guided_irrigation": (
            "45 L/palm every four days only when age is 18 to <24 months and "
            "month is in configured dry-season months. This is a simplified "
            "scenario derived from a TNAU source summary, not a complete official schedule."
        ),
    },
    "irrigation_assumptions": {
        "litres_per_palm_per_event": TNAU_LITRES_PER_PALM,
        "interval_days": TNAU_INTERVAL_DAYS,
        "dry_season_months": DRY_SEASON_MONTHS,
        "dry_season_months_status": "provisional project assumption; verify locally",
        "effective_wetted_area_m2": EFFECTIVE_WETTED_AREA_M2,
        "effective_wetted_area_status": (
            "placeholder only; must be measured or supported before interpreting irrigation mm"
        ),
        "source_scope": (
            "TNAU summary refers to 45 L/seedling every four days during dry summer "
            "months in the first two years after planting; verify current official page."
        ),
        "age_24_to_36_months": (
            "No TNAU irrigation schedule assumed by this script for age >=24 months."
        ),
    },
    "formulas": {
        "ETc": "potential_ETc_mm_day = provisional_Kc * ET0_mm_day",
        "TAW": "TAW_mm = (field_capacity_vwc - wilting_point_vwc) * root_zone_depth_m * 1000",
        "effective_rainfall": "effective_rainfall = max(0, rainfall - runoff)",
        "irrigation_conversion": "irrigation_mm = irrigation_litres_per_palm / assumed_effective_wetted_area_m2",
        "water_balance": (
            "pre_drainage = previous_storage + effective_rainfall + irrigation - actual_ET; "
            "drainage = max(0, pre_drainage - TAW); storage = clip(pre_drainage - drainage, 0, TAW)"
        ),
        "actual_ET": "actual_ET = potential_ETc * simplified provisional Ks",
        "soil_moisture": "linear mapping between modelled storage and assumed FC/WP; not sensor calibrated",
    },
    "provisional_parameters": {
        **SOIL,
        "kc_provisional": KC_PROVISIONAL,
        "depletion_trigger_fraction": DEPLETION_TRIGGER,
        "total_available_water_mm_calculated": float(TAW_MM),
        "status": "Prototype assumptions requiring evidence, site soil data and/or field calibration.",
    },
    "validation": {
        "weather_completeness": "checked for configured date range, duplicates and missing required values",
        "water_balance": "storage bounded and drainage closes bucket overflow arithmetically",
        "scenario_comparison": "same daily weather used for both scenarios",
        "agronomic_validation": "not performed",
        "independent_field_validation": "not available",
    },
    "limitations": [
        "NASA POWER is gridded weather data, not on-farm sensor measurements.",
        "ET0 implementation approximates actual vapour pressure using daily mean relative humidity.",
        "Kc, root depth, FC, WP, runoff, initial storage and stress threshold are provisional.",
        "The age clock is a simulation convention, not a real planting record.",
        "The dry-season month list is provisional and needs local verification.",
        "The wetted area is a placeholder and materially affects irrigation depth.",
        "Soil temperature is not modelled and is stored as missing with an explanatory status.",
        "Stress labels and moisture values are model-derived, not ground truth.",
        "The irrigation scenario is not a farm-specific recommendation.",
    ],
}
(OUT_DIR / "stage2_metadata.json").write_text(
    json.dumps(metadata, indent=2), encoding="utf-8"
)

# ---------------- Plots ----------------
fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True)
axes[0].plot(weather["date"], weather["rainfall_mm"])
axes[0].set_ylabel("Rain (mm/day)")
axes[0].set_title("NASA POWER rainfall estimate")
axes[1].plot(weather_only["date"], weather_only["soil_water_storage_mm_modelled"],
             label="Weather only")
axes[1].plot(tnau_guided["date"], tnau_guided["soil_water_storage_mm_modelled"],
             label="TNAU-guided scenario")
axes[1].axhline(TAW_MM, linestyle="--", label="Assumed TAW")
axes[1].set_ylabel("Storage (mm)")
axes[1].legend()
axes[2].plot(daily_compare["date"],
             daily_compare["storage_difference_mm_tnau_minus_weather"])
axes[2].axhline(0, linestyle="--")
axes[2].set_ylabel("Storage difference (mm)")
axes[2].set_xlabel("Date")
for ax in axes:
    ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(OUT_DIR / "stage2_scenario_comparison.png", dpi=160)
plt.show()

print("Stage 2 generation complete (prototype only; not field-validated).")
print("Output directory:", OUT_DIR)
print("Weather rows:", len(weather), "| period:", weather["date"].min(), "to", weather["date"].max())
print("\nScenario comparison:")
print(comparison.to_string(index=False))
print("\nFiles written:")
for name in [
    "stage2_weather_input.csv",
    "stage2_weather_only.csv",
    "stage2_tnau_guided_irrigation.csv",
    "stage2_combined_scenarios.csv",
    "stage2_scenario_comparison.csv",
    "stage2_daily_scenario_differences.csv",
    "stage2_metadata.json",
    "stage2_scenario_comparison.png",
]:
    print(" -", OUT_DIR / name)
