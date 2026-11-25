# Delhi Air Quality Forecasting

A personal machine-learning project for station-level PM2.5 forecasting in Delhi.
The project uses real OpenAQ observations, chronological evaluation, persistence
and Ridge baselines, Random Forest, optional SVR/XGBoost, SHAP, and Streamlit.

## Project boundaries

- This is an academic decision-support prototype, not an official CPCB forecast.
- The PM2.5 model is separate from the city/state AQI summary dataset.
- Metrics should be reproduced only from real, validated data.
- Do not commit API keys or credentials.

## Setup

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run the pipeline

Set an OpenAQ API key in the current PowerShell session:

```powershell
$env:OPENAQ_API_KEY = "YOUR_KEY"
```

Download PM2.5 observations:

```powershell
.\venv\Scripts\python.exe .\src\download_openaq.py
```

Clean, engineer features, split chronologically, and evaluate:

```powershell
.\venv\Scripts\python.exe .\src\cleaning.py
.\venv\Scripts\python.exe .\src\features.py
.\venv\Scripts\python.exe .\src\split_validate.py
.\venv\Scripts\python.exe .\src\models.py
```

## Refresh live Delhi data

The application uses two public sources:

- CPCB real-time PM2.5 readings through data.gov.in
- CAMS PM2.5/PM10 forecasts through Open-Meteo

Refresh the saved live snapshots:

```powershell
.\venv\Scripts\python.exe .\src\download_live_air_quality.py
```

The script prefers `DATAGOV_API_KEY` when set. It has a public documented
demo-key fallback with low-volume limits:

```powershell
$env:DATAGOV_API_KEY = "YOUR_DEDICATED_DATA_GOV_IN_KEY"
```

The live downloader keeps the last successful snapshot if a source is temporarily
unavailable. Never interpret stale data as fresh: the dashboard displays the
latest stored CPCB timestamp and source.

Launch the dashboard:

```powershell
.\venv\Scripts\python.exe -m streamlit run .\app\ui.py
```

## Optional AQI summary

If `aqi.csv` is a city/state daily AQI summary rather than station PM2.5 data:

```powershell
.\venv\Scripts\python.exe .\src\import_aqi_summary.py "C:\path\to\aqi.csv"
```

The AQI summary is separate from the PM2.5 model and is loaded by the dashboard
through `data/processed/aqi_summary.csv`.

## Tests

```powershell
.\venv\Scripts\python.exe -m pytest -q
```
