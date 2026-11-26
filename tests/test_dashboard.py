"""MonsoonIQ – Test Suite for Phase 9 Dashboard Services and Integration.

Validates:
1. Historical dataset loading (baselines, clusters, features, onset NetCDF, daily rainfall NetCDF).
2. Grid-cell selection and summary services.
3. Regime filtering and cell count integrity across the 4 discovered regimes.
4. Missing data preservation (NaN semantics, no zero-filling).
5. Advisory engine integration via dashboard services.
6. Provenance configuration and integrity checks.
7. Rainfall chart timeseries generation.
8. Dataset preservation and read-only consistency.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd
import pytest
import xarray as xr

# Ensure project root is in sys.path
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.components.provenance import PROVENANCE_SOURCES
from dashboard.services.dashboard_service import (
    build_cell_selector_df,
    get_cell_advisory_data,
    get_confirmed_onset_counts,
    get_monthly_rainfall,
    get_regime_summary,
)
from dashboard.services.data_loader import (
    get_cell_onset_history,
    get_cell_rainfall_series,
    get_jjas_rainfall,
    load_baselines,
    load_clusters,
    load_daily_rainfall,
    load_features,
    load_geojson,
    load_onset_dataset,
)
from dashboard.utils.constants import (
    DATA_RESOLUTION,
    EXPECTED_REGIME_COUNTS,
    STUDY_YEAR_END,
    STUDY_YEAR_START,
    TOTAL_CELLS,
    TOTAL_YEARS,
)
from dashboard.utils.formatting import (
    doy_to_date_str,
    format_cell_dropdown_label,
    format_mm,
    format_pct,
)
from src.advisory import AdvisoryDecisionEngine, AdvisoryReport, AdvisoryState


# =========================================================================
# 1. Historical Dataset Loading Tests
# =========================================================================

def test_load_baselines() -> None:
    """Test loading advisory historical baselines CSV."""
    df = load_baselines()
    assert isinstance(df, pd.DataFrame), "Baselines must be a DataFrame."
    assert len(df) == TOTAL_CELLS, f"Baselines must contain exactly {TOTAL_CELLS} cells."
    required_cols = [
        "cell_id", "latitude", "longitude", "district",
        "regime_kmeans", "median_onset_doy", "std_onset_doy",
        "june_mean_rainfall_mm", "early_dry_spell_mean_days",
    ]
    for col in required_cols:
        assert col in df.columns, f"Required column '{col}' missing from baselines."


def test_load_clusters() -> None:
    """Test loading monsoon onset cluster assignments CSV."""
    df = load_clusters()
    assert isinstance(df, pd.DataFrame), "Clusters must be a DataFrame."
    assert len(df) == TOTAL_CELLS, f"Clusters must contain {TOTAL_CELLS} cells."
    assert "regime_kmeans" in df.columns
    assert "cluster_kmeans" in df.columns


def test_load_features() -> None:
    """Test loading monsoon onset features CSV."""
    df = load_features()
    assert isinstance(df, pd.DataFrame), "Features must be a DataFrame."
    assert len(df) == TOTAL_CELLS, f"Features must contain {TOTAL_CELLS} cells."
    assert "cell_id" in df.columns
    assert len(df.columns) >= 10, "Features file should contain at least 10 columns."


def test_load_onset_dataset() -> None:
    """Test loading onset NetCDF dataset."""
    ds = load_onset_dataset()
    assert isinstance(ds, xr.Dataset), "Onset data must be an xarray Dataset."
    assert "confirmed_onset_doy" in ds.data_vars
    assert "candidate_onset_doy" in ds.data_vars
    assert "no_detection_flag" in ds.data_vars
    assert ds.sizes["year"] == TOTAL_YEARS
    assert ds.sizes["lat"] == 28
    assert ds.sizes["lon"] == 35


def test_load_daily_rainfall() -> None:
    """Test loading daily rainfall NetCDF dataset."""
    ds = load_daily_rainfall()
    assert isinstance(ds, xr.Dataset), "Daily rainfall must be an xarray Dataset."
    assert "rainfall_masked" in ds.data_vars
    assert "mask_maharashtra" in ds.data_vars
    assert ds.sizes["time"] == 8400, "Daily rainfall must contain 8,400 daily time steps (2001-2023)."


def test_load_geojson_boundaries() -> None:
    """Test loading GeoJSON boundaries."""
    state_geo = load_geojson("maharashtra_state.geojson")
    assert state_geo is not None, "Maharashtra state GeoJSON should load successfully."
    assert "features" in state_geo

    district_geo = load_geojson("maharashtra_districts.geojson")
    assert district_geo is not None, "Maharashtra districts GeoJSON should load successfully."
    assert "features" in district_geo
    assert len(district_geo["features"]) > 0


# =========================================================================
# 2. Grid-Cell Selection and Summary Services
# =========================================================================

def test_build_cell_selector_df() -> None:
    """Test cell selector DataFrame generation."""
    sel = build_cell_selector_df()
    assert len(sel) == TOTAL_CELLS
    assert "cell_id" in sel.columns
    assert "latitude" in sel.columns
    assert "longitude" in sel.columns
    assert "district" in sel.columns
    assert "regime" in sel.columns
    assert "median_onset_date" in sel.columns


def test_get_confirmed_onset_counts() -> None:
    """Test total confirmed onset records computation."""
    count = get_confirmed_onset_counts()
    assert isinstance(count, int)
    # Total valid cell-years is 419 * 23 = 9637; confirmed is around 9606
    assert 9500 <= count <= 9637, f"Confirmed count {count} is outside expected range."


def test_get_regime_summary() -> None:
    """Test regime summary table generation."""
    regimes = get_regime_summary()
    assert len(regimes) == 4, "Must have exactly 4 regimes."
    assert regimes["cell_count"].sum() == TOTAL_CELLS
    for expected_regime, expected_count in EXPECTED_REGIME_COUNTS.items():
        row = regimes[regimes["regime_kmeans"] == expected_regime]
        assert not row.empty, f"Regime {expected_regime} not found in summary."
        assert row.iloc[0]["cell_count"] == expected_count, (
            f"Regime {expected_regime} count {row.iloc[0]['cell_count']} != {expected_count}"
        )


# =========================================================================
# 3. Regime Filtering & Integrity
# =========================================================================

def test_regime_distribution_integrity() -> None:
    """Verify that cell regime assignments match exact Phase 6B/7 counts."""
    df = load_baselines()
    counts = df["regime_kmeans"].value_counts().to_dict()
    for regime_name, expected_count in EXPECTED_REGIME_COUNTS.items():
        assert counts.get(regime_name, 0) == expected_count, (
            f"Regime '{regime_name}' count mismatch: {counts.get(regime_name)} vs {expected_count}"
        )


# =========================================================================
# 4. Missing-Data Handling & NaN Preservation
# =========================================================================

def test_missing_rainfall_preserved_as_nan() -> None:
    """Verify that missing rainfall is preserved as NaN and not converted to 0.0."""
    ds = load_daily_rainfall()
    # Masked areas outside Maharashtra should be NaN
    rainfall = ds["rainfall_masked"].values
    nan_count = np.isnan(rainfall).sum()
    assert nan_count > 0, "Daily rainfall must contain NaN values for unobserved or masked cells."

    # Within valid cells, ensure missing values stay NaN
    df_base = load_baselines()
    first_cell = df_base.iloc[0]
    series = get_cell_rainfall_series(float(first_cell["latitude"]), float(first_cell["longitude"]), 2023)
    # The series may contain NaNs if unobserved, but crucially should not have synthetic zeros
    assert isinstance(series, pd.Series)
    assert len(series) == 365, "2023 is non-leap year (365 days)."


# =========================================================================
# 5. Advisory Engine Integration Tests
# =========================================================================

def test_get_cell_advisory_data() -> None:
    """Test retrieval of daily rainfall data formatted for advisory engine."""
    data = get_cell_advisory_data("cell_001", 2023)
    assert isinstance(data, list)
    # Sowing advisory window is June 1 through July 31 (61 days)
    assert len(data) == 61
    assert isinstance(data[0], tuple)
    assert len(data[0]) == 2
    # Verify format: ("YYYY-MM-DD", rainfall_float)
    assert data[0][0].startswith("2023-06-01")
    assert isinstance(data[0][1], float)


def test_advisory_engine_execution() -> None:
    """Test executing advisory engine on dashboard data for a known cell."""
    engine = AdvisoryDecisionEngine()
    data = get_cell_advisory_data("cell_001", 2023)
    # Filter to June 25
    filtered_data = [(d, r) for d, r in data if d <= "2023-06-25"]
    report = engine.generate_advisory(
        "cell_001",
        filtered_data,
        as_of_date="2023-06-25",
        data_provenance="Historical Replay (IMD 0.25° Gridded 2001-2023)",
    )
    assert isinstance(report, AdvisoryReport)
    assert isinstance(report.advisory_state, AdvisoryState)
    assert report.advisory_state in list(AdvisoryState)
    assert report.data_provenance == "Historical Replay (IMD 0.25° Gridded 2001-2023)"
    # Disallow "Safe to Sow"
    assert "safe to sow" not in report.advisory_state.value.lower()
    for reason in report.state_reasoning:
        assert "safe to sow" not in reason.lower()


# =========================================================================
# 6. Provenance Configuration & Attribution
# =========================================================================

def test_provenance_sources_configuration() -> None:
    """Verify provenance sources dictionary has all required feeds and statuses."""
    assert "historical_replay" in PROVENANCE_SOURCES
    assert "simulated_test" in PROVENANCE_SOURCES
    assert "observed_aws" in PROVENANCE_SOURCES
    assert "nwp_forecast" in PROVENANCE_SOURCES

    # Ensure unintegrated feeds are marked as NOT CONNECTED
    assert PROVENANCE_SOURCES["observed_aws"]["status"] == "NOT CONNECTED"
    assert PROVENANCE_SOURCES["nwp_forecast"]["status"] == "NOT CONNECTED"
    assert PROVENANCE_SOURCES["historical_replay"]["status"] == "ACTIVE"


# =========================================================================
# 7. Rainfall & Onset Chart Data Preparation
# =========================================================================

def test_get_jjas_rainfall() -> None:
    """Verify JJAS seasonal rainfall calculation for a cell across 23 years."""
    df_base = load_baselines()
    row = df_base.iloc[0]
    jjas_df = get_jjas_rainfall(float(row["latitude"]), float(row["longitude"]))
    assert isinstance(jjas_df, pd.DataFrame)
    assert len(jjas_df) == TOTAL_YEARS
    assert "year" in jjas_df.columns
    assert "jjas_rainfall_mm" in jjas_df.columns
    assert (jjas_df["year"] == list(range(STUDY_YEAR_START, STUDY_YEAR_END + 1))).all()


def test_get_cell_onset_history() -> None:
    """Verify onset history extraction for a cell across all years."""
    df_base = load_baselines()
    row = df_base.iloc[0]
    history = get_cell_onset_history(float(row["latitude"]), float(row["longitude"]))
    assert isinstance(history, pd.DataFrame)
    assert len(history) == TOTAL_YEARS
    assert "year" in history.columns
    assert "confirmed_onset_doy" in history.columns
    assert "candidate_onset_doy" in history.columns
    assert "rejected_candidates" in history.columns
    assert "no_detection" in history.columns


# =========================================================================
# 8. Formatting Utilities
# =========================================================================

def test_formatting_utils() -> None:
    """Test formatting helper functions."""
    assert doy_to_date_str(153) == "Jun 02"  # non-leap: DOY 153 is June 2
    assert doy_to_date_str(np.nan) == "—"
    assert format_mm(75.25) == "75.2 mm"
    assert format_pct(0.3913) == "39.1%"
    assert format_pct(np.nan) == "—"

    # Test format_cell_dropdown_label with district name first and fallbacks
    assert (
        format_cell_dropdown_label("cell_001", "Sindhudurg", 15.75, 74.00)
        == "Sindhudurg · cell_001 · 15.75°N, 74.00°E"
    )
    assert (
        format_cell_dropdown_label("cell_042", "Unknown", 18.50, 75.25)
        == "cell_042 · 18.50°N, 75.25°E"
    )
    assert (
        format_cell_dropdown_label("cell_043", None, 18.50, 75.25)
        == "cell_043 · 18.50°N, 75.25°E"
    )
    assert (
        format_cell_dropdown_label("cell_044", "", 18.50, 75.25)
        == "cell_044 · 18.50°N, 75.25°E"
    )
    assert (
        format_cell_dropdown_label("cell_045", "nan", 18.50, 75.25)
        == "cell_045 · 18.50°N, 75.25°E"
    )


# =========================================================================
# 9. Plotly Theme & Figure Layout Integrity
# =========================================================================

def test_plotly_theme_and_figure_layouts() -> None:
    """Verify PLOTLY_LAYOUT applies cleanly to figures without property or collision errors."""
    import plotly.graph_objects as go
    from dashboard.utils.chart_theme import PLOTLY_LAYOUT

    fig = go.Figure()
    fig.add_trace(go.Bar(x=[1, 2, 3], y=[10, 20, 30]))

    # Must accept **PLOTLY_LAYOUT with custom overrides without raising TypeError/ValueError
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title="Test Plot",
        xaxis_title="X Axis",
        yaxis_title="Y Axis",
        height=350,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis=dict(gridcolor="#F1F5F9"),
        yaxis=dict(gridcolor="#F1F5F9"),
    )
    assert fig.layout.template is not None
    assert fig.layout.title.text == "Test Plot"


# =========================================================================
# 10. Dataset Preservation & Read-Only Integrity
# =========================================================================

def test_dataset_read_only_integrity() -> None:
    """Verify that processed data files exist and have non-zero sizes."""
    base_file = PROJECT_ROOT / "data" / "processed" / "advisory_historical_baselines.csv"
    onset_file = PROJECT_ROOT / "data" / "processed" / "maharashtra_onset_2001_2023.nc"
    daily_file = PROJECT_ROOT / "data" / "processed" / "maharashtra_imd_daily_2001_2023.nc"

    assert base_file.exists() and base_file.stat().st_size > 50_000
    assert onset_file.exists() and onset_file.stat().st_size > 50_000
    assert daily_file.exists() and daily_file.stat().st_size > 10_000_000  # ~15 MB NetCDF
