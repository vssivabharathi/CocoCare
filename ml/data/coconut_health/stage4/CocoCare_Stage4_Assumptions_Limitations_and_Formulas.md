# CocoCare Stage 4 --- Assumptions, Formulae, Data Sources, and Limitations

**Project:** CocoCare coconut water-monitoring prototype\
**Stage:** Stage 4 --- final-stage assessment\
**Assessment age:** 60 months (5 years)\
**Representative location:** Pollachi, Tamil Nadu, India\
**Representative variety:** East Coast Tall coconut\
**Simulation period:** 547 daily records from the Stage 2 weather
baseline\
**Reported evaluation:** 49/49 automated checks passed

> **Scope warning:** Stage 4 is a model-based scenario simulation. The
> 60-month age is an assessment label; the crop and soil parameters have
> not been calibrated for a real five-year-old palm at the target farm.
> Passing automated checks demonstrates internal consistency of the
> implemented pipeline, not agronomic or field validation.

------------------------------------------------------------------------

## 1. Purpose of Stage 4

Stage 4 represents a 60-month-old coconut palm, as required by the
project's stage diagram. It reuses the same Stage 2 weather input and
compares two scenarios:

1.  **Stage 4 weather-only baseline:** no irrigation is added.
2.  **Stage 4 model-triggered irrigation:** irrigation is applied when
    modelled root-zone depletion reaches the configured threshold.

The Stage 4 generator deliberately does not reuse the Stage 3
TNAU-guided irrigation schedule. That schedule was an illustrative rule
intended for the earlier-age scenario and is not assumed to be suitable
for a 60-month-old palm.

The Stage 4 outputs include daily scenario CSVs, a combined dataset,
scenario summaries, a date-aligned comparison CSV, a plot, metadata, and
evaluation reports.

## 2. Input data and provenance

### 2.1 Weather input

The generator reads `stage2_weather_input.csv` from the Stage 2 output
directory. In the reported run, it used 547 daily records. The Stage 4
run reuses the weather baseline rather than downloading a new period, so
the scenarios can be compared under the same weather conditions.

The Stage 2 weather data were previously obtained from NASA POWER daily
point data for the project's representative location. NASA POWER is a
gridded/reanalysis-derived meteorological data service; these values
should not be described as on-farm sensor measurements.

Source: - NASA POWER Daily API documentation:
https://power.larc.nasa.gov/docs/services/api/temporal/daily/

### 2.2 Project location and crop identity

The code sets: - Location: Pollachi, Tamil Nadu, India - Latitude:
10.7460° N - Representative elevation: 286 m - Variety: East Coast
Tall - Assessment age: 60 months

These are project configuration values. The code does not verify a
specific farm boundary, planting date, or the actual age of a real palm.

### 2.3 Weather fields required by the generator

The input must contain: - `date` - `rainfall_mm` - `tmax_c` - `tmin_c` -
`solar_radiation_mj_m2_day` - `relative_humidity_pct` - `wind_speed_m_s`

If `et0_mm_day` or `etc_potential_mm_day_modelled` is absent or contains
missing values, the generator calculates it. The generator rejects
invalid/duplicate dates, missing required weather values, and negative
rainfall.

------------------------------------------------------------------------

## 3. Assumptions and parameter values

  --------------------------------------------------------------------------------------------------------
  Parameter                                                        Implemented value Status and rationale
  ------------------------ --------------------------------------------------------- ---------------------
  Assessment age                                                           60 months Required by the
                                                                                     project diagram; not
                                                                                     derived from a
                                                                                     planting record.

  Crop coefficient (K_c)                                                        0.70 Provisional value
                                                                                     carried forward from
                                                                                     earlier stages; not
                                                                                     calibrated for this
                                                                                     five-year-old palm.

  Effective root-zone                                                         0.45 m Assumed; no field
  depth (Z_r)                                                                        root-depth
                                                                                     measurement is
                                                                                     supplied to the
                                                                                     generator.

  Field-capacity VWC                                                      0.23 m³/m³ Assumed soil
  (`\theta`{=tex}\_{FC})                                                             property; no
                                                                                     site-specific soil
                                                                                     test is used.

  Wilting-point VWC                                                       0.10 m³/m³ Assumed soil
  (`\theta`{=tex}\_{WP})                                                             property; no
                                                                                     site-specific soil
                                                                                     test is used.

  Initial available-water                                                       0.70 Assumed initial
  fraction                                                                           state, not a measured
                                                                                     starting moisture
                                                                                     value.

  Runoff fraction                                             0.05 of daily rainfall Fixed simplification;
                                                                                     actual runoff varies
                                                                                     with rainfall
                                                                                     intensity, soil,
                                                                                     slope, cover, and
                                                                                     infiltration.

  Depletion trigger                                                       0.50 (50%) Provisional rule for
                                                                                     deciding when to
                                                                                     irrigate. It is not
                                                                                     established as an
                                                                                     optimal threshold for
                                                                                     this crop/site.

  Refill target                                                          0.80 of TAW Provisional target
                                                                                     for storage after
                                                                                     irrigation.

  Effective wetted area                                              1.0 m² per palm Placeholder for
                                                                                     converting irrigation
                                                                                     depth to litres.
                                                                                     Actual wetted area
                                                                                     depends on the
                                                                                     irrigation method and
                                                                                     layout.

  Soil temperature                                                      Not modelled The code stores NaN
                                                                                     and an explicit
                                                                                     status because it has
                                                                                     no defensible
                                                                                     soil-temperature
                                                                                     model or
                                                                                     measurements.

  Stress thresholds                                          0.30 and 0.50 depletion Project rules used to
                                                                                     label modelled
                                                                                     stress; not measured
                                                                                     physiological
                                                                                     thresholds.

  ET stress coefficient      (K_s=`\operatorname{clip}`{=tex}((S/TAW)/(1-0.50),0,1)) Simplified
                                                                                     project-specific
                                                                                     response rule, not a
                                                                                     calibrated
                                                                                     coconut-specific
                                                                                     function.
  --------------------------------------------------------------------------------------------------------

### Why some parameters are provisional

The code and current input files do not contain field measurements of
soil texture, field capacity, wilting point, effective rooting depth,
irrigation wetted area, or actual soil moisture. Therefore, these values
are implementation assumptions. They should not be presented as
measurements or as exact official recommendations.

The 60-month assessment changes the age label, but it does **not**
automatically update (K_c), root depth, or the soil parameters for a
five-year-old palm. This is a major limitation to state in a report.

------------------------------------------------------------------------

## 4. Formulae used in Stage 4

### 4.1 Total available water (TAW)

The model calculates root-zone total available water as:

\[ TAW = (`\theta`{=tex}*{FC} - `\theta`{=tex}*{WP}) `\times `{=tex}Z_r
`\times 1000`{=tex} \]

where: - (`\theta`{=tex}*{FC}) = assumed volumetric water content at
field capacity (m³/m³); - (`\theta`{=tex}*{WP}) = assumed volumetric
water content at wilting point (m³/m³); - (Z_r) = assumed effective
root-zone depth (m); - 1000 converts metres of water to millimetres.

Using the configured values:

\[ TAW = (0.23 - 0.10) `\times 0.45`{=tex} `\times 1000`{=tex} =
58.5 `\text{mm}`{=tex} \]

**Interpretation:** 58.5 mm is the model's assumed available storage
capacity for the represented root zone. It is not a measured soil-water
capacity.

This is a standard root-zone water accounting relationship. FAO-56
discusses available soil water and root-zone depletion concepts: -
FAO-56 main publication: https://www.fao.org/4/x0490e/x0490e00.htm -
FAO-56 soil-water stress concepts:
https://www.fao.org/4/X0490E/x0490e0e.htm

### 4.2 Reference evapotranspiration (ET₀)

The generator uses a daily FAO-56-style Penman--Monteith approximation.
The main structure is:

\[ ET_0 =
`\frac{0.408\Delta(R_n-G)+\gamma\frac{900}{T+273}u_2(e_s-e_a)}`{=tex}
{`\Delta`{=tex}+`\gamma`{=tex}(1+0.34u_2)} \]

where: - (ET_0) = reference evapotranspiration (mm/day); -
(`\Delta`{=tex}) = slope of the saturation vapour-pressure curve; -
(R_n) = net radiation at the reference surface (MJ/m²/day); - (G) = soil
heat flux (often approximated as zero for daily time steps in this
formulation); - (`\gamma`{=tex}) = psychrometric constant; - (T) = mean
air temperature (°C); - (u_2) = wind speed at 2 m (m/s); - (e_s) =
saturation vapour pressure (kPa); - (e_a) = actual vapour pressure
(kPa).

The script estimates (e_a) from daily mean relative humidity and
saturation vapour pressure, and estimates atmospheric pressure from the
configured elevation. Therefore, it is best described as an
**FAO-56-style approximation**, not a verified reference implementation
with all input conventions independently validated.

Sources: - FAO-56, reference evapotranspiration calculation:
https://www.fao.org/4/X0490E/x0490e0b.htm - FAO-56 main publication:
https://www.fao.org/4/x0490e/x0490e00.htm

### 4.3 Potential crop evapotranspiration

The generator calculates potential crop evapotranspiration as:

\[ ET_c = K_c `\times `{=tex}ET_0 \]

The configured (K_c=0.70) is carried forward from the prototype. It is
not demonstrated to be the correct crop coefficient for all seasons or
for a 60-month-old East Coast Tall palm at Pollachi.

Source for the general crop-coefficient approach: - FAO-56, crop
evapotranspiration methodology:
https://www.fao.org/4/x0490e/x0490e00.htm

### 4.4 Effective rainfall and runoff

The model assumes a fixed runoff fraction:

\[ R\_{runoff}=0.05R \]

\[ R\_{effective}=`\max`{=tex}(0,R-R\_{runoff}) \]

where (R) is daily rainfall (mm).

This is a project simplification, not a calibrated runoff equation from
NASA POWER or TNAU. It does not account for rainfall intensity, soil
infiltration rate, slope, or ground cover.

### 4.5 Root-zone depletion

Before the irrigation decision, the model calculates:

\[ D_r=1-`\frac{S}{TAW}`{=tex} \]

where: - (D_r) = modelled depletion fraction; - (S) = current modelled
root-zone storage (mm); - (TAW) = assumed total available water (mm).

If (D_r`\geq0.50`{=tex}), the model-triggered scenario applies
irrigation.

The 50% threshold is a configurable project assumption. It should not be
described as a validated optimum for this crop and location.

### 4.6 Refill target and irrigation depth

The target storage is:

\[ S\_{target}=0.80`\times `{=tex}TAW \]

The required depth is:

\[ I\_{mm}=`\max`{=tex}(0,S\_{target}-S) \]

The irrigation volume is calculated as:

\[ I_L=I\_{mm}`\times `{=tex}A\_{wetted} \]

where (A\_{wetted}=1.0 `\text{m}`{=tex}\^2) per palm in the current
prototype.

The unit conversion is based on:

\[
1 `\text{mm}`{=tex}`\times1`{=tex} `\text{m}`{=tex}\^2=1 `\text{litre}`{=tex}
\]

The arithmetic conversion is correct for the stated area, but the real
volume estimate is only as good as the assumed wetted area. Application
efficiency and uneven water distribution are not modelled.

### 4.7 Actual evapotranspiration and simplified stress coefficient

The code calculates relative available storage:

\[
f=`\operatorname{clip}`{=tex}`\left`{=tex}(`\frac{S}{TAW}`{=tex},0,1`\right`{=tex})
\]

It then calculates a simplified stress coefficient:

\[
K_s=`\operatorname{clip}`{=tex}`\left`{=tex}(`\frac{f}{1-0.50}`{=tex},0,1`\right`{=tex})
\]

and:

\[ ET\_{actual}=ET_c`\times `{=tex}K_s \]

This is a prototype rule. It is not a crop-calibrated coconut stress
response and should not be claimed as a validated FAO-56 stress
coefficient for this palm.

FAO-56 provides the general framework for adjusting crop
evapotranspiration for soil-water stress: -
https://www.fao.org/4/X0490E/x0490e0e.htm

### 4.8 Daily root-zone water balance

The code updates storage using:

\[ S\_{pre}=S\_{previous}+R\_{effective}+I\_{mm}-ET\_{actual} \]

Drainage is calculated as:

\[ Drainage=`\max`{=tex}(0,S\_{pre}-TAW) \]

The updated storage is bounded to the range from zero to TAW:

\[ S\_{new}=`\min`{=tex}(TAW,`\max`{=tex}(0,S\_{pre}-Drainage)) \]

This is a single-bucket water balance. It does not explicitly model
multiple soil layers, preferential flow, capillary rise, groundwater, or
measured infiltration and drainage rates.

### 4.9 Simulated volumetric water content (VWC)

The code linearly maps the fraction of root-zone storage between assumed
wilting point and field capacity:

\[
`\theta`{=tex}*{sim}=`\theta`{=tex}*{WP}+`\frac{S}{TAW}`{=tex}(`\theta`{=tex}*{FC}-`\theta`{=tex}*{WP})
\]

The reported percentage is:

\[ VWC\_{%}=100`\times`{=tex}`\theta`{=tex}\_{sim} \]

This is a derived simulated value, not a sensor measurement. The linear
mapping is an assumption and does not use a measured soil-water
retention curve.

### 4.10 Stress labels and action labels

The code classifies depletion as: - **Low stress:** (D_r\<0.30) -
**Moderate stress:** (0.30`\leq `{=tex}D_r\<0.50) - **High stress:**
(D_r`\geq0.50`{=tex})

The action mapping is: - Low → `continue_monitoring` - Moderate →
`reassess_soil_and_weather` - High →
`assess_irrigation_need_if_field_conditions_confirm`

These are model-derived labels and workflow prompts. They are not
ground-truth stress observations or confirmed agricultural
recommendations.

------------------------------------------------------------------------

## 5. Stage 4 results from the reported run

The user-reported Stage 4 generator output was:

  Metric                                    Weather only   Model-triggered irrigation
  ------------------------------------- ---------------- ----------------------------
  Days                                               547                          547
  Total simulated irrigation                    0 L/palm               671.375 L/palm
  Mean modelled storage                     33.494955 mm                 46.530253 mm
  Mean simulated VWC                          17.443323%                   20.340056%
  Low-stress days (rule-derived)                     257                          351
  Moderate-stress days (rule-derived)                 54                          161
  High-stress days (rule-derived)                    236                           35
  Modelled drainage                       1091.907394 mm               1183.701293 mm
  Irrigation events                                    0                           35

The Stage 4 evaluator reported **49/49 checks passed, zero failures**.

Interpretation must remain limited: the table shows how the two model
scenarios differ under the chosen assumptions. It does not prove actual
field moisture, crop stress, yield benefits, or real-world irrigation
savings.

------------------------------------------------------------------------

## 6. Limitations

### Weather limitations

1.  NASA POWER values are gridded meteorological estimates, not direct
    measurements from a weather station beside the palm.
2.  Errors or spatial mismatch in rainfall, temperature, humidity, wind,
    or radiation affect ET₀ and all downstream outputs.
3.  Stage 4 reuses Stage 2 weather; it is not a real-time monitoring or
    forecasting system.

NASA POWER source:
https://power.larc.nasa.gov/docs/services/api/temporal/daily/

### Crop and soil limitations

4.  The 60-month assessment does not automatically adjust crop
    coefficient, rooting depth, or soil properties for age.
5.  Field capacity, wilting point, root-zone depth, initial storage, and
    runoff are assumed, not measured.
6.  The one-bucket model simplifies soil heterogeneity, drainage,
    infiltration, groundwater, and root distribution.
7.  The fixed crop coefficient does not represent all seasonal or
    age-related crop behaviour.

### Irrigation limitations

8.  The 1 m² effective wetted area is a placeholder and directly affects
    irrigation volume in litres.
9.  Application efficiency, distribution uniformity, and losses outside
    the root zone are not explicitly modelled.
10. The 50% depletion trigger and 80% refill target are provisional
    choices, not locally validated irrigation rules.
11. The model-triggered scenario has not been compared with measured
    irrigation, soil moisture, or crop response.

### Stress and temperature limitations

12. The stress coefficient is simplified and not calibrated for coconut
    physiology.
13. Stress labels are rule-derived and have no field-observed ground
    truth.
14. Soil temperature is intentionally not modelled; missing temperature
    values must not be replaced with invented values.
15. The evaluator tests data integrity and internal arithmetic. Passing
    49/49 checks does not validate agronomic accuracy or farm readiness.

------------------------------------------------------------------------

## 7. What the evaluation establishes

The reported 49/49 checks support that the tested Stage 4 output passed
the programmed integrity and consistency checks. They do not prove
that: - the assumed parameters are correct for the actual field; -
simulated soil moisture equals measured soil moisture; - stress labels
reflect actual palm physiology; - the irrigation threshold or refill
target is optimal; - the scenario saves a known amount of real water;
or - the scenario improves yield or plant health.

## 8. Recommended next steps

1.  Preserve the generator, evaluator, CSV outputs, metadata, plot, and
    evaluation report together.
2.  Record the exact input file, location, date range, and parameters in
    the project report.
3.  Perform sensitivity analysis on (K_c), root depth, field capacity,
    wilting point, runoff, depletion trigger, refill target, and wetted
    area.
4.  Compare the ET₀ implementation with a trusted FAO-56 reference
    calculation.
5.  Obtain site-specific soil properties and irrigation-system
    information where feasible.
6.  Validate simulated moisture against field sensor readings and seek
    agricultural expert review before using the output for real
    irrigation decisions.

## 9. References

1.  Allen, R. G., Pereira, L. S., Raes, D., & Smith, M. (1998). *Crop
    Evapotranspiration: Guidelines for Computing Crop Water
    Requirements*. FAO Irrigation and Drainage Paper 56.
    https://www.fao.org/4/x0490e/x0490e00.htm
2.  FAO-56, reference evapotranspiration calculation details.
    https://www.fao.org/4/X0490E/x0490e0b.htm
3.  FAO-56, soil-water stress and adjustment of crop evapotranspiration.
    https://www.fao.org/4/X0490E/x0490e0e.htm
4.  NASA POWER, Daily API documentation.
    https://power.larc.nasa.gov/docs/services/api/temporal/daily/

**Citation note:** The FAO-56 and NASA POWER references support the
general method and weather-source descriptions. The numerical parameter
settings are the values implemented in this CocoCare prototype; they
should not be attributed to these sources unless the source specifically
supports that exact value and context.

## Stage 4 – Limitations

- **Weather Data:** NASA POWER provides gridded weather estimates, not direct farm-level measurements.
- **ET₀ Calculation:** Uses an FAO-56-style approximation that has not been independently validated.
- **Age-Specific Parameters:** The 60-month assessment does not automatically adjust crop or soil parameters for palm age.
- **Soil Properties:** Field capacity (0.23), wilting point (0.10), and root depth (0.45 m) are assumed, not measured.
- **Crop Coefficient:** A fixed Kc of 0.70 is used without calibration for five-month-year-old palms at the target site.
- **Water Balance:** Uses a simplified single-bucket model and assumes a fixed 5% runoff fraction.
- **Irrigation Thresholds:** The 50% depletion trigger and 80% refill target are provisional and not field-validated.
- **Wetted Area:** Assumes an effective wetted area of 1 m² per palm to calculate irrigation volume.
- **Rainfall Awareness:** Irrigation decisions do not consider upcoming rainfall forecasts.
- **Soil Moisture:** VWC is simulated from modelled water storage, not measured by soil sensors.
- **Soil Temperature:** Not modelled because measurements or a defensible estimation method are unavailable.
- **Water Stress:** Stress coefficients, labels, and recommended actions are simplified and not validated against coconut physiology or field observations.
- **Evaluation:** Automated checks assess data integrity and selected calculations, but do not establish agronomic accuracy. Water-balance closure and exact irrigation refill calculations need stronger validation.
- **No Field Validation:** Irrigation quantities and simulated moisture have not been validated against real farm measurements.
- **Generalization:** Results have not been validated across different farms, soil types, seasons, or palm ages.

**Note:** Stage 4 is a provisional simulation for assessing a 60-month-old coconut palm. Its outputs should not be treated as field-validated irrigation recommendations.