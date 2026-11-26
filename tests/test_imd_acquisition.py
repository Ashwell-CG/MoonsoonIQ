"""MonsoonIQ - Automated Test Suite for Phase 2 IMD Acquisition.

This test suite verifies:
1. IMD 2023 binary raw file existence and exact byte size (25,425,900 bytes).
2. Decoding into 365 daily grids of (129 lat x 135 lon) single-precision floats.
3. Coordinate ranges (lat: 6.5 to 38.5, lon: 66.5 to 100.0, step: 0.25).
4. Missing value conventions (-999.0 flag) and physical non-negativity (>= 0 mm).
5. Maharashtra administrative boundary clipping and masking (419 valid land cells).
6. 9 benchmark district mappings and distances.
7. Climatological aggregation consistency (annual mean ~1060.6 mm, JJAS ~932.6 mm).
"""

from pathlib import Path
import json
import numpy as np
import pandas as pd
import pytest
import xarray as xr

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_GRD_PATH = BASE_DIR / "data" / "raw" / "imd" / "ind2023_rfp25.grd"
INTERIM_NC_PATH = BASE_DIR / "data" / "interim" / "maharashtra_imd_2023_masked.nc"
REPORT_JSON_PATH = BASE_DIR / "data" / "interim" / "imd_2023_validation_report.json"


@pytest.fixture(scope="module")
def validation_report() -> dict:
    """Fixture providing the JSON validation report."""
    assert REPORT_JSON_PATH.exists(), f"Validation report not found at {REPORT_JSON_PATH}"
    with open(REPORT_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def masked_imd_ds() -> xr.Dataset:
    """Fixture providing the masked IMD 2023 NetCDF dataset."""
    assert INTERIM_NC_PATH.exists(), f"Masked NetCDF not found at {INTERIM_NC_PATH}"
    return xr.open_dataset(INTERIM_NC_PATH)


class TestIMDRawFile:
    """Tests for raw IMD file integrity and binary layout."""

    def test_file_existence_and_exact_size(self):
        """Verifies file exists and matches exact 25,425,900 byte size."""
        assert RAW_GRD_PATH.exists()
        file_size = RAW_GRD_PATH.stat().st_size
        assert file_size == 25425900, f"Expected 25425900 bytes, got {file_size}"

    def test_binary_layout_and_shape(self):
        """Verifies binary data can be read as 365 x 129 x 135 float32 array."""
        raw_arr = np.fromfile(RAW_GRD_PATH, dtype="<f4")
        assert raw_arr.size == 365 * 129 * 135
        reshaped = raw_arr.reshape((365, 129, 135))
        assert reshaped.shape == (365, 129, 135)


class TestIMDCoordinatesAndBounds:
    """Tests for coordinate ranges, missing flags, and physical bounds."""

    def test_coordinates_and_grid(self, validation_report: dict):
        """Verifies national spatial bounds and 0.25-degree resolution."""
        grid = validation_report["national_validation"]["spatial_grid"]
        assert grid["lat_points"] == 129
        assert grid["lon_points"] == 135
        assert np.isclose(grid["lat_min"], 6.5, atol=1e-3)
        assert np.isclose(grid["lat_max"], 38.5, atol=1e-3)
        assert np.isclose(grid["lon_min"], 66.5, atol=1e-3)
        assert np.isclose(grid["lon_max"], 100.0, atol=1e-3)

    def test_missing_values_and_non_negativity(self, validation_report: dict):
        """Verifies -999.0 missing convention and non-negative rainfall."""
        nat = validation_report["national_validation"]
        assert nat["missing_flag"] == -999.0
        assert nat["is_non_negative"] is True
        assert nat["national_min_rain_mm"] >= 0.0
        assert nat["national_max_rain_mm"] > 500.0  # Dec 18 Tamil Nadu extreme ~689 mm


class TestIMDMaharashtraMasking:
    """Tests for Maharashtra administrative masking and land cells."""

    def test_maharashtra_cells_partition(self, validation_report: dict):
        """Verifies 980 total bounding box cells = 50 sea + 511 out + 419 MH."""
        mh = validation_report["maharashtra_validation"]
        assert mh["total_bounding_box_cells"] == 980
        assert mh["box_lat_points"] == 28
        assert mh["box_lon_points"] == 35
        assert mh["sea_cells_count"] == 50
        assert mh["terrestrial_outside_mh_cells"] == 511
        assert mh["true_maharashtra_land_cells"] == 419

    def test_masked_netcdf_variables(self, masked_imd_ds: xr.Dataset):
        """Verifies variables in interim NetCDF."""
        assert "rainfall" in masked_imd_ds.data_vars
        assert "rainfall_masked" in masked_imd_ds.data_vars
        assert "mask_maharashtra" in masked_imd_ds.data_vars
        assert "is_land" in masked_imd_ds.data_vars
        assert int(np.sum(masked_imd_ds["mask_maharashtra"].values)) == 419


class TestIMDClimatologyAndBenchmarks:
    """Tests for Maharashtra rainfall climatology and benchmark stations."""

    def test_maharashtra_annual_and_jjas_totals(self, validation_report: dict):
        """Verifies statewide annual mean ~1060 mm and JJAS contribution > 80%."""
        mh = validation_report["maharashtra_validation"]
        assert 1000.0 < mh["state_annual_mean_mm"] < 1150.0
        assert 880.0 < mh["state_jjas_mean_mm"] < 1000.0
        assert mh["state_jjas_percentage"] > 80.0

    def test_all_benchmarks_mapped(self, validation_report: dict):
        """Verifies all 9 benchmark districts are resolved within 16 km."""
        benchmarks = validation_report["maharashtra_validation"]["benchmarks"]
        assert len(benchmarks) == 9
        for b in benchmarks:
            assert b["distance_km"] < 16.0, f"Distance too large for {b['benchmark_name']}"

    def test_thane_inside_district_in_imd(self, validation_report: dict):
        """Verifies that in IMD's grid, Thane's nearest node is inside Thane district."""
        benchmarks = validation_report["maharashtra_validation"]["benchmarks"]
        thane = next(b for b in benchmarks if b["benchmark_name"] == "Thane")
        assert thane["grid_node_inside_target_district"] is True
        assert thane["actual_containing_district"].lower() == "thane"
