from pathlib import Path

import pandas as pd
from sklearn.model_selection import TimeSeriesSplit

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"

def perform_chronological_split():
    data_path = PROCESSED_DIR / "model_ready_data.csv"
    
    if not data_path.exists():
        raise FileNotFoundError("Model-ready data not found. Run feature engineering first.")
        
    df = pd.read_csv(data_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True, errors='coerce')
    df = df.dropna(subset=['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    # Chronological Split: Last 1 year for test, previous 0.5 years for val, rest for train
    max_date = df['timestamp'].max()
    test_cutoff = max_date - pd.DateOffset(years=1)
    val_cutoff = test_cutoff - pd.DateOffset(months=6)
    
    train_df = df[df['timestamp'] < val_cutoff]
    val_df = df[(df['timestamp'] >= val_cutoff) & (df['timestamp'] < test_cutoff)]
    test_df = df[df['timestamp'] >= test_cutoff]
    
    if train_df.empty or val_df.empty or test_df.empty:
        raise ValueError(
            f"Chronological split produced empty data: train={len(train_df)}, "
            f"val={len(val_df)}, test={len(test_df)}"
        )

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    train_df.to_csv(PROCESSED_DIR / "train.csv", index=False)
    val_df.to_csv(PROCESSED_DIR / "val.csv", index=False)
    test_df.to_csv(PROCESSED_DIR / "test.csv", index=False)
    
    print(f"Chronological split complete:")
    print(f" - Train set shape: {train_df.shape}")
    print(f" - Validation set shape: {val_df.shape}")
    print(f" - Test set shape: {test_df.shape}")
    
    # Demonstrate TimeSeriesSplit cross-validator setup
    tscv = TimeSeriesSplit(n_splits=5)
    print(f"TimeSeriesSplit configured with {tscv.n_splits} splits for walk-forward validation.")

if __name__ == "__main__":
    perform_chronological_split()