import os
import yaml
import pandas as pd
import numpy as np

def load_config():
    with open("configs/config.yaml", "r") as f:
        return yaml.safe_load(f)

def clean_station_data(file_path):
    df = pd.read_csv(file_path)
    # Ensure timestamp is datetime and set as index
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    # Define physical plausibility boundaries for pollutants
    # e.g., PM2.5 cannot be negative or absurdly high without cap (>1000 check)
    pollutants = ['pm25', 'pm10', 'no2', 'so2', 'co', 'oz']
    for p in pollutants:
        if p in df.columns:
            # Clip negative values to 0
            df[p] = df[p].clip(lower=0.0)
            # Treat extreme sensor lock/faults (> 1500 ug/m3) as NaN for interpolation
            df.loc[df[p] > 1500.0, p] = np.nan
            
            # Interpolate short gaps (up to 6 consecutive hours max)
            df[p] = df[p].interpolate(method='linear', limit=6, limit_direction='both')
            
            # Fill remaining NaNs with rolling median or column median
            df[p] = df[p].fillna(df[p].median())
            
    return df

def run_cleaning_pipeline():
    config = load_config()
    os.makedirs("data/processed", exist_ok=True)
    
    cleaned_dfs = []
    
    raw_paths = sorted(
        path for path in os.listdir("data/raw")
        if path.startswith("air_quality_") and path.endswith(".csv")
    )
    for filename in raw_paths:
        raw_path = os.path.join("data/raw", filename)
        df_clean = clean_station_data(raw_path)
        cleaned_dfs.append(df_clean)
        print(f"Cleaned station data: {filename}")
            
    if cleaned_dfs:
        combined_air = pd.concat(cleaned_dfs, ignore_index=True)
        
        # Load weather raw data
        weather_path = "data/raw/weather_raw.csv"
        if os.path.exists(weather_path):
            df_weather = pd.read_csv(weather_path)
            df_weather["timestamp"] = pd.to_datetime(
                df_weather.get("time", df_weather.get("timestamp")), errors="coerce"
            )
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
        combined_air.to_csv("data/processed/clean_air_quality.csv", index=False)
        print("Successfully saved processed data to data/processed/clean_air_quality.csv")

if __name__ == "__main__":
    run_cleaning_pipeline()
