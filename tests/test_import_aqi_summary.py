import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.import_aqi_summary import import_aqi_summary


def test_import_aqi_summary(tmp_path, monkeypatch):
    source = tmp_path / "aqi.csv"
    pd.DataFrame({
        "date": ["30-04-2025", "01-05-2025"],
        "state": ["Delhi", "Delhi"],
        "area": ["Delhi", "Delhi"],
        "number_of_monitoring_stations": [20, 21],
        "prominent_pollutants": ["PM10", "PM2.5"],
        "aqi_value": [180, 190],
        "air_quality_status": ["Moderate", "Moderate"],
    }).to_csv(source, index=False)

    import src.import_aqi_summary as importer
    monkeypatch.setattr(importer, "OUTPUT", tmp_path / "aqi_summary.csv")
    output = importer.import_aqi_summary(source)
    result = pd.read_csv(output)

    assert len(result) == 2
    assert list(result.columns) == [
        "date", "state", "area", "monitoring_stations",
        "pollutant", "aqi", "status",
    ]
    assert result["aqi"].tolist() == [180, 190]
