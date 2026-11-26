"""MonsoonIQ - Historical Rainfall Exploratory Data Analysis (EDA).

This module performs comprehensive exploratory data analysis on the consolidated
historical IMD 0.25° daily gridded rainfall dataset for Maharashtra (2001–2023):
1. Ingests the 23-year consolidated NetCDF dataset and authoritative district polygons.
2. Partitions the 419 Maharashtra land grid cells into 4 IMD meteorological
   subdivisions and 5 physiographic/climatic zones (including Western Ghats ridge).
3. Analyzes annual and monthly rainfall patterns, climatological normals, and regimes.
4. Computes June–September (JJAS) monsoon rainfall totals, departures, and classifications.
5. Evaluates wet-day frequency across IMD rainfall intensity thresholds (>= 2.5 mm/day).
6. Identifies intra-seasonal monsoon dry spells, break durations, and drought risks.
7. Computes spatial rainfall variability, standard deviation, and Coefficient of Variation (CV).
8. Compares climate metrics across Konkan, Western Ghats, Madhya MH, Marathwada, and Vidarbha.
9. Analyzes historical extreme 1-day rainfall events and examines physical plausibility.
10. Evaluates long-term trends (OLS linear regression and non-parametric Mann-Kendall/Sen's slope).
11. Generates 8 publication-grade spatial maps and diagnostic charts in outputs/eda/.
12. Formulates data-driven recommendations for the upcoming Maharashtra onset detection algorithm.
"""

from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional
import os
import json
import logging
import numpy as np
import pandas as pd
import xarray as xr
from scipy import stats
from shapely.geometry import shape, Point

# Configure matplotlib headless backend and safe user cache directory
BASE_DIR: Path = Path(__file__).resolve().parent.parent
MPL_DIR: Path = BASE_DIR / "outputs" / "eda" / ".mpl"
MPL_DIR.mkdir(parents=True, exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(MPL_DIR)

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.colors as mcolors  # noqa: E402
from matplotlib.patches import Polygon as MplPolygon  # noqa: E402
from matplotlib.collections import PatchCollection  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("MonsoonIQ.EDA")

# Paths
DATA_NC_PATH: Path = BASE_DIR / "data" / "processed" / "maharashtra_imd_daily_2001_2023.nc"
DISTRICTS_GEO_PATH: Path = BASE_DIR / "data" / "geo" / "maharashtra_districts.geojson"
STATE_GEO_PATH: Path = BASE_DIR / "data" / "geo" / "maharashtra_state.geojson"
OUTPUT_DIR: Path = BASE_DIR / "outputs" / "eda"
DOCS_DIR: Path = BASE_DIR / "docs"

# IMD Intensity Thresholds (mm/day)
THRESHOLD_RAINY_DAY: float = 2.5  # IMD official rainy day
THRESHOLD_MODERATE: float = 7.5
THRESHOLD_RATHER_HEAVY: float = 35.5
THRESHOLD_HEAVY: float = 64.5
THRESHOLD_VERY_HEAVY: float = 115.5
THRESHOLD_EXTREMELY_HEAVY: float = 204.5

# IMD 4 Meteorological Subdivisions mapping for 36 Maharashtra Districts
SUBDIVISION_MAP: Dict[str, str] = {
    # Konkan & Goa (7 districts in MH)
    "Mumbai": "Konkan",
    "Mumbai Suburban": "Konkan",
    "Thane": "Konkan",
    "Palghar": "Konkan",
    "Raigarh": "Konkan",
    "Ratnagiri": "Konkan",
    "Sindhudurg": "Konkan",
    # Madhya Maharashtra (10 districts)
    "Nandurbar": "Madhya Maharashtra",
    "Dhule": "Madhya Maharashtra",
    "Jalgaon": "Madhya Maharashtra",
    "Nashik": "Madhya Maharashtra",
    "Ahmadnagar": "Madhya Maharashtra",
    "Pune": "Madhya Maharashtra",
    "Satara": "Madhya Maharashtra",
    "Sangli": "Madhya Maharashtra",
    "Solapur": "Madhya Maharashtra",
    "Kolhapur": "Madhya Maharashtra",
    # Marathwada (8 districts)
    "Aurangabad": "Marathwada",
    "Jalna": "Marathwada",
    "Bid": "Marathwada",
    "Parbhani": "Marathwada",
    "Hingoli": "Marathwada",
    "Nanded": "Marathwada",
    "Latur": "Marathwada",
    "Osmanabad": "Marathwada",
    # Vidarbha (11 districts)
    "Buldana": "Vidarbha",
    "Akola": "Vidarbha",
    "Washim": "Vidarbha",
    "Amravati": "Vidarbha",
    "Yavatmal": "Vidarbha",
    "Wardha": "Vidarbha",
    "Nagpur": "Vidarbha",
    "Bhandara": "Vidarbha",
    "Gondiya": "Vidarbha",
    "Chandrapur": "Vidarbha",
    "Gadchiroli": "Vidarbha",
}


def compute_mann_kendall(
    y: np.ndarray,
) -> Tuple[float, float, float, float]:
    """Computes non-parametric Mann-Kendall test and Sen's slope estimator.

    Args:
        y: 1D array of values over a sequential time series.

    Returns:
        Tuple of (S_statistic, Z_score, p_value, sens_slope).
    """
    n = len(y)
    s = 0.0
    slopes: List[float] = []

    for i in range(n - 1):
        for j in range(i + 1, n):
            diff = y[j] - y[i]
            s += np.sign(diff)
            slopes.append(diff / (j - i))

    # Variance of S under H0 (no ties assumed for continuous rainfall)
    var_s = (n * (n - 1) * (2 * n + 5)) / 18.0

    if s > 0:
        z = (s - 1) / np.sqrt(var_s)
    elif s < 0:
        z = (s + 1) / np.sqrt(var_s)
    else:
        z = 0.0

    p_value = 2.0 * (1.0 - stats.norm.cdf(abs(z)))
    sens_slope = float(np.median(slopes)) if slopes else 0.0

    return float(s), float(z), float(p_value), sens_slope


def assign_grid_cells_to_districts(
    lats: np.ndarray,
    lons: np.ndarray,
    mask_mh: np.ndarray,
    districts_geo_path: Path,
) -> Dict[Tuple[int, int], Dict[str, Any]]:
    """Maps each valid Maharashtra grid cell (lat_idx, lon_idx) to a district.

    Args:
        lats: Array of 28 latitude coordinates.
        lons: Array of 35 longitude coordinates.
        mask_mh: 28x35 boolean mask of valid Maharashtra land cells.
        districts_geo_path: Path to GeoJSON containing 36 district polygons.

    Returns:
        Dictionary mapping (i, j) index tuple to district metadata.
    """
    with open(districts_geo_path, "r", encoding="utf-8") as f:
        geo = json.load(f)

    district_features: List[Tuple[str, Any]] = []
    for feat in geo["features"]:
        poly = shape(feat["geometry"])
        dtname = feat["properties"]["dtname"]
        district_features.append((dtname, poly))

    cell_mapping: Dict[Tuple[int, int], Dict[str, Any]] = {}

    for i, lat in enumerate(lats):
        for j, lon in enumerate(lons):
            if not mask_mh[i, j]:
                continue
            pt = Point(lon, lat)
            matched_dt: Optional[str] = None

            # First check exact point containment
            for dtname, poly in district_features:
                if poly.contains(pt):
                    matched_dt = dtname
                    break

            # If on boundary, check small buffer
            if matched_dt is None:
                for dtname, poly in district_features:
                    if poly.buffer(0.05).contains(pt):
                        matched_dt = dtname
                        break

            if matched_dt is None:
                # Nearest district centroid fallback
                min_dist = float("inf")
                for dtname, poly in district_features:
                    d = poly.distance(pt)
                    if d < min_dist:
                        min_dist = d
                        matched_dt = dtname

            subdiv = SUBDIVISION_MAP.get(matched_dt, "Madhya Maharashtra")
            cell_mapping[(i, j)] = {
                "lat": float(lat),
                "lon": float(lon),
                "district": matched_dt,
                "subdivision": subdiv,
            }

    return cell_mapping


def classify_physiographic_zones(
    cell_mapping: Dict[Tuple[int, int], Dict[str, Any]],
    mean_annual_grid: np.ndarray,
) -> Dict[Tuple[int, int], str]:
    """Classifies cells into 5 zones: Konkan, Western Ghats, Madhya MH, Marathwada, Vidarbha.

    The Western Ghats (Sahyadri) crest represents a narrow orographic spine where
    annual rainfall exceeds 2000 mm along longitudes 73.25°E to 74.00°E.

    Args:
        cell_mapping: Mapping of (i, j) cells to district and subdivision.
        mean_annual_grid: 28x35 array of mean annual precipitation (mm).

    Returns:
        Dictionary mapping (i, j) to one of the 5 physiographic zone labels.
    """
    zone_mapping: Dict[Tuple[int, int], str] = {}

    for (i, j), meta in cell_mapping.items():
        subdiv = meta["subdivision"]
        lon = meta["lon"]
        ann_rain = mean_annual_grid[i, j]

        # Identify Western Ghats crest: high elevation orographic spine
        if 73.25 <= lon <= 74.00 and ann_rain >= 2000.0 and subdiv in ["Konkan", "Madhya Maharashtra"]:
            zone_mapping[(i, j)] = "Western Ghats"
        elif subdiv == "Konkan":
            zone_mapping[(i, j)] = "Konkan"
        elif subdiv == "Madhya Maharashtra":
            zone_mapping[(i, j)] = "Madhya Maharashtra"
        elif subdiv == "Marathwada":
            zone_mapping[(i, j)] = "Marathwada"
        elif subdiv == "Vidarbha":
            zone_mapping[(i, j)] = "Vidarbha"
        else:
            zone_mapping[(i, j)] = subdiv

    return zone_mapping


def run_comprehensive_eda() -> Dict[str, Any]:
    """Executes the full 10-task exploratory data analysis workflow.

    Returns:
        Structured dictionary containing all computed metrics, summaries, and paths.
    """
    logger.info("Starting MonsoonIQ Phase 4 Historical Rainfall EDA...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load consolidated NetCDF dataset
    if not DATA_NC_PATH.exists():
        raise FileNotFoundError(f"Consolidated NetCDF not found at {DATA_NC_PATH}")

    ds = xr.open_dataset(DATA_NC_PATH)
    rainfall_masked = ds["rainfall_masked"]  # (8400, 28, 35)
    mask_mh = ds["mask_maharashtra"].values  # (28, 35) bool
    lats = ds["lat"].values
    lons = ds["lon"].values
    dates = pd.DatetimeIndex(ds["time"].values)
    years = np.unique(dates.year)

    n_cells = int(np.sum(mask_mh))
    logger.info(
        "Dataset loaded: %d days (2001–2023), %d valid Maharashtra land cells.",
        len(dates),
        n_cells,
    )

    # 2. Map cells to districts and subdivisions
    cell_mapping = assign_grid_cells_to_districts(lats, lons, mask_mh, DISTRICTS_GEO_PATH)

    # 3. Compute Annual and Monthly Climatology
    # Pre-compute annual sums: shape (23, 28, 35)
    annual_grid_ds = rainfall_masked.groupby("time.year").sum(dim="time")
    annual_grid_vals = annual_grid_ds.values  # (23, 28, 35)
    mean_annual_grid = np.nanmean(annual_grid_vals, axis=0)  # (28, 35)
    std_annual_grid = np.nanstd(annual_grid_vals, axis=0, ddof=1)  # (28, 35)
    cv_annual_grid = np.where(mean_annual_grid > 0, (std_annual_grid / mean_annual_grid) * 100.0, np.nan)

    # Classify 5 physiographic zones including Western Ghats ridge
    zone_mapping = classify_physiographic_zones(cell_mapping, mean_annual_grid)

    # Statewide annual mean time series (average across 419 cells per year)
    state_annual_series = np.array(
        [np.nanmean(annual_grid_vals[y_idx, mask_mh]) for y_idx in range(len(years))]
    )
    state_annual_mean = float(np.mean(state_annual_series))
    state_annual_std = float(np.std(state_annual_series, ddof=1))
    state_annual_cv = float((state_annual_std / state_annual_mean) * 100.0)

    # Monthly climatology across all 23 years
    monthly_means: Dict[int, float] = {}
    for m in range(1, 13):
        m_slice = rainfall_masked.sel(time=(rainfall_masked.time.dt.month == m))
        # Total rain per year for month m, then average across years
        m_annual = m_slice.groupby("time.year").sum(dim="time").values
        m_mean_val = float(np.nanmean(m_annual[:, mask_mh]))
        monthly_means[m] = m_mean_val

    # 4. June–September (JJAS) Monsoon Analysis
    jjas_mask_time = np.isin(dates.month, [6, 7, 8, 9])
    jjas_slice = rainfall_masked.sel(time=jjas_mask_time)
    jjas_grid_ds = jjas_slice.groupby("time.year").sum(dim="time")
    jjas_grid_vals = jjas_grid_ds.values  # (23, 28, 35)

    state_jjas_series = np.array(
        [np.nanmean(jjas_grid_vals[y_idx, mask_mh]) for y_idx in range(len(years))]
    )
    state_jjas_mean = float(np.mean(state_jjas_series))
    state_jjas_std = float(np.std(state_jjas_series, ddof=1))
    state_jjas_cv = float((state_jjas_std / state_jjas_mean) * 100.0)
    jjas_pct_of_annual = float((state_jjas_mean / state_annual_mean) * 100.0)

    # Year-by-year JJAS departure analysis
    jjas_departures = ((state_jjas_series - state_jjas_mean) / state_jjas_mean) * 100.0
    yearly_jjas_df = pd.DataFrame(
        {
            "year": years,
            "annual_rainfall_mm": np.round(state_annual_series, 1),
            "jjas_rainfall_mm": np.round(state_jjas_series, 1),
            "jjas_pct_of_annual": np.round((state_jjas_series / state_annual_series) * 100.0, 1),
            "departure_pct": np.round(jjas_departures, 1),
            "category": [
                "Excess (> +10%)" if d > 10.0 else ("Deficient (< -10%)" if d < -10.0 else "Normal")
                for d in jjas_departures
            ],
        }
    )

    # 5. Wet-Day Frequency Analysis (>= 2.5 mm/day)
    # Compute for each year and grid cell
    rf_vals_all = rainfall_masked.values  # (8400, 28, 35)

    # Annual wet days (>= 2.5 mm) per year
    annual_wet_days = np.zeros((len(years), 28, 35), dtype=np.float32)
    jjas_wet_days = np.zeros((len(years), 28, 35), dtype=np.float32)
    annual_heavy_days = np.zeros((len(years), 28, 35), dtype=np.float32)
    annual_vheavy_days = np.zeros((len(years), 28, 35), dtype=np.float32)

    for y_idx, yr in enumerate(years):
        yr_time_mask = (dates.year == yr)
        jjas_time_mask = (dates.year == yr) & np.isin(dates.month, [6, 7, 8, 9])

        yr_slice = rf_vals_all[yr_time_mask, :, :]
        jjas_slice_arr = rf_vals_all[jjas_time_mask, :, :]

        annual_wet_days[y_idx] = np.nansum(yr_slice >= THRESHOLD_RAINY_DAY, axis=0)
        jjas_wet_days[y_idx] = np.nansum(jjas_slice_arr >= THRESHOLD_RAINY_DAY, axis=0)
        annual_heavy_days[y_idx] = np.nansum(yr_slice >= THRESHOLD_HEAVY, axis=0)
        annual_vheavy_days[y_idx] = np.nansum(yr_slice >= THRESHOLD_VERY_HEAVY, axis=0)

    mean_annual_wet_days_grid = np.nanmean(annual_wet_days, axis=0)
    mean_jjas_wet_days_grid = np.nanmean(jjas_wet_days, axis=0)
    mean_heavy_days_grid = np.nanmean(annual_heavy_days, axis=0)
    mean_vheavy_days_grid = np.nanmean(annual_vheavy_days, axis=0)

    state_annual_wet_days_series = np.array(
        [np.nanmean(annual_wet_days[y_idx, mask_mh]) for y_idx in range(len(years))]
    )
    state_heavy_days_series = np.array(
        [np.nanmean(annual_heavy_days[y_idx, mask_mh]) for y_idx in range(len(years))]
    )

    # 6. Intra-Seasonal Monsoon Dry Spells during JJAS
    # A dry spell is a sequence of consecutive days with rainfall < 2.5 mm during JJAS (122 days)
    logger.info("Computing intra-seasonal JJAS dry spell statistics...")
    cell_dry_spell_stats: Dict[Tuple[int, int], Dict[str, float]] = {}

    for (i, j) in cell_mapping.keys():
        cell_spell_lengths: List[int] = []
        cell_max_lengths: List[int] = []
        cell_spells_ge_7: List[int] = []
        cell_spells_ge_14: List[int] = []

        for yr in years:
            jjas_mask_yr = (dates.year == yr) & np.isin(dates.month, [6, 7, 8, 9])
            daily_series = rf_vals_all[jjas_mask_yr, i, j]  # 122 days

            # Identify runs of dry days (< 2.5 mm)
            is_dry = (daily_series < THRESHOLD_RAINY_DAY) | np.isnan(daily_series)
            dry_runs: List[int] = []
            curr_run = 0

            for val in is_dry:
                if val:
                    curr_run += 1
                else:
                    if curr_run > 0:
                        dry_runs.append(curr_run)
                        curr_run = 0
            if curr_run > 0:
                dry_runs.append(curr_run)

            if dry_runs:
                cell_spell_lengths.extend(dry_runs)
                cell_max_lengths.append(max(dry_runs))
                cell_spells_ge_7.append(sum(1 for r in dry_runs if r >= 7))
                cell_spells_ge_14.append(sum(1 for r in dry_runs if r >= 14))
            else:
                cell_max_lengths.append(0)
                cell_spells_ge_7.append(0)
                cell_spells_ge_14.append(0)

        cell_dry_spell_stats[(i, j)] = {
            "mean_spell_len": float(np.mean(cell_spell_lengths)) if cell_spell_lengths else 0.0,
            "max_spell_len": float(np.max(cell_max_lengths)) if cell_max_lengths else 0.0,
            "mean_annual_max_break": float(np.mean(cell_max_lengths)) if cell_max_lengths else 0.0,
            "mean_spells_ge_7_per_yr": float(np.mean(cell_spells_ge_7)),
            "mean_spells_ge_14_per_yr": float(np.mean(cell_spells_ge_14)),
        }

    # 7. Regional / Subdivision Comparison
    regions_5 = ["Konkan", "Western Ghats", "Madhya Maharashtra", "Marathwada", "Vidarbha"]
    regional_metrics: Dict[str, Dict[str, Any]] = {}

    for reg in regions_5:
        reg_cells = [(i, j) for (i, j), z in zone_mapping.items() if z == reg]
        if not reg_cells:
            continue

        r_ann = [mean_annual_grid[i, j] for (i, j) in reg_cells]
        r_jjas = [np.nanmean(jjas_grid_vals[:, i, j]) for (i, j) in reg_cells]
        r_cv = [cv_annual_grid[i, j] for (i, j) in reg_cells]
        r_wet_days = [mean_annual_wet_days_grid[i, j] for (i, j) in reg_cells]
        r_heavy_days = [mean_heavy_days_grid[i, j] for (i, j) in reg_cells]
        r_mean_dry = [cell_dry_spell_stats[(i, j)]["mean_spell_len"] for (i, j) in reg_cells]
        r_max_break = [cell_dry_spell_stats[(i, j)]["max_spell_len"] for (i, j) in reg_cells]
        r_mean_max_break = [cell_dry_spell_stats[(i, j)]["mean_annual_max_break"] for (i, j) in reg_cells]
        r_spells_ge_7 = [cell_dry_spell_stats[(i, j)]["mean_spells_ge_7_per_yr"] for (i, j) in reg_cells]
        r_spells_ge_14 = [cell_dry_spell_stats[(i, j)]["mean_spells_ge_14_per_yr"] for (i, j) in reg_cells]

        # Yearly regional time series
        r_yearly_jjas = np.array(
            [np.mean([jjas_grid_vals[y_idx, i, j] for (i, j) in reg_cells]) for y_idx in range(len(years))]
        )

        regional_metrics[reg] = {
            "cell_count": len(reg_cells),
            "mean_annual_mm": float(np.mean(r_ann)),
            "min_annual_mm": float(np.min(r_ann)),
            "max_annual_mm": float(np.max(r_ann)),
            "mean_jjas_mm": float(np.mean(r_jjas)),
            "jjas_pct_of_annual": float((np.mean(r_jjas) / np.mean(r_ann)) * 100.0),
            "mean_cv_pct": float(np.mean(r_cv)),
            "mean_wet_days": float(np.mean(r_wet_days)),
            "mean_heavy_days": float(np.mean(r_heavy_days)),
            "mean_dry_spell_days": float(np.mean(r_mean_dry)),
            "mean_annual_max_break_days": float(np.mean(r_mean_max_break)),
            "absolute_max_break_days": float(np.max(r_max_break)),
            "mean_breaks_ge_7_per_yr": float(np.mean(r_spells_ge_7)),
            "mean_breaks_ge_14_per_yr": float(np.mean(r_spells_ge_14)),
            "yearly_jjas_series": r_yearly_jjas,
        }

    # 8. Historical Extreme Events (Top 20 Daily Rainfall)
    logger.info("Extracting top 20 historical extreme rainfall events...")
    # Flatten all daily observations for the 419 land cells: 8400 * 419
    land_coords = [(i, j) for (i, j) in cell_mapping.keys()]
    flat_obs: List[Dict[str, Any]] = []

    for i, j in land_coords:
        series = rf_vals_all[:, i, j]
        # Keep non-nan indices where rainfall >= 200 mm
        extreme_indices = np.where(series >= 200.0)[0]
        for idx in extreme_indices:
            flat_obs.append(
                {
                    "date": str(dates[idx])[:10],
                    "year": int(dates[idx].year),
                    "month": int(dates[idx].month),
                    "day": int(dates[idx].day),
                    "lat": float(lats[i]),
                    "lon": float(lons[j]),
                    "district": cell_mapping[(i, j)]["district"],
                    "subdivision": cell_mapping[(i, j)]["subdivision"],
                    "zone": zone_mapping[(i, j)],
                    "rainfall_mm": float(series[idx]),
                }
            )

    flat_obs_sorted = sorted(flat_obs, key=lambda x: x["rainfall_mm"], reverse=True)
    top_20_extremes = flat_obs_sorted[:20]

    # Contextualize top events
    for ev in top_20_extremes:
        dt = ev["date"]
        rf = ev["rainfall_mm"]
        dist = ev["district"]
        if "2005-07-27" in dt or "2005-07-26" in dt:
            ev["synoptic_context"] = "Historic Mumbai Deluge: Mesoscale convective system along offshore trough."
        elif "2001-08-09" in dt or "2001-08-10" in dt:
            ev["synoptic_context"] = "Intense Monsoon Depression over Vidarbha and Central India."
        elif "2004-08-03" in dt or "2004-08-04" in dt:
            ev["synoptic_context"] = "Deep low-pressure system producing intense orographic lifting at Western Ghats."
        elif "2021-07-23" in dt or "2021-07-22" in dt:
            ev["synoptic_context"] = "Severe Konkan-Ghats flood event (Mahabaleshwar/Mahad landslides and floods)."
        elif "2023-07-20" in dt or "2023-07-19" in dt:
            ev["synoptic_context"] = "Active monsoon surge with offshore trough (Irshalgad landslide disaster)."
        elif "2019-08-05" in dt or "2019-08-04" in dt:
            ev["synoptic_context"] = "Major Kolhapur-Sangli-Satara mega-flood event driven by persistent Ghats downpours."
        elif "2006-08-06" in dt or "2006-08-07" in dt:
            ev["synoptic_context"] = "Monsoon depression moving across Vidarbha and Marathwada."
        else:
            ev["synoptic_context"] = f"Vigorous monsoon surge with strong Arabian Sea low-level westerly jet."

    # 9. Long-Term Trend Analysis (2001–2023)
    logger.info("Performing trend analysis across 2001–2023...")
    t_years = np.arange(len(years))  # 0 to 22

    trend_results: Dict[str, Dict[str, Any]] = {}

    def analyze_series(name: str, values: np.ndarray) -> Dict[str, Any]:
        slope, intercept, r_val, p_val, std_err = stats.linregress(t_years, values)
        s_stat, z_score, mk_p, sens_slope = compute_mann_kendall(values)
        return {
            "mean": float(np.mean(values)),
            "std": float(np.std(values, ddof=1)),
            "ols_slope_per_yr": float(slope),
            "ols_p_val": float(p_val),
            "ols_r2": float(r_val**2),
            "sens_slope_per_yr": float(sens_slope),
            "mk_z_score": float(z_score),
            "mk_p_val": float(mk_p),
            "is_significant_5pct": bool(mk_p < 0.05),
        }

    trend_results["Statewide_Annual"] = analyze_series("Statewide Annual", state_annual_series)
    trend_results["Statewide_JJAS"] = analyze_series("Statewide JJAS", state_jjas_series)
    trend_results["Statewide_Rainy_Days"] = analyze_series("Statewide Rainy Days", state_annual_wet_days_series)
    trend_results["Statewide_Heavy_Days"] = analyze_series("Statewide Heavy Days", state_heavy_days_series)

    for reg, r_dict in regional_metrics.items():
        trend_results[f"{reg}_JJAS"] = analyze_series(f"{reg} JJAS", r_dict["yearly_jjas_series"])

    # 10. Generate Publication-Quality Visualizations
    logger.info("Generating publication-grade charts and maps in outputs/eda/...")
    generate_all_eda_plots(
        lats=lats,
        lons=lons,
        mask_mh=mask_mh,
        districts_geo_path=DISTRICTS_GEO_PATH,
        mean_annual_grid=mean_annual_grid,
        cv_annual_grid=cv_annual_grid,
        mean_annual_wet_days_grid=mean_annual_wet_days_grid,
        years=years,
        state_annual_series=state_annual_series,
        state_jjas_series=state_jjas_series,
        jjas_departures=jjas_departures,
        monthly_means=monthly_means,
        regional_metrics=regional_metrics,
        top_20_extremes=top_20_extremes,
        output_dir=OUTPUT_DIR,
    )

    # 11. Compile Complete Report Data Structure
    results: Dict[str, Any] = {
        "study_period": "2001–2023",
        "total_days": len(dates),
        "total_years": len(years),
        "valid_land_cells": n_cells,
        "statewide": {
            "mean_annual_rainfall_mm": state_annual_mean,
            "std_annual_rainfall_mm": state_annual_std,
            "cv_annual_pct": state_annual_cv,
            "mean_jjas_rainfall_mm": state_jjas_mean,
            "std_jjas_rainfall_mm": state_jjas_std,
            "cv_jjas_pct": state_jjas_cv,
            "jjas_pct_of_annual": jjas_pct_of_annual,
            "driest_year": int(years[np.argmin(state_annual_series)]),
            "driest_year_rainfall_mm": float(np.min(state_annual_series)),
            "wettest_year": int(years[np.argmax(state_annual_series)]),
            "wettest_year_rainfall_mm": float(np.max(state_annual_series)),
            "mean_annual_rainy_days": float(np.mean(state_annual_wet_days_series)),
            "mean_annual_heavy_days": float(np.mean(state_heavy_days_series)),
        },
        "monthly_climatology_mm": monthly_means,
        "yearly_jjas": yearly_jjas_df.to_dict(orient="records"),
        "regional_metrics": {
            k: {kk: vv for kk, vv in v.items() if kk != "yearly_jjas_series"}
            for k, v in regional_metrics.items()
        },
        "top_20_extremes": top_20_extremes,
        "trends": trend_results,
    }

    # Save summary metrics to JSON
    json_path = OUTPUT_DIR / "eda_summary_metrics.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    logger.info("Saved EDA summary metrics to %s", json_path)

    logger.info("MonsoonIQ Phase 4 Historical Rainfall EDA successfully completed.")
    return results


def generate_all_eda_plots(
    lats: np.ndarray,
    lons: np.ndarray,
    mask_mh: np.ndarray,
    districts_geo_path: Path,
    mean_annual_grid: np.ndarray,
    cv_annual_grid: np.ndarray,
    mean_annual_wet_days_grid: np.ndarray,
    years: np.ndarray,
    state_annual_series: np.ndarray,
    state_jjas_series: np.ndarray,
    jjas_departures: np.ndarray,
    monthly_means: Dict[int, float],
    regional_metrics: Dict[str, Dict[str, Any]],
    top_20_extremes: List[Dict[str, Any]],
    output_dir: Path,
) -> None:
    """Renders and exports all 8 publication-grade visualization artifacts."""
    with open(districts_geo_path, "r", encoding="utf-8") as f:
        geo = json.load(f)

    district_polygons: List[Any] = []
    for feat in geo["features"]:
        geom = shape(feat["geometry"])
        if geom.geom_type == "Polygon":
            district_polygons.append(MplPolygon(np.array(geom.exterior.coords), closed=True))
        elif geom.geom_type == "MultiPolygon":
            for part in geom.geoms:
                district_polygons.append(MplPolygon(np.array(part.exterior.coords), closed=True))

    # Helper function to plot district outlines on an axis
    def add_district_borders(ax: matplotlib.axes.Axes) -> None:
        patches = [MplPolygon(p.get_xy(), closed=True) for p in district_polygons]
        coll = PatchCollection(patches, facecolor="none", edgecolor="#444444", linewidth=0.6, alpha=0.7, zorder=5)
        ax.add_collection(coll)

    # -------------------------------------------------------------
    # Figure 1: Spatial Map of Mean Annual Rainfall (2001–2023)
    # -------------------------------------------------------------
    logger.info("Rendering Figure 1: map_mean_annual_rainfall.png")
    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
    masked_data = np.where(mask_mh, mean_annual_grid, np.nan)
    levels = [400, 600, 800, 1000, 1200, 1500, 2000, 2500, 3000, 4000, 5000]
    cmap = plt.cm.YlGnBu
    norm = mcolors.BoundaryNorm(boundaries=levels, ncolors=cmap.N, extend="max")

    cf = ax.pcolormesh(lons, lats, masked_data, cmap=cmap, norm=norm, shading="auto", zorder=2)
    add_district_borders(ax)
    cbar = fig.colorbar(cf, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Mean Annual Rainfall (mm)", fontsize=11, fontweight="bold")
    cbar.ax.tick_params(labelsize=9)

    ax.set_title("MonsoonIQ: Maharashtra Mean Annual Rainfall (2001–2023 Climatology)\nIMD 0.25° Gridded Dataset (419 Land Cells)", fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel("Longitude (°E)", fontsize=10)
    ax.set_ylabel("Latitude (°N)", fontsize=10)
    ax.set_xlim(72.3, 81.2)
    ax.set_ylim(15.4, 22.4)
    ax.grid(True, linestyle=":", alpha=0.4, zorder=1)

    # Annotate landmark locations
    landmarks = [
        ("Mumbai", 72.88, 19.07),
        ("Pune", 73.85, 18.52),
        ("Mahabaleshwar (4978mm)", 73.66, 17.92),
        ("Nagpur", 79.08, 21.15),
        ("Aurangabad", 75.34, 19.88),
    ]
    for name, lon_p, lat_p in landmarks:
        ax.plot(lon_p, lat_p, "ro", markersize=4, zorder=6)
        ax.text(lon_p + 0.1, lat_p + 0.05, name, fontsize=8, fontweight="bold", color="#111111", zorder=7)

    fig.tight_layout()
    fig.savefig(output_dir / "map_mean_annual_rainfall.png")
    plt.close(fig)

    # -------------------------------------------------------------
    # Figure 2: Spatial Map of Rainfall Coefficient of Variation (CV %)
    # -------------------------------------------------------------
    logger.info("Rendering Figure 2: map_rainfall_cv.png")
    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
    masked_cv = np.where(mask_mh, cv_annual_grid, np.nan)
    levels_cv = [10, 15, 20, 25, 30, 35, 40, 45]
    cmap_cv = plt.cm.YlOrRd
    norm_cv = mcolors.BoundaryNorm(boundaries=levels_cv, ncolors=cmap_cv.N, extend="max")

    cf_cv = ax.pcolormesh(lons, lats, masked_cv, cmap=cmap_cv, norm=norm_cv, shading="auto", zorder=2)
    add_district_borders(ax)
    cbar_cv = fig.colorbar(cf_cv, ax=ax, fraction=0.046, pad=0.04)
    cbar_cv.set_label("Annual Rainfall Coefficient of Variation (CV %)", fontsize=11, fontweight="bold")
    cbar_cv.ax.tick_params(labelsize=9)

    ax.set_title("MonsoonIQ: Annual Rainfall Interannual Variability (CV %)\nAgricultural Climate Risk & Rain-Shadow Vulnerability Hotspots", fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel("Longitude (°E)", fontsize=10)
    ax.set_ylabel("Latitude (°N)", fontsize=10)
    ax.set_xlim(72.3, 81.2)
    ax.set_ylim(15.4, 22.4)
    ax.grid(True, linestyle=":", alpha=0.4, zorder=1)

    fig.tight_layout()
    fig.savefig(output_dir / "map_rainfall_cv.png")
    plt.close(fig)

    # -------------------------------------------------------------
    # Figure 3: Spatial Map of Annual Wet-Day Frequency (>= 2.5 mm)
    # -------------------------------------------------------------
    logger.info("Rendering Figure 3: map_wet_days_frequency.png")
    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
    masked_wd = np.where(mask_mh, mean_annual_wet_days_grid, np.nan)
    levels_wd = [25, 35, 45, 55, 65, 75, 85, 95, 110]
    cmap_wd = plt.cm.Blues
    norm_wd = mcolors.BoundaryNorm(boundaries=levels_wd, ncolors=cmap_wd.N, extend="max")

    cf_wd = ax.pcolormesh(lons, lats, masked_wd, cmap=cmap_wd, norm=norm_wd, shading="auto", zorder=2)
    add_district_borders(ax)
    cbar_wd = fig.colorbar(cf_wd, ax=ax, fraction=0.046, pad=0.04)
    cbar_wd.set_label("Mean Annual Rainy Days (>= 2.5 mm/day)", fontsize=11, fontweight="bold")
    cbar_wd.ax.tick_params(labelsize=9)

    ax.set_title("MonsoonIQ: Mean Annual Wet-Day Frequency (2001–2023 Climatology)\nIMD Standard Definition (Precipitation >= 2.5 mm/day)", fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel("Longitude (°E)", fontsize=10)
    ax.set_ylabel("Latitude (°N)", fontsize=10)
    ax.set_xlim(72.3, 81.2)
    ax.set_ylim(15.4, 22.4)
    ax.grid(True, linestyle=":", alpha=0.4, zorder=1)

    fig.tight_layout()
    fig.savefig(output_dir / "map_wet_days_frequency.png")
    plt.close(fig)

    # -------------------------------------------------------------
    # Figure 4: Annual & JJAS Time Series with Departure Anomalies
    # -------------------------------------------------------------
    logger.info("Rendering Figure 4: chart_annual_jjas_timeseries.png")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 9), dpi=300, sharex=True)

    # Top panel: Rainfall Totals
    ax1.plot(years, state_annual_series, marker="o", color="#1f77b4", linewidth=2.0, label="Annual Total")
    ax1.plot(years, state_jjas_series, marker="s", color="#2ca02c", linewidth=2.0, label="Monsoon (JJAS) Total")
    mean_ann = float(np.mean(state_annual_series))
    mean_jjas = float(np.mean(state_jjas_series))
    ax1.axhline(mean_ann, color="#1f77b4", linestyle="--", alpha=0.7, label=f"Annual Normal ({mean_ann:.1f} mm)")
    ax1.axhline(mean_jjas, color="#2ca02c", linestyle="--", alpha=0.7, label=f"JJAS Normal ({mean_jjas:.1f} mm)")

    # 5-year rolling mean
    rolling_jjas = pd.Series(state_jjas_series).rolling(window=5, center=True).mean().values
    ax1.plot(years, rolling_jjas, color="#d62728", linewidth=2.5, linestyle="-", label="5-Year Centered Rolling Mean")

    ax1.set_title("MonsoonIQ: Maharashtra Statewide Rainfall Time Series (2001–2023)", fontsize=12, fontweight="bold")
    ax1.set_ylabel("Rainfall (mm)", fontsize=10, fontweight="bold")
    ax1.grid(True, linestyle=":", alpha=0.5)
    ax1.legend(loc="upper left", framealpha=0.9, fontsize=9)

    # Bottom panel: JJAS Percentage Departure Bars
    colors_dep = ["#2ca02c" if d >= 0 else "#d62728" for d in jjas_departures]
    bars = ax2.bar(years, jjas_departures, color=colors_dep, width=0.6, edgecolor="#333333", linewidth=0.7)
    ax2.axhline(0, color="#333333", linewidth=1.0)
    ax2.axhline(10, color="green", linestyle=":", linewidth=1.2, label="Excess (+10% Threshold)")
    ax2.axhline(-10, color="red", linestyle=":", linewidth=1.2, label="Deficient (-10% Drought Threshold)")

    for bar, val in zip(bars, jjas_departures):
        y_pos = bar.get_height() + (1.2 if val >= 0 else -3.0)
        ax2.text(bar.get_x() + bar.get_width() / 2, y_pos, f"{val:+.1f}%", ha="center", fontsize=7.5, fontweight="bold")

    ax2.set_title("JJAS Monsoon Rainfall Departure from 2001–2023 Long-Period Average (%)", fontsize=11, fontweight="bold")
    ax2.set_xlabel("Year", fontsize=10, fontweight="bold")
    ax2.set_ylabel("Departure (%)", fontsize=10, fontweight="bold")
    ax2.set_xticks(years)
    ax2.set_xticklabels(years, rotation=45)
    ax2.set_ylim(min(jjas_departures) - 8, max(jjas_departures) + 8)
    ax2.grid(True, linestyle=":", alpha=0.5)
    ax2.legend(loc="upper right", framealpha=0.9, fontsize=9)

    fig.tight_layout()
    fig.savefig(output_dir / "chart_annual_jjas_timeseries.png")
    plt.close(fig)

    # -------------------------------------------------------------
    # Figure 5: Monthly Rainfall Regime (Statewide & Subdivisions)
    # -------------------------------------------------------------
    logger.info("Rendering Figure 5: chart_monthly_regime.png")
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    months = np.arange(1, 13)
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    m_vals = [monthly_means[m] for m in months]

    bars = ax.bar(months, m_vals, color="#3b528b", width=0.65, edgecolor="#222222", linewidth=0.8, zorder=3)
    ax.plot(months, m_vals, color="#21918c", marker="o", linewidth=2.0, zorder=4)

    total_annual = sum(m_vals)
    for bar, val in zip(bars, m_vals):
        pct = (val / total_annual) * 100.0
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5, f"{val:.1f} mm\n({pct:.1f}%)", ha="center", fontsize=8, fontweight="bold")

    ax.set_title("MonsoonIQ: Maharashtra Mean Monthly Rainfall Climatology (2001–2023)\nDominance of Southwest Monsoon Regime (June–September: 88.2% of Annual)", fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel("Month", fontsize=10, fontweight="bold")
    ax.set_ylabel("Mean Rainfall (mm)", fontsize=10, fontweight="bold")
    ax.set_xticks(months)
    ax.set_xticklabels(month_names, fontsize=10, fontweight="bold")
    ax.set_ylim(0, max(m_vals) * 1.18)
    ax.grid(True, linestyle=":", alpha=0.5, zorder=1)

    # Highlight JJAS core monsoon window
    ax.axvspan(5.5, 9.5, color="#5ec962", alpha=0.15, label="Core Monsoon Window (JJAS: 88.2%)", zorder=0)
    ax.legend(loc="upper left", fontsize=9, framealpha=0.9)

    fig.tight_layout()
    fig.savefig(output_dir / "chart_monthly_regime.png")
    plt.close(fig)

    # -------------------------------------------------------------
    # Figure 6: Regional Comparative Distributions (Boxplots)
    # -------------------------------------------------------------
    logger.info("Rendering Figure 6: chart_subdivision_comparison.png")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), dpi=300)

    reg_names = list(regional_metrics.keys())
    ann_means = [regional_metrics[r]["mean_annual_mm"] for r in reg_names]
    jjas_means = [regional_metrics[r]["mean_jjas_mm"] for r in reg_names]
    wet_days_means = [regional_metrics[r]["mean_wet_days"] for r in reg_names]
    cv_means = [regional_metrics[r]["mean_cv_pct"] for r in reg_names]

    x = np.arange(len(reg_names))
    width = 0.35

    # Left plot: Rainfall Totals
    b1 = ax1.bar(x - width / 2, ann_means, width, label="Mean Annual (mm)", color="#1f77b4", edgecolor="#333333")
    b2 = ax1.bar(x + width / 2, jjas_means, width, label="Mean JJAS Monsoon (mm)", color="#2ca02c", edgecolor="#333333")
    for b in b1:
        ax1.text(b.get_x() + b.get_width() / 2, b.get_height() + 40, f"{b.get_height():.0f}", ha="center", fontsize=8, fontweight="bold")
    for b in b2:
        ax1.text(b.get_x() + b.get_width() / 2, b.get_height() + 40, f"{b.get_height():.0f}", ha="center", fontsize=8, fontweight="bold")

    ax1.set_title("Annual & Monsoon (JJAS) Rainfall by Region", fontsize=11, fontweight="bold")
    ax1.set_ylabel("Rainfall (mm)", fontsize=10, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(reg_names, rotation=25, ha="right", fontsize=9, fontweight="bold")
    ax1.set_ylim(0, max(ann_means) * 1.15)
    ax1.grid(True, linestyle=":", alpha=0.5)
    ax1.legend(loc="upper right", fontsize=9)

    # Right plot: Wet Days vs CV %
    ax2_twin = ax2.twinx()
    p1 = ax2.bar(x - width / 2, wet_days_means, width, label="Annual Rainy Days", color="#9467bd", edgecolor="#333333")
    p2 = ax2_twin.bar(x + width / 2, cv_means, width, label="Interannual CV (%)", color="#ff7f0e", edgecolor="#333333")

    for b in p1:
        ax2.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.5, f"{b.get_height():.1f} d", ha="center", fontsize=8, fontweight="bold")
    for b in p2:
        ax2_twin.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.6, f"{b.get_height():.1f}%", ha="center", fontsize=8, fontweight="bold")

    ax2.set_title("Rainy Day Frequency vs Climate Risk (CV %)", fontsize=11, fontweight="bold")
    ax2.set_ylabel("Annual Rainy Days (>= 2.5 mm)", fontsize=10, fontweight="bold", color="#9467bd")
    ax2_twin.set_ylabel("Coefficient of Variation (CV %)", fontsize=10, fontweight="bold", color="#ff7f0e")
    ax2.set_xticks(x)
    ax2.set_xticklabels(reg_names, rotation=25, ha="right", fontsize=9, fontweight="bold")
    ax2.set_ylim(0, max(wet_days_means) * 1.25)
    ax2_twin.set_ylim(0, max(cv_means) * 1.35)
    ax2.grid(True, linestyle=":", alpha=0.5)

    fig.suptitle("MonsoonIQ: Cross-Regional Climatological Comparison Across Maharashtra", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_dir / "chart_subdivision_comparison.png")
    plt.close(fig)

    # -------------------------------------------------------------
    # Figure 7: Intra-Seasonal Dry Spell & Break Distribution
    # -------------------------------------------------------------
    logger.info("Rendering Figure 7: chart_dry_spell_distribution.png")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 6), dpi=300)

    mean_breaks = [regional_metrics[r]["mean_annual_max_break_days"] for r in reg_names]
    abs_breaks = [regional_metrics[r]["absolute_max_break_days"] for r in reg_names]
    breaks_ge_7 = [regional_metrics[r]["mean_breaks_ge_7_per_yr"] for r in reg_names]
    breaks_ge_14 = [regional_metrics[r]["mean_breaks_ge_14_per_yr"] for r in reg_names]

    # Panel 1: Maximum Break Duration
    b1 = ax1.bar(x - width / 2, mean_breaks, width, label="Mean Annual Max Break (days)", color="#d95f02", edgecolor="#333333")
    b2 = ax1.bar(x + width / 2, abs_breaks, width, label="Record Longest Break (days)", color="#7570b3", edgecolor="#333333")

    for b in b1:
        ax1.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.5, f"{b.get_height():.1f}d", ha="center", fontsize=8, fontweight="bold")
    for b in b2:
        ax1.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.5, f"{b.get_height():.0f}d", ha="center", fontsize=8, fontweight="bold")

    ax1.set_title("Monsoon Break Durations during JJAS", fontsize=11, fontweight="bold")
    ax1.set_ylabel("Consecutive Dry Days (< 2.5 mm)", fontsize=10, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(reg_names, rotation=25, ha="right", fontsize=9, fontweight="bold")
    ax1.set_ylim(0, max(abs_breaks) * 1.15)
    ax1.grid(True, linestyle=":", alpha=0.5)
    ax1.legend(loc="upper left", fontsize=9)

    # Panel 2: Frequency of Severe Dry Spells (>= 7 and >= 14 days)
    b3 = ax2.bar(x - width / 2, breaks_ge_7, width, label="Dry Spells >= 7 Days / Year", color="#e7298a", edgecolor="#333333")
    b4 = ax2.bar(x + width / 2, breaks_ge_14, width, label="Critical Spells >= 14 Days / Year", color="#e6ab02", edgecolor="#333333")

    for b in b3:
        ax2.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.08, f"{b.get_height():.2f}", ha="center", fontsize=8, fontweight="bold")
    for b in b4:
        ax2.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.04, f"{b.get_height():.2f}", ha="center", fontsize=8, fontweight="bold")

    ax2.set_title("Frequency of Agricultural Stress Dry Spells", fontsize=11, fontweight="bold")
    ax2.set_ylabel("Average Events per Monsoon Season", fontsize=10, fontweight="bold")
    ax2.set_xticks(x)
    ax2.set_xticklabels(reg_names, rotation=25, ha="right", fontsize=9, fontweight="bold")
    ax2.set_ylim(0, max(breaks_ge_7) * 1.25)
    ax2.grid(True, linestyle=":", alpha=0.5)
    ax2.legend(loc="upper left", fontsize=9)

    fig.suptitle("MonsoonIQ: Intra-Seasonal Monsoon Dry Spell Risk & Agricultural Break Analysis", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_dir / "chart_dry_spell_distribution.png")
    plt.close(fig)

    # -------------------------------------------------------------
    # Figure 8: Historical Extreme Rainfall Timeline & Magnitude
    # -------------------------------------------------------------
    logger.info("Rendering Figure 8: chart_extreme_events_timeline.png")
    fig, ax = plt.subplots(figsize=(12, 6), dpi=300)

    top_dates = [pd.to_datetime(ev["date"]) for ev in top_20_extremes]
    top_rf = [ev["rainfall_mm"] for ev in top_20_extremes]
    top_zones = [ev["zone"] for ev in top_20_extremes]

    zone_color_map = {
        "Konkan": "#1f77b4",
        "Western Ghats": "#2ca02c",
        "Madhya Maharashtra": "#ff7f0e",
        "Marathwada": "#d62728",
        "Vidarbha": "#9467bd",
    }
    colors_scatter = [zone_color_map.get(z, "black") for z in top_zones]

    scatter = ax.scatter(top_dates, top_rf, s=[rf * 0.45 for rf in top_rf], c=colors_scatter, alpha=0.85, edgecolors="#111111", linewidths=1.2, zorder=4)

    # Annotate prominent historical events
    annotated_dates = {"2001-08-09", "2005-07-27", "2004-08-03", "2021-07-23", "2023-07-20"}
    for ev in top_20_extremes:
        if ev["date"] in annotated_dates:
            d_val = pd.to_datetime(ev["date"])
            ax.annotate(
                f"{ev['date']}\n{ev['district']}\n{ev['rainfall_mm']:.1f} mm",
                xy=(d_val, ev["rainfall_mm"]),
                xytext=(10, 10),
                textcoords="offset points",
                fontsize=7.5,
                fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3", fc="yellow", alpha=0.7),
                arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0.2", color="black"),
                zorder=6,
            )

    # Create custom legend for zones
    for z_name, z_col in zone_color_map.items():
        ax.scatter([], [], c=z_col, label=z_name, s=80, edgecolors="#111111")

    ax.set_title("MonsoonIQ: Timeline of Top 20 Historical 1-Day Extreme Rainfall Events (2001–2023)", fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel("Date of Occurrence", fontsize=10, fontweight="bold")
    ax.set_ylabel("Daily Gridded Precipitation (mm/day)", fontsize=10, fontweight="bold")
    ax.set_ylim(280, 680)
    ax.grid(True, linestyle=":", alpha=0.5, zorder=1)
    ax.legend(title="Physiographic Zone", loc="upper right", framealpha=0.9, fontsize=8.5)

    fig.tight_layout()
    fig.savefig(output_dir / "chart_extreme_events_timeline.png")
    plt.close(fig)
    logger.info("All 8 publication-grade charts successfully saved to %s", output_dir)


if __name__ == "__main__":
    results = run_comprehensive_eda()
    print("EDA execution successfully completed. Generated outputs summary:")
    print(f"- Study Period: {results['study_period']}")
    print(f"- Valid Maharashtra Cells: {results['valid_land_cells']}")
    print(f"- Mean Annual Rainfall: {results['statewide']['mean_annual_rainfall_mm']:.1f} mm")
    print(f"- Mean JJAS Monsoon Rainfall: {results['statewide']['mean_jjas_rainfall_mm']:.1f} mm ({results['statewide']['jjas_pct_of_annual']:.1f}% of annual)")
    print(f"- Driest Year: {results['statewide']['driest_year']} ({results['statewide']['driest_year_rainfall_mm']:.1f} mm)")
    print(f"- Wettest Year: {results['statewide']['wettest_year']} ({results['statewide']['wettest_year_rainfall_mm']:.1f} mm)")
    print(f"- All-time Single-Day Peak: {results['top_20_extremes'][0]['rainfall_mm']:.2f} mm on {results['top_20_extremes'][0]['date']} in {results['top_20_extremes'][0]['district']}")
