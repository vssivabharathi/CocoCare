#!/usr/bin/env python3
"""CocoCare Stage 4 evaluator. Checks integrity/arithmetic, not agronomic validity."""
from pathlib import Path
import json, os, math
import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
OUT_DIR = Path(os.environ.get(
    "COCOCARE_STAGE4_OUTPUT_DIR",
    str(SCRIPT_DIR / "data" / "cococare_stage4_outputs")
)).expanduser().resolve()
SCENARIOS = ["stage4_weather_only", "stage4_model_triggered_irrigation"]
TAW_MM = (0.23 - 0.10) * 0.45 * 1000.0
WETTED_AREA = 1.0
AGE_MONTHS = 60.0
checks = []

def record(name, passed, detail=""):
    checks.append({"check": name, "passed": bool(passed), "detail": str(detail)})

def close(a, b, tol=1e-6):
    return bool(np.isclose(a, b, atol=tol, rtol=1e-6))

def main():
    if not OUT_DIR.exists():
        raise FileNotFoundError(f"Stage 4 output directory not found: {OUT_DIR}. Run the generator first.")
    frames = {}
    for name in SCENARIOS:
        path = OUT_DIR / f"{name}.csv"
        record(f"{name}_file_exists", path.exists(), path)
        if not path.exists():
            continue
        df = pd.read_csv(path)
        frames[name] = df
        record(f"{name}_nonempty", len(df) > 0, f"rows={len(df)}")
        record(f"{name}_expected_age", "simulated_palm_age_months" in df and close(df["simulated_palm_age_months"].iloc[0], AGE_MONTHS) if len(df) else False, "expected 60-month assessment label")
        record(f"{name}_no_duplicate_dates", "date" in df and not pd.to_datetime(df["date"], errors="coerce").duplicated().any(), "date uniqueness")
        record(f"{name}_valid_dates", "date" in df and pd.to_datetime(df["date"], errors="coerce").notna().all(), "dates parse successfully")
        record(f"{name}_no_missing_required", not df[["date","rainfall_mm","et0_mm_day","etc_potential_mm_day_modelled","irrigation_litres_per_palm_simulated","irrigation_mm_simulated","soil_water_storage_mm_modelled","depletion_fraction_modelled","soil_moisture_vwc_pct_simulated","water_stress_rule_derived"]].isna().any().any(), "excludes intentionally unmodelled soil_temperature_c")
        record(f"{name}_nonnegative_rain", (df["rainfall_mm"] >= 0).all(), "rainfall >= 0")
        record(f"{name}_nonnegative_irrigation", (df["irrigation_litres_per_palm_simulated"] >= 0).all() and (df["irrigation_mm_simulated"] >= 0).all(), "irrigation >= 0")
        record(f"{name}_storage_bounds", ((df["soil_water_storage_mm_modelled"] >= -1e-8) & (df["soil_water_storage_mm_modelled"] <= TAW_MM + 1e-6)).all(), f"0 <= storage <= {TAW_MM}")
        record(f"{name}_depletion_bounds", ((df["depletion_fraction_modelled"] >= -1e-8) & (df["depletion_fraction_modelled"] <= 1 + 1e-8)).all(), "depletion in [0,1]")
        record(f"{name}_vwc_bounds", ((df["soil_moisture_vwc_pct_simulated"] >= 10 - 1e-6) & (df["soil_moisture_vwc_pct_simulated"] <= 23 + 1e-6)).all(), "VWC between assumed WP and FC percentages")
        record(f"{name}_irrigation_conversion", np.allclose(df["irrigation_mm_simulated"], df["irrigation_litres_per_palm_simulated"] / WETTED_AREA, atol=1e-6, rtol=1e-6), "mm = litres / assumed wetted area")
        expected_stress = np.where(df["depletion_fraction_modelled"] < 0.30, "low",
                          np.where(df["depletion_fraction_modelled"] < 0.50, "moderate", "high"))
        record(f"{name}_stress_labels_match_rules", np.array_equal(df["water_stress_rule_derived"].astype(str).to_numpy(), expected_stress), "labels follow configured thresholds")
        record(f"{name}_soil_temperature_intentionally_unmodelled", df["soil_temperature_c"].isna().all() and (df["soil_temperature_status"] == "not_modelled_no_defensible_method_or_measurements").all(), "NaN intentional; status must be explicit")
        record(f"{name}_prototype_status_present", (df["model_status"] == "prototype_provisional_parameters_not_field_validated").all(), "prototype warning present")
        record(f"{name}_drainage_nonnegative", (df["drainage_mm_modelled"] >= 0).all(), "drainage >= 0")
        record(f"{name}_age_parameter_warning", (df["age_parameter_status"] == "60_month_assessment_age_specific_parameters_not_validated").all(), "age-specific parameters not validated")

    if len(frames) == len(SCENARIOS):
        a, b = (frames[x] for x in SCENARIOS)
        record("scenario_row_counts_equal", len(a) == len(b), f"{len(a)} vs {len(b)}")
        da = pd.to_datetime(a["date"], errors="coerce").reset_index(drop=True)
        db = pd.to_datetime(b["date"], errors="coerce").reset_index(drop=True)
        record("scenario_dates_identical", da.equals(db), "same weather-date baseline")
        record("weather_only_has_zero_irrigation", close(a["irrigation_litres_per_palm_simulated"].sum(), 0), "no-irrigation baseline")
        # If the trigger never occurs, zero events is allowed; otherwise all events must be positive.
        events = b["irrigation_litres_per_palm_simulated"] > 0
        record("triggered_events_positive", (b.loc[events, "irrigation_litres_per_palm_simulated"] > 0).all(), f"events={int(events.sum())}")
        record("trigger_rule_applied_only_at_threshold", (b.loc[events, "depletion_before_irrigation_fraction_modelled"] >= 0.50 - 1e-8).all(), "events must meet depletion threshold")
        record("combined_file_exists", (OUT_DIR / "stage4_combined_scenarios.csv").exists(), "combined scenario CSV")
        record("comparison_file_exists", (OUT_DIR / "stage4_scenario_comparison.csv").exists(), "summary comparison CSV")
        record("daily_comparison_file_exists", (OUT_DIR / "stage4_daily_scenario_comparison.csv").exists(), "date-aligned comparison CSV")
        record("plot_file_exists", (OUT_DIR / "stage4_scenario_comparison.png").exists(), "comparison plot")
        meta_path = OUT_DIR / "stage4_metadata.json"
        record("metadata_file_exists", meta_path.exists(), "metadata JSON")
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                record("metadata_age_is_60", close(meta.get("palm_age_months_assessed", -1), AGE_MONTHS), str(meta.get("palm_age_months_assessed")))
                record("metadata_days_match", int(meta.get("days", -1)) == len(a), f"metadata days={meta.get('days')}, rows={len(a)}")
                record("metadata_has_validation_warning", "field" in meta.get("interpretation_warning", "").lower() and ("validity" in meta.get("interpretation_warning", "").lower() or "validation" in meta.get("interpretation_warning", "").lower()), meta.get("interpretation_warning", ""))
            except Exception as e:
                record("metadata_json_valid", False, repr(e))
    summary_path = OUT_DIR / "stage4_scenario_comparison.csv"
    if summary_path.exists() and len(frames) == len(SCENARIOS):
        summary = pd.read_csv(summary_path)
        record("summary_has_two_scenarios", len(summary) == 2, f"rows={len(summary)}")
        record("summary_irrigation_totals_match", all(
            close(float(summary.loc[summary.scenario == name, "total_irrigation_litres_per_palm_simulated"].iloc[0]),
                  float(frames[name]["irrigation_litres_per_palm_simulated"].sum()))
            for name in SCENARIOS
        ), "summary totals match daily files")
    passed = sum(x["passed"] for x in checks)
    failed = len(checks) - passed
    report = {
        "project": "CocoCare", "stage": "Stage 4",
        "output_directory": str(OUT_DIR),
        "checks_total": len(checks), "checks_passed": passed, "checks_failed": failed,
        "overall_data_pipeline_pass": failed == 0,
        "interpretation_warning": "Passing checks establishes internal consistency only, not field/agronomic validation.",
        "checks": checks,
        "issues": [x for x in checks if not x["passed"]]
    }
    (OUT_DIR / "stage4_evaluation_summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    pd.DataFrame(checks).to_csv(OUT_DIR / "stage4_evaluation_checks.csv", index=False)
    pd.DataFrame(report["issues"]).to_csv(OUT_DIR / "stage4_evaluation_issues.csv", index=False)
    print(f"Stage 4 evaluation: {passed}/{len(checks)} passed; {failed} failed")
    print(f"Report: {OUT_DIR / 'stage4_evaluation_summary.json'}")
    if failed:
        for issue in report["issues"]:
            print(f"FAIL: {issue['check']} — {issue['detail']}")
        raise SystemExit(1)
    print("All checks passed. This is not field/agronomic validation.")

if __name__ == "__main__":
    main()
