# CocoCare
AI-powered coconut farming platform combining disease detection, farm financial management, intelligent market assistance, farmer-to-buyer commerce, and agricultural workforce discovery.

## Stage 1 hybrid water-balance prototype

The Stage 1 pipeline is in [ml/data/coconut_health](ml/data/coconut_health). It combines a saved NASA POWER daily weather snapshot with modelled reference ET, crop ET, and a root-zone bucket. It is a prototype: NASA POWER is gridded weather, soil moisture is simulated, and stress labels/actions are rule-derived rather than measured ground truth or field-validated recommendations.

Main files:

- `cococare_stage1_final_generator.py` — generator and source metadata.
- `evaluvation /cococare_stage1_evaluation.py` — integrity, arithmetic, plots, and reports.
- `data/cococare_stage1_outputs/` — preserved original outputs.
- `audit_artifacts/audited_run/` — reproducible audited run using the preserved weather snapshot.
- `audit_artifacts/sensitivity_analysis.csv` — exploratory one-at-a-time scenarios, not calibration.
- `audit_artifacts/sensitivity_analysis_metadata.json` — scenario definitions, including capacity and near-depletion metrics.
- `audit_artifacts/CocoCare_Stage1_Scientific_Methodology_and_Validation.docx` — full audit report.

### Reproduce the audited run

Create an environment containing `pandas`, `numpy`, `matplotlib`, and `requests`, then run from the repository root:

```bash
export COCOCARE_OUTPUT_DIR="$PWD/ml/data/coconut_health/audit_artifacts/audited_run"
export COCOCARE_WEATHER_CSV="$PWD/ml/data/coconut_health/data/cococare_stage1_outputs/coimbatore_nasa_power_weather.csv"
export MPLBACKEND=Agg
python ml/data/coconut_health/cococare_stage1_final_generator.py
python 'ml/data/coconut_health/evaluvation /cococare_stage1_evaluation.py'
python ml/data/coconut_health/audit_artifacts/run_sensitivity_analysis.py
python -m unittest discover -s ml/data/coconut_health/tests -v
```

Omit `COCOCARE_WEATHER_CSV` only when intentionally downloading a fresh NASA POWER input. A new download can change results; retain its CSV and request provenance before comparing runs.

### Important limitations

- `Kc=0.70`, field capacity, wilting point, root-zone depth, runoff, initial storage, and stress threshold are provisional model assumptions, not locally validated values.
- The sensitivity ranges are exploratory. Coconut Kc studies in other varieties, ages and climates provide context but do not validate a value for this exact palm and site.
- Passing pipeline checks demonstrates schema and arithmetic consistency, not physical accuracy or independent validation.
- The weather-only scenario contains no irrigation. Its simulated “consider irrigation” action requires field confirmation and must not be used as an operational prescription.
- Real-world validation requires local rain/meteorological measurements, soil texture and calibrated retention curves, root observations, irrigation logs, and independently observed crop/soil-water outcomes.
