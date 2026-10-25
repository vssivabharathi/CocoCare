"""
CocoCare Stage 1 — Dataset Evaluation
Location: Pollachi, Tamil Nadu, India

Checks:
1. Dataset integrity and date coverage
2. Missing values and duplicates
3. Location and metadata
4. Weather value ranges
5. ETc = Kc * ET0
6. Runoff and effective rainfall
7. Exact daily water balance and drainage
8. Soil-water, depletion, and VWC consistency
9. Stress labels and recommended actions
10. Weather snapshot consistency
11. Plots and evaluation reports

Important:
These tests check data integrity and internal arithmetic consistency.
They do not prove agronomic accuracy. Stress labels are model-derived,
not field-measured ground truth.
"""

from pathlib import Path
import os
import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================
# 1. PATHS AND CONFIGURATION
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent

# Evaluator is inside stage1/evaluvation/
# Outputs are inside stage1/data/cococare_stage1_outputs/
DEFAULT_OUTPUT_DIR = (
    SCRIPT_DIR.parent / "data" / "cococare_stage1_outputs"
)

OUTPUT_DIR = Path(
    os.environ.get(
        "COCOCARE_OUTPUT_DIR",
        str(DEFAULT_OUTPUT_DIR)
    )
).expanduser().resolve()

DATASET_PATH = OUTPUT_DIR / "stage1_hybrid_dataset.csv"
METADATA_PATH = OUTPUT_DIR / "stage1_metadata.json"

# Keep this filename because it is what the current generator writes.
WEATHER_PATH = OUTPUT_DIR / "coimbatore_nasa_power_weather.csv"

REPORT_DIR = OUTPUT_DIR / "evaluation_reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

EXPECTED_START = "2023-01-01"
EXPECTED_END = "2023-12-31"

EXPECTED_LOCATION = "Pollachi, Tamil Nadu, India"
EXPECTED_LATITUDE = 10.7423
EXPECTED_LONGITUDE = 77.1042
EXPECTED_VARIETY = "East Coast Tall"
EXPECTED_PALM_AGE_MONTHS = 18

TOL = 1e-8

# Defaults must match the generator.
FC_DEFAULT = 0.23
WP_DEFAULT = 0.10
ROOT_DEPTH_DEFAULT = 0.45
KC_DEFAULT = 0.70
RUNOFF_DEFAULT = 0.05
INITIAL_WATER_FRACTION_DEFAULT = 0.70
DEPLETION_TRIGGER_DEFAULT = 0.50


# ============================================================
# 2. LOAD DATA
# ============================================================

if not DATASET_PATH.exists():
    raise FileNotFoundError(
        f"\nDataset not found:\n{DATASET_PATH}\n\n"
        "Set COCOCARE_OUTPUT_DIR to the folder containing "
        "stage1_hybrid_dataset.csv."
    )

df = pd.read_csv(DATASET_PATH)

if "date" not in df.columns:
    raise ValueError("Dataset must contain a 'date' column.")

df["date"] = pd.to_datetime(df["date"], errors="coerce")
source_column_count = len(df.columns)

metadata = {}

if METADATA_PATH.exists():
    with open(METADATA_PATH, "r", encoding="utf-8") as file:
        metadata = json.load(file)

# Read parameters from metadata, with generator-matching fallbacks.
params = metadata.get("provisional_parameters", {})

fc = float(params.get(
    "field_capacity_vwc_m3_m3", FC_DEFAULT
))
wp = float(params.get(
    "wilting_point_vwc_m3_m3", WP_DEFAULT
))
root_depth = float(params.get(
    "root_zone_depth_m", ROOT_DEPTH_DEFAULT
))
kc = float(params.get("kc_provisional", KC_DEFAULT))
runoff_fraction = float(params.get(
    "runoff_fraction_of_rainfall", RUNOFF_DEFAULT
))
initial_fraction = float(params.get(
    "initial_available_water_fraction",
    INITIAL_WATER_FRACTION_DEFAULT
))
depletion_trigger = float(params.get(
    "depletion_trigger_fraction",
    DEPLETION_TRIGGER_DEFAULT
))

if fc <= wp or root_depth <= 0:
    raise ValueError("Invalid FC, WP, or root-zone depth.")

TAW = (fc - wp) * root_depth * 1000.0
INITIAL_STORAGE = TAW * initial_fraction

print("=" * 72)
print("COCOCARE STAGE 1 — DATASET EVALUATION")
print("=" * 72)
print("Dataset:", DATASET_PATH)
print("Shape:", df.shape)
print("Output folder:", REPORT_DIR)
print("Expected location:", EXPECTED_LOCATION)
print(f"TAW: {TAW:.6f} mm")
print(f"Initial storage: {INITIAL_STORAGE:.6f} mm")


# ============================================================
# 3. REQUIRED COLUMNS AND INTEGRITY
# ============================================================

required_columns = [
    "date",
    "rainfall_mm",
    "tmax_c",
    "tmin_c",
    "solar_radiation_mj_m2_day",
    "relative_humidity_pct",
    "wind_speed_m_s",
    "et0_mm_day",
    "etc_potential_mm_day_modelled",
    "effective_rainfall_mm_modelled",
    "runoff_mm_modelled",
    "irrigation_mm_simulated",
    "actual_et_mm_day_modelled",
    "drainage_mm_modelled",
    "soil_water_storage_mm_modelled",
    "depletion_fraction_modelled",
    "soil_moisture_vwc_pct_simulated",
    "water_stress_rule_derived",
    "recommended_action_simulated",
    "model_status",
    "data_class",
    "stress_label_status",
]

missing_columns = [
    col for col in required_columns
    if col not in df.columns
]

if missing_columns:
    raise ValueError(
        f"Missing required columns: {missing_columns}"
    )

numeric_columns = [
    "rainfall_mm",
    "tmax_c",
    "tmin_c",
    "solar_radiation_mj_m2_day",
    "relative_humidity_pct",
    "wind_speed_m_s",
    "et0_mm_day",
    "etc_potential_mm_day_modelled",
    "effective_rainfall_mm_modelled",
    "runoff_mm_modelled",
    "irrigation_mm_simulated",
    "actual_et_mm_day_modelled",
    "drainage_mm_modelled",
    "soil_water_storage_mm_modelled",
    "depletion_fraction_modelled",
    "soil_moisture_vwc_pct_simulated",
]

for col in numeric_columns:
    df[col] = pd.to_numeric(df[col], errors="coerce")

structure = pd.DataFrame({
    "dtype": df.dtypes.astype(str),
    "missing_count": df.isna().sum(),
    "missing_percent": (df.isna().mean() * 100).round(3),
    "unique_values": df.nunique(dropna=False),
})

structure.to_csv(
    REPORT_DIR / "column_quality_report.csv"
)

expected_dates = pd.date_range(
    EXPECTED_START, EXPECTED_END, freq="D"
)

observed_dates = pd.DatetimeIndex(
    df["date"].dropna().dt.normalize().unique()
)

missing_dates = expected_dates.difference(observed_dates)
unexpected_dates = observed_dates.difference(expected_dates)

duplicate_rows = int(df.duplicated().sum())
duplicate_dates = int(df["date"].duplicated().sum())

integrity = {
    "rows": int(len(df)),
    "source_columns": source_column_count,
    "duplicate_rows": duplicate_rows,
    "duplicate_dates": duplicate_dates,
    "invalid_dates": int(df["date"].isna().sum()),
    "missing_source_cells": int(df.isna().sum().sum()),
    "expected_days": int(len(expected_dates)),
    "unique_observed_dates": int(len(observed_dates)),
    "missing_calendar_dates": int(len(missing_dates)),
    "unexpected_dates": int(len(unexpected_dates)),
    "date_min": str(df["date"].min()),
    "date_max": str(df["date"].max()),
}

print("\n[1] DATASET INTEGRITY")
print(json.dumps(integrity, indent=2))

if len(missing_dates):
    print(
        "Missing dates:",
        missing_dates.strftime("%Y-%m-%d").tolist()
    )


# ============================================================
# 4. LOCATION AND METADATA
# ============================================================

coords = metadata.get("coordinates", {})

location_checks = {
    "metadata_file_found": bool(METADATA_PATH.exists()),
    "metadata_location_matches": (
        metadata.get("location") == EXPECTED_LOCATION
    ),
    "metadata_latitude_matches": False,
    "metadata_longitude_matches": False,
    "dataset_location_matches": False,
    "dataset_latitude_matches": False,
    "dataset_longitude_matches": False,
    "metadata_variety_matches": (
        metadata.get("variety") == EXPECTED_VARIETY
    ),
    "metadata_palm_age_matches": (
        metadata.get("palm_age_months")
        == EXPECTED_PALM_AGE_MONTHS
    ),
}

try:
    location_checks["metadata_latitude_matches"] = (
        abs(float(coords["latitude"]) - EXPECTED_LATITUDE) < 1e-5
    )
    location_checks["metadata_longitude_matches"] = (
        abs(float(coords["longitude"]) - EXPECTED_LONGITUDE) < 1e-5
    )
except (KeyError, TypeError, ValueError):
    pass

if "location" in df.columns:
    location_checks["dataset_location_matches"] = bool(
        len(df) > 0
        and df["location"].notna().all()
        and df["location"].eq(EXPECTED_LOCATION).all()
    )

if "latitude" in df.columns:
    lat = pd.to_numeric(df["latitude"], errors="coerce")
    location_checks["dataset_latitude_matches"] = bool(
        len(df) > 0
        and lat.notna().all()
        and (lat.sub(EXPECTED_LATITUDE).abs() < 1e-5).all()
    )

if "longitude" in df.columns:
    lon = pd.to_numeric(df["longitude"], errors="coerce")
    location_checks["dataset_longitude_matches"] = bool(
        len(df) > 0
        and lon.notna().all()
        and (lon.sub(EXPECTED_LONGITUDE).abs() < 1e-5).all()
    )

# Convert all values to regular Python booleans for JSON.
location_checks = {
    key: bool(value)
    for key, value in location_checks.items()
}

print("\n[2] LOCATION AND METADATA")
print(json.dumps(location_checks, indent=2))


# ============================================================
# 5. WEATHER AND OUTPUT RANGE SCREENING
# ============================================================

screening_ranges = {
    "rainfall_mm": (0, 500),
    "tmax_c": (-10, 60),
    "tmin_c": (-15, 50),
    "solar_radiation_mj_m2_day": (0, 45),
    "relative_humidity_pct": (0, 100),
    "wind_speed_m_s": (0, 75),
    "et0_mm_day": (0, 20),
    "etc_potential_mm_day_modelled": (0, 20),
    "effective_rainfall_mm_modelled": (0, 500),
    "runoff_mm_modelled": (0, 500),
    "irrigation_mm_simulated": (0, 500),
    "actual_et_mm_day_modelled": (0, 20),
    "drainage_mm_modelled": (0, 500),
    "soil_water_storage_mm_modelled": (0, TAW),
    "depletion_fraction_modelled": (0, 1),
    "soil_moisture_vwc_pct_simulated": (0, 100),
}

range_rows = []

for col, (lower, upper) in screening_ranges.items():
    values = df[col]
    outside = (values < lower) | (values > upper)

    range_rows.append({
        "column": col,
        "lower_screen": lower,
        "upper_screen": upper,
        "below_lower_count": int((values < lower).sum()),
        "above_upper_count": int((values > upper).sum()),
        "out_of_range_count": int(outside.sum()),
        "minimum": values.min(),
        "maximum": values.max(),
    })

range_report = pd.DataFrame(range_rows)

range_report.to_csv(
    REPORT_DIR / "range_screening_report.csv",
    index=False
)

temperature_inversions = int(
    (df["tmax_c"] < df["tmin_c"]).sum()
)

print("\n[3] RANGE SCREENING")
print(range_report.to_string(index=False))
print("Days where Tmax < Tmin:", temperature_inversions)


# ============================================================
# 6. ETc CONSISTENCY
# ============================================================

df["etc_reconstructed_mm_day"] = kc * df["et0_mm_day"]

df["etc_abs_error_mm_day"] = (
    df["etc_potential_mm_day_modelled"]
    - df["etc_reconstructed_mm_day"]
).abs()

etc_errors = df["etc_abs_error_mm_day"].dropna()

etc_summary = {
    "kc_provisional": kc,
    "mean_absolute_error_mm_day": (
        float(etc_errors.mean())
        if len(etc_errors) else None
    ),
    "maximum_absolute_error_mm_day": (
        float(etc_errors.max())
        if len(etc_errors) else None
    ),
    "days_error_above_tolerance": int(
        (etc_errors > TOL).sum()
    ),
}

print("\n[4] ETc CONSISTENCY")
print(json.dumps(etc_summary, indent=2))


# ============================================================
# 7. RUNOFF AND EFFECTIVE RAINFALL
# ============================================================

rain = df["rainfall_mm"].clip(lower=0)

expected_runoff = rain * runoff_fraction
expected_effective_rain = (
    rain - expected_runoff
).clip(lower=0)

df["runoff_abs_error_mm"] = (
    df["runoff_mm_modelled"] - expected_runoff
).abs()

df["effective_rain_abs_error_mm"] = (
    df["effective_rainfall_mm_modelled"]
    - expected_effective_rain
).abs()

rain_summary = {
    "runoff_fraction_configured": runoff_fraction,
    "maximum_runoff_error_mm": float(
        df["runoff_abs_error_mm"].max()
    ),
    "runoff_errors_above_tolerance": int(
        (df["runoff_abs_error_mm"] > TOL).sum()
    ),
    "maximum_effective_rainfall_error_mm": float(
        df["effective_rain_abs_error_mm"].max()
    ),
    "effective_rainfall_errors_above_tolerance": int(
        (df["effective_rain_abs_error_mm"] > TOL).sum()
    ),
    "runoff_exceeds_rainfall_days": int(
        (
            df["runoff_mm_modelled"]
            > df["rainfall_mm"] + TOL
        ).sum()
    ),
}

print("\n[5] RUNOFF AND EFFECTIVE RAINFALL")
print(json.dumps(rain_summary, indent=2))


# ============================================================
# 8. EXACT WATER-BALANCE VALIDATION
# ============================================================

# Sort chronologically before reconstructing the water balance.
df = df.sort_values("date").reset_index(drop=True)

# First day starts from the generator's configured initial storage.
# Each subsequent day starts from the previous day's output storage.
previous_storage = (
    df["soil_water_storage_mm_modelled"].shift(1)
)

if len(df) > 0:
    previous_storage.iloc[0] = INITIAL_STORAGE

pre_drainage = (
    previous_storage
    + df["effective_rainfall_mm_modelled"]
    + df["irrigation_mm_simulated"]
    - df["actual_et_mm_day_modelled"]
)

# Generator equation:
# drainage = max(0, pre_drainage - TAW)
# storage = clip(pre_drainage - drainage, 0, TAW)
expected_drainage = (
    pre_drainage - TAW
).clip(lower=0)

expected_storage = (
    pre_drainage - expected_drainage
).clip(lower=0, upper=TAW)

df["expected_pre_drainage_mm"] = pre_drainage
df["expected_drainage_mm"] = expected_drainage
df["expected_storage_mm"] = expected_storage

df["drainage_abs_error_mm"] = (
    df["drainage_mm_modelled"] - expected_drainage
).abs()

df["storage_abs_error_mm"] = (
    df["soil_water_storage_mm_modelled"] - expected_storage
).abs()

water_summary = {
    "TAW_mm": float(TAW),
    "initial_storage_mm": float(INITIAL_STORAGE),
    "days_checked": int(len(df)),
    "maximum_drainage_error_mm": float(
        df["drainage_abs_error_mm"].max()
    ),
    "drainage_errors_above_tolerance": int(
        (df["drainage_abs_error_mm"] > TOL).sum()
    ),
    "maximum_storage_error_mm": float(
        df["storage_abs_error_mm"].max()
    ),
    "storage_errors_above_tolerance": int(
        (df["storage_abs_error_mm"] > TOL).sum()
    ),
    "interpretation": (
        "Internal arithmetic consistency only; not field validation."
    ),
}

print("\n[6] EXACT WATER-BALANCE CHECK")
print(json.dumps(water_summary, indent=2))

water_mismatches = df.loc[
    (df["drainage_abs_error_mm"] > TOL)
    | (df["storage_abs_error_mm"] > TOL),
    [
        "date",
        "expected_pre_drainage_mm",
        "drainage_mm_modelled",
        "expected_drainage_mm",
        "drainage_abs_error_mm",
        "soil_water_storage_mm_modelled",
        "expected_storage_mm",
        "storage_abs_error_mm",
    ],
]

water_mismatches.to_csv(
    REPORT_DIR / "water_balance_mismatches.csv",
    index=False
)


# ============================================================
# 9. SOIL-WATER DERIVED VARIABLES AND LABELS
# ============================================================

df["depletion_reconstructed"] = (
    1 - df["soil_water_storage_mm_modelled"] / TAW
)

df["vwc_reconstructed_pct"] = (
    wp
    + (
        df["soil_water_storage_mm_modelled"] / TAW
    ) * (fc - wp)
) * 100

df["depletion_abs_error"] = (
    df["depletion_fraction_modelled"]
    - df["depletion_reconstructed"]
).abs()

df["vwc_abs_error_pct"] = (
    df["soil_moisture_vwc_pct_simulated"]
    - df["vwc_reconstructed_pct"]
).abs()

expected_stress = df["depletion_fraction_modelled"].apply(
    lambda value: (
        "low" if value < 0.30
        else "moderate" if value < depletion_trigger
        else "high"
    )
)

stress_mismatches = int(
    (expected_stress != df["water_stress_rule_derived"]).sum()
)

expected_actions = df["water_stress_rule_derived"].map({
    "low": "continue_monitoring",
    "moderate": "recheck_soil_and_weather",
    "high": "consider_irrigation_if_field_conditions_confirm",
})

action_mismatches = int(
    (expected_actions != df["recommended_action_simulated"]).sum()
)

derived_summary = {
    "maximum_depletion_formula_error": float(
        df["depletion_abs_error"].max()
    ),
    "maximum_vwc_formula_error_percentage_points": float(
        df["vwc_abs_error_pct"].max()
    ),
    "storage_below_zero_count": int(
        (df["soil_water_storage_mm_modelled"] < -TOL).sum()
    ),
    "storage_above_TAW_count": int(
        (df["soil_water_storage_mm_modelled"] > TAW + TOL).sum()
    ),
    "stress_label_mismatches": stress_mismatches,
    "action_mapping_mismatches": action_mismatches,
    "actual_ET_exceeds_potential_ETc_days": int(
        (
            df["actual_et_mm_day_modelled"]
            > df["etc_potential_mm_day_modelled"] + TOL
        ).sum()
    ),
}

print("\n[7] SOIL-WATER AND LABEL CHECKS")
print(json.dumps(derived_summary, indent=2))


# ============================================================
# 10. WEATHER SNAPSHOT CROSS-CHECK
# ============================================================

weather = None

weather_summary = {
    "weather_file_found": bool(WEATHER_PATH.exists())
}

weather_columns = [
    "rainfall_mm",
    "tmax_c",
    "tmin_c",
    "solar_radiation_mj_m2_day",
    "relative_humidity_pct",
    "wind_speed_m_s",
]

if WEATHER_PATH.exists():
    weather = pd.read_csv(WEATHER_PATH)

    if "date" in weather.columns:
        weather["date"] = pd.to_datetime(
            weather["date"], errors="coerce"
        )

    weather_summary["weather_rows"] = int(len(weather))
    weather_summary["weather_rows_match_dataset"] = bool(
        len(weather) == len(df)
    )

    if "date" in weather.columns:
        weather_summary["weather_duplicate_dates"] = int(
            weather["date"].duplicated().sum()
        )

    if (
        "date" in weather.columns
        and all(col in weather.columns for col in weather_columns)
    ):
        merged = df[["date"] + weather_columns].merge(
            weather[["date"] + weather_columns],
            on="date",
            how="outer",
            suffixes=("_dataset", "_weather"),
            indicator=True,
        )

        weather_summary["date_join_not_both_count"] = int(
            (merged["_merge"] != "both").sum()
        )

        for col in weather_columns:
            differences = (
                merged[f"{col}_dataset"]
                - merged[f"{col}_weather"]
            ).abs()

            weather_summary[f"{col}_max_abs_difference"] = (
                float(differences.max())
                if differences.notna().any()
                else None
            )
    else:
        weather_summary["comparison_note"] = (
            "Weather CSV is missing required columns."
        )

print("\n[8] WEATHER SNAPSHOT CROSS-CHECK")
print(json.dumps(weather_summary, indent=2))


# ============================================================
# 11. LABEL DISTRIBUTIONS
# ============================================================

stress_counts = df[
    "water_stress_rule_derived"
].value_counts(dropna=False)

action_counts = df[
    "recommended_action_simulated"
].value_counts(dropna=False)

stress_counts.rename_axis("stress_label").to_frame(
    "count"
).to_csv(REPORT_DIR / "stress_label_distribution.csv")

action_counts.rename_axis("action").to_frame(
    "count"
).to_csv(REPORT_DIR / "recommended_action_distribution.csv")

print("\n[9] STRESS LABEL DISTRIBUTION")
print(stress_counts.to_string())

print("\nRECOMMENDED ACTION DISTRIBUTION")
print(action_counts.to_string())


# ============================================================
# 12. SAVE PLOTS
# ============================================================

plot_specs = [
    ("rainfall_mm", "Rainfall estimate (mm/day)"),
    ("tmax_c", "Maximum temperature (°C)"),
    ("tmin_c", "Minimum temperature (°C)"),
    ("et0_mm_day", "Estimated reference ET0 (mm/day)"),
    (
        "etc_potential_mm_day_modelled",
        "Modelled potential ETc (mm/day)"
    ),
    (
        "soil_water_storage_mm_modelled",
        "Modelled soil-water storage (mm)"
    ),
    (
        "depletion_fraction_modelled",
        "Modelled depletion fraction"
    ),
    ("drainage_mm_modelled", "Modelled drainage (mm/day)"),
]

for column, ylabel in plot_specs:
    fig, ax = plt.subplots(figsize=(12, 3.5))

    ax.plot(df["date"], df[column])
    ax.set_title(column)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Date")
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(
        REPORT_DIR / f"{column}.png",
        dpi=140
    )
    plt.close(fig)

correlation_columns = [
    col for col in numeric_columns
    if col in df.columns and df[col].nunique(dropna=True) > 1
]

correlation = df[correlation_columns].corr()

correlation.to_csv(
    REPORT_DIR / "numeric_correlations.csv"
)

fig, ax = plt.subplots(figsize=(12, 9))

image = ax.imshow(
    correlation,
    aspect="auto",
    vmin=-1,
    vmax=1
)

fig.colorbar(image, ax=ax, label="Pearson correlation")

ax.set_xticks(range(len(correlation.columns)))
ax.set_xticklabels(correlation.columns, rotation=90)

ax.set_yticks(range(len(correlation.index)))
ax.set_yticklabels(correlation.index)

ax.set_title("CocoCare Stage 1 Numeric Correlations")
fig.tight_layout()

fig.savefig(
    REPORT_DIR / "numeric_correlation_heatmap.png",
    dpi=140
)

plt.close(fig)


# ============================================================
# 13. PIPELINE CHECKLIST
# ============================================================

weather_matches = (
    weather is not None
    and weather_summary.get("date_join_not_both_count", 1) == 0
    and all(
        weather_summary.get(f"{col}_max_abs_difference") is not None
        and weather_summary.get(f"{col}_max_abs_difference") < TOL
        for col in weather_columns
    )
)

location_matches = all([
    location_checks["metadata_location_matches"],
    location_checks["metadata_latitude_matches"],
    location_checks["metadata_longitude_matches"],
    location_checks["dataset_location_matches"],
    location_checks["dataset_latitude_matches"],
    location_checks["dataset_longitude_matches"],
])

checks = {
    "expected_row_count": len(df) == len(expected_dates,
    ),
    "no_duplicate_dates": duplicate_dates == 0,
    "no_duplicate_rows": duplicate_rows == 0,
    "no_invalid_dates": df["date"].isna().sum() == 0,
    "no_missing_source_cells": int(df.isna().sum().sum()) == 0,
    "calendar_dates_complete": (
        len(missing_dates) == 0
        and len(unexpected_dates) == 0
    ),
    "weather_range_screening_clean": (
        int(range_report["out_of_range_count"].sum()) == 0
    ),
    "temperature_order_valid": temperature_inversions == 0,
    "location_metadata_matches_pollachi": location_matches,
    "ETc_formula_consistent": (
        etc_summary["days_error_above_tolerance"] == 0
    ),
    "runoff_formula_consistent": (
        rain_summary["runoff_errors_above_tolerance"] == 0
    ),
    "effective_rainfall_consistent": (
        rain_summary["effective_rainfall_errors_above_tolerance"] == 0
    ),
    "water_balance_drainage_consistent": (
        water_summary["drainage_errors_above_tolerance"] == 0
    ),
    "water_balance_storage_consistent": (
        water_summary["storage_errors_above_tolerance"] == 0
    ),
    "derived_variables_consistent": (
        derived_summary["maximum_depletion_formula_error"] < TOL
        and derived_summary[
            "maximum_vwc_formula_error_percentage_points"
        ] < TOL
    ),
    "stress_labels_match_rule": stress_mismatches == 0,
    "stress_action_mapping_consistent": action_mismatches == 0,
    "weather_snapshot_matches_dataset": bool(weather_matches),
}

checks_df = pd.DataFrame([
    {"check": name, "passed": bool(value)}
    for name, value in checks.items()
])

checks_df.to_csv(
    REPORT_DIR / "pipeline_checklist.csv",
    index=False
)


# ============================================================
# 14. SAVE JSON SUMMARY
# ============================================================

summary = {
    "dataset_path": str(DATASET_PATH),
    "output_directory": str(OUTPUT_DIR),
    "dataset_shape": {
        "rows": int(df.shape[0]),
        "source_columns": source_column_count,
    },
    "date_range": {
        "start": str(df["date"].min()),
        "end": str(df["date"].max()),
    },
    "integrity": integrity,
    "location_checks": location_checks,
    "configured_parameters": {
        "field_capacity_vwc_m3_m3": fc,
        "wilting_point_vwc_m3_m3": wp,
        "root_zone_depth_m": root_depth,
        "kc_provisional": kc,
        "runoff_fraction_of_rainfall": runoff_fraction,
        "initial_available_water_fraction": initial_fraction,
        "depletion_trigger_fraction": depletion_trigger,
        "TAW_mm": float(TAW),
        "initial_storage_mm": float(INITIAL_STORAGE),
    },
    "range_screening": range_rows,
    "temperature_inversions": temperature_inversions,
    "etc_consistency": etc_summary,
    "rainfall_runoff_consistency": rain_summary,
    "water_balance": water_summary,
    "derived_variables": derived_summary,
    "weather_crosscheck": weather_summary,
    "stress_label_counts": {
        str(key): int(value)
        for key, value in stress_counts.items()
    },
    "recommended_action_counts": {
        str(key): int(value)
        for key, value in action_counts.items()
    },
    "pipeline_checks": {
        str(row["check"]): bool(row["passed"])
        for _, row in checks_df.iterrows()
    },
    "scientific_status": {
        "weather": (
            "NASA POWER gridded estimates, not on-farm measurements"
        ),
        "ET0": (
            "Independent reference comparison not performed by this script"
        ),
        "crop_and_soil_parameters": "provisional",
        "stress_labels": "rule-derived, not ground truth",
        "agronomic_validation": "not performed",
        "independent_field_validation": "not available",
    },
}

with open(
    REPORT_DIR / "evaluation_summary.json",
    "w",
    encoding="utf-8"
) as file:
    json.dump(summary, file, indent=2, default=str)


# ============================================================
# 15. FINAL RESULTS
# ============================================================

print("\n[10] PIPELINE CHECKLIST")
print(checks_df.to_string(index=False))

passed = int(checks_df["passed"].sum())
total = len(checks_df)

print(f"\nPassed: {passed}/{total}")
print("Reports saved to:", REPORT_DIR)
print(
    "\nIMPORTANT: Passing these checks confirms data integrity "
    "and internal consistency only. It does not establish "
    "agronomic accuracy or validate the stress labels."
)