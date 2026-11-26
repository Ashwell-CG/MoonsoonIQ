"""MonsoonIQ - Automated Test Suite for Phase 3 IMD Data Preprocessing.

This test suite validates:
1. Existence and integrity of data/processed/maharashtra_imd_daily_2001_2023.nc.
2. Exact temporal dimension: 8,400 consecutive days from 2001-01-01 to 2023-12-31.
3. Zero missing dates and zero duplicate timestamps.
4. Correct spatial dimensions (28 lats x 35 lons = 980 bounding box cells).
5. Exact authoritative Maharashtra masking: 419 valid land cells, 50 Arabian sea cells.
6. Zero missing values on Maharashtra land across the entire 23-year multi-decadal record.
7. Physical plausibility: strictly non-negative values (>= 0 mm), finite numbers, and
   accurate representation of historical extremes (e.g., 2001 Vidarbha peak, 2005 Mumbai deluge).
"""

from pathlib import Path
import json
import numpy as np
import pandas as pd
import pytest
import xarray as xr

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_NC_PATH = BASE_DIR / "data" / "processed" / "maharashtra_imd_daily_2001_2023.nc"
SUMMARY_JSON_PATH = BASE_DIR / "data" / "processed" / "preprocessing_summary.json"


@pytest.fixture(scope="module")
def processed_ds() -> xr.Dataset:
    """Fixture providing the consolidated 2001–2023 NetCDF dataset."""
    assert (
        PROCESSED_NC_PATH.exists()
    ), f"Consolidated NetCDF not found at {PROCESSED_NC_PATH}"
    return xr.open_dataset(PROCESSED_NC_PATH)


@pytest.fixture(scope="module")
def summary_data() -> dict:
    """Fixture providing the preprocessing summary JSON."""
    assert (
        SUMMARY_JSON_PATH.exists()
    ), f"Summary JSON not found at {SUMMARY_JSON_PATH}"
    with open(SUMMARY_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class TestProcessedDatasetIntegrity:
    """Tests for file presence, size, dimensions, and variables."""

    def test_file_exists_and_size_reasonable(self, summary_data: dict):
        """Verifies file exists and compressed size is between 10 MB and 30 MB."""
        assert PROCESSED_NC_PATH.exists()
        size_mb = summary_data["file_size_mb"]
        assert 10.0 <= size_mb <= 30.0, f"Unexpected file size: {size_mb} MB"
        assert summary_data["status"] == "PASS"

    def test_dimensions_and_variables(self, processed_ds: xr.Dataset):
        """Verifies dimensions (8400, 28, 35) and all required variables."""
        assert processed_ds.sizes["time"] == 8400
        assert processed_ds.sizes["lat"] == 28
        assert processed_ds.sizes["lon"] == 35

        expected_vars = {"rainfall", "rainfall_masked", "mask_maharashtra", "is_land"}
        assert expected_vars.issubset(set(processed_ds.data_vars))

    def test_coordinate_values_and_steps(self, processed_ds: xr.Dataset):
        """Verifies 0.25-degree grid spacing across lat and lon."""
        lats = processed_ds["lat"].values
        lons = processed_ds["lon"].values

        assert np.isclose(lats[0], 15.5, atol=1e-3)
        assert np.isclose(lats[-1], 22.25, atol=1e-3)
        assert np.allclose(np.diff(lats), 0.25, atol=1e-3)

        assert np.isclose(lons[0], 72.5, atol=1e-3)
        assert np.isclose(lons[-1], 81.0, atol=1e-3)
        assert np.allclose(np.diff(lons), 0.25, atol=1e-3)


class TestTemporalContinuity:
    """Tests for strict continuous daily date sequence without gaps or duplicates."""

    def test_temporal_continuity_and_completeness(self, processed_ds: xr.Dataset):
        """Verifies exactly 8,400 contiguous calendar days from 2001-01-01 to 2023-12-31."""
        times = pd.to_datetime(processed_ds["time"].values)
        expected_dates = pd.date_range("2001-01-01", "2023-12-31", freq="D")

        assert len(times) == 8400
        assert len(times) == len(expected_dates)
        assert not pd.DatetimeIndex(times).has_duplicates
        assert (times.normalize() == expected_dates).all()

    def test_leap_years_included(self, processed_ds: xr.Dataset):
        """Verifies all 5 leap years (2004, 2008, 2012, 2016, 2020) contain Feb 29."""
        times = pd.to_datetime(processed_ds["time"].values)
        for leap_yr in [2004, 2008, 2012, 2016, 2020]:
            feb_29 = pd.Timestamp(f"{leap_yr}-02-29")
            assert feb_29 in times, f"Missing Feb 29 for leap year {leap_yr}"


class TestSpatialMaskingAndMissingValues:
    """Tests for authoritative administrative masking and NaN conventions."""

    def test_maharashtra_mask_counts(self, processed_ds: xr.Dataset):
        """Verifies exactly 419 valid Maharashtra land cells and 50 sea cells."""
        mask_mh = processed_ds["mask_maharashtra"].values
        is_land = processed_ds["is_land"].values

        assert int(np.sum(mask_mh)) == 419
        assert int(np.sum(~is_land)) == 50
        assert int(np.sum(is_land)) == 930
        assert mask_mh.size == 28 * 35

    def test_zero_missing_values_on_maharashtra_land(self, processed_ds: xr.Dataset):
        """Verifies that all 419 Maharashtra land cells have 0 missing values over 8,400 days."""
        mask_mh = processed_ds["mask_maharashtra"].values
        rf_masked = processed_ds["rainfall_masked"].values  # (8400, 28, 35)

        # Extract only Maharashtra land cells
        mh_land_vals = rf_masked[:, mask_mh]  # (8400, 419)
        assert mh_land_vals.size == 8400 * 419
        assert not np.any(np.isnan(mh_land_vals)), "Found unexpected NaNs on Maharashtra land!"

    def test_ocean_cells_are_all_nan(self, processed_ds: xr.Dataset):
        """Verifies all 50 Arabian Sea cells are strictly NaN across all 8,400 days."""
        is_land = processed_ds["is_land"].values
        rf = processed_ds["rainfall"].values

        sea_vals = rf[:, ~is_land]  # (8400, 50)
        assert np.all(np.isnan(sea_vals))
        assert sea_vals.size == 8400 * 50


class TestPhysicalPlausibilityAndExtremes:
    """Tests for physical value boundaries and historical meteorological extremes."""

    def test_non_negativity_and_finiteness(self, processed_ds: xr.Dataset):
        """Verifies rainfall is non-negative and finite everywhere on land."""
        mask_mh = processed_ds["mask_maharashtra"].values
        mh_vals = processed_ds["rainfall_masked"].values[:, mask_mh]

        assert np.all(mh_vals >= 0.0)
        assert np.all(np.isfinite(mh_vals))

    def test_historical_peak_event_2001(self, summary_data: dict):
        """Verifies 23-year historical maximum is 639.27 mm on 2001-08-09."""
        peak = summary_data["rainfall_statistics"]["peak_event"]
        assert np.isclose(peak["rainfall_mm"], 639.27, atol=1e-1)
        assert peak["date"] == "2001-08-09"
        assert np.isclose(peak["lat"], 21.25, atol=1e-2)
        assert np.isclose(peak["lon"], 79.50, atol=1e-2)

    def test_mumbai_deluge_2005_captured(self, processed_ds: xr.Dataset):
        """Verifies July 27, 2005 extreme exceeds 500 mm in coastal Konkan."""
        deluge_cell = processed_ds["rainfall"].sel(
            time="2005-07-27", lat=19.25, lon=73.00, method="nearest"
        )
        assert float(deluge_cell.values) > 500.0
