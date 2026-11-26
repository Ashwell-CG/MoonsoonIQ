"""MonsoonIQ - Automated Test Suite for CHIRPS 2023 Scientific Audit.

This test module verifies the correctness of:
1. Julian day temporal conversion and continuity across 365 calendar days.
2. Spatial bounds, 0.25-degree resolution, sea masking, and Maharashtra land cells.
3. Extreme rainfall decoding, peak validation, and physical bounds.
4. Benchmark district coordinates, distance, point-in-polygon containment, and area averages.
5. Statistical re-aggregation, JJAS seasonality, and masked dataset integrity.
"""

from pathlib import Path
import json
import numpy as np
import pandas as pd
import pytest
import xarray as xr

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_NC_PATH = BASE_DIR / "data" / "raw" / "chirps" / "chirps_2023_regional_raw.nc"
INTERIM_NC_PATH = BASE_DIR / "data" / "interim" / "maharashtra_chirps_2023.nc"
MASKED_NC_PATH = BASE_DIR / "data" / "interim" / "maharashtra_chirps_2023_masked.nc"
AUDIT_JSON_PATH = BASE_DIR / "data" / "interim" / "audit_results_2023.json"


@pytest.fixture(scope="module")
def audit_results() -> dict:
    """Fixture providing cached audit results from the JSON output."""
    assert (
        AUDIT_JSON_PATH.exists()
    ), f"Audit JSON results not found at {AUDIT_JSON_PATH}"
    with open(AUDIT_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def interim_ds() -> xr.Dataset:
    """Fixture providing the interim CHIRPS 2023 dataset."""
    assert (
        INTERIM_NC_PATH.exists()
    ), f"Interim NetCDF not found at {INTERIM_NC_PATH}"
    return xr.open_dataset(INTERIM_NC_PATH)


@pytest.fixture(scope="module")
def masked_ds() -> xr.Dataset:
    """Fixture providing the masked CHIRPS 2023 dataset."""
    assert MASKED_NC_PATH.exists(), f"Masked NetCDF not found at {MASKED_NC_PATH}"
    return xr.open_dataset(MASKED_NC_PATH)


class TestTask1Metadata:
    """Test suite for Task 1: Dataset Verification and Metadata."""

    def test_variable_and_units(self, interim_ds: xr.Dataset, audit_results: dict):
        """Verifies precipitation units and variable definitions."""
        assert "rainfall" in interim_ds.data_vars
        meta = audit_results["task_1_metadata"]
        assert meta["raw_units"] == "mm/day"
        assert meta["product_version"] == "UCSB CHIRPS v2.0"
        assert meta["nominal_resolution"] == "0.25 degree (15 arc-minute)"

    def test_spatial_resolution(self, interim_ds: xr.Dataset, audit_results: dict):
        """Verifies 0.25-degree grid spacing."""
        meta = audit_results["task_1_metadata"]
        assert np.isclose(meta["spatial_resolution_lat"], 0.25, atol=1e-3)
        assert np.isclose(meta["spatial_resolution_lon"], 0.25, atol=1e-3)


class TestTask2TimeValidation:
    """Test suite for Task 2: Temporal Validation and Julian Day Conversion."""

    def test_julian_conversion_and_noon_utc(self, audit_results: dict):
        """Verifies Julian day 2459946.0 decodes to 2023-01-01 12:00:00 UTC."""
        time_res = audit_results["task_2_time"]
        assert time_res["raw_first_julian"] == 2459946.0
        assert time_res["raw_decoded_first_timestamp"] == "2023-01-01 12:00:00"
        assert time_res["is_noon_utc_midpoint"] is True

    def test_calendar_continuity(self, interim_ds: xr.Dataset, audit_results: dict):
        """Verifies strict 365-day continuity without gaps or duplicates."""
        time_res = audit_results["task_2_time"]
        assert time_res["interim_num_days"] == 365
        assert time_res["interim_first_date"] == "2023-01-01"
        assert time_res["interim_last_date"] == "2023-12-31"
        assert time_res["temporal_continuity_passed"] is True

        # Directly verify xarray time coordinate
        times = pd.to_datetime(interim_ds["time"].values)
        expected = pd.date_range("2023-01-01", "2023-12-31", freq="D")
        assert (times.normalize() == expected).all()


class TestTask3GeographicValidation:
    """Test suite for Task 3: Geographic Boundary and Spatial Masking."""

    def test_grid_cell_counts(self, audit_results: dict):
        """Verifies cell breakdown: 918 total = 44 sea + 453 out-of-state + 421 MH."""
        spatial = audit_results["task_3_spatial"]
        assert spatial["total_bounding_box_cells"] == 918
        assert spatial["lat_count"] == 27
        assert spatial["lon_count"] == 34
        assert spatial["sea_cells_count"] == 44
        assert spatial["terrestrial_outside_mh_cells"] == 453
        assert spatial["true_maharashtra_land_cells"] == 421
        assert spatial["state_mask_sum_matches"] is True

    def test_sea_points_all_nan(self, masked_ds: xr.Dataset):
        """Verifies sea cells are entirely NaN across all 365 days."""
        is_land = masked_ds["is_land"].values  # (27, 34)
        rf = masked_ds["rainfall"].values  # (365, 27, 34)
        # For all sea cells (~is_land), every day must be NaN
        sea_rf = rf[:, ~is_land]
        assert np.all(np.isnan(sea_rf))
        # Total NaN count over sea
        assert sea_rf.size == 44 * 365


class TestTask4ExtremeRainfall:
    """Test suite for Task 4: Extreme Rainfall and Physical Bounds."""

    def test_maximum_rainfall_record(self, audit_results: dict):
        """Verifies peak 448.24 mm/day on 2023-07-07 at (17.875N, 73.125E)."""
        ext = audit_results["task_4_extremes"]
        assert np.isclose(ext["max_rainfall_mm"], 448.24377, atol=1e-3)
        assert ext["max_date"] == "2023-07-07"
        assert np.isclose(ext["max_latitude"], 17.875, atol=1e-3)
        assert np.isclose(ext["max_longitude"], 73.125, atol=1e-3)
        assert ext["values_strictly_match"] is True

    def test_physical_plausibility(self, masked_ds: xr.Dataset):
        """Verifies rainfall values are non-negative and finite on land."""
        rf_masked = masked_ds["rainfall_masked"].values
        # All non-NaN values must be >= 0.0 mm
        valid_vals = rf_masked[~np.isnan(rf_masked)]
        assert np.all(valid_vals >= 0.0)
        assert np.all(np.isfinite(valid_vals))


class TestTask5BenchmarkLocations:
    """Test suite for Task 5: 9 Benchmark District Headquarters."""

    def test_all_benchmarks_present(self, audit_results: dict):
        """Verifies all 9 benchmark locations were audited."""
        benchmarks = audit_results["task_5_benchmarks"]
        assert len(benchmarks) == 9
        names = {b["benchmark_name"] for b in benchmarks}
        expected_names = {
            "Ratnagiri",
            "Thane",
            "Kolhapur",
            "Pune",
            "Solapur",
            "Chhatrapati Sambhaji Nagar",
            "Latur",
            "Akola",
            "Nagpur",
        }
        assert names == expected_names

    def test_grid_distances_under_20km(self, audit_results: dict):
        """Verifies nearest grid node is within 20 km for all headquarters."""
        for b in audit_results["task_5_benchmarks"]:
            dist = b["distance_to_grid_km"]
            assert dist < 20.0, f"Distance too large for {b['benchmark_name']}: {dist} km"

    def test_thane_boundary_proximity_documented(self, audit_results: dict):
        """Verifies Thane's nearest node falls in Mumbai Suburban due to border proximity."""
        thane = next(
            b
            for b in audit_results["task_5_benchmarks"]
            if b["benchmark_name"] == "Thane"
        )
        assert thane["grid_node_inside_target_district"] is False
        assert thane["actual_containing_district"].lower() == "mumbai suburban"
        # Confirm that district average differs significantly from coastal node
        assert thane["district_avg_annual_mm"] < thane["node_annual_rainfall_mm"]


class TestTask6StatisticalAggregations:
    """Test suite for Task 6: Statistical Re-aggregation and Seasonal Ratios."""

    def test_jjas_dominance(self, audit_results: dict):
        """Verifies JJAS monsoon contributes > 80% of annual rainfall."""
        stats = audit_results["task_6_statistics"]
        assert stats["jjas_percentage_mean"] > 80.0
        assert stats["jjas_mean_mm"] < stats["annual_mean_mm"]
        assert stats["valid_land_cells_count"] == 421

    def test_masked_dataset_integrity(self, masked_ds: xr.Dataset):
        """Verifies masked NetCDF contains all variables and consistent coordinates."""
        assert "rainfall" in masked_ds.data_vars
        assert "rainfall_masked" in masked_ds.data_vars
        assert "mask_maharashtra" in masked_ds.data_vars
        assert "is_land" in masked_ds.data_vars

        # mask_maharashtra must have exactly 421 True values
        assert int(np.sum(masked_ds["mask_maharashtra"].values)) == 421
        # is_land must have exactly 874 True values (918 - 44)
        assert int(np.sum(masked_ds["is_land"].values)) == 874
