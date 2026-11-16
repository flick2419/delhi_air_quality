"""Download real Delhi PM2.5 observations from OpenAQ into data/raw.

OpenAQ v3 requires an API key. Set OPENAQ_API_KEY in PowerShell before running:
    $env:OPENAQ_API_KEY = "your-key"
"""

import argparse
import os
import re
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
API_URL = "https://api.openaq.org/v3"
# OpenAQ expects min longitude, min latitude, max longitude, max latitude.
DELHI_BBOX = "76.80,28.40,77.40,28.90"


def api_get(session, path, params):
    response = session.get(f"{API_URL}{path}", params=params, timeout=60)
    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", "5"))
        time.sleep(min(retry_after, 30))
        response = session.get(f"{API_URL}{path}", params=params, timeout=60)
    if not response.ok:
        detail = response.text[:1000].replace("\n", " ")
        raise RuntimeError(
            f"OpenAQ request failed ({response.status_code}) for {response.url}: {detail}"
        )
    return response.json()


def safe_name(value):
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def find_pm25_sensors(session, max_stations):
    payload = api_get(
        session,
        "/locations",
        {
            "bbox": DELHI_BBOX,
            "limit": max_stations,
            "page": 1,
        },
    )
    locations = payload.get("results", [])
    found_sensors = []
    for location in locations:
        location_id = location.get("id")
        location_sensors = location.get("sensors", [])
        if not location_sensors:
            location_sensors = api_get(
                session, f"/locations/{location_id}/sensors", {}
            ).get("results", [])
        for sensor in location_sensors:
            parameter = sensor.get("parameter", {})
            if parameter.get("name") == "pm25" or parameter.get("id") == 2:
                sensor_id = sensor.get("id") or sensor.get("sensorsId")
                if sensor_id is None:
                    continue
                found_sensors.append(
                    {
                        "sensor_id": sensor_id,
                        "location_id": location_id,
                        "name": location.get("name") or f"OpenAQ_{location_id}",
                    }
                )
                break
    return found_sensors


def download_sensor(session, sensor, start_date, end_date, page_size):
    rows = []
    page = 1
    while True:
        payload = api_get(
            session,
            f"/sensors/{sensor['sensor_id']}/hours",
            {
                "date_from": f"{start_date}T00:00:00Z",
                "date_to": f"{end_date}T23:59:59Z",
                "limit": page_size,
                "page": page,
            },
        )
        results = payload.get("results", [])
        rows.extend(results)
        if len(results) < page_size:
            break
        page += 1
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(
        {
            "timestamp": [
                row.get("period", {}).get("datetimeFrom", {}).get("local")
                or row.get("period", {}).get("datetimeTo", {}).get("local")
                or row.get("datetime", {}).get("local")
                for row in rows
            ],
            "station": sensor["name"],
            "pm25": [row.get("value") for row in rows],
        }
    ).dropna(subset=["timestamp", "pm25"])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    frame = frame.dropna(subset=["timestamp"])
    frame = frame[
        (frame["timestamp"].dt.date >= date.fromisoformat(start_date))
        & (frame["timestamp"].dt.date <= date.fromisoformat(end_date))
    ]
    return frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-key", default=os.environ.get("OPENAQ_API_KEY"))
    parser.add_argument("--start-date", default=(date.today() - timedelta(days=365 * 3)).isoformat())
    parser.add_argument("--end-date", default=date.today().isoformat())
    parser.add_argument("--max-stations", type=int, default=5)
    parser.add_argument("--page-size", type=int, default=1000)
    args = parser.parse_args()

    if not args.api_key:
        raise SystemExit(
            "Missing OpenAQ API key. Set OPENAQ_API_KEY or pass --api-key. "
            "Create one at https://openaq.org/"
        )
    if args.start_date > args.end_date:
        raise SystemExit("--start-date must be before --end-date.")

    session = requests.Session()
    session.headers.update({"X-API-Key": args.api_key, "Accept": "application/json"})
    sensors = find_pm25_sensors(session, args.max_stations)
    if not sensors:
        raise RuntimeError("No OpenAQ PM2.5 sensors were found in the Delhi bounding box.")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    saved = 0
    total_rows = 0
    for sensor in sensors:
        frame = download_sensor(
            session, sensor, args.start_date, args.end_date, args.page_size
        )
        if frame.empty:
            print(f"No observations: {sensor['name']}")
            continue
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
        frame["pm25"] = pd.to_numeric(frame["pm25"], errors="coerce")
        frame = frame.dropna(subset=["timestamp", "pm25"]).drop_duplicates(
            subset=["timestamp", "station"]
        ).sort_values("timestamp")
        output = RAW_DIR / f"air_quality_{safe_name(sensor['name'])}.csv"
        frame.to_csv(output, index=False)
        saved += 1
        total_rows += len(frame)
        print(f"Saved {len(frame):,} observations: {output}")

    if not saved:
        raise RuntimeError("OpenAQ returned no usable observations for the selected dates.")
    print(f"Downloaded {total_rows:,} observations across {saved} stations.")


if __name__ == "__main__":
    main()
