"""Download or import real input data for the Delhi air-quality pipeline."""

import argparse
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"


def load_config():
    with (ROOT / "configs" / "config.yaml").open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def safe_station_name(station):
    name = station.split(",")[0].lower()
    return re.sub(r"[^a-z0-9]+", "_", name).strip("_")


def fetch_open_meteo_weather(start_date, end_date):
    """Fetch hourly weather and return the saved path."""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": 28.6139,
        "longitude": 77.2090,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": (
            "temperature_2m,relative_humidity_2m,wind_speed_10m,"
            "wind_direction_10m,precipitation"
        ),
        "timezone": "Asia/Kolkata",
    }
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()
    hourly = response.json().get("hourly", {})
    if not hourly.get("time"):
        raise ValueError("Open-Meteo returned no hourly observations.")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    output = RAW_DIR / "weather_raw.csv"
    pd.DataFrame(hourly).to_csv(output, index=False)
    print(f"Saved weather data: {output}")
    return output


def import_csv_directory(input_dir):
    """Copy/normalise user-supplied station CSVs into data/raw.

    Files must contain a timestamp column and a PM2.5 column. Other pollutant
    columns are retained when present and normalised to the pipeline names.
    """
    source_dir = Path(input_dir)
    if not source_dir.is_dir():
        raise FileNotFoundError(f"CSV directory does not exist: {source_dir}")

    aliases = {
        "date": "timestamp",
        "datetime": "timestamp",
        "time": "timestamp",
        "pm2.5": "pm25",
        "pm_2_5": "pm25",
        "pm10": "pm10",
        "no2": "no2",
        "so2": "so2",
        "co": "co",
        "o3": "oz",
        "ozone": "oz",
    }
    imported = 0
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    for source in sorted(source_dir.glob("*.csv")):
        frame = pd.read_csv(source)
        frame.columns = [
            aliases.get(str(column).strip().lower(), str(column).strip().lower())
            for column in frame.columns
        ]
        if "timestamp" not in frame or "pm25" not in frame:
            print(f"Skipped {source.name}: requires timestamp and PM2.5 columns")
            continue
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
        frame = frame.dropna(subset=["timestamp", "pm25"]).sort_values("timestamp")
        if frame.empty:
            print(f"Skipped {source.name}: no valid observations")
            continue
        if "station" not in frame:
            frame["station"] = source.stem
        for station_name, station_frame in frame.groupby("station", dropna=False):
            station_name = str(station_name)
            destination = RAW_DIR / f"air_quality_{safe_station_name(station_name)}.csv"
            station_frame.to_csv(destination, index=False)
            imported += 1
            print(f"Imported {source.name} ({station_name}) -> {destination}")

    if not imported:
        raise ValueError("No usable CSV files were imported.")
    return imported


def validate_raw_data():
    files = sorted(RAW_DIR.glob("air_quality_*.csv"))
    if not files:
        raise FileNotFoundError("No station files found in data/raw.")
    total_rows = 0
    distinct_pm25 = set()
    for path in files:
        frame = pd.read_csv(path)
        required = {"timestamp", "pm25"}
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")
        total_rows += len(frame)
        distinct_pm25.update(pd.to_numeric(frame["pm25"], errors="coerce").dropna().round(6))
    print(f"Validated {len(files)} station files, {total_rows} rows, "
          f"{len(distinct_pm25)} distinct PM2.5 values.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-dir", help="Directory containing real station CSV files.")
    parser.add_argument("--no-weather", action="store_true")
    args = parser.parse_args()

    config = load_config()
    if args.csv_dir:
        import_csv_directory(args.csv_dir)
    if not args.no_weather:
        start = config["data"]["start_date"]
        end = datetime.now().strftime("%Y-%m-%d")
        fetch_open_meteo_weather(start, end)
    validate_raw_data()


if __name__ == "__main__":
    main()
