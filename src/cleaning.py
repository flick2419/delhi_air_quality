from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"

def clean_station_data(file_path):
    df = pd.read_csv(file_path)
    if "timestamp" not in df or "pm25" not in df:
        raise ValueError(f"{file_path} must contain timestamp and pm25 columns")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    df["timestamp"] = df["timestamp"].dt.tz_convert("Asia/Kolkata")
    df["pm25"] = pd.to_numeric(df["pm25"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    if df.empty:
        raise ValueError(f"{file_path} contains no valid timestamps")
    
    # Define physical plausibility boundaries for pollutants
    # e.g., PM2.5 cannot be negative or absurdly high without cap (>1000 check)
    pollutants = ['pm25', 'pm10', 'no2', 'so2', 'co', 'oz']
    for p in pollutants:
        if p in df.columns:
            # Clip negative values to 0
            df[p] = pd.to_numeric(df[p], errors="coerce").clip(lower=0.0)
            # Treat extreme sensor lock/faults (> 1500 ug/m3) as NaN for interpolation
            df.loc[df[p] > 1500.0, p] = np.nan
            
            # Interpolate short gaps (up to 6 consecutive hours max)
            df[p] = df[p].interpolate(method='linear', limit=6, limit_direction='both')
            
            # Fill remaining NaNs with rolling median or column median
            df[p] = df[p].fillna(df[p].median())
            
    return df

def run_cleaning_pipeline():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    cleaned_dfs = []
    raw_paths = sorted(RAW_DIR.glob("air_quality_*.csv"))
    if not raw_paths:
        raise FileNotFoundError(f"No raw station CSV files found in {RAW_DIR}")
    for raw_path in raw_paths:
        df_clean = clean_station_data(raw_path)
        cleaned_dfs.append(df_clean)
        print(f"Cleaned station data: {raw_path.name}")
            
    if cleaned_dfs:
        combined_air = pd.concat(cleaned_dfs, ignore_index=True)
        
        # Load weather raw data
        weather_path = RAW_DIR / "weather_raw.csv"
        if weather_path.exists():
            df_weather = pd.read_csv(weather_path)
            weather_time = df_weather["time"] if "time" in df_weather else df_weather.get("timestamp")
            df_weather["timestamp"] = pd.to_datetime(
                weather_time, errors="coerce", utc=True
            )
            df_weather["timestamp"] = df_weather["timestamp"].dt.tz_convert("Asia/Kolkata")
            weather_columns = [
                column for column in df_weather.columns
                if column not in {"time", "timestamp"}
            ]
            if weather_columns:
                combined_air = combined_air.merge(
                    df_weather[["timestamp"] + weather_columns],
                    on="timestamp",
                    how="left",
                )
                print("Weather data merged by timestamp.")
            
        # Save processed baseline
        combined_air.to_csv(PROCESSED_DIR / "clean_air_quality.csv", index=False)
        print(f"Successfully saved processed data to {PROCESSED_DIR / 'clean_air_quality.csv'}")

if __name__ == "__main__":
    run_cleaning_pipeline()
