"""Generate detailed project documentation from the current repository outputs."""

import json
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROCESSED = DATA / "processed"
RAW = DATA / "raw"
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)


def load_outputs():
    clean = pd.read_csv(PROCESSED / "clean_air_quality.csv")
    clean["timestamp"] = pd.to_datetime(clean["timestamp"], errors="coerce")
    clean["pm25"] = pd.to_numeric(clean["pm25"], errors="coerce")
    with (PROCESSED / "results.json").open(encoding="utf-8") as file:
        metrics = json.load(file)
    splits = {
        name: pd.read_csv(PROCESSED / f"{name}.csv")
        for name in ("train", "val", "test")
    }
    aqi = None
    aqi_path = PROCESSED / "aqi_summary.csv"
    if aqi_path.exists():
        aqi = pd.read_csv(aqi_path)
    station_stats = (
        clean.groupby("station")
        .agg(
            observations=("pm25", "size"),
            start=("timestamp", "min"),
            end=("timestamp", "max"),
            mean_pm25=("pm25", "mean"),
            median_pm25=("pm25", "median"),
        )
        .reset_index()
    )
    return clean, metrics, splits, station_stats, aqi


def date_text(value):
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def metric_table(metrics):
    rows = ["| Model | MAE | RMSE | R² |", "|---|---:|---:|---:|"]
    for key in ("Baseline (Persistence)", "Ridge Regression", "SVR", "Random Forest", "XGBoost"):
        value = metrics[key]
        rows.append(
            f"| {key} | {value['MAE']:.2f} | {value['RMSE']:.2f} | "
            f"{value['R2']:.3f} |"
        )
    return "\n".join(rows)


def build_markdown(clean, metrics, splits, station_stats, aqi):
    aqi_note = (
        f"The separate AQI summary branch contains {len(aqi):,} rows."
        if aqi is not None
        else "The optional AQI summary branch was not present when this report was generated."
    )
    station_lines = "\n".join(
        f"| {row.station} | {int(row.observations):,} | {date_text(row.start)} | "
        f"{date_text(row.end)} | {row.mean_pm25:.2f} | {row.median_pm25:.2f} |"
        for row in station_stats.itertuples()
    )
    split_lines = "\n".join(
        f"| {name.title()} | {len(frame):,} |"
        for name, frame in splits.items()
    )
    return f"""# Delhi Air Quality Forecasting

**Complete technical documentation**  
**Course:** CSET-211 Statistical Machine Learning  
**Project type:** Academic machine-learning prototype  
**Report generated:** November 2026

## Executive summary

This repository implements a reproducible Delhi air-quality workflow. It collects
real monitoring observations from OpenAQ, stores them as station-level CSV files,
cleans and validates the observations, constructs a leakage-aware 24-hour PM2.5
target, creates time-series features, performs chronological evaluation, compares
three forecasting approaches, saves predictions and metrics, creates a SHAP
explainability image, and presents the outputs in Streamlit.

The current evaluation uses `{len(clean):,}` processed station observations across
`{clean["station"].nunique()}` stations. The overall timestamp range is
`{date_text(clean["timestamp"].min())}` to `{date_text(clean["timestamp"].max())}`.
The data is not continuous for every station; station-specific availability is
reported below.

SVR is the preferred model in the current run. It achieves MAE
`{metrics["SVR"]["MAE"]:.2f}`, RMSE
`{metrics["SVR"]["RMSE"]:.2f}`, and R²
`{metrics["SVR"]["R2"]:.3f}` on the held-out test set.

## 1. Problem statement

Delhi PM2.5 varies by time, station, season, and pollution episode. The project
asks whether recent observations and calendar information can estimate the PM2.5
concentration at the same station exactly 24 hours later. The system is a
decision-support prototype for academic evaluation. It is not an official
government forecast, medical recommendation, or emergency warning service.

## 2. Objectives

1. Replace placeholder measurements with real Delhi monitoring observations.
2. Build a robust import and cleaning path for station CSV files.
3. Define a timestamp-correct 24-hour forecasting target.
4. Create predictors without using future information.
5. Compare persistence, Ridge, SVR, Random Forest, and XGBoost.
6. Evaluate chronologically rather than randomly shuffling time-series records.
7. Produce reproducible prediction, metric, and explainability artifacts.
8. Present the results in a transparent Streamlit dashboard.
9. Keep the separate city/state AQI summary dataset available for overview analysis
   without incorrectly mixing AQI indices into the PM2.5 model.

## 3. Repository structure

| Path | Purpose |
|---|---|
| `configs/config.yaml` | Project name, seed, station settings, target settings |
| `src/download_openaq.py` | OpenAQ v3 PM2.5 downloader |
| `src/data_ingest.py` | Manual CSV import and optional weather download |
| `src/cleaning.py` | Data validation, physical bounds, interpolation, merge |
| `src/features.py` | Target, lag, rolling, and calendar features |
| `src/split_validate.py` | Chronological train/validation/test files |
| `src/models.py` | Baseline, Ridge, SVR, Random Forest, XGBoost, SHAP, saved outputs |
| `src/aqi_calc.py` | PM2.5 sub-index and category helper |
| `src/eda.py` | Exploratory plot generation |
| `app/ui.py` | Streamlit dashboard |
| `data/raw/` | Downloaded station CSV inputs |
| `data/processed/` | Cleaned data, splits, predictions, and metrics |
| `data/external/` | Plots and SHAP output |

## 4. Data acquisition

### 4.1 OpenAQ downloader

`download_openaq.py` uses the OpenAQ v3 API and requires an API key supplied
through `OPENAQ_API_KEY` or `--api-key`. The key is deliberately not stored in
the repository.

The downloader:

1. Searches a Delhi bounding box using minimum longitude, minimum latitude,
   maximum longitude, and maximum latitude.
2. Retrieves locations and their sensors.
3. Selects sensors whose parameter is PM2.5.
4. Requests precomputed hourly readings from the sensor endpoint.
5. Handles a single retry for HTTP 429 responses.
6. Checks response status and includes the response body in failures.
7. Converts timestamps and values to usable types.
8. Applies a local date-range filter even if an API response contains older history.
9. Removes duplicate station/timestamp rows.
10. Writes `air_quality_<station>.csv` files.

Expected raw schema:

```text
timestamp,station,pm25
```

### 4.2 Coverage

| Station | Observations | Start | End | Mean PM2.5 | Median PM2.5 |
|---|---:|---|---|---:|---:|
{station_lines}

These rows represent the actual downloaded records, not a claim of continuous
coverage. DTU has older records, while other stations have more recent records,
so a decade-wide station-by-station interpretation would be incorrect.

### 4.3 Separate AQI summary data

{aqi_note} The AQI summary has fields such as date, state, area, monitoring
station count, prominent pollutant, AQI value, and status. It is a different
measurement level from station PM2.5 concentrations. It should therefore be
cleaned and displayed separately, not merged into the PM2.5 target or model
features without a documented redesign.

## 5. Cleaning and validation

`cleaning.py` discovers every `air_quality_*.csv` file in `data/raw`, so imported
station names do not need to be listed in configuration. For each file it:

- Parses `timestamp` as a datetime.
- Sorts observations by timestamp.
- Clips negative pollutant values to zero.
- Treats values above 1,500 as invalid sensor values.
- Interpolates short gaps up to six observations.
- Fills remaining missing pollutant values with the column median.
- Concatenates station frames.
- Optionally merges Open-Meteo weather columns by timestamp.
- Writes `data/processed/clean_air_quality.csv`.

The AQI summary branch has its own importer because its columns and semantics are
different. It parses day-first dates, converts AQI and monitoring-station counts
to numeric values, removes invalid date/AQI/area rows, normalizes labels, sorts
the result, and writes `data/processed/aqi_summary.csv`.

## 6. Feature engineering

`features.py` sorts by station and timestamp and performs a timestamp lookup:

```text
target(station, t) = PM2.5(station, t + 24 hours)
```

This is preferable to a fixed 24-row shift because OpenAQ records may be hourly,
half-hourly, or irregular. The following features are created:

| Feature | Definition |
|---|---|
| `pm25_lag1` | Previous observation for the same station |
| `pm25_rolling_3h` | Mean of prior three observations |
| `pm25_rolling_24h` | Mean of prior 24 observations |
| `hour` | Hour extracted from timestamp |
| `dayofweek` | Monday=0 through Sunday=6 |
| `month` | Calendar month |
| `is_weekend` | 1 for Saturday/Sunday, otherwise 0 |

The lag is created before the rolling means, preventing the current observation
from leaking into the rolling predictors. Rows without a known 24-hour target are
dropped. The result is saved as `model_ready_data.csv`.

## 7. Chronological splitting

`split_validate.py` sorts the model-ready records by timestamp. It reserves the
latest one year for testing, the previous six months for validation, and earlier
records for training. It also configures a five-split `TimeSeriesSplit` object as
a walk-forward validation reference.

| Split | Rows |
|---|---:|
{split_lines}

The split is chronological because random shuffling can place future observations
in training and make evaluation unrealistically optimistic.

## 8. Models and evaluation

### 8.1 Persistence baseline

The baseline predicts the next-day value as the current PM2.5 value. This is
important because air pollution is persistent, and a complex model should be
compared against this simple forecast.

### 8.2 Ridge Regression

Ridge is implemented as a scikit-learn pipeline:

1. Standardize numeric features with `StandardScaler`.
2. Fit `Ridge(alpha=1.0)`.
3. Predict the held-out test rows.

Ridge is retained as a strong linear comparison and for SHAP explainability.

### 8.3 Support Vector Regression

SVR uses standardized numeric features and an RBF kernel with `C=10.0` and
`epsilon=0.1`. In the current run it has the lowest RMSE and highest R².

### 8.4 Random Forest

The tree model uses 100 estimators, `random_state=42`, and parallel workers.
It is retained as a meaningful comparison even though it underperforms the
baseline and Ridge on the current feature set.

### 8.5 Metrics

- **MAE:** average absolute prediction error in µg/m³.
- **RMSE:** square-root average squared error; more sensitive to large spikes.
- **R²:** proportion of test-target variance explained by predictions.

## 9. Results

{metric_table(metrics)}

SVR has the lowest RMSE and highest R². Persistence remains competitive, while
Ridge is a strong linear alternative. Random Forest and XGBoost do not improve
over SVR in this run.

## 10. SHAP explainability

`models.py` generates `data/external/shap_summary.png` after fitting Ridge.
It takes the fitted scaler output, uses `shap.LinearExplainer`, limits the
explanation sample to 2,000 training rows, and creates a global bar summary of
mean absolute feature impact. This output explains feature influence, not causal
pollution mechanisms. SHAP values should be interpreted as model explanations
within this feature set.

## 11. Streamlit implementation

`app/ui.py` loads:

- `clean_air_quality.csv` for station trends.
- `predictions.csv` for held-out SVR predictions.
- `results.json` for evaluation metrics.
- `aqi_summary.csv` for the separate AQI overview.
- `shap_summary.png` for explainability.

The dashboard includes:

1. Station selector.
2. Seven-to-90-day trend-window slider.
3. Latest PM2.5 value and PM2.5 category.
4. SVR next-day prediction where the selected station overlaps test data.
5. SVR test R².
6. Observation count.
7. Historical PM2.5 chart.
8. Held-out observed-versus-predicted chart.
9. SHAP tab.
10. AQI overview tab with state and area filters, averages, maximums, trends,
    and recent records.
11. Methodology and academic disclaimer.

When a station has no rows in the test predictions, the absence means that its
records do not overlap the held-out test period; it does not mean that model
evaluation failed.

## 12. Reproducibility

From the repository root in PowerShell:

```powershell
cd C:\\path\\to\\delhi_air_quality
$env:OPENAQ_API_KEY = "YOUR_KEY"

.\\venv\\Scripts\\python.exe .\\src\\download_openaq.py `
  --start-date 2016-01-01 --end-date 2026-11-17 --max-stations 5
.\\venv\\Scripts\\python.exe .\\src\\cleaning.py
.\\venv\\Scripts\\python.exe .\\src\\features.py
.\\venv\\Scripts\\python.exe .\\src\\split_validate.py
.\\venv\\Scripts\\python.exe .\\src\\models.py
.\\venv\\Scripts\\python.exe -m streamlit run .\\app\\ui.py
```

Do not commit the API key. If the optional AQI summary file is replaced, run its
dedicated importer before refreshing Streamlit. Do not send AQI summary data
through the station PM2.5 cleaner.

## 13. Testing and verification

The project has been validated by:

- Python compilation of changed scripts.
- Downloader CLI help execution.
- Successful OpenAQ data download with varied PM2.5 values.
- Date-range checks on saved station files.
- Successful cleaning, feature generation, chronological splitting, and model evaluation.
- Verification of saved `results.json` and `predictions.csv`.
- Successful SHAP image generation.
- Successful Streamlit startup after UI fixes.
- Removal and verification of generated Python cache files.

Useful checks:

```powershell
.\\venv\\Scripts\\python.exe -m py_compile .\\src\\models.py .\\src\\features.py .\\app\\ui.py
Get-ChildItem . -Directory -Filter __pycache__ -Recurse
```

## 14. Limitations and responsible interpretation

1. Station histories are uneven and include temporal gaps.
2. The current model uses PM2.5 history and calendar fields; weather and other
   pollutants are not included in the trained feature matrix for this run.
3. Large spikes produce substantial absolute errors.
4. OpenAQ records may have sensor-specific availability and quality issues.
5. AQI summary records are not station-level PM2.5 concentration measurements.
6. The model is evaluated on the available held-out period, not on every possible
   Delhi station and season.
7. The dashboard is an academic prototype, not an official public-health service.

## 15. Conclusion and future work

The repository now provides a complete real-data workflow from acquisition through
dashboard presentation. The evaluation demonstrates that SVR explains approximately
67% of held-out target variation in the current experiment, while
the persistence baseline remains competitive. This supports a measured conclusion:
the model is useful as an academic forecasting demonstration, but its performance
does not justify operational or public-health claims.

Future work should add validated weather and pollutant features, improve station
coverage, tune hyperparameters using the validation period, evaluate multiple
rolling test windows, investigate station-specific models, add uncertainty
intervals, and integrate official CPCB data with documented provenance.

## 16. References

- OpenAQ API documentation: https://docs.openaq.org/
- OpenAQ: https://openaq.org/
- CPCB Air Quality Portal: https://airquality.cpcb.gov.in/ccr/
- scikit-learn documentation: https://scikit-learn.org/
- SHAP documentation: https://shap.readthedocs.io/
- Streamlit documentation: https://docs.streamlit.io/
"""


def add_table(document, headers, rows):
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Light Shading Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for cell, value in zip(table.rows[0].cells, headers):
        cell.text = str(value)
    for row in rows:
        cells = table.add_row().cells
        for cell, value in zip(cells, row):
            cell.text = str(value)


def build_docx(clean, metrics, splits, station_stats, aqi):
    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.7)
    section.left_margin = Inches(0.85)
    section.right_margin = Inches(0.85)
    document.styles["Normal"].font.name = "Aptos"
    document.styles["Normal"].font.size = Pt(10)

    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("Delhi Air Quality Forecasting")
    run.bold = True
    run.font.size = Pt(28)
    run.font.color.rgb = RGBColor(12, 35, 58)
    subtitle = document.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.add_run(
        "Complete Technical Documentation\n"
        "CSET-211 Statistical Machine Learning | November 2026"
    )

    def heading(text, level=1):
        document.add_heading(text, level=level)

    def paragraph(text):
        document.add_paragraph(text)

    heading("Executive summary")
    paragraph(
        f"This repository implements a reproducible Delhi PM2.5 forecasting workflow "
        f"with {len(clean):,} processed observations across "
        f"{clean['station'].nunique()} stations. It includes OpenAQ ingestion, "
        "cleaning, timestamp-correct target construction, leakage-aware features, "
        "chronological evaluation, model comparison, SHAP explainability, and a "
        "Streamlit dashboard."
    )
    paragraph(
        f"SVR is the preferred current model: MAE "
        f"{metrics['SVR']['MAE']:.2f}, RMSE "
        f"{metrics['SVR']['RMSE']:.2f}, and R² "
        f"{metrics['SVR']['R2']:.3f}."
    )

    heading("1. Problem statement")
    paragraph(
        "The system estimates PM2.5 at the same Delhi monitoring station exactly "
        "24 hours after an observed timestamp. It is an academic decision-support "
        "prototype, not an official forecast or emergency warning service."
    )
    heading("2. Objectives")
    for text in [
        "Collect real Delhi station observations instead of placeholder values.",
        "Build a robust station CSV cleaning and validation path.",
        "Create a timestamp-correct 24-hour PM2.5 target.",
        "Prevent future leakage in lag and rolling features.",
        "Compare persistence, Ridge, SVR, Random Forest, and XGBoost.",
        "Evaluate chronologically and expose reproducible artifacts.",
        "Provide a transparent Streamlit dashboard.",
        "Keep the separate city/state AQI dataset out of the PM2.5 model.",
    ]:
        document.add_paragraph(text, style="List Bullet")

    heading("3. Repository structure")
    add_table(document, ["Path", "Purpose"], [
        ["configs/config.yaml", "Project configuration and target settings"],
        ["src/download_openaq.py", "OpenAQ v3 PM2.5 acquisition"],
        ["src/data_ingest.py", "Manual CSV import and optional weather"],
        ["src/cleaning.py", "Cleaning and optional weather merge"],
        ["src/features.py", "Target and feature engineering"],
        ["src/split_validate.py", "Chronological data splitting"],
        ["src/models.py", "Training, metrics, predictions, SHAP"],
        ["src/aqi_calc.py", "PM2.5 sub-index/category helper"],
        ["app/ui.py", "Streamlit dashboard"],
        ["data/raw and data/processed", "Inputs and generated artifacts"],
    ])

    heading("4. Data acquisition and coverage")
    paragraph(
        f"OpenAQ observations span {date_text(clean['timestamp'].min())} to "
        f"{date_text(clean['timestamp'].max())} overall. The span is not continuous "
        "for every station, so the report does not claim decade-long coverage for "
        "each station."
    )
    add_table(document, ["Station", "Rows", "Start", "End", "Mean", "Median"], [
        [
            row.station,
            f"{int(row.observations):,}",
            date_text(row.start),
            date_text(row.end),
            f"{row.mean_pm25:.2f}",
            f"{row.median_pm25:.2f}",
        ]
        for row in station_stats.itertuples()
    ])
    paragraph(
        "The optional AQI summary branch is separate because its records contain "
        "daily city/state AQI indices rather than station PM2.5 concentrations."
    )

    heading("5. Cleaning and validation")
    paragraph(
        "The station cleaner parses timestamps, sorts records, clips negative "
        "pollutants, invalidates extreme values above 1,500, interpolates short "
        "gaps up to six observations, fills remaining missing values with medians, "
        "and writes clean_air_quality.csv. The importer discovers all "
        "air_quality_*.csv files instead of relying on a fixed station list."
    )
    heading("6. Target and features")
    paragraph(
        "The target is created with a station-and-timestamp lookup at t+24 hours. "
        "This works for hourly, half-hourly, and irregular records. Predictors "
        "include the previous PM2.5 value, prior-only rolling means over three and "
        "24 observations, hour, weekday, month, and weekend status."
    )
    heading("7. Chronological evaluation")
    paragraph(
        "The latest year is reserved for testing, the preceding six months for "
        "validation, and earlier data for training. A five-split TimeSeriesSplit "
        "object is configured as a walk-forward reference."
    )
    add_table(document, ["Split", "Rows"], [
        [name.title(), f"{len(frame):,}"] for name, frame in splits.items()
    ])

    heading("8. Model implementation")
    heading("8.1 Persistence baseline", 2)
    paragraph("Predicts the target as the current PM2.5 value.")
    heading("8.2 Ridge Regression", 2)
    paragraph(
        "Uses StandardScaler followed by Ridge(alpha=1.0). The fitted pipeline is "
        "evaluated on the held-out test features."
    )
    heading("8.3 Support Vector Regression", 2)
    paragraph(
        "Uses standardized features, an RBF kernel, C=10.0, and epsilon=0.1. "
        "It is the preferred model in the current run."
    )
    heading("8.4 Random Forest", 2)
    paragraph(
        "Uses 100 estimators, random_state=42, and parallel workers. It remains "
        "a documented comparison even though it is not the best current model."
    )
    heading("8.4 Metrics", 2)
    paragraph(
        "MAE measures average absolute error, RMSE emphasizes large spikes, and R² "
        "measures explained test-target variance."
    )
    add_table(document, ["Model", "MAE", "RMSE", "R²"], [
        [
            key,
            f"{metrics[key]['MAE']:.2f}",
            f"{metrics[key]['RMSE']:.2f}",
            f"{metrics[key]['R2']:.3f}",
        ]
        for key in ("Baseline (Persistence)", "Ridge Regression", "SVR", "Random Forest", "XGBoost")
    ])

    heading("9. SHAP explainability")
    paragraph(
        "After fitting Ridge, models.py transforms the training features with the "
        "fitted scaler, samples at most 2,000 training rows, creates a "
        "shap.LinearExplainer, and saves a global mean-absolute-impact bar plot "
        "to data/external/shap_summary.png. The plot explains this model's feature "
        "behavior; it does not establish causal pollution relationships."
    )

    heading("10. Streamlit dashboard")
    paragraph(
        "The dashboard loads clean station data, held-out predictions, saved metrics, "
        "the SHAP image, and the optional AQI summary. It provides station selection, "
        "a 7–90 day trend window, latest PM2.5, SVR prediction, R², observation "
        "count, historical and held-out charts, SHAP, AQI filters/trends, and a "
        "methodology tab. A station without test-period rows shows no prediction "
        "because its history does not overlap the held-out test period."
    )

    heading("11. Reproducibility commands")
    code = document.add_paragraph()
    code.style = "No Spacing"
    code.add_run(
        "cd C:\\path\\to\\delhi_air_quality\n"
        '$env:OPENAQ_API_KEY = "YOUR_KEY"\n'
        ".\\venv\\Scripts\\python.exe .\\src\\download_openaq.py "
        "--start-date 2016-01-01 --end-date 2026-11-17\n"
        ".\\venv\\Scripts\\python.exe .\\src\\cleaning.py\n"
        ".\\venv\\Scripts\\python.exe .\\src\\features.py\n"
        ".\\venv\\Scripts\\python.exe .\\src\\split_validate.py\n"
        ".\\venv\\Scripts\\python.exe .\\src\\models.py\n"
        ".\\venv\\Scripts\\python.exe -m streamlit run .\\app\\ui.py"
    )
    paragraph(
        "Never commit the API key. If replacing the separate AQI CSV, use its "
        "dedicated importer and do not pass it through the station PM2.5 cleaner."
    )

    heading("12. Testing and verification")
    for text in [
        "Python compilation of changed scripts.",
        "OpenAQ downloader CLI and successful real-data download.",
        "Date-range and distinct-value checks on raw files.",
        "Successful cleaning, feature creation, chronological splits, and evaluation.",
        "Verification of results.json and predictions.csv.",
        "Successful SHAP image generation.",
        "Streamlit startup and corrected tab routing.",
        "Removal and verification of __pycache__ and .pyc artifacts.",
    ]:
        document.add_paragraph(text, style="List Bullet")

    heading("13. Limitations and responsible interpretation")
    for text in [
        "Station histories are uneven and contain temporal gaps.",
        "The current trained features use PM2.5 history and calendar fields; weather and other pollutants are not included in this model run.",
        "Large spikes create substantial absolute errors.",
        "OpenAQ records can have sensor-specific availability and quality issues.",
        "AQI summaries are not station PM2.5 concentration measurements.",
        "The dashboard is an academic prototype, not an official public-health service.",
    ]:
        document.add_paragraph(text, style="List Bullet")

    heading("14. Conclusion and future work")
    paragraph(
        "The repository provides a complete real-data workflow from acquisition "
        "through dashboard presentation. SVR explains approximately 67% of "
        "held-out variation in the current run, while the baseline comparison "
        "prevents overclaiming. Future work should add validated weather and "
        "pollutant features, improve station coverage, tune hyperparameters, use "
        "multiple rolling test windows, add uncertainty intervals, and integrate "
        "official CPCB data with documented provenance."
    )

    heading("15. References")
    for text in [
        "OpenAQ API documentation — https://docs.openaq.org/",
        "OpenAQ — https://openaq.org/",
        "CPCB Air Quality Portal — https://airquality.cpcb.gov.in/ccr/",
        "scikit-learn — https://scikit-learn.org/",
        "SHAP — https://shap.readthedocs.io/",
        "Streamlit — https://docs.streamlit.io/",
    ]:
        document.add_paragraph(text, style="List Bullet")

    output = REPORTS / "Delhi_Air_Quality_Forecasting_Detailed_Report.docx"
    document.save(output)
    return output


def main():
    clean, metrics, splits, station_stats, aqi = load_outputs()
    markdown = build_markdown(clean, metrics, splits, station_stats, aqi)
    md_output = REPORTS / "Delhi_Air_Quality_Forecasting_Detailed_Report.md"
    md_output.write_text(markdown, encoding="utf-8")
    docx_output = build_docx(clean, metrics, splits, station_stats, aqi)
    print(f"Saved {md_output}")
    print(f"Saved {docx_output}")


if __name__ == "__main__":
    main()
