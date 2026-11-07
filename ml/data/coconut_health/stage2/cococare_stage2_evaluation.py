"""
CocoCare Stage 2 dataset evaluation
-----------------------------------
Evaluates the CSVs produced by cococare_stage2_generator.py.

This is a data-quality, arithmetic-consistency and scenario-comparison audit.
It does NOT establish agronomic accuracy or validate stress labels against real
field observations.

Usage:
    python cococare_stage2_evaluation.py

Optional:
    COCOCARE_STAGE2_OUTPUT_DIR=/path/to/cococare_stage2_outputs python cococare_stage2_evaluation.py
"""

from pathlib import Path
import json
import os
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get(
    "COCOCARE_STAGE2_OUTPUT_DIR",
    str(SCRIPT_DIR / "data" / "cococare_stage2_outputs"),
)).expanduser().resolve()
REPORT_DIR = DATA_DIR / "evaluation_reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

FILES = {
    "weather": DATA_DIR / "stage2_weather_input.csv",
    "weather_only": DATA_DIR / "stage2_weather_only.csv",
    "tnau_guided": DATA_DIR / "stage2_tnau_guided_irrigation.csv",
    "combined": DATA_DIR / "stage2_combined_scenarios.csv",
    "comparison": DATA_DIR / "stage2_scenario_comparison.csv",
    "daily_differences": DATA_DIR / "stage2_daily_scenario_differences.csv",
    "metadata": DATA_DIR / "stage2_metadata.json",
}

issues = []
checks = []

def record(name, passed, details=""):
    checks.append({"check": name, "passed": bool(passed), "details": str(details)})
    if not passed:
        issues.append({"check": name, "details": str(details)})

def read_csv(key):
    path = FILES[key]
    if not path.exists():
        record(f"file_exists_{key}", False, f"Missing file: {path}")
        return None
    try:
        return pd.read_csv(path)
    except Exception as exc:
        record(f"file_readable_{key}", False, repr(exc))
        return None

def numeric(df, col):
    if col not in df:
        record(f"column_exists_{col}", False, "Required column missing")
        return None
    converted = pd.to_numeric(df[col], errors="coerce")
    record(f"numeric_{col}", not converted.isna().any(),
           f"non-numeric or missing values={int(converted.isna().sum())}")
    return converted

def main():
    print("CocoCare Stage 2 evaluation")
    print("Input directory:", DATA_DIR)

    # File existence and metadata checks
    for key in FILES:
        if key == "metadata":
            if not FILES[key].exists():
                record("file_exists_metadata", False, str(FILES[key]))
        else:
            read_csv(key)
    if not FILES["metadata"].exists():
        metadata = {}
    else:
        try:
            metadata = json.loads(FILES["metadata"].read_text(encoding="utf-8"))
            record("metadata_valid_json", isinstance(metadata, dict), "JSON parsed")
        except Exception as exc:
            metadata = {}
            record("metadata_valid_json", False, repr(exc))

    weather = read_csv("weather")
    a = read_csv("weather_only")
    b = read_csv("tnau_guided")
    combined = read_csv("combined")
    summary = read_csv("comparison")
    daily_diff = read_csv("daily_differences")

    if any(x is None for x in [weather, a, b, combined, summary, daily_diff]):
        print("Evaluation stopped: one or more required files could not be loaded.")
        write_reports()
        return 2

    required_weather = [
        "date", "rainfall_mm", "tmax_c", "tmin_c",
        "solar_radiation_mj_m2_day", "relative_humidity_pct", "wind_speed_m_s",
        "et0_mm_day", "etc_potential_mm_day_modelled",
    ]
    required_output = [
        "date", "scenario", "rainfall_mm", "et0_mm_day",
        "etc_potential_mm_day_modelled", "effective_rainfall_mm_modelled",
        "runoff_mm_modelled", "irrigation_litres_per_palm_simulated",
        "irrigation_mm_simulated", "actual_et_mm_day_modelled",
        "drainage_mm_modelled", "soil_water_storage_mm_modelled",
        "depletion_fraction_modelled", "soil_moisture_vwc_pct_simulated",
        "water_stress_rule_derived", "recommended_action_simulated",
        "simulated_palm_age_months", "soil_temperature_c",
    ]
    for col in required_weather:
        record(f"weather_column_{col}", col in weather, "required weather/output input")
    for name, df in [("weather_only", a), ("tnau_guided", b)]:
        for col in required_output:
            record(f"{name}_column_{col}", col in df, "required output column")
        record(f"{name}_row_count_positive", len(df) > 0, f"rows={len(df)}")

    # Stop deep checks if essential columns are missing.
    essential = set(required_output) | {"date"}
    if not essential.issubset(set(a.columns)) or not essential.issubset(set(b.columns)):
        print("Evaluation stopped: essential output columns are missing.")
        write_reports()
        return 2

    # Date parsing, coverage, duplicates and scenario labels
    for name, df, expected_scenario in [
        ("weather_only", a, "weather_only"),
        ("tnau_guided", b, "tnau_guided_irrigation"),
    ]:
        dates = pd.to_datetime(df["date"], errors="coerce")
        record(f"{name}_valid_dates", not dates.isna().any(),
               f"invalid_dates={int(dates.isna().sum())}")
        record(f"{name}_unique_dates", not dates.duplicated().any(),
               f"duplicate_dates={int(dates.duplicated().sum())}")
        if dates.notna().all():
            record(f"{name}_sorted_dates", dates.is_monotonic_increasing, "dates ascending")
            record(f"{name}_scenario_label",
                   set(df["scenario"].dropna().unique()) == {expected_scenario},
                   f"labels={sorted(df['scenario'].dropna().unique().tolist())}")
    wa_dates = pd.to_datetime(weather["date"], errors="coerce")
    a_dates = pd.to_datetime(a["date"], errors="coerce")
    b_dates = pd.to_datetime(b["date"], errors="coerce")
    record("weather_and_scenarios_same_dates",
           wa_dates.reset_index(drop=True).equals(a_dates.reset_index(drop=True))
           and wa_dates.reset_index(drop=True).equals(b_dates.reset_index(drop=True)),
           f"weather={len(weather)}, baseline={len(a)}, irrigation={len(b)}")

    # Required numeric values and missingness
    weather_numeric = [
        "rainfall_mm", "tmax_c", "tmin_c", "solar_radiation_mj_m2_day",
        "relative_humidity_pct", "wind_speed_m_s", "et0_mm_day",
        "etc_potential_mm_day_modelled",
    ]
    output_numeric = [
        "rainfall_mm", "et0_mm_day", "etc_potential_mm_day_modelled",
        "effective_rainfall_mm_modelled", "runoff_mm_modelled",
        "irrigation_litres_per_palm_simulated", "irrigation_mm_simulated",
        "actual_et_mm_day_modelled", "drainage_mm_modelled",
        "soil_water_storage_mm_modelled", "depletion_fraction_modelled",
        "soil_moisture_vwc_pct_simulated", "simulated_palm_age_months",
    ]
    for col in weather_numeric:
        if col in weather:
            vals = pd.to_numeric(weather[col], errors="coerce")
            record(f"weather_no_missing_{col}", not vals.isna().any(),
                   f"missing/non-numeric={int(vals.isna().sum())}")
    for name, df in [("weather_only", a), ("tnau_guided", b)]:
        for col in output_numeric:
            if col in df:
                vals = pd.to_numeric(df[col], errors="coerce")
                record(f"{name}_no_missing_{col}", not vals.isna().any(),
                       f"missing/non-numeric={int(vals.isna().sum())}")
        record(f"{name}_no_duplicate_rows", not df.duplicated().any(),
               f"duplicate_rows={int(df.duplicated().sum())}")
        # Soil temperature is intentionally unmodelled in this version.
        # Exclude only that explicitly documented column from the source-data
        # completeness check; keep the dedicated soil-temperature audit below.
        intentionally_unmodelled = {"soil_temperature_c"}
        checked_columns = [
            column for column in df.columns
            if column not in intentionally_unmodelled
        ]
        unexpected_missing = int(df[checked_columns].isna().sum().sum())
        record(
            f"{name}_source_missing_cells_zero",
            unexpected_missing == 0,
            (
                f"unexpected_missing_cells={unexpected_missing}; "
                "soil_temperature_c is intentionally unmodelled and checked separately"
            ),
        )

    # Plausibility screens: flags are broad screening checks, not local validation.
    range_limits = {
        "rainfall_mm": (0, 500),
        "tmax_c": (-5, 60),
        "tmin_c": (-10, 50),
        "solar_radiation_mj_m2_day": (0, 45),
        "relative_humidity_pct": (0, 100),
        "wind_speed_m_s": (0, 50),
        "et0_mm_day": (0, 15),
        "etc_potential_mm_day_modelled": (0, 20),
        "soil_water_storage_mm_modelled": (0, None),
        "depletion_fraction_modelled": (0, 1),
        "soil_moisture_vwc_pct_simulated": (0, 100),
        "irrigation_litres_per_palm_simulated": (0, None),
        "irrigation_mm_simulated": (0, None),
        "actual_et_mm_day_modelled": (0, 20),
        "drainage_mm_modelled": (0, None),
    }
    for name, df in [("weather", weather), ("weather_only", a), ("tnau_guided", b)]:
        for col, (lo, hi) in range_limits.items():
            if col not in df:
                continue
            vals = pd.to_numeric(df[col], errors="coerce")
            ok = vals.notna() & (vals >= lo)
            if hi is not None:
                ok &= vals <= hi
            record(f"{name}_range_{col}", bool(ok.all()),
                   f"observed min={vals.min()}, max={vals.max()}, expected lower={lo}, upper={hi}")

    # Formula checks
    if "kc_provisional" in metadata.get("provisional_parameters", {}):
        kc = float(metadata["provisional_parameters"]["kc_provisional"])
        for name, df in [("weather_only", a), ("tnau_guided", b)]:
            expected_etc = kc * pd.to_numeric(df["et0_mm_day"], errors="coerce")
            err = (expected_etc - pd.to_numeric(df["etc_potential_mm_day_modelled"], errors="coerce")).abs()
            record(f"{name}_etc_formula", bool((err < 1e-6).all()),
                   f"max_abs_error={err.max()}")
    else:
        record("metadata_kc_available", False, "Cannot verify ETc without kc_provisional")

    soil = metadata.get("provisional_parameters", {})
    if all(k in soil for k in [
        "field_capacity_vwc_m3_m3", "wilting_point_vwc_m3_m3", "root_zone_depth_m"
    ]):
        taw = (
            (float(soil["field_capacity_vwc_m3_m3"])
             - float(soil["wilting_point_vwc_m3_m3"]))
            * float(soil["root_zone_depth_m"]) * 1000
        )
        record("metadata_taw_positive", taw > 0, f"TAW={taw}")
        for name, df in [("weather_only", a), ("tnau_guided", b)]:
            storage = pd.to_numeric(df["soil_water_storage_mm_modelled"], errors="coerce")
            record(f"{name}_storage_within_bucket", bool(storage.between(-1e-8, taw + 1e-8).all()),
                   f"TAW={taw}, storage min={storage.min()}, max={storage.max()}")
            depletion_expected = 1 - storage / taw
            dep_error = (depletion_expected - pd.to_numeric(df["depletion_fraction_modelled"], errors="coerce")).abs()
            record(f"{name}_depletion_formula", bool((dep_error < 1e-6).all()),
                   f"max_abs_error={dep_error.max()}")
            fc = float(soil["field_capacity_vwc_m3_m3"])
            wp = float(soil["wilting_point_vwc_m3_m3"])
            vwc_expected = (wp + storage / taw * (fc - wp)) * 100
            vwc_error = (vwc_expected - pd.to_numeric(df["soil_moisture_vwc_pct_simulated"], errors="coerce")).abs()
            record(f"{name}_vwc_formula", bool((vwc_error < 1e-5).all()),
                   f"max_abs_error_percentage_points={vwc_error.max()}")
            # Reconstruct the daily water balance from initial storage and fluxes.
            initial_fraction = float(soil["initial_available_water_fraction"])
            previous = taw * initial_fraction
            residuals = []
            for _, row in df.iterrows():
                effective_rain = float(row["effective_rainfall_mm_modelled"])
                irrigation = float(row["irrigation_mm_simulated"])
                aet = float(row["actual_et_mm_day_modelled"])
                drainage = float(row["drainage_mm_modelled"])
                predicted = previous + effective_rain + irrigation - aet - drainage
                observed = float(row["soil_water_storage_mm_modelled"])
                residuals.append(abs(predicted - observed))
                previous = observed
            max_resid = max(residuals) if residuals else 0
            record(f"{name}_water_balance_closure", max_resid < 1e-5,
                   f"max_abs_daily_residual_mm={max_resid}")

    # Irrigation schedule audit
    irrigation_l = pd.to_numeric(b["irrigation_litres_per_palm_simulated"], errors="coerce")
    age = pd.to_numeric(b["simulated_palm_age_months"], errors="coerce")
    dates_b = pd.to_datetime(b["date"])
    dry_months = metadata.get("irrigation_assumptions", {}).get("dry_season_months", [])
    interval = int(metadata.get("irrigation_assumptions", {}).get("interval_days", 4))
    amount = float(metadata.get("irrigation_assumptions", {}).get("litres_per_palm_per_event", 45))
    eligible = age.between(18, 24, inclusive="left") & dates_b.dt.month.isin(dry_months)
    scheduled = np.array([(i % interval == 0) for i in range(len(b))])
    expected_irrigation = np.where(eligible & scheduled, amount, 0.0)
    schedule_err = np.abs(irrigation_l.to_numpy() - expected_irrigation)
    record("tnau_scenario_matches_declared_schedule",
           bool(np.all(schedule_err < 1e-8)),
           f"irrigation event count={int((irrigation_l > 0).sum())}; max_abs_error_L={schedule_err.max() if len(schedule_err) else 0}")
    baseline_irrigation = pd.to_numeric(a["irrigation_litres_per_palm_simulated"], errors="coerce")
    record("weather_only_irrigation_is_zero",
           bool((baseline_irrigation.abs() < 1e-9).all()),
           f"total_L={baseline_irrigation.sum()}")
    wetted_area = float(metadata.get("irrigation_assumptions", {}).get("effective_wetted_area_m2", np.nan))
    if np.isfinite(wetted_area) and wetted_area > 0:
        expected_mm = irrigation_l / wetted_area
        err = (expected_mm - pd.to_numeric(b["irrigation_mm_simulated"], errors="coerce")).abs()
        record("irrigation_litres_to_mm_conversion",
               bool((err < 1e-6).all()), f"max_abs_error_mm={err.max()}")

    # Soil temperature is expected to remain explicitly unmodelled in this version.
    soil_temp_ok = True
    soil_temp_details = []
    for scenario_name, scenario_df in [("weather_only", a), ("tnau_guided", b)]:
        soil_temp_status = scenario_df.get(
            "soil_temperature_status", pd.Series(dtype=str)
        ).astype(str)
        soil_temp_values = pd.to_numeric(
            scenario_df.get("soil_temperature_c", pd.Series(dtype=float)),
            errors="coerce",
        )
        scenario_ok = (
            len(soil_temp_values) == len(scenario_df)
            and soil_temp_values.isna().all()
            and len(soil_temp_status) == len(scenario_df)
            and soil_temp_status.str.contains("not_modelled", case=False).all()
        )
        soil_temp_ok = soil_temp_ok and scenario_ok
        soil_temp_details.append(f"{scenario_name}={scenario_ok}")
    record(
        "soil_temperature_not_fabricated",
        soil_temp_ok,
        "Soil temperature is intentionally not estimated; " + ", ".join(soil_temp_details),
    )

    # Combined file and summary consistency
    expected_combined_rows = len(a) + len(b)
    record("combined_row_count", len(combined) == expected_combined_rows,
           f"expected={expected_combined_rows}, actual={len(combined)}")
    if "scenario" in combined:
        record("combined_scenario_counts",
               combined["scenario"].value_counts().to_dict() == {
                   "weather_only": len(a),
                   "tnau_guided_irrigation": len(b),
               },
               str(combined["scenario"].value_counts().to_dict()))
    record("comparison_has_two_scenarios", len(summary) == 2,
           f"rows={len(summary)}")
    if {"scenario", "total_irrigation_litres_per_palm_simulated"} <= set(summary.columns):
        s = summary.set_index("scenario")
        if {"weather_only", "tnau_guided_irrigation"} <= set(s.index):
            record("summary_baseline_irrigation_zero",
                   abs(float(s.loc["weather_only", "total_irrigation_litres_per_palm_simulated"])) < 1e-6,
                   "summary total")
            record("summary_irrigation_scenario_nonnegative",
                   float(s.loc["tnau_guided_irrigation", "total_irrigation_litres_per_palm_simulated"]) >= 0,
                   "summary total")
            expected_litres = float(irrigation_l.sum())
            record("summary_irrigation_total_matches_daily",
                   abs(expected_litres - float(s.loc["tnau_guided_irrigation", "total_irrigation_litres_per_palm_simulated"])) < 1e-6,
                   f"daily sum={expected_litres}")
    if "storage_difference_mm_tnau_minus_weather" in daily_diff:
        expected_diff = (
            pd.to_numeric(b["soil_water_storage_mm_modelled"], errors="coerce").to_numpy()
            - pd.to_numeric(a["soil_water_storage_mm_modelled"], errors="coerce").to_numpy()
        )
        observed_diff = pd.to_numeric(daily_diff["storage_difference_mm_tnau_minus_weather"], errors="coerce").to_numpy()
        record("daily_difference_storage_matches",
               len(expected_diff) == len(observed_diff)
               and np.allclose(expected_diff, observed_diff, atol=1e-6, rtol=0),
               f"rows={len(observed_diff)}")

    # Compare stress labels and storage, but do not call them truth.
    stress_rows = []
    for name, df in [("weather_only", a), ("tnau_guided_irrigation", b)]:
        counts = df["water_stress_rule_derived"].value_counts()
        stress_rows.append({
            "scenario": name,
            "days": len(df),
            "irrigation_litres_per_palm_total": pd.to_numeric(
                df["irrigation_litres_per_palm_simulated"], errors="coerce"
            ).sum(),
            "mean_storage_mm": pd.to_numeric(df["soil_water_storage_mm_modelled"], errors="coerce").mean(),
            "mean_vwc_pct_simulated": pd.to_numeric(df["soil_moisture_vwc_pct_simulated"], errors="coerce").mean(),
            "low_stress_days_rule_derived": int(counts.get("low", 0)),
            "moderate_stress_days_rule_derived": int(counts.get("moderate", 0)),
            "high_stress_days_rule_derived": int(counts.get("high", 0)),
        })
    stress_summary = pd.DataFrame(stress_rows)
    stress_summary.to_csv(REPORT_DIR / "stress_and_scenario_summary.csv", index=False)

    # Save checks, issues and summary metrics.
    check_df = pd.DataFrame(checks)
    check_df.to_csv(REPORT_DIR / "evaluation_checks.csv", index=False)
    issues_df = pd.DataFrame(issues, columns=["check", "details"])
    issues_df.to_csv(REPORT_DIR / "evaluation_issues.csv", index=False)

    summary_json = {
        "project": "CocoCare",
        "stage": "Stage 2",
        "data_directory": str(DATA_DIR),
        "checks_total": len(checks),
        "checks_passed": int(sum(c["passed"] for c in checks)),
        "checks_failed": int(sum(not c["passed"] for c in checks)),
        "overall_data_pipeline_pass": bool(checks) and all(c["passed"] for c in checks),
        "issues": issues,
        "interpretation_warning": (
            "Passing checks indicates data integrity and arithmetic consistency only. "
            "It does not validate irrigation assumptions, simulated moisture, soil temperature, "
            "stress labels or agronomic recommendations against field observations."
        ),
        "scenario_summary": stress_summary.to_dict(orient="records"),
    }
    (REPORT_DIR / "evaluation_summary.json").write_text(
        json.dumps(summary_json, indent=2, default=str), encoding="utf-8"
    )

    # Plot scenario comparison.
    fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True)
    axes[0].plot(pd.to_datetime(a["date"]), a["rainfall_mm"])
    axes[0].set_ylabel("Rain (mm/day)")
    axes[0].set_title("Stage 2 evaluation: weather and scenario comparison")
    axes[1].plot(pd.to_datetime(a["date"]), a["soil_water_storage_mm_modelled"], label="Weather only")
    axes[1].plot(pd.to_datetime(b["date"]), b["soil_water_storage_mm_modelled"], label="TNAU-guided scenario")
    axes[1].set_ylabel("Storage (mm)")
    axes[1].legend()
    axes[2].plot(pd.to_datetime(b["date"]), b["irrigation_litres_per_palm_simulated"])
    axes[2].set_ylabel("Irrigation (L/palm/day)")
    axes[2].set_xlabel("Date")
    for ax in axes:
        ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plot_path = REPORT_DIR / "stage2_evaluation_plot.png"
    plt.savefig(plot_path, dpi=160)
    plt.close(fig)

    print("\n=== CocoCare Stage 2 evaluation summary ===")
    print(f"Checks passed: {summary_json['checks_passed']}/{summary_json['checks_total']}")
    print("Pipeline checks:", "PASS" if summary_json["overall_data_pipeline_pass"] else "FAIL")
    print("\nScenario summary:")
    print(stress_summary.to_string(index=False))
    if issues:
        print("\nFailed checks:")
        for item in issues:
            print(f"- {item['check']}: {item['details']}")
    print("\nReports written to:", REPORT_DIR)
    print("- evaluation_summary.json")
    print("- evaluation_checks.csv")
    print("- evaluation_issues.csv")
    print("- stress_and_scenario_summary.csv")
    print("- stage2_evaluation_plot.png")
    print("\nReminder: this audit does not establish field/agronomic validity.")
    return 0 if summary_json["overall_data_pipeline_pass"] else 1


def write_reports():
    pd.DataFrame(checks).to_csv(REPORT_DIR / "evaluation_checks.csv", index=False)
    pd.DataFrame(issues, columns=["check", "details"]).to_csv(
        REPORT_DIR / "evaluation_issues.csv", index=False
    )
    (REPORT_DIR / "evaluation_summary.json").write_text(
        json.dumps({
            "project": "CocoCare",
            "stage": "Stage 2",
            "checks_total": len(checks),
            "checks_passed": int(sum(c["passed"] for c in checks)),
            "checks_failed": int(sum(not c["passed"] for c in checks)),
            "issues": issues,
        }, indent=2), encoding="utf-8"
    )

if __name__ == "__main__":
    sys.exit(main())

