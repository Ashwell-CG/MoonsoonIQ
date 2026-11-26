"""MonsoonIQ - Test Suite for Phase 7 Regime Agricultural Relevance Validation.

Validates the independent agricultural relevance dataset, physical bounds of external metrics,
decadal volatility persistence of the 42 rain-shadow cells, and visualization outputs.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

BASE_DIR: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

VALIDATION_CSV: Path = BASE_DIR / "data" / "processed" / "regime_agricultural_validation.csv"
ONSET_CLUSTERS_CSV: Path = BASE_DIR / "data" / "processed" / "monsoon_onset_clusters.csv"
SUMMARY_JSON: Path = BASE_DIR / "outputs" / "regime_validation" / "regime_agricultural_summary.json"
PLOTS_DIR: Path = BASE_DIR / "outputs" / "regime_validation"

EXPECTED_CELL_COUNT: int = 419

REQUIRED_INDEPENDENT_COLUMNS = [
    "june_mean_rainfall_mm",
    "june_rainfall_cv_pct",
    "jj_mean_rainfall_mm",
    "may_mean_rainfall_mm",
    "june_mean_wet_days",
    "sowing_trigger_median_doy",
    "sowing_delay_past_july1_freq",
    "early_dry_spell_mean_days",
    "early_dry_spell_max_days",
    "severe_dry_spell_10d_freq",
    "onset_std_p1_2001_2011",
    "onset_std_p2_2012_2023",
]


@pytest.fixture(scope="module")
def df_agri() -> pd.DataFrame:
    """Fixture providing the enriched agricultural validation DataFrame."""
    assert VALIDATION_CSV.exists(), f"Missing validation CSV at {VALIDATION_CSV}"
    return pd.read_csv(VALIDATION_CSV)


@pytest.fixture(scope="module")
def summary_dict() -> dict:
    """Fixture providing the agricultural summary JSON."""
    assert SUMMARY_JSON.exists(), f"Missing summary JSON at {SUMMARY_JSON}"
    with open(SUMMARY_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def test_validation_dataset_dimensions_and_nulls(df_agri: pd.DataFrame) -> None:
    """Verifies that the validated agricultural dataset has 419 rows and no NaNs."""
    assert len(df_agri) == EXPECTED_CELL_COUNT
    for col in REQUIRED_INDEPENDENT_COLUMNS:
        assert col in df_agri.columns, f"Missing column {col}"
        assert not df_agri[col].isna().any(), f"NaNs found in {col}"
        assert not np.isinf(df_agri[col]).any(), f"Infs found in {col}"


def test_independent_metrics_physical_bounds(df_agri: pd.DataFrame) -> None:
    """Verifies that independent rainfall and agricultural metrics obey physical bounds."""
    # June Rainfall: [50 mm, 2500 mm]
    assert (df_agri["june_mean_rainfall_mm"] >= 40.0).all()
    assert (df_agri["june_mean_rainfall_mm"] <= 2500.0).all()

    # June CV: [30%, 120%]
    assert (df_agri["june_rainfall_cv_pct"] >= 25.0).all()
    assert (df_agri["june_rainfall_cv_pct"] <= 120.0).all()

    # Sowing Trigger DOY: June 1 (152) to late July (210)
    assert (df_agri["sowing_trigger_median_doy"] >= 150.0).all()
    assert (df_agri["sowing_trigger_median_doy"] <= 210.0).all()

    # Sowing Delay Frequency in [0, 1]
    assert (df_agri["sowing_delay_past_july1_freq"] >= 0.0).all()
    assert (df_agri["sowing_delay_past_july1_freq"] <= 1.0).all()

    # Early Dry Spell Max in [5, 45] days
    assert (df_agri["early_dry_spell_max_days"] >= 5.0).all()
    assert (df_agri["early_dry_spell_max_days"] <= 45.0).all()


def test_high_volatility_decadal_persistence(df_agri: pd.DataFrame, summary_dict: dict) -> None:
    """Verifies that the 42 high-volatility cells maintain consistent high variability across both sub-periods."""
    vol_sub = df_agri[df_agri["regime_kmeans"] == "Rain-Shadow High-Volatility"]
    assert len(vol_sub) == 42, f"Expected 42 cells, got {len(vol_sub)}"

    # Must exceed 25 days in both periods
    p1_mean = float(vol_sub["onset_std_p1_2001_2011"].mean())
    p2_mean = float(vol_sub["onset_std_p2_2012_2023"].mean())
    assert p1_mean >= 25.0, f"Period 1 std too low: {p1_mean}"
    assert p2_mean >= 25.0, f"Period 2 std too low: {p2_mean}"
    # Difference between periods should be small (< 3 days)
    assert abs(p1_mean - p2_mean) < 3.0

    # Highest early-season dry spell exposure
    assert float(vol_sub["early_dry_spell_mean_days"].mean()) > 13.0
    assert float(vol_sub["sowing_delay_past_july1_freq"].mean()) > 0.20


def test_phase_preservation() -> None:
    """Verifies that Phase 5 and Phase 6 data files were preserved unchanged."""
    assert ONSET_CLUSTERS_CSV.exists()
    df_prev = pd.read_csv(ONSET_CLUSTERS_CSV)
    assert len(df_prev) == 419
    assert "cluster_kmeans" in df_prev.columns
    assert "regime_kmeans" in df_prev.columns


def test_geospatial_plots_generated() -> None:
    """Verifies that all 7 required Phase 7 geospatial and diagnostic figures exist."""
    required_plots = [
        "map_regime_classification.png",
        "map_early_onset_frequency.png",
        "map_delayed_onset_frequency.png",
        "map_onset_variability.png",
        "map_high_volatility_focus.png",
        "chart_independent_agricultural_metrics.png",
        "map_sowing_opportunity_delay.png",
    ]
    for p_name in required_plots:
        p_path = PLOTS_DIR / p_name
        assert p_path.exists(), f"Missing required figure: {p_path}"
        assert p_path.stat().st_size > 15000, f"Suspiciously small plot {p_path}"
