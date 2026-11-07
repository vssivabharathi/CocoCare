"""One-at-a-time exploratory sensitivity analysis for the Stage 1 bucket model.

This is scenario analysis, not calibration or independent validation.  The
weather snapshot is fixed; each scenario changes one provisional parameter.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
BASE = ROOT / "audited_run"
DATA = pd.read_csv(BASE / "stage1_hybrid_dataset.csv", parse_dates=["date"])

BASELINE = {"kc": .70, "fc": .23, "wp": .10, "root_depth_m": .45,
            "initial_available_water_fraction": .70, "runoff_fraction": .05,
            "depletion_trigger": .50}
SCENARIOS = {
    "baseline": BASELINE,
    "kc_low_exploratory": {**BASELINE, "kc": .55},
    "kc_high_exploratory": {**BASELINE, "kc": .85},
    "available_water_low_exploratory": {**BASELINE, "fc": .18, "wp": .10},
    "available_water_high_exploratory": {**BASELINE, "fc": .30, "wp": .08},
    "root_depth_low_exploratory": {**BASELINE, "root_depth_m": .30},
    "root_depth_high_exploratory": {**BASELINE, "root_depth_m": .60},
    "initial_storage_low_exploratory": {**BASELINE, "initial_available_water_fraction": .40},
    "initial_storage_high_exploratory": {**BASELINE, "initial_available_water_fraction": .90},
    "runoff_zero_exploratory": {**BASELINE, "runoff_fraction": 0.0},
    "runoff_high_exploratory": {**BASELINE, "runoff_fraction": .15},
    "trigger_early_exploratory": {**BASELINE, "depletion_trigger": .40},
    "trigger_late_exploratory": {**BASELINE, "depletion_trigger": .60},
}


def simulate(p):
    taw = (p["fc"] - p["wp"]) * p["root_depth_m"] * 1000
    storage = taw * p["initial_available_water_fraction"]
    rows = []
    for row in DATA.itertuples(index=False):
        effective_rain = max(0.0, row.rainfall_mm * (1 - p["runoff_fraction"]))
        etc = row.et0_mm_day * p["kc"]
        ks = np.clip((storage / taw) / max(.01, 1 - p["depletion_trigger"]), 0, 1)
        actual_et = etc * ks
        pre_drainage = storage + effective_rain - actual_et
        drainage = max(0.0, pre_drainage - taw)
        storage = np.clip(pre_drainage - drainage, 0, taw)
        depletion = 1 - storage / taw
        stress = "low" if depletion < .30 else ("moderate" if depletion < p["depletion_trigger"] else "high")
        rows.append((storage, depletion, stress))
    result = pd.DataFrame(rows, columns=["storage_mm", "depletion_fraction", "stress"])
    counts = result["stress"].value_counts()
    capacity_days = int((result.storage_mm >= taw - 1e-8).sum())
    near_depletion_days = int((result.depletion_fraction >= .95).sum())
    n_days = len(result)
    return {
        **p, "taw_mm": taw, "mean_storage_mm": result.storage_mm.mean(),
        "minimum_storage_mm": result.storage_mm.min(),
        "maximum_storage_mm": result.storage_mm.max(),
        "mean_depletion_fraction": result.depletion_fraction.mean(),
        "storage_capacity_days": capacity_days,
        "storage_capacity_pct": 100 * capacity_days / n_days,
        "near_complete_depletion_days": near_depletion_days,
        "near_complete_depletion_pct": 100 * near_depletion_days / n_days,
        "low_days": int(counts.get("low", 0)), "moderate_days": int(counts.get("moderate", 0)),
        "high_days": int(counts.get("high", 0)),
        "low_pct": 100 * int(counts.get("low", 0)) / n_days,
        "moderate_pct": 100 * int(counts.get("moderate", 0)) / n_days,
        "high_pct": 100 * int(counts.get("high", 0)) / n_days,
        "action_continue_monitoring_days": int(counts.get("low", 0)),
        "action_recheck_days": int(counts.get("moderate", 0)),
        "action_consider_irrigation_days": int(counts.get("high", 0)),
    }


results = pd.DataFrame({name: simulate(params) for name, params in SCENARIOS.items()}).T
results.index.name = "scenario"
results.to_csv(ROOT / "sensitivity_analysis.csv")
(ROOT / "sensitivity_analysis_metadata.json").write_text(json.dumps({
    "method": "one-at-a-time exploratory scenarios using the audited frozen weather snapshot",
    "not_validation": True,
    "parameter_evidence_status": "All ranges are deliberately labelled exploratory; they are not claimed as matched evidence for 18-month East Coast Tall coconut at Pollachi. Kc scenarios bracket the 0.70 prototype but are not a recommendation.",
    "definitions": {"storage_capacity": "storage >= TAW minus 1e-8 mm", "near_complete_depletion": "depletion fraction >= 0.95"},
    "fixed_model_features": "zero irrigation weather-only scenario; full overflow drainage; simplified storage-based Ks",
}, indent=2))
print(results.to_string())
