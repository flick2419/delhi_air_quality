"""Streamlit dashboard backed by the pipeline's saved data and metrics."""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
EXTERNAL = ROOT / "data" / "external"

st.set_page_config(
    page_title="Delhi Air Quality Forecasting",
    page_icon="🌫️",
    layout="wide",
)
st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 3rem; }
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #102a43 0%, #1f4e79 100%);
        border: 1px solid #2f6690;
        border-radius: 14px;
        padding: 1rem 1.1rem;
    }
    [data-testid="stMetricLabel"], [data-testid="stMetricValue"],
    [data-testid="stMetricDelta"] { color: white; }
    .status-card {
        border-radius: 14px; padding: 1rem 1.2rem; margin: .4rem 0 1.2rem;
        border-left: 6px solid #2f6690; background: #eef6fb;
    }
    .muted { color: #52606d; font-size: .9rem; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.warning(
    "Academic prototype only. This is not an official government forecast "
    "or emergency warning service."
)
st.title("🌫️ Delhi Air Quality Forecasting")
st.caption("A real-data academic prototype for station-level PM2.5 forecasting")


@st.cache_data
def load_frame(path):
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    if "timestamp" in frame:
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    return frame


def load_metrics():
    path = PROCESSED / "results.json"
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        st.error(f"Could not read {path.name}: {error}")
        return {}


def pm25_category(value):
    if value is None:
        return "Unavailable"
    if value <= 30:
        return "Good"
    if value <= 60:
        return "Satisfactory"
    if value <= 90:
        return "Moderate"
    if value <= 120:
        return "Poor"
    if value <= 250:
        return "Very Poor"
    return "Severe"


data = load_frame(PROCESSED / "clean_air_quality.csv")
predictions = load_frame(PROCESSED / "predictions.csv")
aqi_summary = load_frame(PROCESSED / "aqi_summary.csv")
metrics = load_metrics()

if data.empty:
    st.info("Run the ingestion and processing pipeline before opening the dashboard.")
    st.stop()

stations = sorted(data["station"].dropna().unique())
st.sidebar.header("Dashboard controls")
station = st.sidebar.selectbox("Monitoring station", stations)
window_days = st.sidebar.slider("Trend window (days)", 7, 90, 30)
st.sidebar.caption("Use the refresh button in the browser after rerunning the pipeline.")
station_data = data[data["station"] == station].sort_values("timestamp")

latest = station_data.iloc[-1]
latest_pm25 = float(latest["pm25"]) if pd.notna(latest["pm25"]) else None
model_prediction = None
if not predictions.empty and "station" in predictions:
    selected = predictions[predictions["station"] == station]
    if not selected.empty and "prediction_ridge" in selected:
        model_prediction = float(selected.sort_values("timestamp").iloc[-1]["prediction_ridge"])

ridge_metrics = metrics.get("Ridge Regression", {})
r2 = ridge_metrics.get("R2")
latest_timestamp = latest.get("timestamp")
category = pm25_category(latest_pm25)

st.markdown(
    f'<div class="status-card"><strong>{station}</strong><br>'
    f'<span class="muted">Latest observation: '
    f'{latest_timestamp if pd.notna(latest_timestamp) else "Unavailable"} · '
    f'PM2.5 category: <strong>{category}</strong></span></div>',
    unsafe_allow_html=True,
)

col1, col2, col3, col4 = st.columns(4)
col1.metric(
    "Latest PM2.5",
    f"{latest_pm25:.1f} µg/m³" if latest_pm25 is not None else "Unavailable",
)
col2.metric(
    "Ridge next-day prediction",
    f"{model_prediction:.1f} µg/m³"
    if model_prediction is not None
    else "Run model evaluation",
)
col3.metric("Ridge test R²", f"{float(r2):.3f}" if r2 is not None else "Unavailable")
col4.metric("Observations", f"{len(station_data):,}")

tab1, tab2, tab3, tab4 = st.tabs(
    ["📈 Trends & forecast", "🧠 Explainability", "🌍 AQI overview", "ℹ️ Methodology"]
)
with tab1:
    chart = station_data.set_index("timestamp")[["pm25"]].rename(
        columns={"pm25": "Actual PM2.5"}
    )
    if not chart.empty:
        chart = chart.tail(max(1, window_days * 48))
        st.line_chart(chart)
    if not predictions.empty and "station" in predictions:
        selected = predictions[predictions["station"] == station].sort_values("timestamp")
        if not selected.empty and {"pm25_next_day", "prediction_ridge"}.issubset(selected.columns):
            st.subheader("Held-out comparison")
            comparison = selected.set_index("timestamp")[
                ["pm25_next_day", "prediction_ridge"]
            ].rename(
                columns={
                    "pm25_next_day": "Observed next-day PM2.5",
                    "prediction_ridge": "Ridge prediction",
                }
            )
            st.line_chart(comparison.tail(max(1, window_days * 48)))
    st.subheader("Latest observations")
    st.dataframe(station_data.tail(10), use_container_width=True, hide_index=True)

with tab3:
    if aqi_summary.empty:
        st.info("Import `aqi.csv` to enable the national AQI overview.")
    else:
        st.subheader("Daily AQI summary")
        st.caption(
            "This is a separate city/state AQI dataset and is not used by the PM2.5 model."
        )
        aqi_states = ["All states"] + sorted(aqi_summary["state"].unique())
        selected_state = st.selectbox("State", aqi_states)
        filtered_aqi = aqi_summary
        if selected_state != "All states":
            filtered_aqi = filtered_aqi[filtered_aqi["state"] == selected_state]
        aqi_areas = ["All areas"] + sorted(filtered_aqi["area"].unique())
        selected_area = st.selectbox("Area", aqi_areas)
        if selected_area != "All areas":
            filtered_aqi = filtered_aqi[filtered_aqi["area"] == selected_area]

        aqi_col1, aqi_col2, aqi_col3 = st.columns(3)
        aqi_col1.metric("Rows", f"{len(filtered_aqi):,}")
        aqi_col2.metric(
            "Average AQI",
            f"{filtered_aqi['aqi'].mean():.0f}" if not filtered_aqi.empty else "Unavailable",
        )
        aqi_col3.metric(
            "Highest AQI",
            f"{filtered_aqi['aqi'].max():.0f}" if not filtered_aqi.empty else "Unavailable",
        )
        if not filtered_aqi.empty:
            trend = (
                filtered_aqi.groupby("date", as_index=True)["aqi"]
                .mean()
                .rename("Average AQI")
            )
            st.line_chart(trend)
            st.dataframe(
                filtered_aqi.sort_values("date", ascending=False).head(20),
                use_container_width=True,
                hide_index=True,
            )

with tab2:
    shap_path = EXTERNAL / "shap_summary.png"
    if shap_path.exists():
        st.image(str(shap_path), caption="Feature impact summary")
    else:
        st.info("SHAP output is not available yet.")

with tab4:
    st.markdown("#### What this dashboard shows")
    st.markdown(
        "- **Latest PM2.5:** most recent observation for the selected station.\n"
        "- **Prediction:** Ridge Regression output from the held-out test file.\n"
        "- **R²:** test-set performance loaded from `results.json`.\n"
        "- **Category:** PM2.5-based CPCB-style category, not an official AQI bulletin."
    )
    st.markdown("#### Pipeline")
    st.code(
        "OpenAQ → cleaning → 24-hour target → chronological split → Ridge model",
        language="text",
    )
    st.caption(
        "This application is for academic evaluation. It is not an official "
        "government forecast or emergency warning service."
    )
#.\venv\Scripts\python.exe -m streamlit run .\app\ui.py to run the website 
