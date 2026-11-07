#!/usr/bin/env python3
"""CocoCare Stage 3: model-triggered irrigation scenario.

Uses the frozen Stage 2 weather input as the common weather baseline. Does not
modify Stage 2. All soil/crop parameters remain provisional; outputs are simulated.
"""
from pathlib import Path
import json, os, math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

SCRIPT_DIR = Path(__file__).resolve().parent
# Prefer the sibling Stage 2 output directory in the user's existing project.
# An explicit environment variable always takes precedence.
DEFAULT_STAGE2_DIR = SCRIPT_DIR.parent / "stage2" / "data" / "cococare_stage2_outputs"
STAGE2_DIR = Path(os.environ.get(
    "COCOCARE_STAGE2_OUTPUT_DIR", str(DEFAULT_STAGE2_DIR)
)).expanduser().resolve()
OUT_DIR = Path(os.environ.get(
    "COCOCARE_STAGE3_OUTPUT_DIR",
    str(SCRIPT_DIR / "data" / "cococare_stage3_outputs")
)).expanduser().resolve()
OUT_DIR.mkdir(parents=True, exist_ok=True)
WEATHER_FILE = STAGE2_DIR / "stage2_weather_input.csv"

LATITUDE, ELEVATION_M = 10.7460, 286.0
LOCATION, VARIETY = "Pollachi, Tamil Nadu, India", "East Coast Tall"
START_AGE_MONTHS = 18.0  # Stage 3 age as shown in the project diagram
KC = 0.70
ROOT_DEPTH_M = 0.45
FC_VWC, WP_VWC = 0.23, 0.10
INITIAL_AVAILABLE_FRACTION = 0.70
RUNOFF_FRACTION = 0.05
DEPLETION_TRIGGER = 0.50
# Triggered strategy fills root-zone storage toward 80% of TAW, not above it.
REFILL_TARGET_FRACTION = 0.80
# Explicitly provisional placeholder: must be measured/justified.
EFFECTIVE_WETTED_AREA_M2 = 1.0
TNAU_LITRES = 45.0
TNAU_INTERVAL_DAYS = 4
DRY_SEASON_MONTHS = [3, 4, 5]  # provisional project calendar, not a TNAU-prescribed month list
TAW_MM = (FC_VWC - WP_VWC) * ROOT_DEPTH_M * 1000.0


def et0(row):
    """Stage-2 FAO-56-style Penman-Monteith approximation; mean RH estimates ea."""
    def esat(t): return 0.6108 * np.exp((17.27 * t) / (t + 237.3))
    tmax, tmin = float(row.tmax_c), float(row.tmin_c)
    rh = float(np.clip(row.relative_humidity_pct, 0, 100))
    u2 = max(0.0, float(row.wind_speed_m_s)); rs = max(0.0, float(row.solar_radiation_mj_m2_day))
    tm = (tmax + tmin) / 2
    es = (esat(tmax) + esat(tmin)) / 2
    ea = rh / 100 * es
    delta = 4098 * esat(tm) / (tm + 237.3) ** 2
    pressure = 101.3 * (((293 - 0.0065 * ELEVATION_M) / 293) ** 5.26)
    gamma = 0.000665 * pressure
    doy = pd.Timestamp(row.date).dayofyear
    phi = math.radians(LATITUDE)
    dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)
    decl = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
    ws = math.acos(float(np.clip(-math.tan(phi) * math.tan(decl), -1, 1)))
    ra = (24 * 60 / math.pi) * 0.0820 * dr * (ws * math.sin(phi) * math.sin(decl) + math.cos(phi) * math.cos(decl) * math.sin(ws))
    rso = (0.75 + 2e-5 * ELEVATION_M) * ra
    rns = (1 - 0.23) * rs
    ratio = float(np.clip(rs / rso, 0, 1)) if rso > 0 else 0.0
    rnl = 4.903e-9 * (((tmax + 273.16)**4 + (tmin + 273.16)**4) / 2) * (0.34 - 0.14 * math.sqrt(max(0, ea))) * (1.35 * ratio - 0.35)
    rn = rns - rnl
    num = 0.408 * delta * rn + gamma * (900 / (tm + 273)) * u2 * (es - ea)
    den = delta + gamma * (1 + 0.34 * u2)
    return max(0.0, num / den) if den > 0 else np.nan


def load_weather():
    if not WEATHER_FILE.exists():
        raise FileNotFoundError(
            f"Stage 2 weather input not found: {WEATHER_FILE}\n"
            "Set COCOCARE_STAGE2_OUTPUT_DIR to your existing Stage 2 output directory."
        )
    df = pd.read_csv(WEATHER_FILE)
    if 'date' not in df: raise ValueError("stage2_weather_input.csv needs a date column")
    df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.normalize()
    if df.date.isna().any() or df.date.duplicated().any(): raise ValueError("Invalid or duplicate weather dates")
    df = df.sort_values('date').reset_index(drop=True)
    needed = ['rainfall_mm','tmax_c','tmin_c','solar_radiation_mj_m2_day','relative_humidity_pct','wind_speed_m_s']
    missing = [c for c in needed if c not in df]
    if missing: raise ValueError(f"Weather input missing columns: {missing}")
    if df[needed].isna().any().any(): raise ValueError("Weather input has missing required weather values")
    if 'et0_mm_day' not in df or df['et0_mm_day'].isna().any(): df['et0_mm_day'] = df.apply(et0, axis=1)
    if 'etc_potential_mm_day_modelled' not in df or df['etc_potential_mm_day_modelled'].isna().any(): df['etc_potential_mm_day_modelled'] = KC * df['et0_mm_day']
    if not len(df): raise ValueError("No weather rows found")
    return df


def simulate(weather, scenario):
    """Run a transparent daily bucket model; all outputs are simulated."""
    storage = TAW_MM * INITIAL_AVAILABLE_FRACTION
    rows = []
    first_date = pd.Timestamp(weather.date.iloc[0])
    for i, r in weather.iterrows():
        current_date = pd.Timestamp(r.date)
        elapsed_days = (current_date - first_date).days
        # Treat the first date as an 18-month-old palm and advance age by elapsed time.
        age_months = START_AGE_MONTHS + elapsed_days / 30.4375
        rain = max(0.0, float(r.rainfall_mm))
        runoff = rain * RUNOFF_FRACTION
        effective_rain = max(0.0, rain - runoff)
        etc = max(0.0, float(r.etc_potential_mm_day_modelled))
        depletion_before_irrigation = 1.0 - storage / TAW_MM
        irrigation_l = 0.0

        if scenario == 'tnau_guided_irrigation':
            # Illustrative comparison rule, not a full TNAU irrigation model.
            if (age_months < 24 and current_date.month in DRY_SEASON_MONTHS
                    and elapsed_days % TNAU_INTERVAL_DAYS == 0):
                irrigation_l = TNAU_LITRES
        elif scenario == 'model_triggered_irrigation':
            # Apply irrigation at the start of the day when depletion meets the trigger.
            if depletion_before_irrigation >= DEPLETION_TRIGGER:
                target_storage = TAW_MM * REFILL_TARGET_FRACTION
                needed_mm = max(0.0, target_storage - storage)
                irrigation_l = needed_mm * EFFECTIVE_WETTED_AREA_M2
        elif scenario != 'weather_only':
            raise ValueError(f"Unknown scenario {scenario}")

        irrigation_mm = irrigation_l / EFFECTIVE_WETTED_AREA_M2
        # Irrigation is applied before ET; compute stress coefficient from post-irrigation storage.
        storage_after_irrigation = min(TAW_MM, storage + irrigation_mm)
        relative_available = float(np.clip(storage_after_irrigation / TAW_MM, 0.0, 1.0))
        ks = float(np.clip(relative_available / max(0.01, 1.0 - DEPLETION_TRIGGER), 0.0, 1.0))
        actual_et = min(etc * ks, storage_after_irrigation + effective_rain)
        pre_drainage = storage + effective_rain + irrigation_mm - actual_et
        drainage = max(0.0, pre_drainage - TAW_MM)
        storage = float(np.clip(pre_drainage - drainage, 0.0, TAW_MM))
        depletion = 1.0 - storage / TAW_MM
        stress = 'low' if depletion < 0.30 else ('moderate' if depletion < DEPLETION_TRIGGER else 'high')
        action = ('continue_monitoring' if stress == 'low' else
                  'recheck_soil_and_weather' if stress == 'moderate' else
                  'consider_irrigation_if_field_conditions_confirm')
        vwc = WP_VWC + (storage / TAW_MM) * (FC_VWC - WP_VWC)
        row = r.to_dict()
        row.update({
            'scenario': scenario, 'simulated_palm_age_months': age_months,
            'effective_rainfall_mm_modelled': effective_rain, 'runoff_mm_modelled': runoff,
            'irrigation_litres_per_palm_simulated': irrigation_l,
            'effective_wetted_area_m2_assumed': EFFECTIVE_WETTED_AREA_M2,
            'irrigation_mm_simulated': irrigation_mm,
            'actual_et_mm_day_modelled': actual_et, 'drainage_mm_modelled': drainage,
            'soil_water_storage_mm_modelled': storage, 'depletion_fraction_modelled': depletion,
            'depletion_before_irrigation_fraction_modelled': depletion_before_irrigation,
            'soil_moisture_vwc_pct_simulated': vwc * 100,
            'water_stress_rule_derived': stress, 'recommended_action_simulated': action,
            'soil_temperature_c': np.nan,
            'soil_temperature_status': 'not_modelled_no_defensible_method_or_measurements',
            'model_status': 'prototype_provisional_parameters_not_field_validated',
            'stress_label_status': 'rule_derived_not_ground_truth'
        })
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    weather = load_weather()
    weather.to_csv(OUT_DIR / 'stage3_weather_baseline.csv', index=False)
    scenarios = {
        'weather_only': simulate(weather, 'weather_only'),
        'tnau_guided_irrigation': simulate(weather, 'tnau_guided_irrigation'),
        'model_triggered_irrigation': simulate(weather, 'model_triggered_irrigation'),
    }
    summaries = []
    for name, df in scenarios.items():
        df.to_csv(OUT_DIR / f'stage3_{name}.csv', index=False)
        counts = df.water_stress_rule_derived.value_counts()
        summaries.append({
            'scenario': name, 'days': len(df),
            'total_irrigation_litres_per_palm_simulated': float(df.irrigation_litres_per_palm_simulated.sum()),
            'total_irrigation_mm_simulated': float(df.irrigation_mm_simulated.sum()),
            'mean_storage_mm_modelled': float(df.soil_water_storage_mm_modelled.mean()),
            'mean_vwc_pct_simulated': float(df.soil_moisture_vwc_pct_simulated.mean()),
            'low_stress_days_rule_derived': int(counts.get('low',0)),
            'moderate_stress_days_rule_derived': int(counts.get('moderate',0)),
            'high_stress_days_rule_derived': int(counts.get('high',0)),
            'total_drainage_mm_modelled': float(df.drainage_mm_modelled.sum()),
            'irrigation_events': int((df.irrigation_litres_per_palm_simulated > 0).sum())
        })
    summary = pd.DataFrame(summaries)
    summary.to_csv(OUT_DIR / 'stage3_scenario_comparison.csv', index=False)
    combined = pd.concat(scenarios.values(), ignore_index=True)
    combined.to_csv(OUT_DIR / 'stage3_combined_scenarios.csv', index=False)
    # Pairwise date-aligned output for inspection.
    compare = scenarios['weather_only'][['date','soil_water_storage_mm_modelled','soil_moisture_vwc_pct_simulated','depletion_fraction_modelled']].rename(columns={
        'soil_water_storage_mm_modelled':'storage_weather_only_mm','soil_moisture_vwc_pct_simulated':'vwc_weather_only_pct','depletion_fraction_modelled':'depletion_weather_only'})
    for name in ['tnau_guided_irrigation','model_triggered_irrigation']:
        tmp = scenarios[name][['date','soil_water_storage_mm_modelled','soil_moisture_vwc_pct_simulated','depletion_fraction_modelled','irrigation_litres_per_palm_simulated']].rename(columns={
            'soil_water_storage_mm_modelled':f'storage_{name}_mm','soil_moisture_vwc_pct_simulated':f'vwc_{name}_pct','depletion_fraction_modelled':f'depletion_{name}','irrigation_litres_per_palm_simulated':f'irrigation_{name}_litres'})
        compare = compare.merge(tmp, on='date', validate='one_to_one')
    compare.to_csv(OUT_DIR / 'stage3_daily_scenario_comparison.csv', index=False)
    fig, axes = plt.subplots(3,1,figsize=(15,11),sharex=True)
    axes[0].plot(weather.date, weather.rainfall_mm); axes[0].set_ylabel('Rain (mm/day)'); axes[0].set_title('CocoCare Stage 3: three-scenario comparison')
    for name, label in [('weather_only','Weather only'),('tnau_guided_irrigation','TNAU-guided (illustrative)'),('model_triggered_irrigation','Model-triggered (provisional)')]:
        axes[1].plot(scenarios[name].date, scenarios[name].soil_water_storage_mm_modelled, label=label)
    axes[1].axhline(TAW_MM, linestyle='--', label='Assumed TAW'); axes[1].set_ylabel('Storage (mm)'); axes[1].legend()
    for name, label in [('tnau_guided_irrigation','TNAU-guided'),('model_triggered_irrigation','Model-triggered')]:
        axes[2].plot(scenarios[name].date, scenarios[name].irrigation_litres_per_palm_simulated, label=label)
    axes[2].set_ylabel('Irrigation (L/palm/day)'); axes[2].set_xlabel('Date'); axes[2].legend()
    for ax in axes: ax.grid(True, alpha=.25)
    fig.tight_layout(); fig.savefig(OUT_DIR / 'stage3_scenario_comparison.png', dpi=160); plt.close(fig)
    metadata = {
        'project':'CocoCare','stage':'Stage 3','location':LOCATION,'variety':VARIETY,
        'input_weather_file':str(WEATHER_FILE),'days':len(weather),
        'parameters':{'kc_provisional':KC,'root_depth_m':ROOT_DEPTH_M,'field_capacity_vwc':FC_VWC,'wilting_point_vwc':WP_VWC,
          'initial_available_fraction':INITIAL_AVAILABLE_FRACTION,'runoff_fraction':RUNOFF_FRACTION,'depletion_trigger':DEPLETION_TRIGGER,
          'refill_target_fraction':REFILL_TARGET_FRACTION,'effective_wetted_area_m2_placeholder':EFFECTIVE_WETTED_AREA_M2,
          'TAW_mm':TAW_MM,'age_months_at_first_weather_date':START_AGE_MONTHS},
        'model_trigger_rule':'At start of a day, if modelled depletion >= configured threshold, apply water toward target storage; irrigation L = irrigation depth mm * assumed wetted area m2. ET stress coefficient uses post-irrigation storage.',
        'tnau_scenario_note':'Illustrative comparison rule: 45 L on dates whose elapsed-day index is divisible by 4, only in provisional March-May months and simulated age <24 months. This is not a complete TNAU algorithm.',
        'soil_temperature':'not modelled; output intentionally NaN',
        'interpretation_warning':'Simulated scenarios only. Passing arithmetic checks is not field/agronomic validation. Parameters and wetted area are provisional.',
        'source_urls':{'NASA_POWER':'https://power.larc.nasa.gov/docs/services/api/temporal/daily/','FAO56_ET0':'https://www.fao.org/4/X0490E/x0490e0b.htm','TNAU_irrigation':'https://www.agritech.tnau.ac.in/expert_system/coconut/coconut/coconut_irrigation_management.html'}
    }
    (OUT_DIR/'stage3_metadata.json').write_text(json.dumps(metadata,indent=2), encoding='utf-8')
    print(f'Stage 3 generated successfully: {OUT_DIR}')
    print(f'Days per scenario: {len(weather)} | TAW assumed: {TAW_MM:.3f} mm')
    print(summary.to_string(index=False))
    print('Reminder: outputs are simulated and not field validated.')

if __name__ == '__main__': main()
