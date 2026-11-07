from pathlib import Path
import json
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parent
RUN = ROOT / "audited_run"
REPORTS = RUN / "evaluation_reports"
OUT = ROOT / "CocoCare_Stage1_Scientific_Methodology_and_Validation.docx"
summary = json.loads((REPORTS / "evaluation_summary.json").read_text())
doc = Document()
sec = doc.sections[0]
sec.top_margin = Inches(.75); sec.bottom_margin = Inches(.75); sec.left_margin = Inches(.8); sec.right_margin = Inches(.8)
for name, size in [("Normal", 10.5), ("Title", 22), ("Heading 1", 15), ("Heading 2", 12)]:
    doc.styles[name].font.name = "Aptos"
    doc.styles[name].font.size = Pt(size)
    doc.styles[name].font.color.rgb = RGBColor(0, 0, 0)
title_ppr = doc.styles["Title"].element.get_or_add_pPr()
for child in list(title_ppr):
    if child.tag == qn("w:pBdr"):
        title_ppr.remove(child)

def cell_style(cell, fill=None, white=False):
    tcPr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        e = OxmlElement("w:" + edge); e.set(qn("w:val"), "single"); e.set(qn("w:sz"), "4"); e.set(qn("w:color"), "D9D9D9"); borders.append(e)
    tcPr.append(borders)
    if fill:
        s = OxmlElement("w:shd"); s.set(qn("w:fill"), fill); tcPr.append(s)
    if white:
        for r in cell.paragraphs[0].runs: r.font.color.rgb = RGBColor(255, 255, 255); r.font.bold = True

def add_table(headers, rows):
    t = doc.add_table(rows=1, cols=len(headers)); t.alignment = WD_TABLE_ALIGNMENT.CENTER; t.style = "Table Grid"
    for i, value in enumerate(headers):
        t.rows[0].cells[i].text = str(value); cell_style(t.rows[0].cells[i], "1F4E78", True)
    header = OxmlElement("w:tblHeader"); header.set(qn("w:val"), "true")
    t.rows[0]._tr.get_or_add_trPr().append(header)
    for idx, row in enumerate(rows):
        cells = t.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = str(value); cell_style(cells[i], "F3F7FA" if idx % 2 else None)
    doc.add_paragraph()

def para(text, lead=None):
    p = doc.add_paragraph()
    if lead:
        r = p.add_run(lead); r.bold = True
    p.add_run(text)

def figure(filename, caption):
    path = REPORTS / filename
    if path.exists():
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.add_run().add_picture(str(path), width=Inches(6.6))
        p = doc.add_paragraph(caption); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for r in p.runs: r.italic = True

title = doc.add_paragraph(style="Title"); title.alignment = WD_ALIGN_PARAGRAPH.CENTER
title.add_run("CocoCare Stage 1 Scientific Methodology and Validation")
p = doc.add_paragraph("End to end audit of the hybrid weather and water balance prototype")
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p = doc.add_paragraph("Audit date 18 October 2026  |  Scope 2023 daily data  |  Pollachi Tamil Nadu")
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
para("The audited frozen-weather run is complete and internally arithmetic-consistent after correction of software defects. It is not field-validated: weather is gridded, soil water and labels are modelled, and crop and soil parameters remain provisional.", "Conclusion. ")
doc.add_page_break()

doc.add_heading("1 Scope and inspected material", 1)
para("The audit inspected the Stage 1 generator, evaluator, both Stage 1 notebooks, original output CSV/JSON/plot reports, metadata and reference table. It preserved the original output directory, generated a separate audited run from the saved weather CSV, added a test, and performed exploratory one-at-a-time sensitivity scenarios.")
add_table(["Artifact", "Role", "Disposition"], [
["cococare_stage1_final_generator.py", "Weather, ET, bucket and metadata", "Corrected output/reuse controls and overflow drainage"],
["evaluvation /cococare_stage1_evaluation.py", "Quality, formulas and figures", "Corrected source-column/missingness and correlation inputs"],
["data/cococare_stage1_outputs", "Original outputs", "Preserved; original dataset SHA-256 4fb17c38db268f8b4d3e1476428e32d436adc0036af328c75434afc21c8ce7f6"],
["audit_artifacts/audited_run", "Corrected rerun", "365 rows, 30 source columns, all checks pass"],
["audit_artifacts/sensitivity_analysis.csv", "Exploratory scenarios", "Not calibration or independent validation"],
])

doc.add_heading("2 Provenance schema and transformations", 1)
para("External values are NASA POWER daily point-request estimates: precipitation, maximum/minimum air temperature, all-sky surface shortwave radiation, relative humidity and wind. NASA describes its Daily API as analysis-ready solar and meteorological time series at the original source spatial resolution. It is not an on-farm weather-station record. The request did not set a time standard, so NASA POWER defaults to Local Solar Time.")
add_table(["Class", "Fields", "Status"], [
["External weather", "rainfall, Tmax, Tmin, radiation, RH, wind", "NASA POWER gridded estimates; not local observations"],
["Calculated", "ET0", "FAO-56-style calculation from supplied weather and fixed elevation"],
["Modelled", "ETc, effective rain, runoff, ETa, drainage, storage, depletion, VWC", "Deterministic outputs of provisional rules"],
["Rule labels", "stress and simulated recommended action", "Not ground truth or operational advice"],
["Static metadata", "location, variety, age and coordinates", "Configuration assertions, not independent field records"],
])
para("The audited dataset has 365 days from 2023-01-01 to 2023-12-31, 30 source columns, no duplicate or invalid dates, no source missing cells, and exact agreement of source weather values with the frozen CSV. Broad range screens are plausibility checks only.")

doc.add_heading("3 Formula by formula assessment", 1)
add_table(["Component", "Equation or rule", "Scientific assessment"], [
["ET0", "FAO Penman Monteith daily form; G=0", "FAO-56 supports the general method. Mean RH is used to estimate actual vapour pressure; output remains an estimate."],
["Potential ETc", "ETc = Kc ET0; Kc=0.70", "FAO-56 Eq 58 supports relationship, not this coconut-specific value."],
["Available water", "TAW=1000(thetaFC-thetaWP)Zr=58.5 mm", "Exactly FAO-56 Eq 82. FC=.23, WP=.10 and Zr=.45 m are unverified site assumptions."],
["Rain/runoff", "effective rain=rain minus .05 rain", "Arithmetic correct; no site/event/topography evidence for fixed 5 percent runoff."],
["Stress ET", "ETa=ETc simplified storage Ks", "Related to FAO-56 stress adjustment but not its complete crop-specific Ks method."],
["Drainage", "max(0, pre-drainage minus TAW)", "Corrected to report all overflow and close the bucket."],
["Labels", "low D<.30; moderate D<.50; high otherwise", "Rule-derived classes only, not observed water stress."],
])

doc.add_heading("4 Evaluation anomalies and corrected results", 1)
para("The original evaluation JSON mixed the 30-column source CSV with 38 columns after temporary diagnostics were added. Its missing-value check falsely failed because first-row reconstructed storage is intentionally undefined. The evaluator now records source column count and source missingness before diagnostics, and excludes temporary/constant values from the exploratory correlation matrix.")
para("The original drainage rule removed only half of above-capacity water before clipping storage. Clipping silently removed the remainder. Full-overflow drainage changes reported peak drainage from 18.0704 to 36.1408 mm; it does not change the storage state or rule-label counts because the previous clip forced the same storage state.")
para("Daily-record investigation attributes the largest storage gain (15.67 mm on 2023-04-26) to 17.90 mm rain and 17.005 mm effective rainfall. The largest one-day decline (3.63 mm on 2023-05-16) follows 0.07 mm rain and 3.70 mm modelled actual ET. The 98 capacity days and 28 near-complete-depletion days are therefore consequences of the frozen weather sequence and the simplified 58.5 mm bucket, not soil-moisture observations.")
add_table(["Check", "Audited result"], [
["Coverage and missingness", "365 expected days; no duplicates, invalid dates or source missing cells"],
["Weather broad screens", "rain 0 to 39.61 mm/day; Tmax 23.21 to 38.47 C; Tmin 13.69 to 23.96 C; all pass"],
["ETc check", "max reconstruction error 8.88e-16 mm/day"],
["Water balance", "364 transitions; max absolute error 1.42e-14 mm"],
["Storage and VWC", "storage within 0 to 58.5 mm; derived variable errors below 7.11e-15 percentage points"],
["Rule labels", "low 197 days, moderate 43, high 125; action mapping exact"],
])
figure("soil_water_storage_mm_modelled.png", "Figure 1. Modelled bucket storage; saturation at 58.5 mm is a capacity artefact, not a measured soil-water plateau.")
figure("depletion_fraction_modelled.png", "Figure 2. Modelled depletion; rapid shifts arise from the daily bucket rule and weather input.")
figure("rainfall_mm.png", "Figure 3. Frozen NASA POWER daily rainfall estimate used in the audited run.")
figure("numeric_correlation_heatmap.png", "Figure 4. Exploratory source-field correlations; deterministic variables correlate by construction and do not prove causality.")

doc.add_heading("5 Sources evidence and applicability", 1)
add_table(["Source and access date", "Support", "Applicability boundary"], [
["NASA POWER Daily API documentation, NASA, accessed 2026-10-18, https://power.larc.nasa.gov/docs/services/api/temporal/daily/", "Daily data service, original source resolution and Local Solar Time default", "Supports provenance/API use, not farm-level measurement accuracy."],
["Allen, Pereira, Raes and Smith, Crop Evapotranspiration, FAO 56, 1998, Ch 2 and 4, https://www.fao.org/4/x0490e/x0490e06.htm", "FAO Penman Monteith reference ET and required inputs", "Supports general ET0 equation, not local validation."],
["Allen et al, FAO 56, 1998, Ch 6 Eq 58, https://www.fao.org/4/X0490E/x0490e0b.htm", "ETc=Kc ET0 and stage/condition adjustments", "Does not establish Kc .70 for 18 month East Coast Tall at Pollachi."],
["Allen et al, FAO 56, 1998, Ch 8 Eq 82 to 83, https://www.fao.org/4/X0490E/x0490e0e.htm", "TAW, RAW, field capacity, wilting point and stress concepts", "Does not establish soil texture, retention curve or root depth for this site."],
["Jayakumar, Saseendran and Hemaprabha, Crop coefficient for coconut, Agricultural and Forest Meteorology, 1988, DOI 10.1016/0168-1923(88)90051-2", "A lysimeter study of 6-year coconut reported method-dependent Kc values including 0.73 for Blaney Criddle.", "Useful contextual evidence only: different palm age, reference method, season and site; it does not validate Kc 0.70."],
["Miranda et al, Evapotranspiration and crop coefficients for green dwarf coconut, Revista Ciencia Agronomica, 2008, https://periodicos.ufc.br/revistacienciaagronomica/article/view/83857", "At 11 to 41 months, Kc increased from 0.63 to 1.00 under irrigated green dwarf conditions in coastal Ceara.", "Age overlap is partial, but variety, climate, irrigation and country differ; not transferable without calibration."],
["Carvalho et al, Bragantia 83, 2024, DOI 10.1590/1678-4499.20230160", "A 5-year green dwarf coconut study found mean dry-season Kc 1.06 plus or minus 0.12 under its conditions.", "Not applicable as a numerical value to an 18-month East Coast Tall palm at Pollachi; it demonstrates context dependence."],
["Rajagopal, Kasturi Bai and Voleti, Root activity and root-zone soil water dynamics of coconut palms, Agricultural Water Management 38, 1998, DOI 10.1016/S0378-3774(98)00064-X", "An older-palm study in gravelly soil reported most roots between 20 and 100 cm depth.", "Root architecture varies by age and soil. This is contextual evidence, not validation of the provisional 0.45 m root-zone depth."],
["TNAU Coconut nutrient management, accessed 2026-10-18, https://agritech.tnau.ac.in/expert_system/coconut/coconut/coconut_nutrient_management.html", "Tamil Nadu table lists 20 kg compost/palm/year in second year", "Age-aligned nutrient reference only; not a water-balance parameter source."],
["TNAU irrigation URL in project, accessed 2026-10-18, https://www.agritech.tnau.ac.in/expert_system/coconut/coconut/coconut_irrigation_management.html", "Could not be reliably retrieved", "Stored 45 L seedling summary remains unverified and is not an operational recommendation."],
])

doc.add_heading("6 Parameter verification status", 1)
add_table(["Parameter", "Prototype value", "Evidence and status"], [
["Kc", "0.70 dimensionless", "Provisional. Coconut studies report context-specific values from 0.63 upward and historical method-dependent values; none matches the study palm/site."],
["Field capacity", "0.23 m3/m3", "Provisional. FAO-56 supports use in TAW but requires soil-specific retention information."],
["Wilting point", "0.10 m3/m3", "Provisional. Requires site texture/retention measurement."],
["Root-zone depth", "0.45 m", "Provisional. Coconut root-distribution evidence is mainly for older palms and different soils; no age-matched root observations."],
["Initial available water", "0.70 fraction of TAW", "Initial-condition assumption, not an observation. New sensitivity scenarios test 0.40 and 0.90."],
["Runoff", "0.05 of rainfall", "Provisional fixed fraction; needs slope, surface, rainfall-intensity and infiltration evidence."],
["Drainage", "all storage above TAW", "Mathematically required for closure of this bucket; physical drainage rate is not calibrated."],
["Stress threshold p", "0.50 depletion fraction", "FAO-56 notes p is crop and ETc dependent; 0.50 is a common generic default, not a validated coconut threshold."],
])

doc.add_heading("7 Exploratory sensitivity analysis", 1)
para("One parameter was changed at a time with the 2023 frozen weather held fixed. Ranges are explicitly exploratory because no source matching 18-month East Coast Tall, Pollachi, the actual soil and management was established. This is not independent validation.")
add_table(["Scenario", "Mean min max storage mm", "Capacity days", "Near depletion days", "High-rule days"], [
["Baseline", "38.09 / 0.47 / 58.50", "98 (26.8%)", "28 (7.7%)", "125 (34.2%)"],
["Kc .55 / .85", "41.23 / 1.13 / 58.50; 35.45 / .23 / 58.50", "121 / 78", "19 / 36", "109 / 154"],
["Available water low / high", "22.42 / .06 / 36.00; 68.67 / 2.80 / 99.00", "104 / 95", "42 / 15", "150 / 109"],
["Root depth .30 / .60 m", "24.46 / .10 / 39.00; 52.66 / 1.42 / 78.00", "102 / 95", "39 / 22", "146 / 110"],
["Initial storage .40 / .90", "37.47 / .45 / 58.50; 38.68 / .50 / 58.50", "98 / 98", "29 / 28", "129 / 119"],
["Runoff 0 / 15 percent", "38.63 / .50 / 58.50; 36.98 / .43 / 58.50", "102 / 85", "27 / 31", "122 / 139"],
["Trigger .40 / .60", "38.91 / .91 / 58.50; 37.44 / .21 / 58.50", "99 / 97", "22 / 38", "144 / 112"],
])
para("Capacity uses storage at TAW within 1e-8 mm; near complete depletion means depletion at least 0.95. Baseline actions are 197 continue-monitoring, 43 recheck, and 125 consider-irrigation-if-field-conditions-confirm. For each scenario the action counts exactly equal low, moderate and high rule counts. Available-water capacity, root depth and Kc have the greatest simulated effect; initial storage chiefly affects early-season classification. Thus 125 high-rule days cannot be interpreted as observed stress frequency.")

doc.add_page_break()
doc.add_heading("8 Reproducibility and remaining work", 1)
para("Run from repository root with pandas, numpy, matplotlib and requests installed: export COCOCARE_OUTPUT_DIR to ml/data/coconut_health/audit_artifacts/audited_run; export COCOCARE_WEATHER_CSV to ml/data/coconut_health/data/cococare_stage1_outputs/coimbatore_nasa_power_weather.csv; run the generator, evaluator, run_sensitivity_analysis.py, then python -m unittest discover -s ml/data/coconut_health/tests -v. Omit the weather CSV only to intentionally retrieve a fresh NASA POWER input, and retain the new snapshot/provenance.")
para("Field validation remains required. Collect site elevation and coordinates, measured rain/weather, soil texture and retention curves, effective root depth by age, irrigation dates/volumes, and repeated soil-water observations. Compare prospectively against independent withheld observations and revise parameters only under a documented calibration protocol. A zero arithmetic residual is not proof of physical accuracy.", "Required next work. ")
add_table(["Final audit area", "Status"], [
["Original data preserved", "Yes; original directory untouched and hash recorded"],
["Generator and evaluator rerun", "Yes; separate frozen-input audited output"],
["Defects fixed", "Drainage closure, output/reuse controls, source missingness/columns, correlation inputs"],
["Automated test", "Frozen-input end-to-end test passes"],
["Independent field validation", "Not available"],
["Operational irrigation recommendations", "Not justified by this prototype"],
])
doc.save(OUT)
print(OUT)
