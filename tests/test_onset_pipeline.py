"""MonsoonIQ - Comprehensive Unit Tests for Phase 5B Monsoon Onset Pipeline.

Validates:
1. Leap year temporal conventions and day-of-year mapping.
2. Search boundary dates (May 25 Maritime vs. June 1 Interior).
3. Missing value safeguards (NaN treated as unknown, never as dry).
4. Consecutive dry spell detection (13-day passes, 14-day rejected).
5. Overlapping candidate prevention (stepping past accumulation window).
6. Incomplete verification period safeguards (unverified state).
7. No-detection case handling (drought scenarios).
8. Five physiographic zone parameter mapping and cell distributions.
9. Processed NetCDF schema, coordinates, dimensions, and data completeness.
10. Official IMD benchmark validation (Mumbai N=23 MAE < 6d, Pune N=5 MAE < 11d).
"""

from pathlib import Path
from typing import Dict, Any
import sys
import json
import numpy as np
import pandas as pd
import pytest
import xarray as xr

BASE_DIR: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from scripts.detect_monsoon_onset import (
    detect_cell_year_onset,
    ZONE_CONFIGS,
    WET_DAY_THRESHOLD,
    VERIFICATION_WINDOW_DAYS,
    MAX_DRY_SPELL_BREAK_DAYS,
)

ONSET_NC_PATH: Path = BASE_DIR / "data" / "processed" / "maharashtra_onset_2001_2023.nc"
METRICS_JSON_PATH: Path = BASE_DIR / "outputs" / "onset" / "onset_summary_metrics.json"
REJECTED_LOG_PATH: Path = BASE_DIR / "outputs" / "onset" / "rejected_candidates_log.json"


@pytest.fixture(scope="module")
def onset_dataset() -> xr.Dataset:
    """Loads the processed onset NetCDF dataset."""
    assert ONSET_NC_PATH.exists(), f"Processed onset NetCDF missing: {ONSET_NC_PATH}"
    ds = xr.open_dataset(ONSET_NC_PATH)
    yield ds
    ds.close()


@pytest.fixture(scope="module")
def summary_metrics() -> Dict[str, Any]:
    """Loads the summary metrics JSON."""
    assert METRICS_JSON_PATH.exists(), f"Missing metrics file: {METRICS_JSON_PATH}"
    with open(METRICS_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Leap Year & Date Boundary Tests
# ---------------------------------------------------------------------------

def test_leap_year_handling() -> None:
    """Verifies day-of-year calculations handle leap years and non-leap years correctly."""
    # 2020 is a leap year (366 days), 2021 is a common year (365 days)
    dates_2020 = pd.date_range("2020-01-01", "2020-12-31", freq="D")
    dates_2021 = pd.date_range("2021-01-01", "2021-12-31", freq="D")

    assert len(dates_2020) == 366
    assert len(dates_2021) == 365

    # June 1 in leap year is DOY 153; in common year is DOY 152
    doy_jun1_2020 = pd.Timestamp("2020-06-01").day_of_year
    doy_jun1_2021 = pd.Timestamp("2021-06-01").day_of_year
    assert doy_jun1_2020 == 153
    assert doy_jun1_2021 == 152


def test_date_boundary_filtering() -> None:
    """Verifies that pre-monsoon convective rain prior to t_start is strictly ignored."""
    dates_2023 = pd.date_range("2023-01-01", "2023-12-31", freq="D")
    rain_series = np.zeros(365, dtype=np.float32)

    # Place a heavy storm (50 mm across May 15-18) before any search start
    idx_may15 = int(np.where(dates_2023 == pd.Timestamp("2023-05-15"))[0][0])
    rain_series[idx_may15 : idx_may15 + 4] = 20.0  # 80 mm total

    # Place a post-start rain surge on June 10 (30 mm over 5 days) followed by sustained rain
    idx_jun10 = int(np.where(dates_2023 == pd.Timestamp("2023-06-10"))[0][0])
    rain_series[idx_jun10 : idx_jun10 + 5] = 10.0  # 50 mm
    rain_series[idx_jun10 + 5 : idx_jun10 + 25] = 5.0  # wet verification

    # Test Maritime Zone (start May 25): May 15 storm MUST be ignored
    res_maritime = detect_cell_year_onset(
        daily_rain=rain_series,
        dates_series=dates_2023,
        zone_name="Konkan",
        year=2023,
        lat=19.25,
        lon=73.00,
        district_name="Thane",
    )
    assert res_maritime["confirmed_date"] == "2023-06-10"

    # Test Interior Zone (start June 1): Rain on May 28 (30 mm) MUST also be ignored
    idx_may28 = int(np.where(dates_2023 == pd.Timestamp("2023-05-28"))[0][0])
    rain_series[idx_may28 : idx_may28 + 3] = 15.0  # 45 mm
    res_interior = detect_cell_year_onset(
        daily_rain=rain_series,
        dates_series=dates_2023,
        zone_name="Madhya Maharashtra",
        year=2023,
        lat=18.50,
        lon=73.75,
        district_name="Pune",
    )
    assert res_interior["confirmed_date"] == "2023-06-10"


# ---------------------------------------------------------------------------
# 2. Missing Value & Dry Spell Safeguards
# ---------------------------------------------------------------------------

def test_missing_value_treated_as_unknown() -> None:
    """Verifies that missing rainfall (NaN) is never automatically treated as dry."""
    dates_2023 = pd.date_range("2023-01-01", "2023-12-31", freq="D")
    rain_series = np.zeros(365, dtype=np.float32)

    # Candidate starts on June 5 with 30 mm over 5 days (Interior zone)
    idx_cand = int(np.where(dates_2023 == pd.Timestamp("2023-06-05"))[0][0])
    rain_series[idx_cand : idx_cand + 5] = 8.0  # 40 mm

    # In verification window (June 10 to June 29):
    # Days 0-9: Dry (10 dry days)
    # Days 10-14: Missing (NaN) -> 5 days
    # Days 15-19: Dry (5 dry days)
    # If NaN were treated as dry, total dry spell would be 10 + 5 + 5 = 20 days (rejected).
    # Since NaN is unknown, max consecutive dry streak is only 10 days!
    verif_start = idx_cand + 5
    rain_series[verif_start : verif_start + 10] = 0.0
    rain_series[verif_start + 10 : verif_start + 15] = np.nan
    rain_series[verif_start + 15 : verif_start + 20] = 0.0

    res = detect_cell_year_onset(
        daily_rain=rain_series,
        dates_series=dates_2023,
        zone_name="Madhya Maharashtra",
        year=2023,
        lat=18.50,
        lon=73.75,
        district_name="Pune",
    )

    # Max dry streak must NOT exceed 10 days (cannot bridge across NaNs)
    assert res["max_post_candidate_dry_spell"] == 10
    # Because 5 days were missing, verification completeness is 15/20 = 0.75
    # The candidate cannot be confirmed because verification is incomplete!
    assert res["verification_completeness"] < 1.0


def test_dry_spell_rejection_boundary() -> None:
    """Verifies that 13 consecutive dry days passes, while 14 consecutive dry days triggers rejection."""
    dates = pd.date_range("2023-01-01", "2023-12-31", freq="D")
    rain_13d = np.zeros(365, dtype=np.float32)
    rain_14d = np.zeros(365, dtype=np.float32)

    idx_start = int(np.where(dates == pd.Timestamp("2023-06-05"))[0][0])
    # Accumulation: 30 mm
    rain_13d[idx_start : idx_start + 5] = 6.0
    rain_14d[idx_start : idx_start + 5] = 6.0

    # 13 consecutive dry days, then rain on day 14
    verif = idx_start + 5
    rain_13d[verif : verif + 13] = 0.0
    rain_13d[verif + 13] = 10.0  # Rain breaks the streak at 13 days
    rain_13d[verif + 14 : verif + 20] = 0.0

    # 14 consecutive dry days
    rain_14d[verif : verif + 14] = 0.0
    rain_14d[verif + 14] = 10.0
    rain_14d[verif + 15 : verif + 20] = 0.0

    # Follow-up genuine onset on July 10
    idx_jul10 = int(np.where(dates == pd.Timestamp("2023-07-10"))[0][0])
    rain_14d[idx_jul10 : idx_jul10 + 5] = 10.0
    rain_14d[idx_jul10 + 5 : idx_jul10 + 25] = 5.0

    res_13 = detect_cell_year_onset(
        daily_rain=rain_13d, dates_series=dates, zone_name="Vidarbha",
        year=2023, lat=21.0, lon=79.0, district_name="Nagpur"
    )
    res_14 = detect_cell_year_onset(
        daily_rain=rain_14d, dates_series=dates, zone_name="Vidarbha",
        year=2023, lat=21.0, lon=79.0, district_name="Nagpur"
    )

    # 13-day dry spell passes: onset confirmed on June 5
    assert res_13["confirmed_date"] == "2023-06-05"
    assert res_13["rejected_candidate_count"] == 0

    # 14-day dry spell rejected: June 5 rejected, confirmed on July 10
    assert res_14["confirmed_date"] == "2023-07-10"
    assert res_14["rejected_candidate_count"] == 1
    assert res_14["has_rejected_candidate"] == 1


# ---------------------------------------------------------------------------
# 3. Overlapping Candidate Prevention & Incomplete Verification
# ---------------------------------------------------------------------------

def test_overlapping_candidate_prevention() -> None:
    """Verifies that rejecting a candidate does not evaluate overlapping candidate windows."""
    dates = pd.date_range("2023-01-01", "2023-12-31", freq="D")
    rain = np.zeros(365, dtype=np.float32)

    # Multi-day storm on June 5, 6, 7 (20 mm each = 60 mm)
    idx_c = int(np.where(dates == pd.Timestamp("2023-06-05"))[0][0])
    rain[idx_c : idx_c + 3] = 20.0

    # Followed immediately by 15 dry days
    rain[idx_c + 3 : idx_c + 25] = 0.0

    # Second genuine surge on July 15
    idx_jul15 = int(np.where(dates == pd.Timestamp("2023-07-15"))[0][0])
    rain[idx_jul15 : idx_jul15 + 5] = 10.0
    rain[idx_jul15 + 5 : idx_jul15 + 25] = 5.0

    res = detect_cell_year_onset(
        daily_rain=rain, dates_series=dates, zone_name="Marathwada",
        year=2023, lat=19.0, lon=76.0, district_name="Jalna"
    )

    # Candidate 1 was on June 5. June 6 and June 7 MUST NOT be separate rejected candidates.
    assert res["rejected_candidate_count"] == 1
    assert res["confirmed_date"] == "2023-07-15"


def test_incomplete_verification_near_year_end() -> None:
    """Verifies that candidate near end of time series without full 20 days is marked unverified."""
    dates = pd.date_range("2023-01-01", "2023-12-31", freq="D")
    rain = np.zeros(365, dtype=np.float32)

    # First candidate occurs on Dec 20 (only 11 days remain in year)
    idx_dec20 = int(np.where(dates == pd.Timestamp("2023-12-20"))[0][0])
    rain[idx_dec20 : idx_dec20 + 5] = 10.0
    rain[idx_dec20 + 5 :] = 5.0

    res = detect_cell_year_onset(
        daily_rain=rain, dates_series=dates, zone_name="Vidarbha",
        year=2023, lat=21.0, lon=79.0, district_name="Nagpur"
    )

    # Cannot confirm without full 20-day verification
    assert res["confirmed_date"] is None
    assert res["no_detection_flag"] == 1
    assert res["quality_flag"] == -1  # Unverified flag


def test_no_detection_case() -> None:
    """Verifies that completely dry or severe drought years result in no-detection flag = 1."""
    dates = pd.date_range("2023-01-01", "2023-12-31", freq="D")
    rain = np.zeros(365, dtype=np.float32)  # Zero rain all year

    res = detect_cell_year_onset(
        daily_rain=rain, dates_series=dates, zone_name="Madhya Maharashtra",
        year=2023, lat=18.5, lon=73.75, district_name="Pune"
    )

    assert res["confirmed_date"] is None
    assert np.isnan(res["confirmed_doy"])
    assert res["no_detection_flag"] == 1
    assert res["quality_flag"] == 0


# ---------------------------------------------------------------------------
# 4. Regional Classifications & Parameters
# ---------------------------------------------------------------------------

def test_five_zone_configurations() -> None:
    """Verifies that all 5 zones have correctly assigned parameters."""
    assert len(ZONE_CONFIGS) == 5
    for zname in ["Western Ghats", "Konkan"]:
        assert ZONE_CONFIGS[zname]["tier"] == 1
        assert ZONE_CONFIGS[zname]["search_start_month"] == 5
        assert ZONE_CONFIGS[zname]["search_start_day"] == 25
        assert ZONE_CONFIGS[zname]["cumulative_threshold_mm"] == 35.0

    for zname in ["Madhya Maharashtra", "Marathwada", "Vidarbha"]:
        assert ZONE_CONFIGS[zname]["tier"] == 2
        assert ZONE_CONFIGS[zname]["search_start_month"] == 6
        assert ZONE_CONFIGS[zname]["search_start_day"] == 1
        assert ZONE_CONFIGS[zname]["cumulative_threshold_mm"] == 25.0


# ---------------------------------------------------------------------------
# 5. Processed NetCDF Dataset & Benchmark Validation Tests
# ---------------------------------------------------------------------------

def test_netcdf_dataset_integrity(onset_dataset: xr.Dataset) -> None:
    """Verifies dimensions, coordinates, variables, and cell count of processed NetCDF."""
    assert "year" in onset_dataset.dims
    assert "lat" in onset_dataset.dims
    assert "lon" in onset_dataset.dims
    assert len(onset_dataset["year"]) == 23
    assert len(onset_dataset["lat"]) == 28
    assert len(onset_dataset["lon"]) == 35

    # Valid Maharashtra cells
    mask = onset_dataset["mask_maharashtra"].values
    assert int(mask.sum()) == 419

    # Required data variables
    req_vars = [
        "candidate_onset_doy", "confirmed_onset_doy", "candidate_count",
        "rejected_candidate_count", "max_post_candidate_dry_spell",
        "has_rejected_candidate", "verification_completeness",
        "no_detection_flag", "quality_flag", "cyclone_flag", "zone_id",
    ]
    for v in req_vars:
        assert v in onset_dataset.data_vars, f"Missing required variable: {v}"

    # Global attributes
    assert "title" in onset_dataset.attrs
    assert "algorithm_version" in onset_dataset.attrs
    assert "benchmark_coordinate" in onset_dataset.attrs


def test_statewide_onset_completeness(summary_metrics: Dict[str, Any]) -> None:
    """Verifies that full 23-year onset calculation achieves > 99.5% confirmed onsets."""
    res = summary_metrics["overall_results"]
    assert res["confirmed_onsets_count"] >= 9600
    assert res["confirmed_onsets_pct"] > 99.5
    assert res["no_detection_count"] <= 35
    assert res["unverified_count"] == 0


def test_mumbai_benchmark_accuracy(summary_metrics: Dict[str, Any]) -> None:
    """Verifies Mumbai benchmark evaluation achieves MAE < 5.0 days across 23 years."""
    mumbai = summary_metrics["mumbai_benchmark"]
    assert mumbai["evaluation_years"] == 23
    assert mumbai["missing_years"] == 0
    assert mumbai["mae_days"] < 5.0
    assert -4.5 < mumbai["bias_days"] < -2.0


def test_pune_benchmark_accuracy(summary_metrics: Dict[str, Any]) -> None:
    """Verifies Pune benchmark evaluation achieves MAE < 11.0 days across 5 years."""
    pune = summary_metrics["pune_benchmark"]
    assert pune["evaluation_years"] == 5
    assert pune["missing_years"] == 18
    assert pune["mae_days"] < 11.0


def test_regional_progression_order(summary_metrics: Dict[str, Any]) -> None:
    """Verifies regional chronological order: Western Ghats and Konkan precede interior plateau."""
    reg = summary_metrics["regional_metrics"]
    ghats_doy = reg["Western Ghats"]["median_doy"]
    konkan_doy = reg["Konkan"]["median_doy"]
    vidarbha_doy = reg["Vidarbha"]["median_doy"]
    marathwada_doy = reg["Marathwada"]["median_doy"]
    madhya_doy = reg["Madhya Maharashtra"]["median_doy"]

    # Maritime arrives earliest
    assert ghats_doy <= 158.0  # June 7 or earlier
    assert konkan_doy <= 160.0  # June 9 or earlier
    # Interior arrives later
    assert ghats_doy < vidarbha_doy
    assert konkan_doy < vidarbha_doy
    # Rejection break frequency is highest in Madhya Maharashtra
    assert reg["Madhya Maharashtra"]["rejection_frequency_pct"] > reg["Western Ghats"]["rejection_frequency_pct"]
    assert reg["Madhya Maharashtra"]["rejection_frequency_pct"] > 8.0
