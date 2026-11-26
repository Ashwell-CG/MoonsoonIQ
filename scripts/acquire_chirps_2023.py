"""MonsoonIQ - CHIRPS 2023 Pipeline Validation Script.

This script executes a controlled test acquisition of the CHIRPS 2023 daily
precipitation dataset via the Columbia University IRI Climate Data Library,
saves the immutable raw dataset, ingests and decodes it using Xarray,
performs spatial clipping to Maharashtra, validates all multidimensional
properties, and saves the verified dataset into data/interim/.

NOTE: CHIRPS is used strictly as a pipeline validation and independent
comparison dataset, NOT as a replacement for IMD ground observations.
"""

from pathlib import Path
from typing import Dict, Any, Tuple, List
import argparse
import io
import logging
import time
import urllib.request
import numpy as np
import pandas as pd
import xarray as xr

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("MonsoonIQ.CHIRPS_Validation")

# Regional Bounding Box for Raw Data (Encompassing Maharashtra + surrounding buffer)
RAW_BOUNDS = {
    "lon_min": 71.50,
    "lon_max": 82.00,
    "lat_min": 15.00,
    "lat_max": 22.75,
}

# Maharashtra Analysis Bounding Box (Target Clipping Bounds)
MAHARASHTRA_BOUNDS = {
    "lon_min": 72.50,
    "lon_max": 81.00,
    "lat_min": 15.50,
    "lat_max": 22.25,
}

# 9 Benchmark District Headquarters
BENCHMARK_DISTRICTS: Dict[str, Tuple[float, float, str]] = {
    "Ratnagiri": (16.99, 73.30, "Konkan"),
    "Thane": (19.20, 72.98, "Konkan"),
    "Kolhapur": (16.70, 74.24, "Madhya Maharashtra"),
    "Pune": (18.52, 73.86, "Madhya Maharashtra"),
    "Solapur": (17.66, 75.91, "Madhya Maharashtra"),
    "Chhatrapati Sambhaji Nagar": (19.88, 75.34, "Marathwada"),
    "Latur": (18.40, 76.58, "Marathwada"),
    "Akola": (20.70, 77.01, "Vidarbha"),
    "Nagpur": (21.15, 79.08, "Vidarbha"),
}

# Quarterly Time Windows for Reliable Download Chunking
QUARTERS_2023: List[Tuple[str, str, str]] = [
    ("Q1", "1%20Jan%202023", "31%20Mar%202023"),
    ("Q2", "1%20Apr%202023", "30%20Jun%202023"),
    ("Q3", "1%20Jul%202023", "30%20Sep%202023"),
    ("Q4", "1%20Oct%202023", "31%20Dec%202023"),
]


def download_chirps_quarter(
    label: str,
    t_start: str,
    t_end: str,
    bounds: Dict[str, float],
    raw_dir: Path,
    timeout: int = 45,
) -> Path:
    """Download a quarterly slice of CHIRPS 0.25° NetCDF data from Columbia IRI.

    Args:
        label: Quarter label (e.g. 'Q1').
        t_start: Encoded start date string (e.g. '1%20Jan%202023').
        t_end: Encoded end date string (e.g. '31%20Mar%202023').
        bounds: Dictionary containing lon_min, lon_max, lat_min, lat_max.
        raw_dir: Target directory for saving raw files.
        timeout: Network timeout in seconds.

    Returns:
        Path to the saved raw NetCDF file for this quarter.
    """
    url = (
        "http://iridl.ldeo.columbia.edu/SOURCES/.UCSB/.CHIRPS/.v2p0/"
        ".daily-improved/.global/.0p25/.prcp/"
        f"X/({bounds['lon_min']})/({bounds['lon_max']})/RANGEEDGES/"
        f"Y/({bounds['lat_min']})/({bounds['lat_max']})/RANGEEDGES/"
        f"T/({t_start})/({t_end})/RANGEEDGES/data.nc"
    )

    quarter_path = raw_dir / f"chirps_2023_{label}_raw.nc"
    logger.info("Downloading CHIRPS %s: %s to %s", label, t_start, t_end)
    logger.debug("Request URL: %s", url)

    req = urllib.request.Request(url, headers={"User-Agent": "MonsoonIQ-Research/1.0"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as response:
        content = response.read()

    elapsed = time.time() - t0
    logger.info(
        "Downloaded %s: %d bytes in %.2f seconds (%.2f KB/s)",
        label, len(content), elapsed, (len(content) / 1024) / max(elapsed, 0.01),
    )

    # Validate NetCDF magic bytes
    if not (content[:3] == b"CDF" or content[1:4] == b"HDF"):
        raise ValueError(f"Downloaded file for {label} does not contain valid NetCDF header bytes.")

    quarter_path.write_bytes(content)
    return quarter_path


def find_nearest_grid_point(
    lat_target: float,
    lon_target: float,
    grid_lats: np.ndarray,
    grid_lons: np.ndarray,
) -> Tuple[float, float, float]:
    """Find nearest grid coordinate and Euclidean angular distance.

    Args:
        lat_target: Target latitude in degrees.
        lon_target: Target longitude in degrees.
        grid_lats: Array of grid latitudes.
        grid_lons: Array of grid longitudes.

    Returns:
        Tuple of (nearest_lat, nearest_lon, angular_distance_degrees).
    """
    nearest_lat = float(grid_lats[np.abs(grid_lats - lat_target).argmin()])
    nearest_lon = float(grid_lons[np.abs(grid_lons - lon_target).argmin()])
    dist = float(np.sqrt((nearest_lat - lat_target) ** 2 + (nearest_lon - lon_target) ** 2))
    return nearest_lat, nearest_lon, dist


def acquire_and_validate_chirps_2023(base_dir: Path) -> Dict[str, Any]:
    """Run full CHIRPS 2023 acquisition, spatial clipping, and validation.

    Args:
        base_dir: Project root directory.

    Returns:
        Validation summary dictionary with multidimensional metrics.
    """
    raw_dir = base_dir / "data" / "raw" / "chirps"
    interim_dir = base_dir / "data" / "interim"
    raw_dir.mkdir(parents=True, exist_ok=True)
    interim_dir.mkdir(parents=True, exist_ok=True)

    # 1. Download Quarters
    quarter_files: List[Path] = []
    for label, t_start, t_end in QUARTERS_2023:
        q_path = download_chirps_quarter(label, t_start, t_end, RAW_BOUNDS, raw_dir)
        quarter_files.append(q_path)

    # 2. Ingest and Concatenate Quarters in Xarray
    logger.info("Opening and concatenating quarterly datasets with Xarray...")
    ds_quarters = [xr.open_dataset(p) for p in quarter_files]
    ds_raw = xr.concat(ds_quarters, dim="T")

    # Save consolidated raw regional NetCDF file
    consolidated_raw_path = raw_dir / "chirps_2023_regional_raw.nc"
    ds_raw.to_netcdf(consolidated_raw_path)
    logger.info(
        "Consolidated raw regional NetCDF saved: %s (Size: %.2f KB)",
        consolidated_raw_path, consolidated_raw_path.stat().st_size / 1024,
    )

    # 3. Decode Coordinates and Dimensions
    raw_lats = ds_raw["Y"].values
    raw_lons = ds_raw["X"].values
    julian_times = ds_raw["T"].values

    # Decode Julian Day to standard UTC timestamps
    decoded_dates = pd.to_datetime(julian_times, unit="D", origin="julian").normalize()
    ds_raw = ds_raw.assign_coords(time=("T", decoded_dates))
    ds_raw = ds_raw.swap_dims({"T": "time"}).drop_vars("T")
    ds_raw = ds_raw.rename({"Y": "lat", "X": "lon", "prcp": "rainfall"})

    raw_days = len(ds_raw["time"])
    raw_num_lats = len(ds_raw["lat"])
    raw_num_lons = len(ds_raw["lon"])
    raw_total_cells = raw_num_lats * raw_num_lons

    logger.info(
        "Raw regional dimensions: time=%d days, lat=%d (%.3f to %.3f), lon=%d (%.3f to %.3f)",
        raw_days, raw_num_lats, raw_lats.min(), raw_lats.max(), raw_num_lons, raw_lons.min(), raw_lons.max(),
    )

    # 4. Perform Spatial Clipping to Maharashtra Bounding Box
    logger.info("Clipping dataset to Maharashtra bounding box...")
    lat_mask = (ds_raw["lat"] >= MAHARASHTRA_BOUNDS["lat_min"]) & (ds_raw["lat"] <= MAHARASHTRA_BOUNDS["lat_max"])
    lon_mask = (ds_raw["lon"] >= MAHARASHTRA_BOUNDS["lon_min"]) & (ds_raw["lon"] <= MAHARASHTRA_BOUNDS["lon_max"])

    ds_mh = ds_raw.sel(lat=lat_mask, lon=lon_mask)

    mh_lats = ds_mh["lat"].values
    mh_lons = ds_mh["lon"].values
    mh_times = ds_mh["time"].values
    mh_rain_vals = ds_mh["rainfall"].values

    mh_days = len(mh_times)
    mh_num_lats = len(mh_lats)
    mh_num_lons = len(mh_lons)
    mh_total_grid_cells = mh_num_lats * mh_num_lons

    # 5. Multidimensional Validation
    logger.info("Validating clipped dataset properties...")
    nan_count = int(np.isnan(mh_rain_vals).sum())
    valid_count = int((~np.isnan(mh_rain_vals)).sum())
    total_elements = mh_rain_vals.size

    rain_min = float(np.nanmin(mh_rain_vals))
    rain_max = float(np.nanmax(mh_rain_vals))
    rain_mean = float(np.nanmean(mh_rain_vals))
    rain_p95 = float(np.nanpercentile(mh_rain_vals, 95))
    rain_p99 = float(np.nanpercentile(mh_rain_vals, 99))

    # Identify Peak 24-hr Rainfall Event
    peak_idx = np.unravel_index(np.nanargmax(mh_rain_vals), mh_rain_vals.shape)
    peak_date = str(mh_times[peak_idx[0]])[:10]
    peak_lat = float(mh_lats[peak_idx[1]])
    peak_lon = float(mh_lons[peak_idx[2]])
    peak_val = float(mh_rain_vals[peak_idx])

    logger.info(
        "Clipped dimensions: time=%d, lat=%d (%.3f° to %.3f°), lon=%d (%.3f° to %.3f°)",
        mh_days, mh_num_lats, mh_lats.min(), mh_lats.max(), mh_num_lons, mh_lons.min(), mh_lons.max(),
    )
    logger.info("Total grid points per time slice: %d (Active elements: %d, NaNs: %d)", mh_total_grid_cells, valid_count, nan_count)
    logger.info("Temporal span: %s to %s (Expected 365, Actual: %d)", str(mh_times[0])[:10], str(mh_times[-1])[:10], mh_days)
    logger.info("Rainfall statistics (mm/day): min=%.2f, max=%.2f, mean=%.2f, p95=%.2f, p99=%.2f", rain_min, rain_max, rain_mean, rain_p95, rain_p99)
    logger.info("Peak 24-hr event: %.2f mm on %s at (%.3f°N, %.3f°E)", peak_val, peak_date, peak_lat, peak_lon)

    # 6. Benchmark District Coordinates & 2023 Annual Accumulation
    logger.info("Mapping 9 Benchmark District Grid Nodes...")
    benchmark_results = {}
    for name, (t_lat, t_lon, region) in BENCHMARK_DISTRICTS.items():
        n_lat, n_lon, dist = find_nearest_grid_point(t_lat, t_lon, mh_lats, mh_lons)
        cell_rain_series = ds_mh["rainfall"].sel(lat=n_lat, lon=n_lon).values
        annual_total = float(np.nansum(cell_rain_series))
        monsoon_total = float(np.nansum(
            ds_mh["rainfall"].sel(lat=n_lat, lon=n_lon)
            .sel(time=slice("2023-06-01", "2023-09-30")).values
        ))
        benchmark_results[name] = {
            "subdivision": region,
            "target_coords": (t_lat, t_lon),
            "nearest_grid_node": (round(n_lat, 3), round(n_lon, 3)),
            "angular_distance_deg": round(dist, 4),
            "approx_distance_km": round(dist * 111.13, 2),
            "annual_rainfall_2023_mm": round(annual_total, 2),
            "monsoon_rainfall_2023_mm": round(monsoon_total, 2),
        }
        logger.info(
            "  %-26s [%-18s]: Target (%.2f, %.2f) -> Node (%.3f, %.3f) | Dist: %.1f km | Annual: %7.1f mm | JJAS: %7.1f mm",
            name, region, t_lat, t_lon, n_lat, n_lon, dist * 111.13, annual_total, monsoon_total,
        )

    # 7. Save Clipped Dataset in data/interim/
    out_interim_path = interim_dir / "maharashtra_chirps_2023.nc"
    # Attach clear provenance metadata
    ds_mh.attrs["title"] = "MonsoonIQ - Maharashtra Daily Rainfall 2023 (CHIRPS Pipeline Validation)"
    ds_mh.attrs["source"] = "UCSB CHIRPS v2.0 via Columbia University IRI Data Library"
    ds_mh.attrs["resolution"] = "0.25 degree"
    ds_mh.attrs["purpose"] = "Pipeline validation and independent comparative benchmark"
    ds_mh["rainfall"].attrs["units"] = "mm/day"
    ds_mh["rainfall"].attrs["standard_name"] = "precipitation_flux"

    ds_mh.to_netcdf(out_interim_path)
    logger.info(
        "Clipped Maharashtra dataset saved: %s (Size: %.2f KB)",
        out_interim_path, out_interim_path.stat().st_size / 1024,
    )

    return {
        "raw_file": str(consolidated_raw_path),
        "clipped_file": str(out_interim_path),
        "raw_dimensions": {"time": raw_days, "lat": raw_num_lats, "lon": raw_num_lons},
        "clipped_dimensions": {"time": mh_days, "lat": mh_num_lats, "lon": mh_num_lons},
        "temporal_range": (str(mh_times[0])[:10], str(mh_times[-1])[:10]),
        "total_clipped_grid_cells": mh_total_grid_cells,
        "rainfall_summary_mm": {
            "min": rain_min,
            "max": rain_max,
            "mean": rain_mean,
            "p95": rain_p95,
            "p99": rain_p99,
        },
        "peak_event": {
            "rainfall_mm": peak_val,
            "date": peak_date,
            "lat": peak_lat,
            "lon": peak_lon,
        },
        "benchmark_districts": benchmark_results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MonsoonIQ CHIRPS 2023 Validation")
    parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    results = acquire_and_validate_chirps_2023(project_root)
    print("\n--- VALIDATION RUN SUCCESSFUL ---")
    print(f"Raw Regional File   : {results['raw_file']}")
    print(f"Clipped MH File     : {results['clipped_file']}")
    print(f"Clipped Grid Shape  : {results['clipped_dimensions']}")
    print(f"Temporal Span       : {results['temporal_range']}")
    print(f"2023 MH Peak Event  : {results['peak_event']['rainfall_mm']} mm on {results['peak_event']['date']}")
