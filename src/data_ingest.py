import os
import yaml
import requests
import pandas as pd
from datetime import datetime, timedelta

def load_config():
    with open("configs/config.yaml", "r") as f:
        return yaml.safe_load(f)

def fetch_open_meteo_weather(start_date, end_date):
    print("Fetching weather data from Open-Meteo...")
    url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude=28.6139&longitude=77.2090&start_date={start_date}&end_date={end_date}"
        f"&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation"
    )
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        hourly = data.get("hourly", {})
        df = pd.DataFrame(hourly)
        df.to_csv("data/raw/weather_raw.csv", index=False)
        print("Successfully saved data/raw/weather_raw.csv")
    else:
        print(f"Failed to fetch weather data: {response.status_code}")

def generate_station_template(config):
    print("Initializing station raw data structure...")
    stations = config["data"]["stations"]
    # Fixed freq="h" for Pandas 2.2+ compatibility
    dates = pd.date_range(start=config["data"]["start_date"], end=datetime.now(), freq="h")
    
    for station in stations:
        temp_df = pd.DataFrame({
            "timestamp": dates,
            "station": station,
            "pm25": [150.0] * len(dates),
            "pm10": [250.0] * len(dates),
            "no2": [40.0] * len(dates),
            "so2": [15.0] * len(dates),
            "co": [1.2] * len(dates),
            "oz": [30.0] * len(dates)
        })
        safe_name = station.split(",")[0].lower().replace(" ", "_")
        path = f"data/raw/air_quality_{safe_name}.csv"
        temp_df.to_csv(path, index=False)
        print(f"Saved raw template for: {station} -> {path}")

if __name__ == "__main__":
    os.makedirs("data/raw", exist_ok=True)
    config = load_config()
    start_date = config["data"]["start_date"]
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    fetch_open_meteo_weather(start_date, end_date)
    generate_station_template(config)
    