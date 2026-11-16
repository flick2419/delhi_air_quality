import os
import yaml
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit

def load_config():
    with open("configs/config.yaml", "r") as f:
        return yaml.safe_load(f)

def perform_chronological_split():
    config = load_config()
    data_path = "data/processed/model_ready_data.csv"
    
    if not os.path.exists(data_path):
        print("Model-ready data not found. Run feature engineering first.")
        return
        
    df = pd.read_csv(data_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    # Chronological Split: Last 1 year for test, previous 0.5 years for val, rest for train
    max_date = df['timestamp'].max()
    test_cutoff = max_date - pd.DateOffset(years=1)
    val_cutoff = test_cutoff - pd.DateOffset(months=6)
    
    train_df = df[df['timestamp'] < val_cutoff]
    val_df = df[(df['timestamp'] >= val_cutoff) & (df['timestamp'] < test_cutoff)]
    test_df = df[df['timestamp'] >= test_cutoff]
    
    os.makedirs("data/processed", exist_ok=True)
    train_df.to_csv("data/processed/train.csv", index=False)
    val_df.to_csv("data/processed/val.csv", index=False)
    test_df.to_csv("data/processed/test.csv", index=False)
    
    print(f"Chronological split complete:")
    print(f" - Train set shape: {train_df.shape}")
    print(f" - Validation set shape: {val_df.shape}")
    print(f" - Test set shape: {test_df.shape}")
    
    # Demonstrate TimeSeriesSplit cross-validator setup
    tscv = TimeSeriesSplit(n_splits=5)
    print(f"TimeSeriesSplit configured with {tscv.n_splits} splits for walk-forward validation.")

if __name__ == "__main__":
    perform_chronological_split()