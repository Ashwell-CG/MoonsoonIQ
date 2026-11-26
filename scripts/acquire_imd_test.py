"""MonsoonIQ - IMD 0.25° Gridded Rainfall Acquisition and Validation Script.

This script acquires official daily gridded rainfall data from IMD Pune,
validates the multidimensional array structure, handles missing value flags,
extracts the Maharashtra geographic subset, and verifies representative
benchmark district grid coordinates.
"""

from pathlib import Path
from typing import Dict, Any, Tuple
import argparse
import logging
import numpy as np
import xarray as xr
import imdlib as imd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("MonsoonIQ.Acquisition")

# Maharashtra Bounding Box (inclusive buffer around state perimeter)
MAHARASHTRA_BOUNDS = {
    "lat_min": 15.50,
    "lat_max": 22.25,
    "lon_min": 72.50,
    "lon_max": 81.00,
}

# 9 Benchmark District Headquarters (Official Approximate Coordinates)
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


def find_nearest_grid_point(
    lat_target: float,
    lon_target: float,
    grid_lats: np.ndarray,
    grid_lons: np.ndarray,
) -> Tuple[float, float, float]:
    """Find the nearest grid cell coordinate and Euclidean angular distance.

    Args:
        lat_target: Target latitude in decimal degrees.
        lon_target: Target longitude in decimal degrees.
        grid_lats: Array of grid latitudes.
        grid_lons: Array of grid longitudes.

    Returns:
        Tuple of (nearest_lat, nearest_lon, angular_distance_degrees).
    """
    nearest_lat = float(grid_lats[np.abs(grid_lats - lat_target).argmin()])
    nearest_lon = float(grid_lons[np.abs(grid_lons - lon_target).argmin()])
    dist = float(np.sqrt((nearest_lat - lat_target) ** 2 + (nearest_lon - lon_target) ** 2))
    return nearest_lat, nearest_lon, dist


def acquire_and_validate_imd_year(
    year: int,
    base_dir: Path,
) -> Dict[str, Any]:
    """Download, inspect, clip, and validate IMD gridded rainfall for a single year.

    Args:
        year: Target historical calendar year (e.g. 2023).
        base_dir: Root project directory path.

    Returns:
        Dictionary containing validation metrics, coordinates, and file paths.
    """
    raw_dir = base_dir / "data" / "raw" / "imd_binary"
    interim_dir = base_dir / "data" / "interim"
    raw_dir.mkdir(parents=True, exist_ok=True)
    interim_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Initiating IMD acquisition for year: %d", year)
    logger.info("Raw storage directory: %s", raw_dir)

    # 1. Download via imdlib
    data = imd.get_data("rain", year, year, fn_format="yearwise", file_dir=str(raw_dir))

    # 2. Ingest into xarray.Dataset
    ds = data.get_xarray()
    logger.info("Successfully converted binary data to xarray.Dataset")

    # Native coordinates and dimensions
    var_name = list(ds.data_vars)[0]
    rain_da = ds[var_name]
    lats = ds["lat"].values
    lons = ds["lon"].values
    times = ds["time"].values

    total_days = len(times)
    num_lats = len(lats)
    num_lons = len(lons)
    total_grid_points = num_lats * num_lons

    # Raw value statistics
    raw_vals = rain_da.values
    missing_mask = (raw_vals == -999.0)
    missing_count = int(np.sum(missing_mask))
    valid_mask = ~missing_mask
    valid_vals = raw_vals[valid_mask]

    min_valid_rain = float(np.min(valid_vals))
    max_valid_rain = float(np.max(valid_vals))
    mean_valid_rain = float(np.mean(valid_vals))

    logger.info(
        "Native dimensions: time=%d, lat=%d (%.2f to %.2f), lon=%d (%.2f to %.2f)",
        total_days, num_lats, lats.min(), lats.max(), num_lons, lons.min(), lons.max(),
    )
    logger.info(
        "Raw rainfall range: min=%.2f mm, max=%.2f mm, mean=%.2f mm (Missing flag -999.0 cells: %d)",
        min_valid_rain, max_valid_rain, mean_valid_rain, missing_count,
    )

    # 3. Spatial Clipping for Maharashtra Bounding Box
    lat_slice = slice(MAHARASHTRA_BOUNDS["lat_min"], MAHARASHTRA_BOUNDS["lat_max"])
    lon_slice = slice(MAHARASHTRA_BOUNDS["lon_min"], MAHARASHTRA_BOUNDS["lon_max"])

    ds_mh = ds.sel(lat=lat_slice, lon=lon_slice)

    # 4. Handle Missing Values: Replace -999.0 with np.nan
    ds_mh_clean = ds_mh.where(ds_mh[var_name] != -999.0, other=np.nan)

    mh_rain = ds_mh_clean[var_name]
    mh_lats = ds_mh_clean["lat"].values
    mh_lons = ds_mh_clean["lon"].values

    total_mh_box_cells = len(mh_lats) * len(mh_lons)
    # A land cell has non-NaN values across time
    land_cells_mask = np.any(~np.isnan(mh_rain.values), axis=0)
    total_land_cells = int(np.sum(land_cells_mask))
    ocean_buffer_cells = total_mh_box_cells - total_land_cells

    mh_max_rain = float(np.nanmax(mh_rain.values))
    mh_mean_rain = float(np.nanmean(mh_rain.values))

    # Find date and location of peak 24-hr rainfall in Maharashtra in 2023
    peak_idx = np.unravel_index(np.nanargmax(mh_rain.values), mh_rain.shape)
    peak_time = str(times[peak_idx[0]])[:10]
    peak_lat = float(mh_lats[peak_idx[1]])
    peak_lon = float(mh_lons[peak_idx[2]])

    logger.info("Maharashtra bounding box clipped:")
    logger.info(
        "Lat: %d points (%.2f to %.2f), Lon: %d points (%.2f to %.2f), Total box cells: %d",
        len(mh_lats), mh_lats.min(), mh_lats.max(), len(mh_lons), mh_lons.min(), mh_lons.max(), total_mh_box_cells,
    )
    logger.info(
        "Active land cells: %d (ocean/unmonitored buffer cells: %d)",
        total_land_cells, ocean_buffer_cells,
    )
    logger.info(
        "2023 MH Peak 24-hr Rainfall: %.2f mm on %s at (%.2f°N, %.2f°E)",
        mh_max_rain, peak_time, peak_lat, peak_lon,
    )

    # 5. Benchmark Station Grid Mapping
    logger.info("Resolving 9 Benchmark District Grid Nodes...")
    benchmark_mapping = {}
    for name, (t_lat, t_lon, region) in BENCHMARK_DISTRICTS.items():
        n_lat, n_lon, dist = find_nearest_grid_point(t_lat, t_lon, mh_lats, mh_lons)
        # Check annual total at this grid cell
        cell_annual = float(np.nansum(mh_rain.sel(lat=n_lat, lon=n_lon).values))
        benchmark_mapping[name] = {
            "region": region,
            "target_lat_lon": (t_lat, t_lon),
            "grid_node_lat_lon": (n_lat, n_lon),
            "angular_distance_deg": round(dist, 4),
            "annual_rainfall_2023_mm": round(cell_annual, 2),
        }
        logger.info(
            "  %-26s [%-18s]: Target (%.2f, %.2f) -> Grid (%.2f, %.2f) | Dist: %.4f° | 2023 Total: %.1f mm",
            name, region, t_lat, t_lon, n_lat, n_lon, dist, cell_annual,
        )

    # 6. Save Clipped NetCDF File
    out_nc_path = interim_dir / f"maharashtra_rainfall_{year}.nc"
    ds_mh_clean.to_netcdf(out_nc_path)
    logger.info("Saved clipped Maharashtra NetCDF file: %s (Size: %.2f KB)", out_nc_path, out_nc_path.stat().st_size / 1024)

    return {
        "year": year,
        "native_shape": (total_days, num_lats, num_lons),
        "clipped_shape": (total_days, len(mh_lats), len(mh_lons)),
        "total_days": total_days,
        "start_date": str(times[0])[:10],
        "end_date": str(times[-1])[:10],
        "box_grid_cells": total_mh_box_cells,
        "valid_land_cells": total_land_cells,
        "ocean_or_outside_cells": ocean_buffer_cells,
        "mh_max_daily_rain_mm": mh_max_rain,
        "mh_peak_event": {"date": peak_time, "lat": peak_lat, "lon": peak_lon},
        "mh_mean_daily_rain_mm": mh_mean_rain,
        "benchmark_mapping": benchmark_mapping,
        "saved_netcdf_path": str(out_nc_path),
        "raw_binary_path": str(raw_dir / f"{year}.grd"),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MonsoonIQ IMD Data Acquisition")
    parser.add_argument("--year", type=int, default=2023, help="Year to acquire (default: 2023)")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    acquire_and_validate_imd_year(args.year, project_root)
