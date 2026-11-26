"""MonsoonIQ Dashboard – Dashboard Service.

Higher-level functions that combine data from multiple sources
to produce dashboard-ready summary statistics and DataFrames.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Ensure project root is importable
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.services.data_loader import (
    get_cell_onset_history,
    get_cell_rainfall_series,
    get_jjas_rainfall,
    load_baselines,
    load_clusters,
    load_onset_dataset,
)
from dashboard.utils.formatting import doy_to_date_str


def get_regime_summary() -> pd.DataFrame:
    """Build a regime comparison summary table.

    Returns:
        pd.DataFrame with one row per regime containing counts, onset stats,
        variability, dry-spell metrics, etc.
    """
    df = load_baselines()
    regimes = df.groupby("regime_kmeans").agg(
        cell_count=("cell_id", "count"),
        median_onset_doy=("median_onset_doy", "median"),
        mean_onset_doy=("mean_onset_doy", "mean"),
        mean_std_onset=("std_onset_doy", "mean"),
        mean_iqr_onset=("iqr_onset_doy", "mean"),
        mean_early_freq=("early_onset_freq", "mean"),
        mean_delayed_freq=("delayed_onset_freq", "mean"),
        mean_rejected_freq=("rejected_candidate_freq", "mean"),
        mean_detection_freq=("onset_detection_freq", "mean"),
        mean_june_rain=("june_mean_rainfall_mm", "mean"),
        mean_june_cv=("june_rainfall_cv_pct", "mean"),
        mean_dry_spell=("early_dry_spell_mean_days", "mean"),
        max_dry_spell=("early_dry_spell_max_days", "max"),
        mean_severe_10d=("severe_dry_spell_10d_freq", "mean"),
    ).reset_index()

    regimes["pct_of_total"] = (regimes["cell_count"] / regimes["cell_count"].sum() * 100).round(1)
    regimes["median_onset_date"] = regimes["median_onset_doy"].apply(doy_to_date_str)
    return regimes


def get_confirmed_onset_counts() -> int:
    """Count total confirmed onset records across all cells and years.

    Returns:
        Integer count of confirmed (non-NaN) onset DOY entries.
    """
    ds = load_onset_dataset()
    confirmed = ds["confirmed_onset_doy"].values
    return int(np.sum(~np.isnan(confirmed) & (confirmed > 0)))


def build_cell_selector_df() -> pd.DataFrame:
    """Build a DataFrame for sidebar cell selection with display-friendly columns.

    Returns:
        pd.DataFrame with cell_id, latitude, longitude, district, regime, median_onset, etc.
    """
    df = load_baselines()
    sel = df[["cell_id", "latitude", "longitude", "district", "regime_kmeans",
              "median_onset_doy", "std_onset_doy"]].copy()
    sel["median_onset_date"] = sel["median_onset_doy"].apply(doy_to_date_str)
    sel = sel.rename(columns={"regime_kmeans": "regime"})
    return sel


def get_monthly_rainfall(cell_lat: float, cell_lon: float, year: int) -> pd.DataFrame:
    """Get monthly rainfall totals and wet-day counts for a cell and year.

    Args:
        cell_lat: Grid cell latitude.
        cell_lon: Grid cell longitude.
        year: Calendar year.

    Returns:
        pd.DataFrame with month, total_mm, wet_days columns.
    """
    daily = get_cell_rainfall_series(cell_lat, cell_lon, year)
    df = daily.reset_index()
    df.columns = ["date", "rainfall_mm"]
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.month

    monthly = df.groupby("month").agg(
        total_mm=("rainfall_mm", lambda x: float(x.sum(skipna=True))),
        wet_days=("rainfall_mm", lambda x: int((x >= 2.5).sum())),
    ).reset_index()
    return monthly


def get_cell_advisory_data(
    cell_id: str, year: int
) -> List[Tuple[str, Optional[float]]]:
    """Build daily rainfall list for the advisory engine from historical data.

    Args:
        cell_id: Grid cell identifier (e.g. 'cell_020').
        year: Calendar year (2001-2023).

    Returns:
        List of (date_str, rainfall_mm) tuples for June 1 through July 31.
    """
    df = load_baselines()
    row = df[df["cell_id"] == cell_id]
    if row.empty:
        return []

    lat = float(row.iloc[0]["latitude"])
    lon = float(row.iloc[0]["longitude"])

    daily = get_cell_rainfall_series(lat, lon, year)

    start_dt = pd.Timestamp(f"{year}-06-01")
    end_dt = pd.Timestamp(f"{year}-07-31")
    subset = daily.loc[start_dt:end_dt]

    result = []
    for dt, val in subset.items():
        date_str = pd.Timestamp(dt).strftime("%Y-%m-%d")
        rain_val = float(val) if not np.isnan(val) else None
        result.append((date_str, rain_val))
    return result
