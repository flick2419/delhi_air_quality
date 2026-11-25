"""Modern live and historical air-quality dashboard."""

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
EXTERNAL = ROOT / "data" / "external"

st.set_page_config(
    page_title="AirSight Delhi",
    page_icon="◉",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :html, body, [class*="css"] { font-family: Inter, Aptos, -apple-system, sans-serif; }
    .stApp { background: #eef3f7; }
    section[data-testid="stSidebar"] {
        background: #0b1f33;
        border-right: 1px solid rgba(255,255,255,.08);
    }
    section[data-testid="stSidebar"] * { color: #edf5f7; }
    .block-container { max-width: 1180px; padding-top: 1.25rem; padding-bottom: 2.5rem; }
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #dde6ec;
        border-radius: 16px;
        padding: 18px 20px;
        box-shadow: 0 8px 24px rgba(30, 52, 72, .06);
    }
    [data-testid="stMetricLabel"] { color: #667784; }
    [data-testid="stMetricValue"] { color: #132f46; }
    [data-testid="stDataFrame"] { border-radius: 14px; overflow: hidden; }
    .brand-row {
        display:flex; align-items:center; justify-content:space-between;
        margin: 4px 0 18px 0;
    }
    .brand { display:flex; align-items:center; gap:12px; }
    .brand-mark {
        width:44px; height:44px; border-radius:14px;
        background:linear-gradient(135deg,#18b6a4,#1d6fa5);
        display:grid; place-items:center; color:white; font-weight:800;
        box-shadow: 0 8px 18px rgba(29,111,165,.22);
    }
    .brand-title { color:#102a43; font-size:28px; font-weight:800; letter-spacing:-.5px; }
    .brand-sub { color:#71818d; font-size:13px; margin-top:-2px; }
    .source-pill {
        background:#e5f6f2; color:#14796d; border:1px solid #c5e8df;
        border-radius:999px; padding:7px 12px; font-size:12px; font-weight:700;
    }
    .notice {
        background:#fff8e7; border:1px solid #ecdba8; border-radius:14px;
        color:#5d5028; padding:12px 16px; margin:8px 0 18px 0;
        font-size:13px;
    }
    .section-title { color:#102a43; font-weight:800; font-size:20px; margin-bottom:4px; }
    .section-sub { color:#71818d; font-size:13px; margin-bottom:14px; }
    .stTabs [data-baseweb="tab-list"] { gap:8px; }
    .stTabs [data-baseweb="tab"] {
        background:#fff; border:1px solid #dde6ec; border-radius:10px;
        padding:8px 14px; color:#5d6f7c;
    }
    .stTabs [aria-selected="true"] {
        background:#102a43; border-color:#102a43; color:#fff;
    }
    [data-testid="stAppViewContainer"] {
        color: #1f3444;
    }
    [data-testid="stAppViewContainer"] p,
    [data-testid="stAppViewContainer"] li,
    [data-testid="stAppViewContainer"] label,
    [data-testid="stAppViewContainer"] span {
        color: inherit;
    }
    .stCaption, [data-testid="stCaptionContainer"] {
        color: #6b7c87 !important;
    }
    [data-testid="stDataFrame"] * {
        color: #203746 !important;
    }
    [data-testid="stDataFrame"] th {
        background: #edf3f6 !important;
    }
    [data-testid="stSelectbox"] > div,
    [data-testid="stSlider"] {
        background: transparent;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=300)
def load_csv(path):
    path = Path(path)
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    if "timestamp" in frame:
        frame["timestamp"] = pd.to_datetime(
            frame["timestamp"], errors="coerce", format="mixed", dayfirst=True
        )
    return frame


@st.cache_data(ttl=300)
def load_status():
    path = PROCESSED / "live_status.json"
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8-sig")
        return json.loads(text)
    except (OSError, json.JSONDecodeError):
        return {}


@st.cache_data(ttl=300)
def load_metrics():
    path = PROCESSED / "results.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def start_live_refresh():
    """Start a bounded live refresh without blocking Streamlit reruns."""
    placeholder = st.session_state.get("live_refresh_placeholder")
    if st.session_state.get("live_refresh_running"):
        return
    st.session_state["live_refresh_running"] = True
    st.session_state["live_refresh_error"] = ""
    st.session_state["live_refresh_started"] = time.time()

    def refresh():
        try:
            result = subprocess.run(
                [sys.executable, str(ROOT / "src" / "download_live_air_quality.py")],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=120,
            )
            st.session_state["live_refresh_result"] = (
                "success" if result.returncode == 0
                else (result.stderr[-1200:] or "Live refresh failed.")
            )
        except subprocess.TimeoutExpired:
            st.session_state["live_refresh_result"] = "Live refresh timed out."
        except Exception as error:
            st.session_state["live_refresh_result"] = str(error)
        finally:
            st.session_state["live_refresh_running"] = False
            load_csv.clear()
            load_status.clear()

    thread = threading.Thread(target=refresh, daemon=True)
    thread.start()


def category_for_pm25(value):
    if pd.isna(value):
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


live = load_csv(PROCESSED / "live_cpcb_pm25.csv")
forecast = load_csv(PROCESSED / "open_meteo_air_quality_forecast.csv")
aqi_summary = load_csv(PROCESSED / "aqi_summary.csv")
metrics = load_metrics()
status = load_status()

st.markdown(
    """
    <div class="brand-row">
      <div class="brand">
        <div class="brand-mark">A</div>
        <div>
          <div class="brand-title">AirSight Delhi</div>
          <div class="brand-sub">Live air-quality intelligence</div>
        </div>
      </div>
      <div class="source-pill">VERIFIED PUBLIC DATA</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="notice"><b>Academic prototype.</b> Live readings and forecasts '
    'come from public sources and must not be used as an official emergency '
    'health warning.</div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("## Controls")
    live_station = None
    if not live.empty:
        station_options = sorted(live["station"].dropna().unique())
        live_station = st.selectbox("Monitoring station", ["All stations"] + station_options)
    else:
        st.info("No live CPCB snapshot available.")

    forecast_days = st.slider("Forecast horizon", 24, 120, 72, 24)
    st.markdown("---")
    refresh_result = st.session_state.get("live_refresh_result")
    refresh_running = st.session_state.get("live_refresh_running", False)
    if refresh_running:
        st.button("Refreshing live data...", use_container_width=True, disabled=True)
        st.caption("The existing snapshot remains visible.")
    else:
        if st.button("Refresh live data", use_container_width=True):
            start_live_refresh()
            st.rerun()
    if refresh_result == "success":
        st.success("Live sources refreshed.")
        st.session_state["live_refresh_result"] = None
    elif refresh_result:
        st.error(refresh_result)
        st.session_state["live_refresh_result"] = None

    st.markdown("### Sources")
    st.caption("CPCB via data.gov.in")
    st.caption("CAMS via Open-Meteo")
    st.caption("OpenAQ historical archive")

live_filtered = live
if live_station and live_station != "All stations":
    live_filtered = live[live["station"] == live_station]

tab_live, tab_forecast, tab_explain, tab_aqi = st.tabs(
    ["Live Delhi", "Forecast", "Explainability", "AQI overview"]
)

with tab_live:
    if live.empty:
        st.warning(
            "No live snapshot is present. Click **Refresh live data** in the sidebar "
            "or run the live downloader."
        )
    else:
        live_valid = live[live["pm25"].fillna(0) > 0].copy()
        if live_valid.empty:
            st.warning("CPCB PM2.5 readings are currently unavailable.")
        else:
            latest_time = pd.to_datetime(live_valid["timestamp"], errors="coerce").max()
            mean_pm25 = live_valid["pm25"].mean()
            max_row = live_valid.loc[live_valid["pm25"].idxmax()]

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Stations reporting", f"{live_valid['station'].nunique():,}")
            k2.metric("Average PM2.5", f"{mean_pm25:.1f} µg/m³")
            k3.metric("Highest station", f"{float(max_row['pm25']):.1f} µg/m³")
            k4.metric(
                "Latest CPCB update",
                latest_time.strftime("%d %b, %H:%M") if pd.notna(latest_time) else "Unavailable",
            )

            st.markdown(
                f"<div class='section-title'>Live station conditions</div>"
                f"<div class='section-sub'>Highest reading: "
                f"<b>{max_row['station']}</b> · "
                f"{category_for_pm25(max_row['pm25'])}</div>",
                unsafe_allow_html=True,
            )

            filtered_valid = live_filtered[live_filtered["pm25"].fillna(0) > 0].copy()
            map_frame = filtered_valid[
                ["latitude", "longitude", "station", "pm25"]
            ].dropna().rename(columns={"latitude": "lat", "longitude": "lon"})
            if not map_frame.empty:
                st.map(map_frame, size=80, zoom=9)

            view = filtered_valid.sort_values("pm25", ascending=False).copy()
            view["category"] = view["pm25"].apply(category_for_pm25)
            view = view[
                [
                    "station", "pm25", "pm25_min", "pm25_max", "category",
                    "timestamp", "source",
                ]
            ].rename(columns={
                "pm25": "PM2.5",
                "pm25_min": "Minimum",
                "pm25_max": "Maximum",
                "category": "Category",
                "timestamp": "Update",
            })
            st.dataframe(view, use_container_width=True, hide_index=True)

            st.caption(
                f"Snapshot source: {status.get('live_source', 'CPCB via data.gov.in')}. "
                f"{len(live_valid)} usable station readings; "
                f"{status.get('latest_observation', 'timestamp unavailable')}."
            )

with tab_forecast:
    st.markdown("<div class='section-title'>CAMS PM2.5 forecast</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='section-sub'>No-key Open-Meteo forecast for central Delhi. "
        "This is a source forecast, not the repository's trained SVR model.</div>",
        unsafe_allow_html=True,
    )
    if forecast.empty:
        st.info("Run the live downloader to generate the Open-Meteo forecast.")
    else:
        chart = forecast.set_index("timestamp").sort_index()
        chart = chart[chart.index <= chart.index.min() + pd.Timedelta(hours=forecast_days)]
        st.line_chart(chart)
        c1, c2, c3 = st.columns(3)
        current_status = status.get("open_meteo_current", {})
        c1.metric(
            "Current PM2.5",
            f"{float(current_status.get('pm2_5', chart['pm25_forecast'].iloc[0])):.1f} µg/m³",
        )
        c2.metric(
            "Current PM10",
            f"{float(current_status.get('pm10', chart['pm10_forecast'].iloc[0])):.1f} µg/m³",
        )
        c3.metric(
            "US AQI",
            f"{int(current_status.get('us_aqi', 0))}" if current_status else "Unavailable",
        )
        st.dataframe(
            chart.tail(24).reset_index().rename(columns={
                "pm25_forecast": "PM2.5 forecast",
                "pm10_forecast": "PM10 forecast",
            }),
            use_container_width=True,
            hide_index=True,
        )

with tab_explain:
    st.markdown("<div class='section-title'>Model explainability</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='section-sub'>A transparent summary of the historical PM2.5 "
        "evaluation. These metrics are not live CPCB readings.</div>",
        unsafe_allow_html=True,
    )
    svr_metrics = metrics.get("SVR", {})
    if svr_metrics:
        c1, c2, c3 = st.columns(3)
        c1.metric("SVR MAE", f"{float(svr_metrics['MAE']):.1f} µg/m³")
        c2.metric("SVR RMSE", f"{float(svr_metrics['RMSE']):.1f} µg/m³")
        c3.metric("SVR test R²", f"{float(svr_metrics['R2']):.3f}")
        st.caption(
            "The held-out result compares 24-hour PM2.5 targets against Ridge, SVR, "
            "Random Forest, XGBoost, and persistence. SVR was strongest in this run."
        )
    shap_path = EXTERNAL / "shap_summary.png"
    if shap_path.exists():
        st.image(str(shap_path), caption="Ridge global feature-impact summary")
    else:
        st.info("Run `python src/models.py` to generate the SHAP summary.")

with tab_aqi:
    if aqi_summary.empty:
        st.info("Import a city/state AQI summary with `src/import_aqi_summary.py`.")
    else:
        state_options = ["All states"] + sorted(aqi_summary["state"].dropna().unique())
        state = st.selectbox("State", state_options)
        filtered = aqi_summary.copy()
        if state != "All states":
            filtered = filtered[filtered["state"] == state]
        area_options = ["All areas"] + sorted(filtered["area"].dropna().unique())
        area = st.selectbox("Area", area_options)
        if area != "All areas":
            filtered = filtered[filtered["area"] == area]
        c1, c2, c3 = st.columns(3)
        c1.metric("Rows", f"{len(filtered):,}")
        c2.metric("Average AQI", f"{filtered['aqi'].mean():.0f}" if not filtered.empty else "Unavailable")
        c3.metric("Highest AQI", f"{filtered['aqi'].max():.0f}" if not filtered.empty else "Unavailable")
        if not filtered.empty:
            trend = filtered.groupby("date", as_index=True)["aqi"].mean().rename("Average AQI")
            st.line_chart(trend)
            st.dataframe(filtered.sort_values("date", ascending=False).head(20), use_container_width=True, hide_index=True)
