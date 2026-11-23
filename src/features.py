from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"

def build_features():
    processed_path = PROCESSED_DIR / "clean_air_quality.csv"
    if not processed_path.exists():
        raise FileNotFoundError("Processed data not found. Run cleaning first.")
        
    df = pd.read_csv(processed_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True, errors='coerce')
    df = df.dropna(subset=['timestamp', 'station', 'pm25'])
    df['pm25'] = pd.to_numeric(df['pm25'], errors='coerce')
    df = df.dropna(subset=['pm25'])
    df = df.drop_duplicates(subset=['station', 'timestamp'])
    df = df.sort_values(['station', 'timestamp']).reset_index(drop=True)
    
    # 1. Target Definition: PM2.5 at the same station exactly 24 hours later.
    # Timestamp matching remains correct for hourly, half-hourly, and irregular data.
    target_lookup = df.set_index(['station', 'timestamp'])['pm25']
    target_index = pd.MultiIndex.from_arrays(
        [
            df['station'].to_numpy(),
            (df['timestamp'] + pd.Timedelta(days=1)).to_numpy(),
        ],
        names=['station', 'timestamp'],
    )
    df['pm25_next_day'] = target_lookup.reindex(target_index).to_numpy()
    
    # 2. Autoregressive Lags & Leakage-Free Rolling Features
    # Shift by 1 first so rolling means do NOT include current hour t (prevents data leakage)
    df['pm25_lag1'] = df.groupby('station')['pm25'].shift(1)
    df['pm25_rolling_3h'] = df.groupby('station')['pm25_lag1'].transform(
        lambda x: x.rolling(3, min_periods=1).mean()
    )
    df['pm25_rolling_24h'] = df.groupby('station')['pm25_lag1'].transform(
        lambda x: x.rolling(24, min_periods=1).mean()
    )
    
    # 3. Calendar Features
    df['hour'] = df['timestamp'].dt.hour
    df['dayofweek'] = df['timestamp'].dt.day_of_week
    df['month'] = df['timestamp'].dt.month
    df['is_weekend'] = df['dayofweek'].isin([5, 6]).astype(int)
    
    # Drop rows where target is NaN (last 24 hours of dataset)
    df_model = df.dropna(subset=['pm25_next_day']).copy()
    
    output_path = PROCESSED_DIR / "model_ready_data.csv"
    df_model.to_csv(output_path, index=False)
    print(f"Feature engineering complete. Saved model-ready data to {output_path}")

if __name__ == "__main__":
    build_features()