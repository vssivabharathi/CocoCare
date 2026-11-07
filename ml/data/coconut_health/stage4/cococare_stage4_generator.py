#!/usr/bin/env python3
"""CocoCare Stage 4: 60-month-old coconut palm water-balance assessment.

Prototype only. Uses the Stage 2 daily weather baseline and provisional soil/crop
parameters. It does not provide field-validated irrigation recommendations.
"""
from pathlib import Path
import json, os, math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
STAGE2_DIR = Path(os.environ.get(
    "COCOCARE_STAGE2_OUTPUT_DIR",
    str(PROJECT_ROOT / "stage2" / "data" / "cococare_stage2_outputs")
)).expanduser().resolve()
OUT_DIR = Path(os.environ.get(
    "COCOCARE_STAGE4_OUTPUT_DIR",
    str(SCRIPT_DIR / "data" / "cococare_stage4_outputs")
)).expanduser().resolve()
WEATHER_FILE = STAGE2_DIR / "stage2_weather_input.csv"

LATITUDE = 10.7460
ELEVATION_M = 286.0
LOCATION = "Pollachi, Tamil Nadu, India"
VARIETY = "East Coast Tall"
PALM_AGE_MONTHS = 60.0

# Provisional parameters carried forward for controlled comparison only.
# They are NOT validated for a 60-month-old palm or this particular field.
KC = 0.70
ROOT_DEPTH_M = 0.45
FC_VWC = 0.23
WP_VWC = 0.10
INITIAL_AVAILABLE_FRACTION = 0.70
RUNOFF_FRACTION = 0.05
DEPLETION_TRIGGER = 0.50
REFILL_TARGET_FRACTION = 0.80
EFFECTIVE_WETTED_AREA_M2 = 1.0  # placeholder; measure/justify for actual system
TAW_MM = (FC_VWC - WP_VWC) * ROOT_DEPTH_M * 1000.0

def et0(row):
    """FAO-56-style PM approximation; ea is approximated from daily mean RH."""
    def esat(t):
        return 0.6108 * np.exp((17.27 * t) / (t + 237.3))
    tmax, tmin = float(row.tmax_c), float(row.tmin_c)
    rh = float(np.clip(row.relative_humidity_pct, 0, 100))
    u2 = max(0.0, float(row.wind_speed_m_s))
    rs = max(0.0, float(row.solar_radiation_mj_m2_day))
    tm = (tmax + tmin) / 2.0
    es = (esat(tmax) + esat(tmin)) / 2.0
    ea = rh / 100.0 * es
    delta = 4098.0 * esat(tm) / ((tm + 237.3) ** 2)
    pressure = 101.3 * (((293.0 - 0.0065 * ELEVATION_M) / 293.0) ** 5.26)
    gamma = 0.000665 * pressure
    doy = pd.Timestamp(row.date).dayofyear
    phi = math.radians(LATITUDE)
    dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)
    decl = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
    ws = math.acos(float(np.clip(-math.tan(phi) * math.tan(decl), -1, 1)))
    ra = (24 * 60 / math.pi) * 0.0820 * dr * (
        ws * math.sin(phi) * math.sin(decl)
        + math.cos(phi) * math.cos(decl) * math.sin(ws)
    )
    rso = (0.75 + 2e-5 * ELEVATION_M) * ra
    rns = (1 - 0.23) * rs
    ratio = float(np.clip(rs / rso, 0, 1)) if rso > 0 else 0.0
    rnl = 4.903e-9 * (
        ((tmax + 273.16)**4 + (tmin + 273.16)**4) / 2
    ) * (0.34 - 0.14 * math.sqrt(max(0, ea))) * (1.35 * ratio - 0.35)
    rn = rns - rnl
    num = 0.408 * delta * rn + gamma * (900 / (tm + 273)) * u2 * (es - ea)
    den = delta + gamma * (1 + 0.34 * u2)
    return max(0.0, num / den) if den > 0 else np.nan

def load_weather():
    if not WEATHER_FILE.exists():
        raise FileNotFoundError(
            f"Stage 2 weather input not found: {WEATHER_FILE}\n"
            "Set COCOCARE_STAGE2_OUTPUT_DIR to the existing Stage 2 output directory."
        )
    df = pd.read_csv(WEATHER_FILE)
    if "date" not in df:
        raise ValueError("stage2_weather_input.csv needs a date column")
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    if df["date"].isna().any() or df["date"].duplicated().any():
        raise ValueError("Weather input contains invalid or duplicate dates")
    df = df.sort_values("date").reset_index(drop=True)
    needed = [
        "rainfall_mm", "tmax_c", "tmin_c", "solar_radiation_mj_m2_day",
        "relative_humidity_pct", "wind_speed_m_s"
    ]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise ValueError(f"Weather input missing columns: {missing}")
    if df[needed].isna().any().any():
        raise ValueError("Weather input has missing required weather values")
    if (df["rainfall_mm"] < 0).any():
        raise ValueError("Rainfall contains negative values")
    if "et0_mm_day" not in df.columns or df["et0_mm_day"].isna().any():
        df["et0_mm_day"] = df.apply(et0, axis=1)
    if "etc_potential_mm_day_modelled" not in df.columns or df["etc_potential_mm_day_modelled"].isna().any():
        df["etc_potential_mm_day_modelled"] = KC * df["et0_mm_day"]
    if df.empty:
        raise ValueError("No weather rows found")
    return df

def simulate(weather, scenario):
    storage = TAW_MM * INITIAL_AVAILABLE_FRACTION
    rows = []
    for _, r in weather.iterrows():
        rain = max(0.0, float(r.rainfall_mm))
        runoff = rain * RUNOFF_FRACTION
        effective_rain = max(0.0, rain - runoff)
        etc = max(0.0, float(r.etc_potential_mm_day_modelled))
        depletion_before_irrigation = 1.0 - storage / TAW_MM
        irrigation_l = 0.0

        if scenario == "stage4_model_triggered_irrigation":
            if depletion_before_irrigation >= DEPLETION_TRIGGER:
                target_storage = TAW_MM * REFILL_TARGET_FRACTION
                needed_mm = max(0.0, target_storage - storage)
                irrigation_l = needed_mm * EFFECTIVE_WETTED_AREA_M2
        elif scenario != "stage4_weather_only":
            raise ValueError(f"Unknown scenario: {scenario}")

        irrigation_mm = irrigation_l / EFFECTIVE_WETTED_AREA_M2
        relative_available = float(np.clip(storage / TAW_MM, 0, 1))
        ks = float(np.clip(relative_available / max(0.01, 1 - DEPLETION_TRIGGER), 0, 1))
        actual_et = etc * ks
        pre_drainage = storage + effective_rain + irrigation_mm - actual_et
        drainage = max(0.0, pre_drainage - TAW_MM)
        storage = float(np.clip(pre_drainage - drainage, 0, TAW_MM))
        depletion = 1.0 - storage / TAW_MM
        stress = "low" if depletion < 0.30 else (
            "moderate" if depletion < DEPLETION_TRIGGER else "high"
        )
        action = "continue_monitoring" if stress == "low" else (
            "reassess_soil_and_weather" if stress == "moderate"
            else "assess_irrigation_need_if_field_conditions_confirm"
        )
        vwc = WP_VWC + (storage / TAW_MM) * (FC_VWC - WP_VWC)

        out = r.to_dict()
        out.update({
            "scenario": scenario,
            "simulated_palm_age_months": PALM_AGE_MONTHS,
            "effective_rainfall_mm_modelled": effective_rain,
            "runoff_mm_modelled": runoff,
            "irrigation_litres_per_palm_simulated": irrigation_l,
            "effective_wetted_area_m2_assumed": EFFECTIVE_WETTED_AREA_M2,
            "irrigation_mm_simulated": irrigation_mm,
            "actual_et_mm_day_modelled": actual_et,
            "drainage_mm_modelled": drainage,
            "soil_water_storage_mm_modelled": storage,
            "depletion_fraction_modelled": depletion,
            "depletion_before_irrigation_fraction_modelled": depletion_before_irrigation,
            "soil_moisture_vwc_pct_simulated": vwc * 100.0,
            "water_stress_rule_derived": stress,
            "recommended_action_simulated": action,
            "soil_temperature_c": np.nan,
            "soil_temperature_status": "not_modelled_no_defensible_method_or_measurements",
            "model_status": "prototype_provisional_parameters_not_field_validated",
            "stress_label_status": "rule_derived_not_ground_truth",
            "age_parameter_status": "60_month_assessment_age_specific_parameters_not_validated"
        })
        rows.append(out)
    return pd.DataFrame(rows)

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    weather = load_weather()
    weather.to_csv(OUT_DIR / "stage4_weather_baseline.csv", index=False)
    scenarios = {
        "stage4_weather_only": simulate(weather, "stage4_weather_only"),
        "stage4_model_triggered_irrigation": simulate(weather, "stage4_model_triggered_irrigation"),
    }
    summaries = []
    for name, df in scenarios.items():
        df.to_csv(OUT_DIR / f"{name}.csv", index=False)
        counts = df["water_stress_rule_derived"].value_counts()
        summaries.append({
            "scenario": name,
            "palm_age_months_assessed": PALM_AGE_MONTHS,
            "days": len(df),
            "total_irrigation_litres_per_palm_simulated": float(df["irrigation_litres_per_palm_simulated"].sum()),
            "total_irrigation_mm_simulated": float(df["irrigation_mm_simulated"].sum()),
            "mean_storage_mm_modelled": float(df["soil_water_storage_mm_modelled"].mean()),
            "mean_vwc_pct_simulated": float(df["soil_moisture_vwc_pct_simulated"].mean()),
            "low_stress_days_rule_derived": int(counts.get("low", 0)),
            "moderate_stress_days_rule_derived": int(counts.get("moderate", 0)),
            "high_stress_days_rule_derived": int(counts.get("high", 0)),
            "total_drainage_mm_modelled": float(df["drainage_mm_modelled"].sum()),
            "irrigation_events": int((df["irrigation_litres_per_palm_simulated"] > 0).sum())
        })
    summary = pd.DataFrame(summaries)
    summary.to_csv(OUT_DIR / "stage4_scenario_comparison.csv", index=False)
    combined = pd.concat(scenarios.values(), ignore_index=True)
    combined.to_csv(OUT_DIR / "stage4_combined_scenarios.csv", index=False)

    compare = scenarios["stage4_weather_only"][[
        "date", "soil_water_storage_mm_modelled", "soil_moisture_vwc_pct_simulated",
        "depletion_fraction_modelled"
    ]].rename(columns={
        "soil_water_storage_mm_modelled": "storage_weather_only_mm",
        "soil_moisture_vwc_pct_simulated": "vwc_weather_only_pct",
        "depletion_fraction_modelled": "depletion_weather_only"
    })
    triggered = scenarios["stage4_model_triggered_irrigation"][[
        "date", "soil_water_storage_mm_modelled", "soil_moisture_vwc_pct_simulated",
        "depletion_fraction_modelled", "irrigation_litres_per_palm_simulated"
    ]].rename(columns={
        "soil_water_storage_mm_modelled": "storage_model_triggered_mm",
        "soil_moisture_vwc_pct_simulated": "vwc_model_triggered_pct",
        "depletion_fraction_modelled": "depletion_model_triggered",
        "irrigation_litres_per_palm_simulated": "irrigation_model_triggered_litres"
    })
    compare = compare.merge(triggered, on="date", validate="one_to_one")
    compare.to_csv(OUT_DIR / "stage4_daily_scenario_comparison.csv", index=False)

    fig, axes = plt.subplots(3, 1, figsize=(15, 11), sharex=True)
    axes[0].plot(weather["date"], weather["rainfall_mm"])
    axes[0].set_ylabel("Rain (mm/day)")
    axes[0].set_title("CocoCare Stage 4: 60-month assessment")
    axes[1].plot(scenarios["stage4_weather_only"]["date"],
                 scenarios["stage4_weather_only"]["soil_water_storage_mm_modelled"],
                 label="Weather only")
    axes[1].plot(scenarios["stage4_model_triggered_irrigation"]["date"],
                 scenarios["stage4_model_triggered_irrigation"]["soil_water_storage_mm_modelled"],
                 label="Model-triggered (provisional)")
    axes[1].axhline(TAW_MM, linestyle="--", label="Assumed TAW")
    axes[1].set_ylabel("Storage (mm)")
    axes[1].legend()
    axes[2].plot(scenarios["stage4_model_triggered_irrigation"]["date"],
                 scenarios["stage4_model_triggered_irrigation"]["irrigation_litres_per_palm_simulated"],
                 label="Model-triggered irrigation")
    axes[2].set_ylabel("Irrigation (L/palm/day)")
    axes[2].set_xlabel("Date")
    axes[2].legend()
    for ax in axes:
        ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "stage4_scenario_comparison.png", dpi=160)
    plt.close(fig)

    metadata = {
        "project": "CocoCare",
        "stage": "Stage 4",
        "location": LOCATION,
        "variety": VARIETY,
        "palm_age_months_assessed": PALM_AGE_MONTHS,
        "input_weather_file": str(WEATHER_FILE),
        "days": len(weather),
        "parameters": {
            "kc_provisional": KC, "root_depth_m_assumed": ROOT_DEPTH_M,
            "field_capacity_vwc_assumed": FC_VWC, "wilting_point_vwc_assumed": WP_VWC,
            "initial_available_fraction_assumed": INITIAL_AVAILABLE_FRACTION,
            "runoff_fraction_assumed": RUNOFF_FRACTION,
            "depletion_trigger_provisional": DEPLETION_TRIGGER,
            "refill_target_fraction_provisional": REFILL_TARGET_FRACTION,
            "effective_wetted_area_m2_placeholder": EFFECTIVE_WETTED_AREA_M2,
            "TAW_mm_assumed": TAW_MM
        },
        "scenarios": [
            "stage4_weather_only",
            "stage4_model_triggered_irrigation"
        ],
        "model_trigger_rule": "At start of day, if modelled depletion >= 0.50, add water toward 0.80*assumed TAW.",
        "age_note": "This is a 60-month assessment label; parameters are not calibrated for this age or site.",
        "soil_temperature": "not modelled; output intentionally NaN",
        "interpretation_warning": "Simulation only. Automated checks do not establish field/agronomic validity.",
        "source_urls": {
            "NASA_POWER": "https://power.larc.nasa.gov/docs/services/api/temporal/daily/",
            "FAO56_ET0": "https://www.fao.org/4/X0490E/x0490e0b.htm",
            "FAO56_MAIN": "https://www.fao.org/4/x0490e/x0490e00.htm"
        }
    }
    (OUT_DIR / "stage4_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Stage 4 generated successfully: {OUT_DIR}")
    print(f"Days per scenario: {len(weather)} | Palm age assessed: {PALM_AGE_MONTHS:.0f} months | TAW assumed: {TAW_MM:.3f} mm")
    print(summary.to_string(index=False))
    print("Reminder: outputs are simulated and not field/agronomically validated.")

if __name__ == "__main__":
    main()
