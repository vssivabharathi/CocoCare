CocoCare Stage 1 hybrid data pipeline notebook

Open CocoCare_Stage1_Hybrid_Data_Pipeline.ipynb in JupyterLab/Notebook or VS Code.

The notebook contains:
- NASA POWER weather download
- quality checks and plots
- FAO-56 Penman-Monteith ET0 implementation
- ETc = Kc × ET0 formula and limitations
- root-zone available water and daily soil-water balance
- TNAU reference guidance table
- CSV and JSON exports
- source provenance, equations, limitations and paper-writing outline

Install dependencies in a notebook cell with %pip install requests pandas numpy matplotlib.
All soil and crop parameters are provisional. Do not use model-generated stress labels as ground truth.

```
Purpose	Date range	Why
Initial development	1 Jan 2023 – 31 Dec 2025	Three complete years of weather data
Model testing	Hold out 2025	Check performance on a year not used for tuning
Longer-term robustness	2016–2025	Ten years to examine more variation in rainfall and temperature
Live monitoring later	Current and future dates	Use new weather and sensor data as they become available```