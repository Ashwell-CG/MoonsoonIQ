"""MonsoonIQ - IMD Historical Rainfall Preprocessing and Consolidation Script.

This script processes all 23 annual IMD binary gridded files (2001–2023):
1. Verifies the presence, completeness, and byte size of every year (including 5 leap years).
2. Parses binary IEEE 754 float32 arrays into daily slices.
3. Crops the national grid (129 x 135) to the Maharashtra regional bounding box (28 x 35).
4. Converts missing value flags (-999.0) to standard IEEE NaNs.
5. Applies the authoritative Maharashtra administrative polygon mask (Census 2011 / LGD).
6. Combines all years into a single continuous daily time series (2001–2023, 8,400 days).
7. Validates temporal continuity, asserts zero date gaps/duplicates, and validates physical bounds.
8. Persists the consolidated dataset to data/processed/maharashtra_imd_daily_2001_2023.nc.
"""

from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional
import json
import logging
import time
import numpy as np
import pandas as pd
import xarray as xr
from shapely.geometry import shape, Point

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("MonsoonIQ.Preprocessing")

# Base Paths
BASE_DIR: Path = Path(__file__).resolve().parent.parent
RAW_IMD_DIR: Path = BASE_DIR / "data" / "raw" / "imd"
PROCESSED_DIR: Path = BASE_DIR / "data" / "processed"
GEO_DIR: Path = BASE_DIR / "data" / "geo"

# IMD National Grid Specs
N_LAT: int = 129
N_LON: int = 135
BYTES_PER_CELL: int = 4
GRID_CELLS_PER_DAY: int = N_LAT * N_LON  # 17,415
MISSING_FLAG: float = -999.0

# Maharashtra Bounding Box: Lat 15.5 to 22.25, Lon 72.5 to 81.0
LAT_START_IDX: int = int((15.5 - 6.5) / 0.25)  # 36
LAT_END_IDX: int = int((22.25 - 6.5) / 0.25) + 1  # 64 (28 points)
LON_START_IDX: int = int((72.5 - 66.5) / 0.25)  # 24
LON_END_IDX: int = int((81.0 - 66.5) / 0.25) + 1  # 59 (35 points)

BOX_N_LAT: int = LAT_END_IDX - LAT_START_IDX  # 28
BOX_N_LON: int = LON_END_IDX - LON_START_IDX  # 35

START_YEAR: int = 2001
END_YEAR: int = 2023
LEAP_YEARS = {2004, 2008, 2012, 2016, 2020}


def is_leap_year(year: int) -> bool:
    """Checks whether a given calendar year is a leap year."""
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


def get_expected_size(year: int) -> int:
    """Returns expected file size in bytes for a given year."""
    days = 366 if is_leap_year(year) else 365
    return days * GRID_CELLS_PER_DAY * BYTES_PER_CELL


def load_authoritative_mask(
    state_geo_path: Path,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Loads authoritative Maharashtra polygon and computes 28x35 boolean mask.

    Args:
        state_geo_path: Path to Maharashtra state GeoJSON.

    Returns:
        Tuple of (mask_mh, lats_box, lons_box).
    """
    with open(state_geo_path, "r", encoding="utf-8") as f:
        geo = json.load(f)
    feature = geo["features"][0] if "features" in geo else geo
    poly = shape(feature["geometry"])

    lats = np.linspace(15.5, 22.25, BOX_N_LAT, dtype=np.float32)
    lons = np.linspace(72.5, 81.0, BOX_N_LON, dtype=np.float32)

    mask_mh = np.zeros((BOX_N_LAT, BOX_N_LON), dtype=bool)
    for i, lat_v in enumerate(lats):
        for j, lon_v in enumerate(lons):
            mask_mh[i, j] = poly.contains(Point(lon_v, lat_v))

    return mask_mh, lats, lons


def preprocess_all_years(
    raw_dir: Path,
    output_nc_path: Path,
    state_geo_path: Path,
) -> Dict[str, Any]:
    """Ingests, cleans, concatenates, and masks all 23 years of IMD daily rainfall.

    Args:
        raw_dir: Directory containing raw IMD .grd files.
        output_nc_path: Path for output consolidated NetCDF file.
        state_geo_path: Path to authoritative Maharashtra GeoJSON.

    Returns:
        Dictionary of comprehensive preprocessing and validation metrics.
    """
    logger.info("Starting historical IMD preprocessing for 2001–2023...")
    t0 = time.time()

    mask_mh, lats_box, lons_box = load_authoritative_mask(state_geo_path)
    mh_land_cells_count = int(np.sum(mask_mh))
    logger.info("Loaded authoritative mask: %d valid Maharashtra land cells", mh_land_cells_count)

    years = list(range(START_YEAR, END_YEAR + 1))
    total_expected_days = sum(366 if is_leap_year(y) else 365 for y in years)

    # Pre-allocate full 3D array: (total_days, 28, 35) float32
    consolidated_array = np.empty((total_expected_days, BOX_N_LAT, BOX_N_LON), dtype=np.float32)

    all_dates: List[pd.Timestamp] = []
    yearly_metadata: List[Dict[str, Any]] = []

    day_offset = 0

    for year in years:
        file_path = raw_dir / f"ind{year}_rfp25.grd"
        if not file_path.exists():
            raise FileNotFoundError(f"Missing raw IMD file for year {year}: {file_path}")

        days_in_year = 366 if is_leap_year(year) else 365
        expected_bytes = get_expected_size(year)
        actual_bytes = file_path.stat().st_size

        if actual_bytes != expected_bytes:
            raise ValueError(
                f"Byte size mismatch for {year}: expected {expected_bytes}, got {actual_bytes}"
            )

        # Read binary array
        raw_data = np.fromfile(file_path, dtype="<f4")
        if raw_data.size != days_in_year * GRID_CELLS_PER_DAY:
            raise ValueError(f"Array size mismatch for {year}: {raw_data.size} elements")

        grid_3d = raw_data.reshape((days_in_year, N_LAT, N_LON))

        # Crop to Maharashtra bounding box
        mh_box = grid_3d[:, LAT_START_IDX:LAT_END_IDX, LON_START_IDX:LON_END_IDX]

        # Convert -999.0 to NaN
        mh_box_clean = np.where(np.isclose(mh_box, MISSING_FLAG, atol=1e-2), np.nan, mh_box)

        # Check for invalid negative values
        valid_land_vals = mh_box_clean[~np.isnan(mh_box_clean)]
        min_val = float(np.min(valid_land_vals)) if len(valid_land_vals) > 0 else 0.0
        max_val = float(np.max(valid_land_vals)) if len(valid_land_vals) > 0 else 0.0

        if min_val < 0.0:
            raise ValueError(f"Invalid negative rainfall found in year {year}: {min_val} mm")

        # Assign into consolidated array
        consolidated_array[day_offset : day_offset + days_in_year, :, :] = mh_box_clean

        year_dates = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
        all_dates.extend(year_dates)

        yearly_metadata.append(
            {
                "year": year,
                "days": days_in_year,
                "is_leap": is_leap_year(year),
                "byte_size": actual_bytes,
                "min_rain_mm": min_val,
                "max_rain_mm": max_val,
                "start_index": day_offset,
                "end_index": day_offset + days_in_year - 1,
            }
        )
        day_offset += days_in_year

    logger.info("Successfully ingested %d days across %d years.", day_offset, len(years))

    # Temporal validation
    date_series = pd.DatetimeIndex(all_dates)
    expected_range = pd.date_range(f"{START_YEAR}-01-01", f"{END_YEAR}-12-31", freq="D")

    # Assert exact continuity
    has_duplicates = bool(date_series.has_duplicates)
    is_exact_match = bool(len(date_series) == len(expected_range) and (date_series == expected_range).all())

    if has_duplicates or not is_exact_match:
        raise ValueError("Temporal continuity validation failed! Dates contain gaps or duplicates.")

    # Spatial mask application
    # Compute is_land: True where cell is not NaN all 8,400 days
    is_land = np.any(~np.isnan(consolidated_array), axis=0)  # (28, 35)
    sea_cells_count = int(np.sum(~is_land))
    terrestrial_out_cells_count = int(np.sum(is_land & ~mask_mh))

    logger.info(
        "Spatial grid partition: Total=980 cells | Sea=%d, Terrestrial non-MH=%d, True MH Land=%d",
        sea_cells_count,
        terrestrial_out_cells_count,
        mh_land_cells_count,
    )

    # Create masked rainfall array: NaN outside Maharashtra land
    rainfall_masked = consolidated_array.copy()
    rainfall_masked[:, ~mask_mh] = np.nan

    # Statistics across Maharashtra land cells
    mh_land_slice = consolidated_array[:, mask_mh]  # (8400, 419)
    mh_missing_on_land = int(np.sum(np.isnan(mh_land_slice)))
    total_land_observations = mh_land_slice.size  # 8400 * 419 = 3,519,600

    min_land_rain = float(np.nanmin(mh_land_slice))
    max_land_rain = float(np.nanmax(mh_land_slice))
    mean_land_rain = float(np.round(np.nanmean(mh_land_slice), 2))

    # Identify multi-decadal record peak in Maharashtra
    peak_idx = np.unravel_index(np.nanargmax(rainfall_masked), rainfall_masked.shape)
    peak_val = float(rainfall_masked[peak_idx])
    peak_date = str(date_series[peak_idx[0]])[:10]
    peak_lat = float(lats_box[peak_idx[1]])
    peak_lon = float(lons_box[peak_idx[2]])

    logger.info(
        "Maharashtra 23-Year Climatology: Min=%.2f mm, Mean=%.2f mm, Peak=%.2f mm on %s at (%.2fN, %.2fE)",
        min_land_rain,
        mean_land_rain,
        peak_val,
        peak_date,
        peak_lat,
        peak_lon,
    )

    # Build Xarray Dataset
    ds = xr.Dataset(
        data_vars={
            "rainfall": (
                ("time", "lat", "lon"),
                consolidated_array,
                {
                    "units": "mm/day",
                    "long_name": "daily gridded precipitation (bounding box)",
                    "source": "India Meteorological Department (IMD) 0.25 degree daily gridded rainfall",
                    "missing_value": "NaN (converted from -999.0)",
                },
            ),
            "rainfall_masked": (
                ("time", "lat", "lon"),
                rainfall_masked,
                {
                    "units": "mm/day",
                    "long_name": "daily gridded precipitation masked to Maharashtra land boundary",
                    "valid_cells": mh_land_cells_count,
                    "source": "IMD Pune 0.25 degree with Census 2011 / LGD boundary mask",
                },
            ),
            "mask_maharashtra": (
                ("lat", "lon"),
                mask_mh.astype(bool),
                {
                    "description": "Authoritative Maharashtra land mask (Census 2011/LGD)",
                    "count_true": mh_land_cells_count,
                },
            ),
            "is_land": (
                ("lat", "lon"),
                is_land.astype(bool),
                {
                    "description": "Terrestrial land mask (excludes Arabian Sea)",
                    "count_true": int(np.sum(is_land)),
                },
            ),
        },
        coords={
            "time": date_series,
            "lat": lats_box,
            "lon": lons_box,
        },
        attrs={
            "title": "MonsoonIQ - Maharashtra Daily Gridded Rainfall (2001–2023)",
            "product": "IMD 0.25° Gridded Daily Rainfall (Consolidated & Masked)",
            "spatial_resolution": "0.25 degree x 0.25 degree",
            "temporal_resolution": "daily (24-hour accumulation: 08:30 IST to 08:30 IST)",
            "geographic_bounds": "Lat 15.50N to 22.25N, Lon 72.50E to 81.00E",
            "study_period": "2001-01-01 to 2023-12-31",
            "total_days": total_expected_days,
            "total_years": len(years),
            "valid_maharashtra_cells": mh_land_cells_count,
            "conventions": "CF-1.8",
            "institution": "MonsoonIQ Research Pipeline (Primary IMD Data Archive)",
            "citation": "Pai et al. (2014) / Rajeevan et al. (2006)",
        },
    )

    # Save to NetCDF
    output_nc_path.parent.mkdir(parents=True, exist_ok=True)
    encoding = {
        "rainfall": {"zlib": True, "complevel": 4},
        "rainfall_masked": {"zlib": True, "complevel": 4},
        "mask_maharashtra": {"zlib": True, "complevel": 4},
        "is_land": {"zlib": True, "complevel": 4},
    }
    logger.info("Saving consolidated NetCDF to %s...", output_nc_path)
    ds.to_netcdf(output_nc_path, encoding=encoding)
    nc_size_bytes = output_nc_path.stat().st_size
    nc_size_mb = float(np.round(nc_size_bytes / (1024 * 1024), 2))
    logger.info("Saved NetCDF successfully: %d bytes (%.2f MB)", nc_size_bytes, nc_size_mb)

    elapsed_sec = float(np.round(time.time() - t0, 2))

    summary = {
        "dataset_name": "maharashtra_imd_daily_2001_2023.nc",
        "output_path": str(output_nc_path),
        "file_size_bytes": nc_size_bytes,
        "file_size_mb": nc_size_mb,
        "total_years": len(years),
        "start_year": START_YEAR,
        "end_year": END_YEAR,
        "total_days": total_expected_days,
        "start_date": "2001-01-01",
        "end_date": "2023-12-31",
        "has_duplicates": has_duplicates,
        "temporal_continuity_passed": is_exact_match,
        "spatial_grid": {
            "n_lat": BOX_N_LAT,
            "n_lon": BOX_N_LON,
            "total_grid_cells": BOX_N_LAT * BOX_N_LON,
            "sea_cells": sea_cells_count,
            "terrestrial_out_cells": terrestrial_out_cells_count,
            "valid_maharashtra_land_cells": mh_land_cells_count,
        },
        "missing_values": {
            "sea_nan_count": sea_cells_count * total_expected_days,
            "maharashtra_land_nan_count": mh_missing_on_land,
            "total_land_observations": total_land_observations,
            "missing_percentage_on_land": float(
                np.round((mh_missing_on_land / total_land_observations) * 100.0, 4)
            ),
        },
        "rainfall_statistics": {
            "min_mm": min_land_rain,
            "max_mm": max_land_rain,
            "mean_daily_mm": mean_land_rain,
            "peak_event": {
                "rainfall_mm": peak_val,
                "date": peak_date,
                "lat": peak_lat,
                "lon": peak_lon,
            },
        },
        "processing_time_seconds": elapsed_sec,
        "status": "PASS",
    }

    # Save summary JSON
    summary_path = PROCESSED_DIR / "preprocessing_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    logger.info("Saved preprocessing summary to %s", summary_path)

    return summary


if __name__ == "__main__":
    raw_dir = RAW_IMD_DIR
    out_nc = PROCESSED_DIR / "maharashtra_imd_daily_2001_2023.nc"
    geo_path = GEO_DIR / "maharashtra_state.geojson"

    summary = preprocess_all_years(raw_dir, out_nc, geo_path)
    print("\n=== MonsoonIQ Phase 3 Preprocessing Summary ===")
    print(f"File: {summary['dataset_name']} ({summary['file_size_mb']} MB)")
    print(f"Total Years: {summary['total_years']} ({summary['start_year']}–{summary['end_year']})")
    print(f"Total Days: {summary['total_days']} ({summary['start_date']} to {summary['end_date']})")
    print(f"Grid Dimensions: {summary['spatial_grid']['n_lat']} lats x {summary['spatial_grid']['n_lon']} lons (Total {summary['spatial_grid']['total_grid_cells']} cells)")
    print(f"Valid Maharashtra Land Cells: {summary['spatial_grid']['valid_maharashtra_land_cells']}")
    print(f"Sea Cells: {summary['spatial_grid']['sea_cells']} ({summary['missing_values']['sea_nan_count']} NaNs)")
    print(f"Missing Values on Land: {summary['missing_values']['maharashtra_land_nan_count']} ({summary['missing_values']['missing_percentage_on_land']}%)")
    print(f"Peak Event: {summary['rainfall_statistics']['peak_event']['rainfall_mm']} mm on {summary['rainfall_statistics']['peak_event']['date']} at ({summary['rainfall_statistics']['peak_event']['lat']}N, {summary['rainfall_statistics']['peak_event']['lon']}E)")
