from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"
EXTERNAL_DIR = ROOT / "data" / "external"

def generate_eda_plots():
    EXTERNAL_DIR.mkdir(parents=True, exist_ok=True)
    processed_path = PROCESSED_DIR / "clean_air_quality.csv"
    
    if not os.path.exists(processed_path):
        print("Processed data not found. Please run cleaning & AQI scripts first.")
        return
        
    df = pd.read_csv(processed_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Set plotting style
    # Plot 1: PM2.5 distribution across stations
    plt.figure(figsize=(10, 6))
    station_names = sorted(df["station"].dropna().unique())
    values = [df.loc[df["station"] == station, "pm25"].dropna() for station in station_names]
    plt.boxplot(values, tick_labels=station_names, patch_artist=True)
    plt.title('PM2.5 Distribution Across Delhi Monitoring Stations')
    plt.xticks(rotation=15)
    plt.ylabel(r'PM2.5 ($\mu g/m^3$)')
    plt.tight_layout()
    plt.savefig(EXTERNAL_DIR / 'pm25_station_boxplot.png', dpi=300)
    plt.close()
    print("Generated: data/external/pm25_station_boxplot.png")
    
    # Takeaway for report:
    print("\n--- REPORT TAKEAWAY ---")

if __name__ == "__main__":
    generate_eda_plots()