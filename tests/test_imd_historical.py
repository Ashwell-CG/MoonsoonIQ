"""MonsoonIQ - Automated Test Suite for Phase 2B Historical IMD Acquisition.

This test suite validates:
1. Complete existence of all 23 historical files (2001–2023) in data/raw/imd/.
2. Exact byte size compliance for all 18 standard years (25,425,900 bytes) and 5 leap years (25,495,560 bytes).
3. Zero missing or failed years in the acquisition log.
4. Physical non-negativity and consistency across all years.
5. Historical meteorological validation (e.g., 2005 Mumbai deluge > 500 mm/day, 2015 drought < 900 mm).
"""

from pathlib import Path
import json
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_IMD_DIR = BASE_DIR / "data" / "raw" / "imd"
LOG_PATH = BASE_DIR / "data" / "interim" / "imd_historical_acquisition_log.json"

LEAP_YEARS = {2004, 2008, 2012, 2016, 2020}
NORMAL_SIZE = 25425900
LEAP_SIZE = 25495560


@pytest.fixture(scope="module")
def acquisition_log() -> dict:
    """Fixture providing the historical acquisition log."""
    assert LOG_PATH.exists(), f"Acquisition log not found at {LOG_PATH}"
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class TestHistoricalFiles:
    """Tests for raw file presence, integrity, and byte sizes."""

    @pytest.mark.parametrize("year", list(range(2001, 2024)))
    def test_file_exists_and_exact_byte_size(self, year: int):
        """Verifies each year's file exists and matches exact expected byte size."""
        file_path = RAW_IMD_DIR / f"ind{year}_rfp25.grd"
        assert file_path.exists(), f"Missing raw file for year {year}"
        expected_size = LEAP_SIZE if year in LEAP_YEARS else NORMAL_SIZE
        actual_size = file_path.stat().st_size
        assert (
            actual_size == expected_size
        ), f"Year {year}: expected {expected_size} bytes, got {actual_size}"


class TestAcquisitionLog:
    """Tests for acquisition log completeness and validation results."""

    def test_all_23_years_passed(self, acquisition_log: dict):
        """Verifies exactly 23 years were acquired with 0 failures."""
        assert acquisition_log["successfully_acquired_years"] == 23
        assert len(acquisition_log["failed_years"]) == 0
        assert acquisition_log["total_storage_mb"] > 550.0

    @pytest.mark.parametrize("year", list(range(2001, 2024)))
    def test_yearly_validation_status_pass(self, acquisition_log: dict, year: int):
        """Verifies each year passed all technical validation checks."""
        yearly_info = acquisition_log["yearly_validation"].get(str(year))
        assert yearly_info is not None, f"Year {year} missing from validation log"
        assert yearly_info["status"] == "PASS"
        assert yearly_info["is_non_negative"] is True
        assert yearly_info["size_verified"] is True
        assert yearly_info["mh_land_cells"] == 419


class TestMeteorologicalClimatology:
    """Tests for physical and meteorological consistency across 2001–2023."""

    def test_monsoon_dominance_all_years(self, acquisition_log: dict):
        """Verifies JJAS monsoon accounts for >= 75% of annual rainfall every year."""
        for yr in range(2001, 2024):
            info = acquisition_log["yearly_validation"][str(yr)]
            jjas_pct = info["mh_jjas_percentage"]
            assert (
                jjas_pct >= 75.0
            ), f"Year {yr} JJAS percentage unexpectedly low: {jjas_pct}%"

    def test_mumbai_2005_extreme_deluge(self, acquisition_log: dict):
        """Verifies the historic July 26-27, 2005 deluge is captured (> 500 mm)."""
        info_2005 = acquisition_log["yearly_validation"]["2005"]
        peak = info_2005["mh_peak_event"]
        assert peak["rainfall_mm"] > 500.0
        assert peak["date"] == "2005-07-27"
        assert peak["lat"] == 19.25
        assert peak["lon"] == 73.00

    def test_drought_and_excess_years_contrast(self, acquisition_log: dict):
        """Verifies drought year 2015 (< 900 mm) vs excess year 2005 (> 1500 mm)."""
        annual_2015 = acquisition_log["yearly_validation"]["2015"]["mh_mean_annual_mm"]
        annual_2005 = acquisition_log["yearly_validation"]["2005"]["mh_mean_annual_mm"]
        assert annual_2015 < 900.0, f"Expected 2015 drought, got {annual_2015} mm"
        assert annual_2005 > 1500.0, f"Expected 2005 excess, got {annual_2005} mm"

