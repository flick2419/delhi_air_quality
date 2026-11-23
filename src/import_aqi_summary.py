"""Import a separate city/state AQI summary dataset for dashboard display."""

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "processed" / "aqi_summary.csv"


def import_aqi_summary(source):
    source_path = Path(source)
    if not source_path.exists():
        raise FileNotFoundError(f"AQI CSV does not exist: {source_path}")

    frame = pd.read_csv(source_path)
    required = {
        "date", "state", "area", "number_of_monitoring_stations",
        "prominent_pollutants", "aqi_value", "air_quality_status",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"AQI CSV is missing columns: {sorted(missing)}")

    frame = frame.rename(columns={
        "number_of_monitoring_stations": "monitoring_stations",
        "prominent_pollutants": "pollutant",
        "aqi_value": "aqi",
        "air_quality_status": "status",
    })
    frame["date"] = pd.to_datetime(frame["date"], dayfirst=True, errors="coerce")
    frame["aqi"] = pd.to_numeric(frame["aqi"], errors="coerce")
    frame["monitoring_stations"] = pd.to_numeric(
        frame["monitoring_stations"], errors="coerce"
    )
    frame = frame.dropna(subset=["date", "aqi", "area"]).copy()
    frame["state"] = frame["state"].fillna("Unknown").astype(str).str.strip()
    frame["area"] = frame["area"].astype(str).str.strip()
    frame["pollutant"] = frame["pollutant"].fillna("Unknown").astype(str).str.strip()
    frame["status"] = frame["status"].fillna("Unknown").astype(str).str.strip()
    frame = frame[[
        "date", "state", "area", "monitoring_stations", "pollutant", "aqi", "status"
    ]].sort_values(["date", "state", "area"])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT, index=False)
    print(f"Saved {len(frame):,} AQI rows to {OUTPUT}")
    print(f"Date range: {frame['date'].min().date()} to {frame['date'].max().date()}")
    print(f"Areas: {frame['area'].nunique():,}; states: {frame['state'].nunique():,}")
    return OUTPUT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Path to a city/state AQI summary CSV.")
    args = parser.parse_args()
    import_aqi_summary(args.source)


if __name__ == "__main__":
    main()
