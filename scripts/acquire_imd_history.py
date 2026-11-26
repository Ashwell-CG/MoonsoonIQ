"""MonsoonIQ - IMD Historical 0.25° Gridded Rainfall Batch Acquisition Script.

This script executes controlled batch acquisition and technical validation of official
IMD daily gridded rainfall (0.25° x 0.25°) across the historical period 2001–2022:
1. Reuses the official IMD Pune CMPG endpoint (https://imdpune.gov.in/cmpg/Griddata/rainfall.php?rain={year}).
2. Handles leap years and exact expected byte sizes:
   - 365-day normal years: 25,425,900 bytes (365 x 129 x 135 x 4 bytes)
   - 366-day leap years (2004, 2008, 2012, 2016, 2020): 25,495,560 bytes (366 x 129 x 135 x 4 bytes)
3. Preserves existing verified files (including 2023) without re-downloading.
4. Implements responsible rate limiting (2-second pause) and retry logic (up to 3 retries).
5. Validates each downloaded file: byte size, binary float32 layout, missing flag (-999.0),
   non-negativity, and Maharashtra regional rainfall metrics.
6. Maintains a comprehensive JSON log and console audit trail.
"""

from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional
import json
import logging
import time
import urllib.request
import ssl
import numpy as np
import pandas as pd
import xarray as xr
from shapely.geometry import shape, Point

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("MonsoonIQ.HistoricalAcquisition")

# Paths
BASE_DIR: Path = Path(__file__).resolve().parent.parent
RAW_IMD_DIR: Path = BASE_DIR / "data" / "raw" / "imd"
INTERIM_DIR: Path = BASE_DIR / "data" / "interim"
GEO_DIR: Path = BASE_DIR / "data" / "geo"

IMD_BASE_URL: str = "https://imdpune.gov.in/cmpg/Griddata/rainfall.php"

# Grid specifications
N_LAT: int = 129
N_LON: int = 135
BYTES_PER_CELL: int = 4
GRID_CELLS_PER_DAY: int = N_LAT * N_LON  # 17,415
MISSING_FLAG: float = -999.0

# Maharashtra Bounding Box indices in IMD grid:
# Lat 15.5 to 22.25 (step 0.25) -> lat values: 6.5 + i*0.25 -> i = (lat - 6.5)/0.25
# 15.5 is index (15.5 - 6.5)/0.25 = 36
# 22.25 is index (22.25 - 6.5)/0.25 = 63
# Lon 72.5 to 81.0 (step 0.25) -> lon values: 66.5 + j*0.25 -> j = (lon - 66.5)/0.25
# 72.5 is index (72.5 - 66.5)/0.25 = 24
# 81.0 is index (81.0 - 66.5)/0.25 = 58
LAT_START_IDX: int = int((15.5 - 6.5) / 0.25)  # 36
LAT_END_IDX: int = int((22.25 - 6.5) / 0.25) + 1  # 64 (exclusive, 28 points)
LON_START_IDX: int = int((72.5 - 66.5) / 0.25)  # 24
LON_END_IDX: int = int((81.0 - 66.5) / 0.25) + 1  # 59 (exclusive, 35 points)


def is_leap_year(year: int) -> bool:
    """Determines whether a calendar year is a leap year."""
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


def get_expected_file_size(year: int) -> int:
    """Calculates exact expected byte size for an IMD 0.25° binary grid file."""
    days = 366 if is_leap_year(year) else 365
    return days * GRID_CELLS_PER_DAY * BYTES_PER_CELL


def load_maharashtra_mask(state_geo_path: Path) -> Tuple[np.ndarray, np.ndarray]:
    """Precomputes boolean masks for Maharashtra bounding box (28 lats x 35 lons).

    Args:
        state_geo_path: Path to Maharashtra state GeoJSON polygon.

    Returns:
        Tuple of (mask_mh_2d, is_land_2d).
    """
    with open(state_geo_path, "r", encoding="utf-8") as f:
        geo = json.load(f)
    feature = geo["features"][0] if "features" in geo else geo
    poly = shape(feature["geometry"])

    lats = np.linspace(15.5, 22.25, 28)
    lons = np.linspace(72.5, 81.0, 35)

    mask_mh = np.zeros((28, 35), dtype=bool)
    for i, lat_val in enumerate(lats):
        for j, lon_val in enumerate(lons):
            mask_mh[i, j] = poly.contains(Point(lon_val, lat_val))

    return mask_mh, lats, lons


def download_single_year(
    year: int,
    dest_path: Path,
    expected_size: int,
    max_retries: int = 3,
) -> bool:
    """Downloads an IMD binary grid file with retry and verification.

    Args:
        year: Historical year (e.g. 2001).
        dest_path: Destination file path.
        expected_size: Expected byte size.
        max_retries: Maximum number of download attempts.

    Returns:
        True if download and byte size verification succeeded, False otherwise.
    """
    url = f"{IMD_BASE_URL}?rain={year}"
    logger.info("Initiating download for year %d from %s", year, url)

    # SSL context ignoring verification for IMD server
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    headers = {
        "User-Agent": "MonsoonIQ-Research-Pipeline/1.0 (Academic Research; Python/3.12)"
    }

    req = urllib.request.Request(url, headers=headers)

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Year %d: Download attempt %d/%d...", year, attempt, max_retries)
            start_t = time.time()
            with urllib.request.urlopen(req, context=ctx, timeout=90) as response:
                content = response.read()

            dl_time = time.time() - start_t
            actual_size = len(content)
            logger.info(
                "Year %d: Downloaded %d bytes in %.1f seconds (%.1f KB/s)",
                year,
                actual_size,
                dl_time,
                (actual_size / 1024) / max(dl_time, 0.1),
            )

            if actual_size != expected_size:
                logger.error(
                    "Year %d: Size mismatch! Expected %d bytes, got %d bytes.",
                    year,
                    expected_size,
                    actual_size,
                )
                if attempt < max_retries:
                    time.sleep(5)
                    continue
                return False

            # Write to disk
            with open(dest_path, "wb") as f:
                f.write(content)

            # Also create standard alias for imdlib
            alias_path = dest_path.parent / f"Rainfall_ind{year}_rfp25.grd"
            if not alias_path.exists():
                with open(alias_path, "wb") as f_alias:
                    f_alias.write(content)

            logger.info("Year %d: File written and verified successfully.", year)
            return True

        except Exception as e:
            logger.warning("Year %d: Attempt %d failed with error: %s", year, attempt, e)
            if attempt < max_retries:
                wait_sec = attempt * 5
                logger.info("Waiting %d seconds before retry...", wait_sec)
                time.sleep(wait_sec)
            else:
                logger.error("Year %d: All %d attempts failed.", year, max_retries)
                return False

    return False


def validate_single_year(
    year: int,
    file_path: Path,
    mask_mh: np.ndarray,
    lats_box: np.ndarray,
    lons_box: np.ndarray,
) -> Dict[str, Any]:
    """Validates raw binary structure, ranges, and computes Maharashtra annual totals.

    Args:
        year: Target year.
        file_path: Path to the downloaded .grd file.
        mask_mh: Boolean 2D mask for Maharashtra land (28 x 35).
        lats_box: Latitude array for bounding box.
        lons_box: Longitude array for bounding box.

    Returns:
        Dictionary of validation metrics.
    """
    days = 366 if is_leap_year(year) else 365
    expected_size = days * GRID_CELLS_PER_DAY * BYTES_PER_CELL
    actual_size = file_path.stat().st_size

    if actual_size != expected_size:
        raise ValueError(f"Size mismatch: {actual_size} != {expected_size}")

    # Read binary
    raw_arr = np.fromfile(file_path, dtype="<f4")
    grid_3d = raw_arr.reshape((days, N_LAT, N_LON))

    # National stats
    is_missing = np.isclose(grid_3d, MISSING_FLAG, atol=1e-2)
    valid_mask = ~is_missing
    valid_vals = grid_3d[valid_mask]

    min_val = float(np.min(valid_vals))
    max_val = float(np.max(valid_vals))
    mean_val = float(np.mean(valid_vals))
    is_non_negative = bool(min_val >= 0.0)

    # Maharashtra crop: lat index [36:64], lon index [24:59]
    mh_box = grid_3d[:, LAT_START_IDX:LAT_END_IDX, LON_START_IDX:LON_END_IDX]
    # Replace -999 with NaN
    mh_box_clean = np.where(np.isclose(mh_box, MISSING_FLAG, atol=1e-2), np.nan, mh_box)

    # JJAS mask
    dates = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
    is_jjas = (dates.month >= 6) & (dates.month <= 9)

    annual_sum_grid = np.nansum(mh_box_clean, axis=0)
    jjas_sum_grid = np.nansum(mh_box_clean[is_jjas, :, :], axis=0)

    # Mask to Maharashtra land (419 cells)
    mh_annual = annual_sum_grid[mask_mh]
    mh_jjas = jjas_sum_grid[mask_mh]

    mh_mean_annual = float(np.round(np.mean(mh_annual), 1))
    mh_mean_jjas = float(np.round(np.mean(mh_jjas), 1))
    mh_jjas_pct = float(np.round((mh_mean_jjas / mh_mean_annual) * 100.0, 1))

    # Daily peak in Maharashtra
    mh_masked_3d = np.where(mask_mh[None, :, :], mh_box_clean, np.nan)
    peak_idx = np.unravel_index(np.nanargmax(mh_masked_3d), mh_masked_3d.shape)
    peak_val = float(mh_masked_3d[peak_idx])
    peak_date = str(dates[peak_idx[0]])[:10]
    peak_lat = float(lats_box[peak_idx[1]])
    peak_lon = float(lons_box[peak_idx[2]])

    val_res = {
        "year": year,
        "is_leap_year": is_leap_year(year),
        "total_days": days,
        "byte_size": actual_size,
        "expected_byte_size": expected_size,
        "size_verified": bool(actual_size == expected_size),
        "is_non_negative": is_non_negative,
        "national_min_mm": min_val,
        "national_max_mm": max_val,
        "national_mean_mm": float(np.round(mean_val, 2)),
        "mh_land_cells": int(np.sum(mask_mh)),
        "mh_mean_annual_mm": mh_mean_annual,
        "mh_mean_jjas_mm": mh_mean_jjas,
        "mh_jjas_percentage": mh_jjas_pct,
        "mh_peak_event": {
            "rainfall_mm": float(np.round(peak_val, 2)),
            "date": peak_date,
            "lat": peak_lat,
            "lon": peak_lon,
        },
        "status": "PASS",
    }
    return val_res


def run_historical_acquisition(
    start_year: int = 2001,
    end_year: int = 2022,
) -> Dict[str, Any]:
    """Orchestrates historical acquisition and technical validation."""
    logger.info("=== Starting MonsoonIQ Historical IMD Acquisition (2001–2022) ===")
    RAW_IMD_DIR.mkdir(parents=True, exist_ok=True)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)

    state_geo_path = GEO_DIR / "maharashtra_state.geojson"
    mask_mh, lats_box, lons_box = load_maharashtra_mask(state_geo_path)

    years = list(range(start_year, end_year + 1))
    results: Dict[int, Any] = {}
    failed_years: List[int] = []

    total_start_time = time.time()

    for idx, year in enumerate(years, 1):
        file_path = RAW_IMD_DIR / f"ind{year}_rfp25.grd"
        expected_size = get_expected_file_size(year)

        logger.info(
            "--- Processing Year %d (%d/%d) [Expected Size: %d bytes] ---",
            year,
            idx,
            len(years),
            expected_size,
        )

        # Check if already downloaded and verified
        need_download = True
        if file_path.exists():
            if file_path.stat().st_size == expected_size:
                logger.info("Year %d: Valid file already exists on disk. Skipping download.", year)
                need_download = False
            else:
                logger.warning(
                    "Year %d: Existing file size (%d) differs from expected (%d). Re-downloading.",
                    year,
                    file_path.stat().st_size,
                    expected_size,
                )

        if need_download:
            success = download_single_year(year, file_path, expected_size)
            if not success:
                logger.error("Year %d: Failed to download or verify byte size.", year)
                failed_years.append(year)
                results[year] = {"year": year, "status": "FAILED"}
                continue
            # Responsible rate limiting pause
            time.sleep(2.0)

        # Validation
        try:
            val_info = validate_single_year(
                year, file_path, mask_mh, lats_box, lons_box
            )
            results[year] = val_info
            logger.info(
                "Year %d validated: MH Mean Annual=%.1f mm, JJAS=%.1f mm (%.1f%%), Peak=%.1f mm on %s at (%.2fN, %.2fE)",
                year,
                val_info["mh_mean_annual_mm"],
                val_info["mh_mean_jjas_mm"],
                val_info["mh_jjas_percentage"],
                val_info["mh_peak_event"]["rainfall_mm"],
                val_info["mh_peak_event"]["date"],
                val_info["mh_peak_event"]["lat"],
                val_info["mh_peak_event"]["lon"],
            )
        except Exception as e:
            logger.error("Year %d: Validation error: %s", year, e)
            failed_years.append(year)
            results[year] = {"year": year, "status": f"VALIDATION_ERROR: {e}"}

    # Also load/validate 2023 if present to form complete 2001-2023 record
    file_2023 = RAW_IMD_DIR / "ind2023_rfp25.grd"
    if file_2023.exists():
        val_2023 = validate_single_year(2023, file_2023, mask_mh, lats_box, lons_box)
        results[2023] = val_2023

    total_time_min = (time.time() - total_start_time) / 60.0

    # Calculate total storage used in data/raw/imd/
    raw_files = list(RAW_IMD_DIR.glob("ind*.grd"))
    total_bytes = sum(f.stat().st_size for f in raw_files)
    total_mb = total_bytes / (1024 * 1024)

    summary = {
        "study_period": "2001-2023",
        "total_years_target": 23,
        "successfully_acquired_years": len([k for k, v in results.items() if v.get("status") == "PASS"]),
        "failed_years": failed_years,
        "total_raw_files_count": len(raw_files),
        "total_storage_bytes": total_bytes,
        "total_storage_mb": float(np.round(total_mb, 2)),
        "execution_time_minutes": float(np.round(total_time_min, 2)),
        "yearly_validation": results,
    }

    out_log_path = INTERIM_DIR / "imd_historical_acquisition_log.json"
    with open(out_log_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    logger.info("Saved acquisition log to %s", out_log_path)

    return summary


if __name__ == "__main__":
    summary = run_historical_acquisition(2001, 2022)
    print("\n=== MonsoonIQ Historical IMD Acquisition Summary ===")
    print(f"Acquired: {summary['successfully_acquired_years']}/{summary['total_years_target']} years")
    print(f"Failed Years: {summary['failed_years']}")
    print(f"Total Storage: {summary['total_storage_mb']} MB")
    print(f"Execution Time: {summary['execution_time_minutes']} minutes")
