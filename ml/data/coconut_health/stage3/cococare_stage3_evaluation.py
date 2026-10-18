#!/usr/bin/env python3
"""CocoCare Stage 3 output integrity and arithmetic evaluator."""
from pathlib import Path
import json, os
import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
OUT_DIR = Path(os.environ.get('COCOCARE_STAGE3_OUTPUT_DIR', str(SCRIPT_DIR/'data'/'cococare_stage3_outputs'))).expanduser().resolve()
SCENARIOS = ['weather_only','tnau_guided_irrigation','model_triggered_irrigation']
TOL = 1e-6
checks=[]
def record(name, passed, detail=''):
    checks.append({'check':name,'passed':bool(passed),'detail':str(detail)})

def main():
    metadata_path=OUT_DIR/'stage3_metadata.json'
    summary_path=OUT_DIR/'stage3_scenario_comparison.csv'
    combined_path=OUT_DIR/'stage3_combined_scenarios.csv'
    if not metadata_path.exists() or not summary_path.exists() or not combined_path.exists():
        raise FileNotFoundError(f"Stage 3 outputs missing in {OUT_DIR}. Run cococare_stage3_generator.py first.")
    meta=json.loads(metadata_path.read_text(encoding='utf-8'))
    summary=pd.read_csv(summary_path)
    combined=pd.read_csv(combined_path, parse_dates=['date'])
    expected_days=int(meta['days']); taw=float(meta['parameters']['TAW_mm'])
    required=['date','scenario','rainfall_mm','effective_rainfall_mm_modelled','runoff_mm_modelled','irrigation_litres_per_palm_simulated','irrigation_mm_simulated','actual_et_mm_day_modelled','drainage_mm_modelled','soil_water_storage_mm_modelled','depletion_fraction_modelled','soil_moisture_vwc_pct_simulated','water_stress_rule_derived','soil_temperature_c','soil_temperature_status']
    record('metadata_days_positive', expected_days>0, expected_days)
    record('TAW_positive', taw>0, taw)
    record('all_three_scenarios_present', set(summary.scenario)==set(SCENARIOS) and set(combined.scenario)==set(SCENARIOS), f"summary={sorted(summary.scenario.unique())}; combined={sorted(combined.scenario.unique())}")
    record('combined_rows_match_expected', len(combined)==expected_days*3, f'rows={len(combined)}, expected={expected_days*3}')
    record('summary_has_three_rows', len(summary)==3, len(summary))
    for name in SCENARIOS:
        p=OUT_DIR/f'stage3_{name}.csv'
        record(f'{name}_file_exists', p.exists(), p)
        if not p.exists(): continue
        df=pd.read_csv(p,parse_dates=['date'])
        missing=[c for c in required if c not in df]
        record(f'{name}_required_columns_present', not missing, missing)
        if missing: continue
        record(f'{name}_row_count',len(df)==expected_days,f'rows={len(df)} expected={expected_days}')
        record(f'{name}_dates_unique',not df.date.duplicated().any(),f'duplicates={int(df.date.duplicated().sum())}')
        record(f'{name}_date_sorted',df.date.is_monotonic_increasing,'dates monotonic')
        ordinary=df.drop(columns=['soil_temperature_c'],errors='ignore')
        miss=int(ordinary.isna().sum().sum())
        record(f'{name}_no_unexpected_missing_values',miss==0,f'missing cells excluding intentionally unmodelled soil temperature={miss}')
        st=df['soil_temperature_c']
        status=(df['soil_temperature_status']=='not_modelled_no_defensible_method_or_measurements').all()
        record(f'{name}_soil_temperature_intentionally_unmodelled',st.isna().all() and status,f'NaNs={int(st.isna().sum())}/{len(st)}; status_ok={status}')
        numeric=['rainfall_mm','effective_rainfall_mm_modelled','runoff_mm_modelled','irrigation_litres_per_palm_simulated','irrigation_mm_simulated','actual_et_mm_day_modelled','drainage_mm_modelled','soil_water_storage_mm_modelled','depletion_fraction_modelled','soil_moisture_vwc_pct_simulated']
        record(f'{name}_numeric_outputs_finite',np.isfinite(df[numeric].to_numpy(dtype=float)).all(),'numeric outputs finite')
        record(f'{name}_storage_within_bucket',df.soil_water_storage_mm_modelled.between(-TOL,taw+TOL).all(),f'min={df.soil_water_storage_mm_modelled.min():.4f}, max={df.soil_water_storage_mm_modelled.max():.4f}, TAW={taw:.4f}')
        record(f'{name}_depletion_range',df.depletion_fraction_modelled.between(-TOL,1+TOL).all(),f'min={df.depletion_fraction_modelled.min():.4f}, max={df.depletion_fraction_modelled.max():.4f}')
        record(f'{name}_irrigation_nonnegative',(df.irrigation_litres_per_palm_simulated>=-TOL).all(),'irrigation >= 0')
        record(f'{name}_irrigation_conversion',np.allclose(df.irrigation_mm_simulated,df.irrigation_litres_per_palm_simulated/float(meta['parameters']['effective_wetted_area_m2_placeholder']),atol=TOL,rtol=0),'mm = litres / assumed wetted area')
        fc=float(meta['parameters']['field_capacity_vwc']); wp=float(meta['parameters']['wilting_point_vwc'])
        expected_vwc=(wp+(df.soil_water_storage_mm_modelled/taw)*(fc-wp))*100
        record(f'{name}_VWC_mapping',np.allclose(df.soil_moisture_vwc_pct_simulated,expected_vwc,atol=1e-5,rtol=0),'VWC matches linear storage mapping')
        # Mass balance: first day's previous storage is initial fraction * TAW; later previous day's ending storage.
        initial=float(meta['parameters']['initial_available_fraction'])*taw
        prev=df.soil_water_storage_mm_modelled.shift(1)
        if len(prev): prev.iloc[0]=initial
        rhs=prev+df.effective_rainfall_mm_modelled+df.irrigation_mm_simulated-df.actual_et_mm_day_modelled-df.drainage_mm_modelled
        record(f'{name}_water_balance_closes',np.allclose(rhs,df.soil_water_storage_mm_modelled,atol=1e-5,rtol=0),f'max_abs_error={float(np.max(np.abs(rhs-df.soil_water_storage_mm_modelled))):.8f} mm')
        expected_stress=np.where(df.depletion_fraction_modelled<0.30,'low',np.where(df.depletion_fraction_modelled<float(meta['parameters']['depletion_trigger']),'moderate','high'))
        record(f'{name}_stress_labels_match_rules',np.array_equal(expected_stress,df.water_stress_rule_derived.to_numpy()),'labels recomputed from depletion thresholds')
        if name=='weather_only': record('weather_only_zero_irrigation',(df.irrigation_litres_per_palm_simulated.abs()<TOL).all(),'baseline should have zero irrigation')
        if name=='model_triggered_irrigation':
            triggered=df.irrigation_litres_per_palm_simulated> TOL
            record('model_triggered_irrigation_event_count_reported',True,f'events={int(triggered.sum())}; zero events can be valid if the configured depletion threshold is never reached')
            if triggered.any():
                record('model_triggered_irrigation_only_on_trigger', (df.loc[triggered,'depletion_before_irrigation_fraction_modelled']>=float(meta['parameters']['depletion_trigger'])-TOL).all(),'irrigation events occur at/above configured trigger')
                record('model_triggered_irrigation_respects_target', (df.loc[triggered,'irrigation_mm_simulated'] <= taw*(float(meta['parameters']['refill_target_fraction'])+TOL)).all(),'irrigation depth does not exceed target storage scale')
        row=summary.loc[summary.scenario==name]
        record(f'{name}_summary_row_exists',len(row)==1,f'rows={len(row)}')
        if len(row)==1:
            s=row.iloc[0]
            record(f'{name}_summary_days_match',int(s.days)==len(df),f"summary={s.days}; actual={len(df)}")
            record(f'{name}_summary_irrigation_matches',abs(float(s.total_irrigation_litres_per_palm_simulated)-df.irrigation_litres_per_palm_simulated.sum())<1e-5,'summary irrigation total matches daily file')
            record(f'{name}_summary_mean_storage_matches',abs(float(s.mean_storage_mm_modelled)-df.soil_water_storage_mm_modelled.mean())<1e-5,'summary mean storage matches daily file')
    checks_df=pd.DataFrame(checks)
    checks_df.to_csv(OUT_DIR/'stage3_evaluation_checks.csv',index=False)
    issues=checks_df.loc[~checks_df.passed].copy()
    issues.to_csv(OUT_DIR/'stage3_evaluation_issues.csv',index=False)
    report={
      'project':'CocoCare','stage':'Stage 3','output_directory':str(OUT_DIR),
      'checks_total':len(checks_df),'checks_passed':int(checks_df.passed.sum()),'checks_failed':int((~checks_df.passed).sum()),
      'overall_data_pipeline_pass':bool(checks_df.passed.all()),'issues':issues.to_dict(orient='records'),
      'interpretation_warning':'Passing checks indicates file integrity and arithmetic consistency only. It does not validate parameters, irrigation strategy, simulated moisture or stress labels against field observations.'
    }
    (OUT_DIR/'stage3_evaluation_summary.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
    print(f"Stage 3 evaluation: {report['checks_passed']}/{report['checks_total']} passed; {report['checks_failed']} failed")
    print(f"Report: {OUT_DIR/'stage3_evaluation_summary.json'}")
    if report['checks_failed']:
        print(issues.to_string(index=False))
        raise SystemExit(1)
    print('All checks passed. This is not field/agronomic validation.')

if __name__=='__main__': main()
