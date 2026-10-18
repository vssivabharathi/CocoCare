"""
CocoCare Stage 1 — Dataset Evaluation Script
------------------------------------------------
Evaluates:
1) CSV integrity and schema
2) Date coverage, duplicates, missingness
3) Basic weather value plausibility
4) ET0 / ETc consistency
5) Water-balance arithmetic consistency
6) Storage / depletion / simulated VWC consistency
7) Stress-label and action distributions
8) Summary plots and CSV/JSON reports

Important:
- This evaluates data quality and internal consistency, not agronomic accuracy.
- Stress labels are model-derived and are not ground truth.
- Check expected columns against your generator if the schema changes.
"""

from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ============================================================
# 1. PATHS AND CONFIGURATION
# ============================================================

# Resolve the output directory robustly.
# Default matches the generator output path from the user's terminal log.
# Override with COCOCARE_OUTPUT_DIR=/absolute/path/to/cococare_stage1_outputs
import os

DEFAULT_OUTPUT_DIR = (
    Path.home()
    / "Documents/FinalYearProject/CocoCare/ml/data/coconut_health/data/cococare_stage1_outputs"
)

OUTPUT_DIR = Path(
    os.environ.get("COCOCARE_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR))
).expanduser().resolve()

DATASET_PATH = OUTPUT_DIR / "stage1_hybrid_dataset.csv"
WEATHER_PATH = OUTPUT_DIR / "coimbatore_nasa_power_weather.csv"
METADATA_PATH = OUTPUT_DIR / "stage1_metadata.json"

REPORT_DIR = OUTPUT_DIR / "evaluation_reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

EXPECTED_START = "2023-01-01"
EXPECTED_END = "2023-12-31"

# Must match the generator's provisional configuration.
# These are not measured field properties.
FC_VWC = 0.23
WP_VWC = 0.10
ROOT_ZONE_DEPTH_M = 0.45
KC_PROVISIONAL = 0.70
RUNOFF_FRACTION = 0.05
DEPLETION_TRIGGER = 0.50

TAW_MM = (FC_VWC - WP_VWC) * ROOT_ZONE_DEPTH_M * 1000

# Numerical tolerance for reconstructed storage equation.
WATER_BALANCE_TOL_MM = 1e-8

# ============================================================
# 2. LOAD FILES
# ============================================================

if not DATASET_PATH.exists():
    raise FileNotFoundError(
        f"Dataset not found: {DATASET_PATH}\n"
        "Set COCOCARE_OUTPUT_DIR to the folder containing the CSV files."
    )

df = pd.read_csv(DATASET_PATH)
df["date"] = pd.to_datetime(df["date"], errors="coerce")
source_column_count = int(df.shape[1])

weather = None
if WEATHER_PATH.exists():
    weather = pd.read_csv(WEATHER_PATH)
    weather["date"] = pd.to_datetime(weather["date"], errors="coerce")

metadata = {}
if METADATA_PATH.exists():
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)

print("=" * 72)
print("COCOCARE STAGE 1 — DATASET EVALUATION")
print("=" * 72)
print("Dataset:", DATASET_PATH)
print("Shape:", df.shape)
print("Report folder:", REPORT_DIR)

# ============================================================
# 3. REQUIRED COLUMNS AND BASIC INTEGRITY
# ============================================================

required_columns = [
    "date", "rainfall_mm", "tmax_c", "tmin_c",
    "solar_radiation_mj_m2_day", "relative_humidity_pct",
    "wind_speed_m_s", "et0_mm_day",
    "etc_potential_mm_day_modelled",
    "effective_rainfall_mm_modelled", "runoff_mm_modelled",
    "irrigation_mm_simulated", "actual_et_mm_day_modelled",
    "drainage_mm_modelled", "soil_water_storage_mm_modelled",
    "depletion_fraction_modelled", "soil_moisture_vwc_pct_simulated",
    "water_stress_rule_derived", "recommended_action_simulated",
    "model_status", "data_class", "stress_label_status",
]
missing_columns = [c for c in required_columns if c not in df.columns]

if missing_columns:
    raise ValueError(f"Required columns missing from dataset: {missing_columns}")

# Convert required numeric columns; non-numeric values become NaN and are reported.
numeric_columns = [
    "rainfall_mm", "tmax_c", "tmin_c", "solar_radiation_mj_m2_day",
    "relative_humidity_pct", "wind_speed_m_s", "et0_mm_day",
    "etc_potential_mm_day_modelled", "effective_rainfall_mm_modelled",
    "runoff_mm_modelled", "irrigation_mm_simulated",
    "actual_et_mm_day_modelled", "drainage_mm_modelled",
    "soil_water_storage_mm_modelled", "depletion_fraction_modelled",
    "soil_moisture_vwc_pct_simulated",
]
for col in numeric_columns:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# Dataset structure
structure = pd.DataFrame({
    "dtype": df.dtypes.astype(str),
    "missing_count": df.isna().sum(),
    "missing_percent": (df.isna().mean() * 100).round(3),
    "unique_values": df.nunique(dropna=False),
})
structure.to_csv(REPORT_DIR / "column_quality_report.csv")

duplicate_rows = int(df.duplicated().sum())
duplicate_dates = int(df["date"].duplicated().sum())
expected_dates = pd.date_range(EXPECTED_START, EXPECTED_END, freq="D")
observed_dates = pd.DatetimeIndex(df["date"].dropna().dt.normalize().unique())
missing_dates = expected_dates.difference(observed_dates)
unexpected_dates = observed_dates.difference(expected_dates)

integrity_summary = {
    "rows": int(len(df)),
    "source_columns": source_column_count,
    "duplicate_rows": duplicate_rows,
    "duplicate_dates": duplicate_dates,
    "invalid_dates": int(df["date"].isna().sum()),
    "source_missing_cells": int(df.isna().sum().sum()),
    "expected_days": int(len(expected_dates)),
    "unique_observed_dates": int(len(observed_dates)),
    "missing_calendar_dates": int(len(missing_dates)),
    "unexpected_dates": int(len(unexpected_dates)),
    "date_min": str(df["date"].min()),
    "date_max": str(df["date"].max()),
}
print("\n[1] DATASET INTEGRITY")
print(json.dumps(integrity_summary, indent=2))
if len(missing_dates):
    print("First missing dates:", missing_dates[:20].strftime("%Y-%m-%d").tolist())

# ============================================================
# 4. WEATHER RANGE SCREENING
# ============================================================

# Broad screening ranges only; these are not biological or regulatory limits.
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
    "soil_water_storage_mm_modelled": (0, TAW_MM),
    "depletion_fraction_modelled": (0, 1),
    "soil_moisture_vwc_pct_simulated": (0, 100),
}
range_rows = []
for col, (lo, hi) in screening_ranges.items():
    values = df[col]
    bad = (values < lo) | (values > hi)
    range_rows.append({
        "column": col,
        "lower_screen": lo,
        "upper_screen": hi,
        "below_lower_count": int((values < lo).sum()),
        "above_upper_count": int((values > hi).sum()),
        "out_of_range_count": int(bad.sum()),
        "minimum": values.min(),
        "maximum": values.max(),
    })
range_report = pd.DataFrame(range_rows)
range_report.to_csv(REPORT_DIR / "range_screening_report.csv", index=False)

temperature_inversions = int((df["tmax_c"] < df["tmin_c"]).sum())
print("\n[2] RANGE SCREENING")
print(range_report.to_string(index=False))
print("Days tmax < tmin:", temperature_inversions)

# ============================================================
# 5. ETc = Kc * ET0 CONSISTENCY
# ============================================================

df["etc_reconstructed_mm_day"] = KC_PROVISIONAL * df["et0_mm_day"]
df["etc_abs_error_mm_day"] = (
    df["etc_potential_mm_day_modelled"] - df["etc_reconstructed_mm_day"]
).abs()

etc_valid = df["etc_abs_error_mm_day"].dropna()
etc_summary = {
    "kc_configured_provisional": KC_PROVISIONAL,
    "mean_absolute_etc_error_mm_day": (
        float(etc_valid.mean()) if len(etc_valid) else None
    ),
    "maximum_absolute_etc_error_mm_day": (
        float(etc_valid.max()) if len(etc_valid) else None
    ),
    "days_error_above_1e-8": int((etc_valid > 1e-8).sum()),
}
print("\n[3] ETc CONSISTENCY")
print(json.dumps(etc_summary, indent=2))

# Implied Kc is diagnostic only; do not treat as agronomic validation.
valid_et0 = df["et0_mm_day"] > 1e-8
implied_kc = (
    df.loc[valid_et0, "etc_potential_mm_day_modelled"]
    / df.loc[valid_et0, "et0_mm_day"]
)
if len(implied_kc):
    print("Implied Kc descriptive statistics:")
    print(implied_kc.describe().to_string())

# ============================================================
# 6. WATER-BALANCE ARITHMETIC
# ============================================================

# effective_rainfall already equals rainfall minus runoff.
# Do not subtract runoff again here.
prev_storage = df["soil_water_storage_mm_modelled"].shift(1)
pre_clip_storage = (
    prev_storage
    + df["effective_rainfall_mm_modelled"]
    + df["irrigation_mm_simulated"]
    - df["actual_et_mm_day_modelled"]
    - df["drainage_mm_modelled"]
)
df["storage_reconstructed_mm"] = pre_clip_storage.clip(0, TAW_MM)
df["storage_abs_error_mm"] = (
    df["soil_water_storage_mm_modelled"] - df["storage_reconstructed_mm"]
).abs()

water_error = df["storage_abs_error_mm"].iloc[1:].dropna()
water_balance_summary = {
    "TAW_assumed_mm": float(TAW_MM),
    "days_compared": int(len(water_error)),
    "mean_absolute_error_mm": float(water_error.mean()) if len(water_error) else None,
    "maximum_absolute_error_mm": float(water_error.max()) if len(water_error) else None,
    "days_error_above_tolerance": int((water_error > WATER_BALANCE_TOL_MM).sum()),
    "tolerance_mm": WATER_BALANCE_TOL_MM,
    "interpretation": "Arithmetic consistency only; not field validation.",
}
print("\n[4] WATER-BALANCE ARITHMETIC")
print(json.dumps(water_balance_summary, indent=2))

water_error_rows = df.loc[
    df["storage_abs_error_mm"] > WATER_BALANCE_TOL_MM,
    ["date", "soil_water_storage_mm_modelled",
     "storage_reconstructed_mm", "storage_abs_error_mm"]
]
water_error_rows.to_csv(REPORT_DIR / "water_balance_mismatches.csv", index=False)

# ============================================================
# 7. SOIL-WATER DERIVED VARIABLE CONSISTENCY
# ============================================================

# Given model definitions:
# depletion = 1 - storage / TAW
# VWC = WP + (storage / TAW) * (FC - WP)
df["depletion_reconstructed"] = 1 - df["soil_water_storage_mm_modelled"] / TAW_MM
df["vwc_reconstructed_pct"] = (
    WP_VWC
    + (df["soil_water_storage_mm_modelled"] / TAW_MM)
    * (FC_VWC - WP_VWC)
) * 100

df["depletion_abs_error"] = (
    df["depletion_fraction_modelled"] - df["depletion_reconstructed"]
).abs()
df["vwc_abs_error_pct"] = (
    df["soil_moisture_vwc_pct_simulated"] - df["vwc_reconstructed_pct"]
).abs()

derived_summary = {
    "max_depletion_formula_error": float(df["depletion_abs_error"].max()),
    "max_vwc_formula_error_percentage_points": float(df["vwc_abs_error_pct"].max()),
    "storage_below_zero_count": int((df["soil_water_storage_mm_modelled"] < 0).sum()),
    "storage_above_TAW_count": int((df["soil_water_storage_mm_modelled"] > TAW_MM + 1e-8).sum()),
}
print("\n[5] DERIVED SOIL-WATER VARIABLES")
print(json.dumps(derived_summary, indent=2))

# ============================================================
# 8. ADDITIONAL MODEL LOGIC CHECKS
# ============================================================

# Effective rainfall should be rainfall minus runoff, floored at zero.
effective_rain_reconstructed = (
    df["rainfall_mm"] - df["runoff_mm_modelled"]
).clip(lower=0)
effective_rain_error = (
    df["effective_rainfall_mm_modelled"] - effective_rain_reconstructed
).abs()

# Actual ET should not exceed modelled potential ETc in this implementation.
# This is a model-logic check, not proof that ET estimates are scientifically valid.
actual_et_exceeds_etc = (
    df["actual_et_mm_day_modelled"]
    > df["etc_potential_mm_day_modelled"] + 1e-8
)

# Runoff cannot exceed rainfall; both values are expected to be non-negative.
runoff_exceeds_rain = (
    df["runoff_mm_modelled"] > df["rainfall_mm"] + 1e-8
)

additional_logic_summary = {
    "effective_rainfall_max_abs_error_mm": (
        float(effective_rain_error.max()) if len(effective_rain_error) else None
    ),
    "effective_rainfall_days_error_above_1e-8": int(
        (effective_rain_error > 1e-8).sum()
    ),
    "actual_ET_exceeds_potential_ETc_days": int(actual_et_exceeds_etc.sum()),
    "runoff_exceeds_rainfall_days": int(runoff_exceeds_rain.sum()),
}
print("\n[6] ADDITIONAL MODEL LOGIC CHECKS")
print(json.dumps(additional_logic_summary, indent=2))

# ============================================================
# 9. LABEL AND ACTION DISTRIBUTIONS
# ============================================================

stress_counts = df["water_stress_rule_derived"].value_counts(dropna=False)
action_counts = df["recommended_action_simulated"].value_counts(dropna=False)
stress_counts.rename_axis("stress_label").to_frame("count").to_csv(
    REPORT_DIR / "stress_label_distribution.csv"
)
action_counts.rename_axis("action").to_frame("count").to_csv(
    REPORT_DIR / "recommended_action_distribution.csv"
)

print("\n[6] STRESS LABEL DISTRIBUTION")
print(stress_counts.to_string())
print("\nRECOMMENDED ACTION DISTRIBUTION")
print(action_counts.to_string())

# Check that action matches the generator's rule mapping.
expected_action = df["water_stress_rule_derived"].map({
    "low": "continue_monitoring",
    "moderate": "recheck_soil_and_weather",
    "high": "consider_irrigation_if_field_conditions_confirm",
})
action_mismatch = int((expected_action != df["recommended_action_simulated"]).sum())
print("Stress/action mapping mismatches:", action_mismatch)

# ============================================================
# 10. WEATHER SOURCE CROSS-CHECK (IF WEATHER CSV EXISTS)
# ============================================================

weather_crosscheck = {"weather_file_found": weather is not None}
if weather is not None:
    weather_crosscheck.update({
        "weather_rows": int(len(weather)),
        "weather_duplicate_dates": int(weather["date"].duplicated().sum()),
        "weather_dataset_rows_match": bool(len(weather) == len(df)),
    })
    compare_cols = [
        "rainfall_mm", "tmax_c", "tmin_c",
        "solar_radiation_mj_m2_day", "relative_humidity_pct", "wind_speed_m_s",
    ]
    merged = df[["date"] + compare_cols].merge(
        weather[["date"] + compare_cols],
        on="date", how="outer", suffixes=("_dataset", "_weather"),
        indicator=True
    )
    weather_crosscheck["date_join_not_both_count"] = int((merged["_merge"] != "both").sum())
    for col in compare_cols:
        diff = (
            merged[f"{col}_dataset"] - merged[f"{col}_weather"]
        ).abs()
        weather_crosscheck[f"{col}_max_abs_difference"] = (
            float(diff.max()) if diff.notna().any() else None
        )

print("\n[7] WEATHER SOURCE CROSS-CHECK")
print(json.dumps(weather_crosscheck, indent=2))

# ============================================================
# 11. PLOTS
# ============================================================

plot_specs = [
    ("rainfall_mm", "Rainfall estimate (mm/day)"),
    ("tmax_c", "Maximum air temperature (°C)"),
    ("tmin_c", "Minimum air temperature (°C)"),
    ("et0_mm_day", "Estimated reference ET0 (mm/day)"),
    ("etc_potential_mm_day_modelled", "Modelled potential ETc (mm/day)"),
    ("soil_water_storage_mm_modelled", "Modelled soil-water storage (mm)"),
    ("depletion_fraction_modelled", "Modelled depletion fraction"),
]
for col, ylabel in plot_specs:
    fig, ax = plt.subplots(figsize=(12, 3.5))
    ax.plot(df["date"], df[col])
    ax.set_title(col)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Date")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(REPORT_DIR / f"{col}.png", dpi=140)
    plt.close(fig)

# Correlation matrix for original numeric dataset fields only.  Exclude
# temporary reconstruction/error columns and constant fields, which otherwise
# create artificial NaN rows and make the plot appear more informative than it is.
correlation_columns = [
    column for column in numeric_columns
    if df[column].nunique(dropna=True) > 1
]
numeric_df = df[correlation_columns]
corr = numeric_df.corr()
corr.to_csv(REPORT_DIR / "numeric_correlations.csv")

fig, ax = plt.subplots(figsize=(12, 9))
im = ax.imshow(corr, aspect="auto", vmin=-1, vmax=1)
fig.colorbar(im, ax=ax, label="Pearson correlation")
ax.set_xticks(range(len(corr.columns)))
ax.set_xticklabels(corr.columns, rotation=90)
ax.set_yticks(range(len(corr.index)))
ax.set_yticklabels(corr.index)
ax.set_title("CocoCare numeric feature correlations (exploratory)")
fig.tight_layout()
fig.savefig(REPORT_DIR / "numeric_correlation_heatmap.png", dpi=140)
plt.close(fig)

# ============================================================
# 12. SAVE SUMMARY REPORTS
# ============================================================

summary = {
    "dataset_path": str(DATASET_PATH),
    "dataset_shape": {"rows": int(df.shape[0]), "source_columns": source_column_count},
    "date_range": {"start": str(df["date"].min()), "end": str(df["date"].max())},
    "integrity": integrity_summary,
    "weather_range_screening": range_rows,
    "temperature_inversions": temperature_inversions,
    "etc_consistency": etc_summary,
    "water_balance_arithmetic": water_balance_summary,
    "derived_soil_water_consistency": derived_summary,
    "additional_model_logic_checks": additional_logic_summary,
    "stress_action_mismatches": action_mismatch,
    "weather_crosscheck": weather_crosscheck,
    "scientific_status": {
        "weather": "NASA POWER gridded estimates; not on-farm sensor observations",
        "Kc_and_soil_parameters": "provisional",
        "stress_labels": "rule-derived, not ground truth",
        "agronomic_validation": "not performed",
        "independent_field_validation": "not available",
    },
}
with open(REPORT_DIR / "evaluation_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, default=str)

# A compact pass/fail overview. These are pipeline checks, not science validation.
checks = {
    "expected_row_count": len(df) == len(expected_dates),
    "no_duplicate_dates": duplicate_dates == 0,
    "no_invalid_dates": df["date"].isna().sum() == 0,
    "no_missing_source_cells": integrity_summary["source_missing_cells"] == 0,
    "weather_range_screening_clean": int(range_report["out_of_range_count"].sum()) == 0,
    "effective_rainfall_consistent": additional_logic_summary["effective_rainfall_days_error_above_1e-8"] == 0,
    "runoff_not_above_rainfall": additional_logic_summary["runoff_exceeds_rainfall_days"] == 0,
    "actual_ET_not_above_potential_ETc": additional_logic_summary["actual_ET_exceeds_potential_ETc_days"] == 0,
    "ETc_formula_consistent": etc_summary["days_error_above_1e-8"] == 0,
    "water_balance_arithmetic_consistent": water_balance_summary["days_error_above_tolerance"] == 0,
    "derived_variables_consistent": (
        derived_summary["max_depletion_formula_error"] < 1e-8
        and derived_summary["max_vwc_formula_error_percentage_points"] < 1e-8
    ),
    "stress_action_mapping_consistent": action_mismatch == 0,
}
checks_df = pd.DataFrame([
    {"check": name, "passed": bool(value)}
    for name, value in checks.items()
])
checks_df.to_csv(REPORT_DIR / "pipeline_checklist.csv", index=False)

print("\n[8] PIPELINE CHECKLIST")
print(checks_df.to_string(index=False))
print("\nReports saved in:", REPORT_DIR.resolve())
print("Reminder: passing checks confirms integrity/internal consistency only, not agronomic accuracy.")
