"""Fetch verified live Delhi PM2.5 observations and a CAMS forecast.

Primary source:
  CPCB real-time resource via India's data.gov.in API.
Forecast source:
  Open-Meteo Air Quality API, based on CAMS atmospheric composition models.
"""

import json
import os
import time
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
DATAGOV_RESOURCE = (
    "https://api.data.gov.in/resource/"
    "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
)
# Public documented sample key for low-volume demo use; a dedicated key is preferred.
DATAGOV_DEMO_KEY = "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b"
OPEN_METEO_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


def fetch_live_cpcb():
    api_key = os.environ.get("DATAGOV_API_KEY", DATAGOV_DEMO_KEY)
    records = []
    offset = 0
    page_size = 10
    total = None

    session = requests.Session()
    session.mount(
        "https://",
        HTTPAdapter(
            max_retries=Retry(
                total=5,
                backoff_factor=1.0,
                status_forcelist=(502, 503, 504),
                allowed_methods=("GET",),
            )
        ),
    )

    while True:
        params = {
            "api-key": api_key,
            "format": "json",
            "limit": page_size,
            "offset": offset,
            "filters[city]": "Delhi",
            "filters[pollutant_id]": "PM2.5",
        }
        response = None
        last_error = None
        for attempt in range(3):
            try:
                response = session.get(DATAGOV_RESOURCE, params=params, timeout=120)
                break
            except requests.RequestException as error:
                last_error = error
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
        if response is None:
            raise RuntimeError(
                f"data.gov.in timed out or failed after retries: {last_error}"
            )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "ok":
            raise RuntimeError(
                f"data.gov.in returned status={payload.get('status')}: "
                f"{payload.get('message', '')}"
            )
        total = int(payload.get("total", total or 0))
        page = payload.get("records", [])
        records.extend(page)
        offset += len(page)
        if not page or (total and offset >= total):
            break

    frame = pd.DataFrame(records)
    if frame.empty:
        raise RuntimeError("No Delhi PM2.5 records were returned by CPCB data.gov.in.")

    frame["timestamp"] = pd.to_datetime(
        frame["last_update"], format="%d-%m-%Y %H:%M:%S", errors="coerce"
    )
    frame["timestamp"] = frame["timestamp"].dt.tz_localize(
        "Asia/Kolkata", ambiguous="NaT", nonexistent="shift_forward"
    )
    for column in ("pollutant_min", "pollutant_max", "pollutant_avg",
                   "latitude", "longitude"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame = frame.rename(columns={
        "pollutant_min": "pm25_min",
        "pollutant_max": "pm25_max",
        "pollutant_avg": "pm25_avg",
    })
    frame["pm25"] = frame["pm25_avg"].where(
        frame["pm25_avg"].notna(),
        frame[["pm25_min", "pm25_max"]].mean(axis=1),
    )
    frame["source"] = "CPCB via data.gov.in"
    frame["unit"] = "µg/m³"
    frame = frame.dropna(subset=["station", "timestamp", "pm25"])
    frame = frame[
        [
            "timestamp", "station", "state", "city", "latitude", "longitude",
            "pm25", "pm25_min", "pm25_max", "pm25_avg", "pollutant_id",
            "source", "unit",
        ]
    ].sort_values(["timestamp", "station"], ascending=[False, True])
    frame = frame.drop_duplicates(
        subset=["station", "timestamp"], keep="first"
    )
    if frame.empty:
        raise RuntimeError("CPCB records contained no usable PM2.5 averages.")
    return frame


def fetch_open_meteo_forecast():
    params = {
        "latitude": 28.6139,
        "longitude": 77.2090,
        "current": "pm2_5,pm10,us_aqi,european_aqi",
        "hourly": "pm2_5,pm10",
        "forecast_days": 5,
        "timezone": "Asia/Kolkata",
    }
    response = requests.get(OPEN_METEO_URL, params=params, timeout=60)
    response.raise_for_status()
    payload = response.json()
    hourly = payload.get("hourly", {})
    frame = pd.DataFrame({
        "timestamp": pd.to_datetime(hourly.get("time", []), errors="coerce"),
        "pm25_forecast": pd.to_numeric(hourly.get("pm2_5", []), errors="coerce"),
        "pm10_forecast": pd.to_numeric(hourly.get("pm10", []), errors="coerce"),
    }).dropna(subset=["timestamp"])
    current = payload.get("current", {})
    return frame, current


def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    live_path = PROCESSED / "live_cpcb_pm25.csv"
    forecast_path = PROCESSED / "open_meteo_air_quality_forecast.csv"
    live_source_status = "CPCB via data.gov.in"

    try:
        live = fetch_live_cpcb()
        live.to_csv(live_path, index=False)
    except Exception as error:
        print(f"CPCB live refresh failed; preserving last snapshot: {error}")
        if live_path.exists():
            live = pd.read_csv(live_path)
            live["timestamp"] = pd.to_datetime(
                live["timestamp"], format="mixed", dayfirst=True, errors="coerce"
            )
            live_source_status = "CPCB snapshot (last successful refresh)"
        else:
            raise

    try:
        forecast, current = fetch_open_meteo_forecast()
        forecast.to_csv(forecast_path, index=False)
    except Exception as error:
        print(f"Open-Meteo refresh failed; preserving last snapshot: {error}")
        if forecast_path.exists():
            forecast = pd.read_csv(forecast_path)
            current = {}
        else:
            raise

    latest_timestamp = live["timestamp"].max()
    status = {
        "live_source": live_source_status,
        "forecast_source": "CAMS via Open-Meteo",
        "stations": int(live["station"].nunique()),
        "records": int(len(live)),
        "latest_observation": latest_timestamp.isoformat(),
        "live_mean_pm25": round(float(live["pm25"].mean()), 2),
        "live_median_pm25": round(float(live["pm25"].median()), 2),
        "live_max_pm25": round(float(live["pm25"].max()), 2),
        "open_meteo_current": current,
        "fetched_at": pd.Timestamp.now(tz="Asia/Kolkata").isoformat(),
    }
    status_path = PROCESSED / "live_status.json"
    with status_path.open("w", encoding="utf-8") as file:
        json.dump(status, file, indent=2)

    print(f"Saved {len(live):,} live PM2.5 station rows to {live_path}")
    print(f"Latest CPCB observation: {latest_timestamp}")
    print(f"Saved {len(forecast):,} forecast hours to {forecast_path}")
    print(f"Saved source status to {status_path}")


if __name__ == "__main__":
    main()
