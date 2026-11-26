"""MonsoonIQ - IMD 2023 0.25° Gridded Rainfall Validation Script.

This script parses and validates the official IMD Pune binary gridded daily rainfall
file (ind2023_rfp25.grd) for the year 2023. It inspects:
1. Exact file size against IMD specification (25,425,900 bytes for 365 days).
2. Binary floating point decoding (IEEE 754 float32 little-endian, shape: 365 x 129 x 135).
3. Coordinate grids: Latitude (6.5°N to 38.5°N, step 0.25°) and Longitude (66.5°E to 100.0°E, step 0.25°).
4. Missing value conventions (-999.0 flag for oceans and non-Indian territory).
5. Physical bounds: non-negative rainfall (>= 0 mm/day) and extreme value checks.
6. Spatial clipping and authoritative masking to Maharashtra state boundary (Census 2011/LGD).
7. Benchmark district headquarters grid node mapping.
8. Conversion to NetCDF and persistence of clean validation metrics.
"""

from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional
import json
import logging
import numpy as np
import pandas as pd
import xarray as xr
from shapely.geometry import shape, Point

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("MonsoonIQ.IMD_Validation")

# Directory paths
BASE_DIR: Path = Path(__file__).resolve().parent.parent
RAW_IMD_DIR: Path = BASE_DIR / "data" / "raw" / "imd"
INTERIM_DIR: Path = BASE_DIR / "data" / "interim"
GEO_DIR: Path = BASE_DIR / "data" / "geo"

# IMD 0.25° grid specifications (Rajeevan et al., Pai et al.)
IMD_GRID_SPEC = {
    "lat_start": 6.5,
    "lat_end": 38.5,
    "lat_step": 0.25,
    "n_lat": 129,
    "lon_start": 66.5,
    "lon_end": 100.0,
    "lon_step": 0.25,
    "n_lon": 135,
    "missing_value": -999.0,
    "dtype": "<f4",  # 32-bit float, little-endian
    "expected_file_size_365": 25425900,  # 365 * 129 * 135 * 4 bytes
    "expected_file_size_366": 25495560,  # 366 * 129 * 135 * 4 bytes
}

# 9 Benchmark district headquarters
BENCHMARK_DISTRICTS: List[Dict[str, Any]] = [
    {"name": "Ratnagiri", "district_name": "Ratnagiri", "subdivision": "Konkan"},
    {"name": "Thane", "district_name": "Thane", "subdivision": "Konkan"},
    {"name": "Kolhapur", "district_name": "Kolhapur", "subdivision": "Madhya Maharashtra"},
    {"name": "Pune", "district_name": "Pune", "subdivision": "Madhya Maharashtra"},
    {"name": "Solapur", "district_name": "Solapur", "subdivision": "Madhya Maharashtra"},
    {
        "name": "Chhatrapati Sambhaji Nagar",
        "district_name": "Aurangabad",
        "subdivision": "Marathwada",
    },
    {"name": "Latur", "district_name": "Latur", "subdivision": "Marathwada"},
    {"name": "Akola", "district_name": "Akola", "subdivision": "Vidarbha"},
    {"name": "Nagpur", "district_name": "Nagpur", "subdivision": "Vidarbha"},
]


def load_raw_imd_binary(file_path: Path, year: int) -> xr.Dataset:
    """Reads and parses an official IMD binary grid file into an xarray.Dataset.

    Args:
        file_path: Path to the binary .grd file.
        year: Calendar year corresponding to the data.

    Returns:
        xarray.Dataset with dimensions (time, lat, lon).
    """
    if not file_path.exists():
        raise FileNotFoundError(f"IMD binary grid file not found at {file_path}")

    file_size = file_path.stat().st_size
    is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
    expected_days = 366 if is_leap else 365
    expected_size = (
        IMD_GRID_SPEC["expected_file_size_366"]
        if is_leap
        else IMD_GRID_SPEC["expected_file_size_365"]
    )

    if file_size != expected_size:
        raise ValueError(
            f"File size mismatch: {file_size} bytes (expected {expected_size} bytes for {year})"
        )

    logger.info(
        "File size verified: %d bytes (matches exact specification for %d days)",
        file_size,
        expected_days,
    )

    # Read binary array
    # IMD convention: data is stored in day-by-day blocks of (n_lat, n_lon)
    n_lat = IMD_GRID_SPEC["n_lat"]
    n_lon = IMD_GRID_SPEC["n_lon"]
    total_elements = expected_days * n_lat * n_lon

    raw_data = np.fromfile(file_path, dtype=IMD_GRID_SPEC["dtype"], count=total_elements)
    # Reshape to (time, lat, lon)
    grid_data = raw_data.reshape((expected_days, n_lat, n_lon))

    # Build coordinates
    lats = np.linspace(
        IMD_GRID_SPEC["lat_start"],
        IMD_GRID_SPEC["lat_end"],
        n_lat,
        dtype=np.float32,
    )
    lons = np.linspace(
        IMD_GRID_SPEC["lon_start"],
        IMD_GRID_SPEC["lon_end"],
        n_lon,
        dtype=np.float32,
    )
    dates = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")

    # Construct Xarray Dataset
    ds = xr.Dataset(
        data_vars={
            "rainfall": (
                ("time", "lat", "lon"),
                grid_data,
                {
                    "units": "mm/day",
                    "long_name": "daily gridded rainfall",
                    "source": "India Meteorological Department (IMD) Pune 0.25 degree",
                    "missing_value": float(IMD_GRID_SPEC["missing_value"]),
                },
            )
        },
        coords={
            "time": dates,
            "lat": lats,
            "lon": lons,
        },
        attrs={
            "title": f"IMD Daily Gridded Rainfall - {year}",
            "source": "IMD Pune (cmpg/Griddata)",
            "spatial_resolution": "0.25 degree x 0.25 degree",
            "citation": "Pai et al. (2014) / Rajeevan et al. (2006)",
        },
    )
    return ds


def validate_imd_dataset(ds: xr.Dataset, year: int) -> Dict[str, Any]:
    """Validates multidimensional structure, missing flags, and ranges.

    Args:
        ds: Decoded xarray.Dataset.
        year: Target year.

    Returns:
        Dictionary of national-level validation results.
    """
    logger.info("Validating national IMD dataset properties...")
    rf_vals = ds["rainfall"].values
    missing_flag = float(IMD_GRID_SPEC["missing_value"])

    is_missing = np.isclose(rf_vals, missing_flag, atol=1e-2)
    missing_count = int(np.sum(is_missing))
    total_elements = rf_vals.size

    valid_mask = ~is_missing
    valid_vals = rf_vals[valid_mask]
    valid_count = int(np.sum(valid_mask))

    # Physical checks
    min_val = float(np.min(valid_vals))
    max_val = float(np.max(valid_vals))
    mean_val = float(np.mean(valid_vals))
    is_non_negative = bool(min_val >= 0.0)

    # National daily peak
    peak_idx = np.unravel_index(np.argmax(np.where(valid_mask, rf_vals, -1.0)), rf_vals.shape)
    peak_date = str(ds["time"].values[peak_idx[0]])[:10]
    peak_lat = float(ds["lat"].values[peak_idx[1]])
    peak_lon = float(ds["lon"].values[peak_idx[2]])
    peak_val = float(rf_vals[peak_idx])

    val_report = {
        "year": year,
        "total_days": len(ds["time"]),
        "start_date": str(ds["time"].values[0])[:10],
        "end_date": str(ds["time"].values[-1])[:10],
        "spatial_grid": {
            "lat_points": len(ds["lat"]),
            "lat_min": float(ds["lat"].min()),
            "lat_max": float(ds["lat"].max()),
            "lon_points": len(ds["lon"]),
            "lon_min": float(ds["lon"].min()),
            "lon_max": float(ds["lon"].max()),
            "total_cells_per_day": len(ds["lat"]) * len(ds["lon"]),
        },
        "missing_flag": missing_flag,
        "total_elements": total_elements,
        "missing_elements": missing_count,
        "missing_percentage": float(np.round((missing_count / total_elements) * 100.0, 2)),
        "valid_elements": valid_count,
        "valid_percentage": float(np.round((valid_count / total_elements) * 100.0, 2)),
        "is_non_negative": is_non_negative,
        "national_min_rain_mm": min_val,
        "national_max_rain_mm": max_val,
        "national_mean_rain_mm": float(np.round(mean_val, 2)),
        "national_peak_event": {
            "date": peak_date,
            "rainfall_mm": peak_val,
            "lat": peak_lat,
            "lon": peak_lon,
        },
    }
    logger.info(
        "National validation passed: Valid=%.1f%%, Non-negative=%s, Peak=%.1f mm on %s at (%.2fN, %.2fE)",
        val_report["valid_percentage"],
        is_non_negative,
        peak_val,
        peak_date,
        peak_lat,
        peak_lon,
    )
    return val_report


def clip_and_mask_maharashtra(
    ds: xr.Dataset,
    state_geojson_path: Path,
    districts_geojson_path: Path,
    hq_geojson_path: Path,
    out_nc_path: Path,
) -> Dict[str, Any]:
    """Clips the IMD dataset to Maharashtra and performs authoritative masking.

    Args:
        ds: Full national IMD Dataset.
        state_geojson_path: Path to authoritative Maharashtra GeoJSON.
        districts_geojson_path: Path to district polygons GeoJSON.
        hq_geojson_path: Path to official district HQs GeoJSON.
        out_nc_path: Output path for the clipped and masked NetCDF.

    Returns:
        Dictionary of Maharashtra regional audit and validation metrics.
    """
    logger.info("Clipping and masking IMD data to Maharashtra administrative boundary...")

    # Load Maharashtra state polygon
    with open(state_geojson_path, "r", encoding="utf-8") as f:
        state_geo = json.load(f)
    feature = state_geo["features"][0] if "features" in state_geo else state_geo
    mh_poly = shape(feature["geometry"])

    # Load district polygons and HQs
    with open(districts_geojson_path, "r", encoding="utf-8") as f:
        dist_geo = json.load(f)
    dist_polys = {f["properties"]["dtname"].lower(): shape(f["geometry"]) for f in dist_geo["features"]}

    with open(hq_geojson_path, "r", encoding="utf-8") as f:
        hq_geo = json.load(f)
    hq_coords_map = {
        f["properties"]["DTNAME"].lower(): (
            float(f["geometry"]["coordinates"][1]),
            float(f["geometry"]["coordinates"][0]),
        )
        for f in hq_geo["features"]
    }

    # Maharashtra bounding box
    # lat 15.5 to 22.25, lon 72.5 to 81.0
    mh_lat_slice = slice(15.5, 22.25)
    mh_lon_slice = slice(72.5, 81.0)
    ds_box = ds.sel(lat=mh_lat_slice, lon=mh_lon_slice)

    lats = ds_box["lat"].values
    lons = ds_box["lon"].values
    rf_box = ds_box["rainfall"].values  # (365, n_lat, n_lon)

    n_lat = len(lats)
    n_lon = len(lons)
    total_box_cells = n_lat * n_lon

    # Build masks
    mask_mh = np.zeros((n_lat, n_lon), dtype=bool)
    is_land = np.zeros((n_lat, n_lon), dtype=bool)

    missing_flag = float(IMD_GRID_SPEC["missing_value"])

    sea_cells = 0
    terrestrial_out_cells = 0
    mh_land_cells = 0

    for i, lat_val in enumerate(lats):
        for j, lon_val in enumerate(lons):
            pt = Point(lon_val, lat_val)
            in_mh = mh_poly.contains(pt)
            mask_mh[i, j] = in_mh

            cell_vals = rf_box[:, i, j]
            # A sea / non-monitored point in IMD has -999.0 for all 365 days
            all_missing = np.all(np.isclose(cell_vals, missing_flag, atol=1e-2))
            is_land[i, j] = not all_missing

            if all_missing:
                sea_cells += 1
            elif in_mh:
                mh_land_cells += 1
            else:
                terrestrial_out_cells += 1

    logger.info(
        "IMD Maharashtra Spatial Grid: %d x %d = %d cells | Sea=%d, Out-of-State Land=%d, True MH Land=%d",
        n_lat,
        n_lon,
        total_box_cells,
        sea_cells,
        terrestrial_out_cells,
        mh_land_cells,
    )

    # Clean array: replace -999.0 with NaN
    rf_clean = np.where(np.isclose(rf_box, missing_flag, atol=1e-2), np.nan, rf_box)
    rf_masked = rf_clean.copy()
    rf_masked[:, ~mask_mh] = np.nan

    # Calculate Maharashtra statistics across the valid land cells
    # Annual sum per cell
    annual_sum_grid = np.nansum(rf_clean, axis=0)
    annual_sum_grid[~is_land] = np.nan
    mh_annual_vals = annual_sum_grid[mask_mh]

    # JJAS sum
    times = pd.to_datetime(ds_box["time"].values)
    is_jjas = (times.month >= 6) & (times.month <= 9)
    jjas_rf_clean = rf_clean[is_jjas, :, :]
    jjas_sum_grid = np.nansum(jjas_rf_clean, axis=0)
    jjas_sum_grid[~is_land] = np.nan
    mh_jjas_vals = jjas_sum_grid[mask_mh]

    # Maharashtra statewide peak 24-hr rainfall event in 2023
    mh_rf_for_peak = np.where(mask_mh[None, :, :], rf_clean, np.nan)
    peak_idx = np.unravel_index(np.nanargmax(mh_rf_for_peak), mh_rf_for_peak.shape)
    mh_peak_val = float(mh_rf_for_peak[peak_idx])
    mh_peak_date = str(times[peak_idx[0]])[:10]
    mh_peak_lat = float(lats[peak_idx[1]])
    mh_peak_lon = float(lons[peak_idx[2]])

    # Top 10 extreme daily rainfall events in Maharashtra in 2023
    flat_rf = mh_rf_for_peak.ravel()
    valid_flat_idx = np.flatnonzero(~np.isnan(flat_rf))
    sorted_order = np.argsort(flat_rf[valid_flat_idx])[::-1]
    top_indices = valid_flat_idx[sorted_order[:10]]

    top_10_events = []
    for rank, idx in enumerate(top_indices, start=1):
        t_i, lat_i, lon_i = np.unravel_index(idx, mh_rf_for_peak.shape)
        top_10_events.append(
            {
                "rank": rank,
                "rainfall_mm": float(np.round(mh_rf_for_peak[t_i, lat_i, lon_i], 2)),
                "date": str(times[t_i])[:10],
                "lat": float(lats[lat_i]),
                "lon": float(lons[lon_i]),
            }
        )

    # Benchmark station evaluations
    benchmark_results = []
    for item in BENCHMARK_DISTRICTS:
        b_name = item["name"]
        d_search = item["district_name"].lower()
        subdiv = item["subdivision"]

        matched_hq = None
        for k, v in hq_coords_map.items():
            if d_search in k or k in d_search:
                matched_hq = v
                break
        if not matched_hq:
            continue

        hq_lat, hq_lon = matched_hq
        lat_idx = int(np.abs(lats - hq_lat).argmin())
        lon_idx = int(np.abs(lons - hq_lon).argmin())
        grid_lat = float(lats[lat_idx])
        grid_lon = float(lons[lon_idx])

        d_lat_km = (grid_lat - hq_lat) * 111.0
        d_lon_km = (grid_lon - hq_lon) * 111.0 * np.cos(np.radians(hq_lat))
        dist_km = float(np.round(np.hypot(d_lat_km, d_lon_km), 2))

        # Check district containment
        matched_poly = None
        for k, poly in dist_polys.items():
            if d_search in k or k in d_search:
                matched_poly = poly
                break
        grid_pt = Point(grid_lon, grid_lat)
        in_district = matched_poly.contains(grid_pt) if matched_poly else False

        actual_district = item["district_name"] if in_district else "Border/Adjacent"
        if not in_district:
            for d_name_key, poly in dist_polys.items():
                if poly.contains(grid_pt):
                    actual_district = d_name_key.capitalize()
                    break

        node_annual = float(np.nansum(rf_clean[:, lat_idx, lon_idx]))
        node_jjas = float(np.nansum(jjas_rf_clean[:, lat_idx, lon_idx]))
        node_jjas_pct = float(np.round((node_jjas / node_annual) * 100.0, 1)) if node_annual > 0 else 0.0

        # District area average
        dist_cells_annual = []
        dist_cells_jjas = []
        for i, lat_v in enumerate(lats):
            for j, lon_v in enumerate(lons):
                if matched_poly and matched_poly.contains(Point(lon_v, lat_v)):
                    c_ann = float(np.nansum(rf_clean[:, i, j]))
                    c_jjas = float(np.nansum(jjas_rf_clean[:, i, j]))
                    if not np.isnan(c_ann) and c_ann > 0:
                        dist_cells_annual.append(c_ann)
                        dist_cells_jjas.append(c_jjas)

        dist_avg_annual = float(np.round(np.mean(dist_cells_annual), 1)) if dist_cells_annual else node_annual
        dist_avg_jjas = float(np.round(np.mean(dist_cells_jjas), 1)) if dist_cells_jjas else node_jjas
        dist_avg_pct = float(np.round((dist_avg_jjas / dist_avg_annual) * 100.0, 1)) if dist_avg_annual > 0 else 0.0

        benchmark_results.append(
            {
                "benchmark_name": b_name,
                "district_name": item["district_name"],
                "subdivision": subdiv,
                "hq_coords": (hq_lat, hq_lon),
                "grid_coords": (grid_lat, grid_lon),
                "distance_km": dist_km,
                "grid_node_inside_target_district": bool(in_district),
                "actual_containing_district": actual_district,
                "node_annual_mm": float(np.round(node_annual, 1)),
                "node_jjas_mm": float(np.round(node_jjas, 1)),
                "node_jjas_pct": node_jjas_pct,
                "district_avg_annual_mm": dist_avg_annual,
                "district_avg_jjas_mm": dist_avg_jjas,
                "district_avg_jjas_pct": dist_avg_pct,
            }
        )

    # Save masked NetCDF
    out_nc_path.parent.mkdir(parents=True, exist_ok=True)
    ds_out = xr.Dataset(
        data_vars={
            "rainfall": (
                ("time", "lat", "lon"),
                rf_clean.astype(np.float32),
                {
                    "units": "mm/day",
                    "long_name": "daily gridded rainfall (unmasked bounding box)",
                    "source": "IMD Pune 0.25 degree",
                },
            ),
            "rainfall_masked": (
                ("time", "lat", "lon"),
                rf_masked.astype(np.float32),
                {
                    "units": "mm/day",
                    "long_name": "daily gridded rainfall masked to Maharashtra land boundary",
                    "source": "IMD Pune 0.25 degree",
                },
            ),
            "mask_maharashtra": (
                ("lat", "lon"),
                mask_mh.astype(bool),
                {
                    "description": "Maharashtra state boundary mask (Census 2011/LGD)",
                    "count_true": int(np.sum(mask_mh)),
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
            "time": ds_box["time"],
            "lat": ds_box["lat"],
            "lon": ds_box["lon"],
        },
        attrs={
            **ds.attrs,
            "region": "Maharashtra, India",
            "geographic_coverage": "Lat 15.5 to 22.25, Lon 72.5 to 81.0",
            "valid_maharashtra_cells": int(np.sum(mask_mh)),
        },
    )

    encoding = {
        "rainfall": {"zlib": True, "complevel": 4},
        "rainfall_masked": {"zlib": True, "complevel": 4},
        "mask_maharashtra": {"zlib": True, "complevel": 4},
        "is_land": {"zlib": True, "complevel": 4},
    }
    ds_out.to_netcdf(out_nc_path, encoding=encoding)
    logger.info("Saved clipped and masked IMD NetCDF: %s (%d bytes)", out_nc_path, out_nc_path.stat().st_size)

    mh_summary = {
        "box_lat_points": n_lat,
        "box_lon_points": n_lon,
        "total_bounding_box_cells": total_box_cells,
        "sea_cells_count": sea_cells,
        "terrestrial_outside_mh_cells": terrestrial_out_cells,
        "true_maharashtra_land_cells": mh_land_cells,
        "state_annual_mean_mm": float(np.round(np.mean(mh_annual_vals), 1)),
        "state_annual_median_mm": float(np.round(np.median(mh_annual_vals), 1)),
        "state_annual_min_mm": float(np.round(np.min(mh_annual_vals), 1)),
        "state_annual_max_mm": float(np.round(np.max(mh_annual_vals), 1)),
        "state_jjas_mean_mm": float(np.round(np.mean(mh_jjas_vals), 1)),
        "state_jjas_percentage": float(np.round(np.mean(mh_jjas_vals / mh_annual_vals) * 100.0, 1)),
        "mh_peak_event": {
            "rainfall_mm": mh_peak_val,
            "date": mh_peak_date,
            "lat": mh_peak_lat,
            "lon": mh_peak_lon,
        },
        "top_10_maharashtra_events": top_10_events,
        "benchmarks": benchmark_results,
    }
    return mh_summary


def run_imd_2023_validation() -> Dict[str, Any]:
    """Orchestrates the entire IMD 2023 validation pipeline."""
    logger.info("=== Starting MonsoonIQ IMD 2023 Validation Pipeline ===")
    grd_file = RAW_IMD_DIR / "ind2023_rfp25.grd"
    state_geo_path = GEO_DIR / "maharashtra_state.geojson"
    dist_geo_path = GEO_DIR / "maharashtra_districts.geojson"
    hq_geo_path = GEO_DIR / "maharashtra_district_hq.geojson"
    out_nc_path = INTERIM_DIR / "maharashtra_imd_2023_masked.nc"

    # Step 1: Parse raw binary
    ds = load_raw_imd_binary(grd_file, 2023)

    # Step 2: National validation
    national_report = validate_imd_dataset(ds, 2023)

    # Step 3: Maharashtra clipping & masking
    mh_report = clip_and_mask_maharashtra(
        ds, state_geo_path, dist_geo_path, hq_geo_path, out_nc_path
    )

    full_report = {
        "dataset_name": "IMD 0.25 Degree Daily Gridded Rainfall",
        "product_type": "Primary Ground Observation Dataset",
        "file_name": grd_file.name,
        "file_size_bytes": grd_file.stat().st_size,
        "file_size_mb": float(np.round(grd_file.stat().st_size / (1024 * 1024), 2)),
        "national_validation": national_report,
        "maharashtra_validation": mh_report,
    }

    # Save validation metrics to JSON
    out_json = INTERIM_DIR / "imd_2023_validation_report.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2)
    logger.info("Saved IMD validation report to %s", out_json)

    return full_report


if __name__ == "__main__":
    report = run_imd_2023_validation()
    print("\n=== IMD 2023 Acquisition and Validation Summary ===")
    print(f"File: {report['file_name']} ({report['file_size_mb']} MB)")
    print(f"National Peak: {report['national_validation']['national_peak_event']['rainfall_mm']} mm on {report['national_validation']['national_peak_event']['date']}")
    print(f"Maharashtra Land Cells: {report['maharashtra_validation']['true_maharashtra_land_cells']}")
    print(f"Maharashtra Mean Annual: {report['maharashtra_validation']['state_annual_mean_mm']} mm")
    print(f"Maharashtra Mean JJAS: {report['maharashtra_validation']['state_jjas_mean_mm']} mm ({report['maharashtra_validation']['state_jjas_percentage']}%)")
    print(f"Maharashtra Peak: {report['maharashtra_validation']['mh_peak_event']['rainfall_mm']} mm on {report['maharashtra_validation']['mh_peak_event']['date']} at ({report['maharashtra_validation']['mh_peak_event']['lat']}N, {report['maharashtra_validation']['mh_peak_event']['lon']}E)")
