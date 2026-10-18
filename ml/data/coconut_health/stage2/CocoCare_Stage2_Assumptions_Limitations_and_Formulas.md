# CocoCare Stage 2: Assumptions, Limitations, and Formula Sources

**Document status:** Stage 2 prototype documentation  
**Evaluation status:** 155/155 automated checks passed  
**Important:** Passing checks confirms data integrity and arithmetic consistency; it does not establish agronomic accuracy or field validity.

## 1. Purpose and scope

Stage 2 simulates daily root-zone water storage for an East Coast Tall coconut palm at Pollachi, Tamil Nadu. It compares two scenarios over **1 January 2023–30 June 2024 (547 days)**:

1. **Weather only:** no irrigation is applied.
2. **TNAU-guided irrigation scenario:** a simplified, illustrative irrigation schedule based on a TNAU recommendation for young coconut seedlings.

Both scenarios use the same daily weather input and water-balance parameters. The results are simulations, not measurements from a real palm or field.

## 2. Site, dates, and age assumptions

- **Location:** Pollachi, Tamil Nadu, India.
- **Coordinates used:** latitude 10.7460°, longitude 77.0976°; elevation approximately 286 m.
- **Variety:** East Coast Tall.
- **Period:** 1 January 2023 to 30 June 2024.
- **Age convention:** the palm is assumed to already be 18 months old on 1 January 2023. Age advances by elapsed days divided by 30.4375 days per month. This is a simulation convention; it is not based on a planting date or farm record.

The date window is approximately an 18-to-36-month simulated age period. The model does not know the actual age, planting date, management history, or soil conditions of a real palm.

## 3. Weather data and provenance

The generator obtains daily data from the **NASA POWER Daily Point API**, unless a user-supplied weather snapshot is configured. Variables used are:

- corrected precipitation (`PRECTOTCORR`),
- daily maximum and minimum temperature (`T2M_MAX`, `T2M_MIN`),
- all-sky surface shortwave solar radiation (`ALLSKY_SFC_SW_DWN`),
- daily relative humidity (`RH2M`), and
- wind speed (`WS2M`).

NASA POWER is gridded/reanalysis-based data suitable for environmental analysis; it is **not a substitute for a local rain gauge, weather station, or on-farm sensor**. Point values may differ from conditions at the exact palm location. If a user-supplied CSV is used, its provenance and units must be checked independently.

## 4. Parameters and their status

| Parameter | Stage 2 value | Status and meaning |
|---|---:|---|
| Crop coefficient, `Kc` | 0.70 | Provisional assumption; not calibrated for this palm's age, variety, and site. |
| Root-zone depth | 0.45 m | Provisional assumption; not measured at the site. |
| Field-capacity volumetric water content, `FC` | 0.23 m³/m³ | Assumed soil property; no soil sample/lab measurement supplied. |
| Wilting-point volumetric water content, `WP` | 0.10 m³/m³ | Assumed soil property; no soil sample/lab measurement supplied. |
| Initial available-water fraction | 0.70 | Assumed initial condition at the start of the simulation. |
| Runoff fraction | 0.05 of rainfall | Fixed simplifying assumption; not estimated from slope, soil, ground cover, or observed runoff. |
| Depletion trigger | 0.50 | Provisional threshold used in the simplified stress-response calculation. |
| Effective wetted area | 1.0 m² per palm | Placeholder used only to convert irrigation litres to water depth; not measured or sourced. |
| Irrigation event | 45 L per palm | Based on TNAU's stated guidance for the first two years during dry summer months, but the scenario's exact calendar implementation is a project assumption. |
| Irrigation interval | 4 days | From the TNAU guidance summary for young seedlings during dry summer months. |
| Dry-season months in code | March, April, May | Provisional project choice; not explicitly established by the cited TNAU page as the complete Pollachi dry-season calendar. |
| Soil temperature | Not modelled | No soil-temperature measurements or defensible soil-temperature model are available in this stage. |

These parameters are deliberately exposed in the generator so they can be replaced when local soil measurements, crop-specific evidence, or field observations become available.

## 5. Formulae used and their sources

### 5.1 Reference evapotranspiration (`ET₀`)

The code implements a **FAO-56-style Penman–Monteith calculation** using daily weather inputs. The general FAO-56 equation is:

\[
ET_0 = \frac{0.408\,\Delta(R_n-G)+\gamma\,\frac{900}{T+273}\,u_2(e_s-e_a)}{\Delta+\gamma(1+0.34u_2)}
\]

where `Rn` is net radiation, `G` is soil heat flux, `T` is mean air temperature, `u₂` is wind speed at 2 m, `es` is saturation vapour pressure, `ea` is actual vapour pressure, `Δ` is the slope of the saturation vapour-pressure curve, and `γ` is the psychrometric constant. The script estimates solar geometry, net radiation, atmospheric pressure, and the related terms from the available inputs.

**Implementation caveat:** actual vapour pressure is approximated in the code as `ea = (daily_mean_RH / 100) × es`, where `es` is the mean saturation vapour pressure calculated from daily maximum and minimum temperature. This is a simplifying approximation; it is not the full preferred FAO-56 procedure using maximum and minimum relative humidity or dew-point temperature. Therefore, the calculated `ET₀` should be described as an estimate, not a locally validated measurement.

**Source:** Allen et al., FAO Irrigation and Drainage Paper 56, *Crop Evapotranspiration — Guidelines for Computing Crop Water Requirements*, especially Chapter 2 (FAO Penman–Monteith) and Chapter 3 (meteorological data):
- https://www.fao.org/4/X0490E/x0490e06.htm
- https://www.fao.org/4/X0490E/x0490e07.htm
- Overview: https://www.fao.org/4/X0490E/x0490e05.htm

### 5.2 Potential crop evapotranspiration (`ETc`)

\[
ET_c = K_c \times ET_0
\]

The generator uses `Kc = 0.70`, so `ETc` is a **modelled potential crop water-use estimate**. The multiplication is the standard crop-coefficient approach, but the value 0.70 is a provisional project parameter and is not established by this project as the correct coefficient for an 18–36-month-old East Coast Tall coconut palm at Pollachi.

**Source for the method:** FAO-56 crop evapotranspiration framework, which relates crop evapotranspiration to reference evapotranspiration through a crop coefficient. The selected numeric `Kc` value is a project assumption, not a value validated by that source for this exact case.

### 5.3 Total available water (`TAW`)

\[
TAW = (FC-WP)\times Z_r\times 1000
\]

where `FC` and `WP` are volumetric water contents in m³/m³, `Zr` is root-zone depth in metres, and 1000 converts metres of water to millimetres. With `FC = 0.23`, `WP = 0.10`, and `Zr = 0.45 m`:

\[
TAW = (0.23-0.10)\times0.45\times1000 = 58.5\text{ mm}
\]

The arithmetic and units follow the standard soil-water storage relationship. **The input soil values and root depth are assumptions**, so 58.5 mm is a model capacity, not a measured site property.

**Source context:** FAO-56 discusses available soil water, root-zone depletion, and water-stress coefficients in its crop-water and soil-water sections:
- https://www.fao.org/4/X0490E/x0490e0e.htm
- https://www.fao.org/4/x0490e/x0490e00.htm

### 5.4 Runoff and effective rainfall

The code uses:

\[
Runoff = 0.05\times Rainfall
\]

\[
Effective\ rainfall = \max(0, Rainfall-Runoff)
\]

The 5% runoff fraction is a **fixed project assumption**, not a value derived from local runoff measurements or a validated runoff model. Effective rainfall here means rainfall remaining after this assumed runoff deduction. The code does not deduct this runoff a second time in the storage balance.

### 5.5 Irrigation litres converted to millimetres

\[
Irrigation\ depth\ (mm)=\frac{Irrigation\ volume\ (L)}{Effective\ wetted\ area\ (m^2)}
\]

This uses the fact that **1 litre spread over 1 m² equals 1 mm of water depth**. The code assumes an effective wetted area of 1.0 m², so a 45 L event becomes 45 mm in the model. That is a placeholder conversion, not a claim that 45 L is actually distributed over 1 m² around a coconut palm. This assumption has a major effect on simulated storage and must be measured or replaced with a defensible irrigation geometry before interpreting the results agronomically.

### 5.6 Simplified stress coefficient and actual evapotranspiration

The script calculates relative available storage as:

\[
r = \mathrm{clip}\left(\frac{S}{TAW},0,1\right)
\]

and uses a simplified stress coefficient:

\[
K_s = \mathrm{clip}\left(\frac{r}{1-p},0,1\right)
\]

where `S` is the previous day's modelled storage and `p = 0.50` is the configured depletion trigger. It then calculates:

\[
ET_{actual}=ET_c\times K_s
\]

This is a **simplified, provisional response function** inspired by the idea of reducing evapotranspiration under water stress. It should not be represented as a fully implemented or crop-calibrated FAO-56 stress model. The chosen threshold and implementation require review and calibration before agronomic use.

**Reference for the general concept of crop water stress and depletion:** FAO-56, soil-water balance and stress coefficient discussion: https://www.fao.org/4/X0490E/x0490e0e.htm. The exact simplified function above is the project's implementation, not a verbatim formula copied from that source.

### 5.7 Daily root-zone storage balance and drainage

The model calculates:

\[
S_{pre}=S_{previous}+P_{effective}+I-ET_{actual}
\]

\[
Drainage=\max(0,S_{pre}-TAW)
\]

\[
S=\mathrm{clip}(S_{pre}-Drainage,0,TAW)
\]

where `I` is irrigation depth in mm. This is a simplified bucket model. Drainage is the amount by which the pre-drainage storage exceeds the assumed storage capacity; the final storage is constrained to `[0, TAW]`. The model does not separately represent capillary rise, groundwater contribution, preferential flow, layered soil, lateral flow, or measured drainage. Water that would drive storage below zero is prevented by clipping; the model does not separately report unmet evapotranspiration demand.

The water-balance equation is a project-level conservation accounting approach. The exact bucket implementation and clipping rules are code choices, not a claim that FAO prescribes this exact implementation for this site.

### 5.8 Simulated volumetric water content (`VWC`)

The code maps storage linearly between the assumed wilting point and field capacity:

\[
VWC=WP+\frac{S}{TAW}(FC-WP)
\]

The result is multiplied by 100 to report percent. This is a **linear model mapping**, not a soil-moisture sensor prediction calibrated for the local soil. It assumes the bucket's fraction of available water translates linearly to volumetric water content between the assumed `WP` and `FC`.

### 5.9 Rule-derived stress labels and actions

The labels are assigned from modelled depletion:

- `low`: depletion < 0.30
- `moderate`: 0.30 ≤ depletion < 0.50
- `high`: depletion ≥ 0.50

The actions (`continue_monitoring`, `recheck_soil_and_weather`, and `consider_irrigation_if_field_conditions_confirm`) are mapped from those labels by project rules. They are **not ground-truth labels, clinical/agronomic diagnoses, or independently validated irrigation recommendations**. The 0.30 boundary and the action mapping are project rules; the 0.50 value is the configured depletion trigger, not proof of a universal coconut threshold.

## 6. Irrigation scenario: source versus implementation

TNAU's coconut irrigation page states that, for the first two years from planting, young seedlings may be irrigated at **45 litres per seedling once every four days during dry summer months**. See:

- TNAU, *Coconut — Irrigation Management*: https://www.agritech.tnau.ac.in/expert_system/coconut/coconut/coconut_irrigation_management.html

The generator translates this into a deliberately simplified scenario:

- 45 L per event,
- one event every four days according to the script's day-index rule,
- only while simulated age is 18 to less than 24 months,
- only in March, April, and May, which are configured as provisional dry-season months,
- no TNAU schedule is assumed for simulated age 24–36 months.

**Important distinction:** TNAU provides the general recommendation, but the exact March–May filter, age-clock convention, day-index scheduling, and exclusion of the 24–36-month period are implementation choices. The TNAU page does not establish that March–May is the complete dry season for this exact site, nor that the simplified schedule is appropriate for every soil, irrigation method, or farm. Do not call this a fully TNAU-compliant schedule or a farm-specific recommendation.

## 7. Major limitations

1. **No field validation:** There are no measured soil-moisture, irrigation, drainage, runoff, or plant-water-stress observations for comparison.
2. **Gridded weather:** NASA POWER estimates may differ from conditions at the farm or individual palm.
3. **Approximate `ET₀`:** daily mean relative humidity is used to approximate actual vapour pressure; this adds uncertainty.
4. **Uncalibrated crop coefficient:** `Kc = 0.70` is provisional and may vary with age, crop condition, climate, and management.
5. **Unmeasured soil properties:** root depth, field capacity, and wilting point are assumed, not measured.
6. **Simplified runoff:** a constant 5% runoff fraction ignores soil texture, slope, rainfall intensity, ground cover, and management.
7. **Simplified soil bucket:** no soil layers, capillary rise, groundwater, lateral flow, or detailed infiltration/drainage dynamics are represented.
8. **Initial condition uncertainty:** starting storage is set to 70% of `TAW` by assumption.
9. **Wetted-area placeholder:** 1 m² converts the irrigation event into a very large modelled water depth; this must be resolved before interpreting irrigation effects.
10. **Simplified irrigation schedule:** the TNAU recommendation is operationalised using a provisional calendar filter and does not model local irrigation method or measured farm practice.
11. **Age is synthetic:** the simulation does not use a real planting date or real palm-age record.
12. **Stress labels are rule-derived:** they are generated from modelled depletion and have not been calibrated against coconut stress observations.
13. **VWC is simulated:** the linear mapping is not calibrated to a soil sensor or soil water-retention curve.
14. **Soil temperature is absent:** it is intentionally stored as missing (`NaN`) with a status field explaining that it is not modelled. No soil-temperature values should be fabricated to remove missing cells.
15. **No uncertainty analysis:** the reported scenario differences do not quantify uncertainty in weather, parameters, or model structure.
16. **No economic or yield validation:** the simulation does not establish yield gains, water savings in practice, costs, or optimal irrigation.

## 8. What the automated evaluation does and does not establish

The Stage 2 evaluator reported **155 checks passed and 0 failed**. These checks cover data completeness and structure (with intentionally unmodelled soil temperature treated separately), date coverage, broad value checks, formula consistency, storage bounds, water-balance arithmetic, irrigation-schedule consistency, scenario output consistency, and metadata/report consistency.

This means the pipeline is internally consistent under its coded assumptions. It does **not** prove that:

- the weather exactly represents the farm,
- the chosen `Kc`, root depth, `FC`, `WP`, runoff fraction, wetted area, or depletion threshold are correct,
- simulated soil moisture matches a sensor,
- stress labels match actual plant stress,
- the irrigation scenario is optimal, or
- the outputs should be used as operational farming advice.

## 9. Recommended validation before real-world use

1. Record actual planting date, variety, irrigation method, and local management schedule.
2. Measure or obtain defensible soil texture, field capacity, wilting point, and effective root depth for the site.
3. Replace the 1 m² wetted-area placeholder with measured/justified wetted area or model the irrigation application geometry explicitly.
4. Compare NASA POWER weather against a local station or rain gauge where possible.
5. Validate `ET₀` and crop-coefficient assumptions with an agronomist or locally relevant published study.
6. Collect soil-moisture measurements at known depths and dates; compare them with simulated VWC and tune parameters on one period, then test on a separate period.
7. Compare simulated irrigation and stress outputs with documented field observations before presenting the system as a decision-support tool.
8. Report parameter uncertainty and scenario sensitivity instead of relying on a single set of assumptions.

## 10. References

1. **NASA POWER**, *Daily API documentation*. Data service and daily meteorological/solar parameter information. https://power.larc.nasa.gov/docs/services/api/temporal/daily/
2. **Allen, R. G., Pereira, L. S., Raes, D., & Smith, M. (1998).** *Crop Evapotranspiration: Guidelines for Computing Crop Water Requirements*. FAO Irrigation and Drainage Paper 56. Chapter 2: https://www.fao.org/4/X0490E/x0490e06.htm ; Chapter 3: https://www.fao.org/4/X0490E/x0490e07.htm ; soil-water/stress discussion: https://www.fao.org/4/X0490E/x0490e0e.htm
3. **Tamil Nadu Agricultural University (TNAU)**, *Coconut — Irrigation Management*. Source for the young-seedling recommendation of 45 L per seedling once every four days during dry summer months in the first two years. https://www.agritech.tnau.ac.in/expert_system/coconut/coconut/coconut_irrigation_management.html

## Suggested wording for the project report

> Stage 2 is a prototype daily root-zone water-balance simulation driven by NASA POWER weather estimates. Reference evapotranspiration is estimated using a FAO-56-style Penman–Monteith implementation, and potential crop evapotranspiration is calculated using a provisional crop coefficient. Two scenarios—no irrigation and a simplified TNAU-guided irrigation scenario—are compared using a bucket water balance. Soil properties, root depth, crop coefficient, runoff fraction, initial storage, wetted area, and stress thresholds are assumptions rather than field measurements. The 155 automated checks passed, confirming pipeline consistency and arithmetic checks; however, the simulated soil moisture, stress labels, and irrigation effects have not been validated against field observations and should not be interpreted as farm-specific recommendations.
