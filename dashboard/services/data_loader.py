"""MonsoonIQ Dashboard – Data Loader Service.

Loads and caches all project datasets: daily rainfall, onset, clusters,
baselines, and geographic boundaries. Uses Streamlit caching.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st
import xarray as xr

logger = logging.getLogger("MonsoonIQ.DataLoader")

# Project root
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent


@st.cache_data(ttl=3600, show_spinner="Loading daily rainfall dataset...")
def load_daily_rainfall() -> xr.Dataset:
    """Load the IMD daily rainfall NetCDF (66 MB).

    Returns:
        xr.Dataset with 'rainfall_masked', 'mask_maharashtra', coordinates.
    """
    path = PROJECT_ROOT / "data" / "processed" / "maharashtra_imd_daily_2001_2023.nc"
    if not path.exists():
        st.error(f"Daily rainfall file not found: {path}")
        st.stop()
    return xr.open_dataset(path)


@st.cache_data(ttl=3600, show_spinner="Loading onset dataset...")
def load_onset_dataset() -> xr.Dataset:
    """Load the onset results NetCDF.

    Returns:
        xr.Dataset with confirmed_onset_doy, candidate_onset_doy, etc.
    """
    path = PROJECT_ROOT / "data" / "processed" / "maharashtra_onset_2001_2023.nc"
    if not path.exists():
        st.error(f"Onset dataset not found: {path}")
        st.stop()
    return xr.open_dataset(path)


@st.cache_data(ttl=3600, show_spinner="Loading baselines...")
def load_baselines() -> pd.DataFrame:
    """Load advisory historical baselines CSV (419 cells × 41 columns).

    Returns:
        pd.DataFrame with cell metadata, regime labels, and historical metrics.
    """
    path = PROJECT_ROOT / "data" / "processed" / "advisory_historical_baselines.csv"
    if not path.exists():
        st.error(f"Baselines CSV not found: {path}")
        st.stop()
    return pd.read_csv(path)


@st.cache_data(ttl=3600, show_spinner="Loading cluster assignments...")
def load_clusters() -> pd.DataFrame:
    """Load monsoon onset cluster assignments CSV (419 cells).

    Returns:
        pd.DataFrame with cell_id, regime_kmeans, cluster assignments, and features.
    """
    path = PROJECT_ROOT / "data" / "processed" / "monsoon_onset_clusters.csv"
    if not path.exists():
        st.error(f"Clusters CSV not found: {path}")
        st.stop()
    return pd.read_csv(path)


@st.cache_data(ttl=3600, show_spinner="Loading onset features...")
def load_features() -> pd.DataFrame:
    """Load monsoon onset features CSV (419 cells × 17 features).

    Returns:
        pd.DataFrame with per-cell onset dynamics features.
    """
    path = PROJECT_ROOT / "data" / "processed" / "monsoon_onset_features.csv"
    if not path.exists():
        st.error(f"Features CSV not found: {path}")
        st.stop()
    return pd.read_csv(path)


@st.cache_data(ttl=3600)
def load_geojson(filename: str) -> Optional[Dict[str, Any]]:
    """Load a GeoJSON file from data/geo/.

    Args:
        filename: GeoJSON filename (e.g. 'maharashtra_state.geojson').

    Returns:
        Parsed GeoJSON dict, or None if file not found.
    """
    path = PROJECT_ROOT / "data" / "geo" / filename
    if not path.exists():
        logger.warning(f"GeoJSON not found: {path}")
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_cell_rainfall_series(
    cell_lat: float, cell_lon: float, year: int
) -> pd.Series:
    """Extract daily rainfall time series for a specific cell and year.

    Args:
        cell_lat: Grid cell latitude.
        cell_lon: Grid cell longitude.
        year: Calendar year (2001-2023).

    Returns:
        pd.Series indexed by datetime with daily rainfall (mm).
    """
    ds = load_daily_rainfall()
    cell_data = ds["rainfall_masked"].sel(
        lat=cell_lat, lon=cell_lon, method="nearest"
    )
    start = f"{year}-01-01"
    end = f"{year}-12-31"
    yearly = cell_data.sel(time=slice(start, end))
    return yearly.to_series()


def get_cell_onset_history(
    cell_lat: float, cell_lon: float
) -> pd.DataFrame:
    """Extract onset history for a specific cell across all years.

    Args:
        cell_lat: Grid cell latitude.
        cell_lon: Grid cell longitude.

    Returns:
        pd.DataFrame with year, confirmed_onset_doy, candidate_onset_doy, etc.
    """
    ds = load_onset_dataset()
    cell = ds.sel(lat=cell_lat, lon=cell_lon, method="nearest")

    records = []
    for yr in ds.year.values:
        confirmed = float(cell["confirmed_onset_doy"].sel(year=yr).values)
        candidate = float(cell["candidate_onset_doy"].sel(year=yr).values)
        rejected = int(cell["rejected_candidate_count"].sel(year=yr).values)
        no_det = int(cell["no_detection_flag"].sel(year=yr).values)
        max_dry = int(cell["max_post_candidate_dry_spell"].sel(year=yr).values)
        records.append({
            "year": int(yr),
            "confirmed_onset_doy": confirmed if not np.isnan(confirmed) else None,
            "candidate_onset_doy": candidate if not np.isnan(candidate) else None,
            "rejected_candidates": rejected,
            "no_detection": no_det,
            "max_post_candidate_dry_spell": max_dry,
        })
    return pd.DataFrame(records)


def get_jjas_rainfall(cell_lat: float, cell_lon: float) -> pd.DataFrame:
    """Get annual JJAS rainfall totals for a cell.

    Args:
        cell_lat: Grid cell latitude.
        cell_lon: Grid cell longitude.

    Returns:
        pd.DataFrame with columns 'year' and 'jjas_rainfall_mm'.
    """
    ds = load_daily_rainfall()
    cell_data = ds["rainfall_masked"].sel(
        lat=cell_lat, lon=cell_lon, method="nearest"
    )
    records = []
    for yr in range(2001, 2024):
        start = f"{yr}-06-01"
        end = f"{yr}-09-30"
        jjas = cell_data.sel(time=slice(start, end))
        total = float(jjas.sum(skipna=True).values)
        records.append({"year": yr, "jjas_rainfall_mm": total})
    return pd.DataFrame(records)
