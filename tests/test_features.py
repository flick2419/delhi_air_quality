import sys
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.features import build_features


def test_exact_24_hour_target(tmp_path, monkeypatch):
    processed = tmp_path / "processed"
    processed.mkdir()
    timestamps = pd.date_range("2025-01-01", periods=49, freq="h", tz="Asia/Kolkata")
    frame = pd.DataFrame({
        "timestamp": timestamps,
        "station": ["Test Station"] * len(timestamps),
        "pm25": np.arange(len(timestamps), dtype=float),
    })
    frame.to_csv(processed / "clean_air_quality.csv", index=False)

    import src.features as features
    monkeypatch.setattr(features, "PROCESSED_DIR", processed)
    features.build_features()

    model_ready = pd.read_csv(processed / "model_ready_data.csv")
    first = model_ready.iloc[0]
    assert first["pm25_next_day"] == first["pm25"] + 24
