# CocoCare Stage 3: Assumptions, Limitations, Equations, and References

**Project:** CocoCare --- coconut water-monitoring prototype\
**Stage:** Stage 3\
**Location represented:** Pollachi, Tamil Nadu, India\
**Crop variety represented:** East Coast Tall coconut\
**Simulation length:** 547 daily records\
**Evaluation status:** 66/66 automated checks passed in the reported run

------------------------------------------------------------------------

## 1. Purpose and scope

Stage 3 extends the Stage 2 water-balance prototype by comparing three
irrigation scenarios under the same daily weather input:

1.  **Weather only:** no irrigation is applied.
2.  **TNAU-guided irrigation:** an illustrative schedule of 45 L per
    palm every four days during the project's assumed March--May
    dry-season window, while simulated palm age is below 24 months.
3.  **Model-triggered irrigation:** irrigation is applied when modelled
    root-zone depletion reaches the configured threshold; the model then
    adds enough water to move storage toward a target fraction of total
    available water (TAW).

Stage 3 is a **simulation and scenario-comparison prototype**. It does
not establish a field-validated irrigation recommendation.

## 2. Input data and simulation setup

-   The generator reads `stage2_weather_input.csv` from the existing
    Stage 2 output directory.
-   The same weather dates are used across all three scenarios to
    support a like-for-like comparison.
-   The reported run contains 547 daily records.
-   The model uses a fixed representative location and crop variety:
    Pollachi, Tamil Nadu, and East Coast Tall coconut.
-   Simulated age starts at 18 months and advances with elapsed days
    using an average month length of 30.4375 days.
-   Stage 2 files are inputs/baseline artefacts and should remain
    unchanged by Stage 3.

The age clock is a simulation convention. It is not a verified planting
date or an observation of the age of a real palm.

## 3. Main assumptions and configured parameters

  ---------------------------------------------------------------------------
  Parameter                             Stage 3 setting Interpretation /
                                                        caveat
  ------------------------ ---------------------------- ---------------------
  Crop coefficient, (K_c)                          0.70 Provisional value
                                                        carried forward from
                                                        the earlier
                                                        prototype; not
                                                        verified for every
                                                        age, season, or local
                                                        field condition.

  Root-zone depth, (Z_r)                         0.45 m Assumed effective
                                                        root-zone depth; no
                                                        site-specific root
                                                        measurement is
                                                        available.

  Field-capacity                             0.23 m³/m³ Assumed soil
  volumetric water                                      property, not a
  content,                                              measured value for
  (`\theta`{=tex}\_{FC})                                the target farm.

  Wilting-point volumetric                   0.10 m³/m³ Assumed soil
  water content,                                        property, not a
  (`\theta`{=tex}\_{WP})                                measured value for
                                                        the target farm.

  Initial available-water                          0.70 Initial condition
  fraction                                              chosen for
                                                        simulation, not an
                                                        observed initial
                                                        moisture value.

  Runoff fraction                      0.05 of rainfall Simplified constant
                                                        fraction; real runoff
                                                        depends on rainfall
                                                        intensity, slope,
                                                        soil, ground cover,
                                                        and infiltration.

  Depletion trigger                                0.50 Provisional threshold
                                                        for the
                                                        model-triggered
                                                        scenario; not
                                                        confirmed as an
                                                        optimum for this palm
                                                        and soil.

  Refill target                             0.80 of TAW Provisional target
                                                        storage fraction
                                                        selected for the
                                                        simulation.

  Effective wetted area                 1.0 m² per palm Placeholder used to
                                                        convert irrigation
                                                        depth to litres; must
                                                        be measured or
                                                        justified for the
                                                        actual irrigation
                                                        method.

  TNAU-scenario                               45 L/palm Used as a
  application                                           source-inspired
                                                        illustrative input,
                                                        not as proof that
                                                        this schedule is
                                                        suitable for this
                                                        exact site and age.

  TNAU-scenario interval                         4 days Applied in the
                                                        project rule, subject
                                                        to the date/month
                                                        filter.

  TNAU-scenario months                March, April, May Provisional project
                                                        dry-season calendar;
                                                        not represented as a
                                                        month list explicitly
                                                        prescribed by TNAU.

  Soil temperature                         Not modelled Output is
                                                        intentionally missing
                                                        because the pipeline
                                                        has no defensible
                                                        soil-temperature
                                                        model or
                                                        measurements.
  ---------------------------------------------------------------------------

### Total available water

The model calculates:

\[ TAW = (`\theta`{=tex}*{FC} - `\theta`{=tex}*{WP}) `\times `{=tex}Z_r
`\times 1000`{=tex} \]

Using the configured values:

\[ TAW = (0.23 - 0.10) `\times 0.45`{=tex} `\times 1000`{=tex} =
58.5 `\text{mm}`{=tex} \]

This is an assumed root-zone storage capacity derived from assumed
inputs; it is not a soil test result.

## 4. Equations and calculation rules

### 4.1 Reference evapotranspiration, ET₀

The code uses an FAO-56-style Penman--Monteith calculation with daily
weather inputs, including maximum and minimum temperature, relative
humidity, wind speed, and solar radiation. The implementation estimates
actual vapour pressure from mean relative humidity and saturation vapour
pressure.

This is an **approximation of the FAO-56 method**, not a guarantee of
exact compliance with every FAO-56 data-processing recommendation.
Results may differ from a reference ET₀ calculation using a fully
specified vapour-pressure method, measured pressure, and independently
verified weather inputs.

Reference: - FAO Irrigation and Drainage Paper 56, Chapter 4 ---
reference evapotranspiration:
https://www.fao.org/4/X0490E/x0490e0b.htm - FAO-56 main publication:
https://www.fao.org/4/x0490e/x0490e00.htm

### 4.2 Potential crop evapotranspiration

The generator uses:

\[ ET_c = K_c `\times `{=tex}ET_0 \]

where (K_c = 0.70) is the provisional crop coefficient used by this
prototype.

The value is carried forward for scenario consistency; it should not be
interpreted as a locally calibrated coefficient for East Coast Tall
palms at every simulated age.

### 4.3 Effective rainfall and runoff

The prototype assumes a fixed runoff fraction:

\[ R\_{runoff} = 0.05 `\times `{=tex}R \]

\[ R\_{effective} = `\max`{=tex}(0, R - R\_{runoff}) \]

where (R) is daily rainfall in millimetres.

This is a simplified accounting rule. It does not calculate runoff from
rainfall intensity, infiltration capacity, slope, or a soil hydraulic
model.

### 4.4 Depletion and irrigation trigger

Before the day's irrigation decision, the model calculates:

\[ D_r = 1 - `\frac{S}{TAW}`{=tex} \]

where (S) is current modelled root-zone water storage in millimetres.

For the model-triggered scenario, if:

\[ D_r `\geq 0.50`{=tex} \]

the target storage is calculated as:

\[ S\_{target} = 0.80 `\times `{=tex}TAW \]

The required irrigation depth is:

\[ I\_{mm} = `\max`{=tex}(0, S\_{target} - S) \]

The model converts this depth to a volume using the assumed wetted area:

\[ I_L = I\_{mm} `\times `{=tex}A\_{wetted} \]

where (A\_{wetted} = 1.0 `\text{m}`{=tex}\^2). This uses the fact that 1
mm of water over 1 m² equals 1 litre. The conversion is dimensionally
correct, but the real-world volume estimate depends directly on the
assumed wetted area and ignores application losses and non-uniform
distribution.

### 4.5 Daily root-zone water balance

The model's daily storage update follows this simplified structure:

\[ S\_{pre-drainage} = S\_{previous} + R\_{effective} + I\_{mm} -
ET\_{actual} \]

Water above TAW is counted as drainage:

\[ Drainage = `\max`{=tex}(0, S\_{pre-drainage} - TAW) \]

Storage is then bounded to the interval from zero to TAW:

\[ S\_{new} = `\min`{=tex}(TAW, `\max`{=tex}(0, S\_{pre-drainage} -
Drainage)) \]

This is a bucket-model approximation. It does not simulate detailed soil
layers, preferential flow, capillary rise, groundwater contribution, or
measured infiltration and drainage dynamics.

### 4.6 Simplified actual evapotranspiration and stress coefficient

The prototype computes relative available storage as:

\[ f = `\operatorname{clip}`{=tex}`\left`{=tex}(`\frac{S}{TAW}`{=tex},
0, 1`\right`{=tex}) \]

and uses a simplified stress coefficient:

\[ K_s =
`\operatorname{clip}`{=tex}`\left`{=tex}(`\frac{f}{1 - 0.50}`{=tex}, 0,
1`\right`{=tex}) \]

Then:

\[ ET\_{actual} = ET_c `\times `{=tex}K_s \]

This is a project-specific simplified response rule. It is **not a
validated coconut-specific soil-water stress function** and should not
be described as a calibrated FAO-56 stress model for the target crop.

FAO-56 provides a framework for water-stress adjustment of crop
evapotranspiration, but the crop-specific parameters and implementation
need to be selected and validated appropriately: - FAO-56, crop
evapotranspiration and water-stress concepts:
https://www.fao.org/4/X0490E/x0490e0e.htm

### 4.7 Simulated volumetric water content

The code maps the modelled storage fraction linearly between the assumed
wilting point and field capacity:

\[ `\theta`{=tex}*{sim} = `\theta`{=tex}*{WP} +
`\frac{S}{TAW}`{=tex}(`\theta`{=tex}*{FC} - `\theta`{=tex}*{WP}) \]

The displayed percentage is (100 `\times `{=tex}`\theta`{=tex}\_{sim}).

This is a derived model estimate, not a sensor reading. The linear
mapping is a simplifying assumption and does not represent a measured
soil-water retention curve.

### 4.8 Rule-derived stress labels and actions

The prototype labels the day using modelled depletion: - `low`:
depletion below 0.30 - `moderate`: depletion from 0.30 up to (but not
including) 0.50 - `high`: depletion of 0.50 or more

Actions are mapped from those labels: - `low` → `continue_monitoring` -
`moderate` → `recheck_soil_and_weather` - `high` →
`consider_irrigation_if_field_conditions_confirm`

These labels are generated by thresholds in the code. They are not
measured stress labels, plant-health observations, or verified agronomic
recommendations.

## 5. Scenario interpretation

The three scenarios are run against the same daily weather baseline:

-   **Weather only** isolates the modelled water balance without
    irrigation.
-   **TNAU-guided** applies the project's illustrative schedule (45 L
    every four days within the configured month and age conditions). It
    is not a complete implementation of all TNAU irrigation guidance.
-   **Model-triggered** applies water when the simulated depletion
    threshold is reached and fills the modelled storage toward 80% of
    TAW.

Any difference in storage, simulated moisture, irrigation volume,
drainage, or stress-day counts is a difference **within the configured
simulation**. It is not evidence by itself that one strategy will
improve real-world yield, water productivity, or palm health.

## 6. Limitations

### Weather and input data

1.  NASA POWER provides gridded meteorological estimates; these are not
    measurements from a weather station located at the target palm.
2.  Errors or spatial mismatch in rainfall, humidity, wind, temperature,
    and radiation propagate into ET₀ and water-balance outputs.
3.  The simulation reuses Stage 2 weather records. It does not represent
    future weather forecasts or real-time farm telemetry.

NASA POWER daily API documentation:
https://power.larc.nasa.gov/docs/services/api/temporal/daily/

### Soil and crop representation

4.  Field capacity, wilting point, root depth, crop coefficient, runoff
    fraction, and initial storage are assumed rather than measured at
    the target site.
5.  A single fixed root-zone bucket cannot capture vertical soil
    variation, root distribution, soil texture changes, preferential
    flow, capillary rise, or groundwater effects.
6.  The model uses a fixed Kc and does not fully represent age-,
    season-, canopy-, or management-dependent crop water use.
7.  The age timeline is calculated from an assumed starting age and
    average month length; no planting date or real palm-age record is
    used.

### Irrigation representation

8.  The effective wetted area of 1 m² is a placeholder. It materially
    affects the conversion from irrigation depth to litres per palm.
9.  The calculation does not explicitly model application efficiency,
    distribution uniformity, evaporation from the application system, or
    losses outside the modelled root zone.
10. The March--May month filter is a provisional project assumption. It
    is not proof of the correct local dry-season calendar for the target
    field.
11. The 45 L/four-day schedule is an illustrative comparison rule. The
    code does not implement the full range of conditions that might
    affect an actual TNAU-based recommendation.

### Model and validation

12. The ET₀ implementation uses a simplified estimate of actual vapour
    pressure and should be compared with a trusted reference calculation
    before being used operationally.
13. The bucket water balance and stress coefficient are simplified, not
    a calibrated process model for coconut.
14. Soil moisture is simulated, not measured. Soil temperature is
    intentionally not modelled and is stored as missing.
15. Stress labels and actions are rule-derived; no ground-truth stress
    labels or agronomist-reviewed outcomes are available.
16. The automated evaluator checks internal data consistency and
    arithmetic. A result of 66/66 passing does not prove agronomic
    accuracy, predictive performance, water savings, yield improvement,
    or suitability for farm decisions.
17. The model-triggered scenario's apparent performance depends on the
    selected threshold, refill target, assumed soil parameters, weather
    inputs, and wetted area. Sensitivity analysis and field validation
    are still needed.

## 7. What the automated evaluation establishes

In the reported run, the Stage 3 evaluator completed **66/66 checks with
zero failures**.

This supports the statement that the tested outputs passed the
programmed integrity and internal-consistency checks. It does **not**
establish that: - the assumed parameters are correct for the actual
field; - the simulated moisture equals actual soil moisture; - the
stress labels match the palm's physiological condition; - the
model-triggered schedule is optimal; - the scenario will save a
specified amount of real irrigation water; or - any scenario improves
yield or plant health.

## 8. Recommended next steps

1.  Preserve the Stage 2 baseline, Stage 3 scripts, output CSV files,
    metadata, plot, and evaluation report together.
2.  Record the exact weather source, location, date range, software
    environment, and parameter values in the project report.
3.  Perform sensitivity analysis for Kc, root depth, field capacity,
    wilting point, runoff fraction, depletion trigger, refill target,
    and wetted area.
4.  Compare ET₀ outputs with a trusted FAO-56 reference implementation
    and document any differences.
5.  Obtain field-specific soil measurements and irrigation-system
    details where feasible.
6.  If possible, compare simulated soil moisture with sensor readings
    and have irrigation rules reviewed by an agricultural expert before
    presenting them as recommendations.

## 9. References

1.  Allen, R. G., Pereira, L. S., Raes, D., & Smith, M. (1998). *Crop
    Evapotranspiration: Guidelines for Computing Crop Water
    Requirements*. FAO Irrigation and Drainage Paper 56.
    https://www.fao.org/4/x0490e/x0490e00.htm
2.  FAO-56, reference evapotranspiration equation and calculation
    details. https://www.fao.org/4/X0490E/x0490e0b.htm
3.  FAO-56, soil-water stress and adjustment of crop evapotranspiration.
    https://www.fao.org/4/X0490E/x0490e0e.htm
4.  NASA POWER, Daily API documentation.
    https://power.larc.nasa.gov/docs/services/api/temporal/daily/
5.  Tamil Nadu Agricultural University (TNAU), Coconut irrigation
    management.
    https://www.agritech.tnau.ac.in/expert_system/coconut/coconut/coconut_irrigation_management.html

**Citation note:** The FAO-56 and NASA POWER links support the general
methods/data-source descriptions. The numerical settings in this
document are the project's implemented assumptions; they should not be
attributed to those sources unless a source specifically supports that
exact value and context.
