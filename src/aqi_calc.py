import pandas as pd
import numpy as np

def calculate_pm25_subindex(cp):
    """Calculates CPCB sub-index for PM2.5 based on 24-hr concentration breakpoints."""
    if pd.isna(cp):
        return np.nan
    if cp <= 30:
        return linear_interpolate(cp, 0, 30, 0, 50)
    elif cp <= 60:
        return linear_interpolate(cp, 31, 60, 51, 100)
    elif cp <= 90:
        return linear_interpolate(cp, 61, 90, 101, 200)
    elif cp <= 120:
        return linear_interpolate(cp, 91, 120, 201, 300)
    elif cp <= 250:
        return linear_interpolate(cp, 121, 250, 301, 400)
    else:
        return linear_interpolate(cp, 251, 430, 401, 500)

def linear_interpolate(cp, bp_lo, bp_hi, ip_lo, ip_hi):
    """Linear sub-index formula prescribed by CPCB."""
    return ((ip_hi - ip_lo) / (bp_hi - bp_lo)) * (cp - bp_lo) + ip_lo

def get_aqi_category(aqi_val):
    """Maps numerical AQI to official CPCB category and color flag."""
    if pd.isna(aqi_val):
        return "Unknown"
    elif aqi_val <= 50:
        return "Good"
    elif aqi_val <= 100:
        return "Satisfactory"
    elif aqi_val <= 200:
        return "Moderate"
    elif aqi_val <= 300:
        return "Poor"
    elif aqi_val <= 400:
        return "Very Poor"
    else:
        return "Severe"

def compute_dataset_aqi(df):
    """Computes PM2.5 sub-index and overall category mapping for the dataframe."""
    df['pm25_subindex'] = df['pm25'].apply(calculate_pm25_subindex)
    # For baseline demonstration, PM2.5 drives the primary AQI sub-index
    df['aqi'] = df['pm25_subindex']
    df['aqi_category'] = df['aqi'].apply(get_aqi_category)
    return df

if __name__ == "__main__":
    # Quick test execution on our processed file
    processed_path = "data/processed/clean_air_quality.csv"
    if os.path.exists(processed_path) if 'os' in globals() else True:
        import os
        if os.path.exists(processed_path):
            df = pd.read_csv(processed_path)
            df = compute_dataset_aqi(df)
            df.to_csv(processed_path, index=False)
            print("Successfully computed CPCB AQI and categories in processed data.")