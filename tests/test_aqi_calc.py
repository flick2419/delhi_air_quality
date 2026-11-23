import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.aqi_calc import calculate_pm25_subindex, get_aqi_category


def test_pm25_subindex_boundaries():
    assert calculate_pm25_subindex(30) == 50
    assert calculate_pm25_subindex(60) == 100


def test_aqi_categories():
    assert get_aqi_category(50) == "Good"
    assert get_aqi_category(75) == "Satisfactory"
    assert get_aqi_category(150) == "Moderate"
    assert get_aqi_category(250) == "Poor"
    assert get_aqi_category(350) == "Very Poor"
    assert get_aqi_category(500) == "Severe"
