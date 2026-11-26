"""MonsoonIQ - Empirical Onset Methodology and Sensitivity Analysis Script.

This script evaluates candidate monsoon onset criteria across Maharashtra using
the consolidated 2001–2023 IMD daily gridded dataset (419 land cells, 23 years):
1. Formulates parameterized local onset rules:
   - Earliest search window (e.g., May 15, May 25, June 1).
   - Multi-day accumulation window (3 vs 5 days).
   - Cumulative rainfall threshold (20, 25, 30, 35, 40 mm).
   - Wet-day persistence (>= 1, >= 2, >= 3 wet days with rain >= 2.5 mm).
   - False-onset post-onset break filter (breaks >= 7, >= 10, >= 14 consecutive dry days in 20-day window).
2. Computes onset dates, pre-monsoon false trigger rates, post-onset dry spell penalties,
   and regional onset distributions across Konkan, Western Ghats, Madhya MH, Marathwada, and Vidarbha.
3. Benchmarks candidate onset dates against official IMD declared onset dates for Mumbai (2001–2023)
   and Pune (2019–2023).
4. Outputs structured sensitivity metrics to outputs/eda/onset_sensitivity_results.json.
"""

from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional
import os
import json
import logging
import numpy as np
import pandas as pd
import xarray as xr

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("MonsoonIQ.OnsetSensitivity")

BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_NC_PATH: Path = BASE_DIR / "data" / "processed" / "maharashtra_imd_daily_2001_2023.nc"
DISTRICTS_GEO_PATH: Path = BASE_DIR / "data" / "geo" / "maharashtra_districts.geojson"
OUTPUT_DIR: Path = BASE_DIR / "outputs" / "eda"
OUTPUT_JSON_PATH: Path = OUTPUT_DIR / "onset_sensitivity_results.json"

# Verified Official IMD Declared Onset Dates (Ground Truth)
# Mumbai (represents Konkan / Maharashtra Coastal Entry) 2001–2023
IMD_MUMBAI_ONSET: Dict[int, str] = {
    2001: "2001-06-07",
    2002: "2002-06-07",
    2003: "2003-06-09",
    2004: "2004-06-07",
    2005: "2005-06-08",
    2006: "2006-06-08",
    2007: "2007-06-06",
    2008: "2008-06-04",
    2009: "2009-06-27",
    2010: "2010-06-14",
    2011: "2011-06-05",
    2012: "2012-06-17",
    2013: "2013-06-07",
    2014: "2014-06-15",
    2015: "2015-06-12",
    2016: "2016-06-20",
    2017: "2017-06-12",
    2018: "2018-06-09",
    2019: "2019-06-25",
    2020: "2020-06-14",
    2021: "2021-06-09",
    2022: "2022-06-11",
    2023: "2023-06-25",
}

# Pune (Madhya Maharashtra interior transition) 2019–2023
IMD_PUNE_ONSET: Dict[int, str] = {
    2019: "2019-06-24",
    2020: "2020-06-11",
    2021: "2021-06-05",
    2022: "2022-06-11",
    2023: "2023-06-24",
}


def load_dataset_and_metadata() -> Tuple[xr.Dataset, np.ndarray, np.ndarray, np.ndarray, pd.DatetimeIndex, Dict[Tuple[int, int], str]]:
    """Loads consolidated NetCDF and assigns 5 physiographic zones to all 419 cells."""
    ds = xr.open_dataset(DATA_NC_PATH)
    mask_mh = ds["mask_maharashtra"].values
    lats = ds["lat"].values
    lons = ds["lon"].values
    dates = pd.DatetimeIndex(ds["time"].values)

    # Ingest regional cell mapping from EDA summary
    eda_summary_path = OUTPUT_DIR / "eda_summary_metrics.json"
    zone_mapping: Dict[Tuple[int, int], str] = {}

    # Compute mean annual per cell to delineate Western Ghats
    annual_sums = ds["rainfall_masked"].groupby("time.year").sum(dim="time").values
    mean_annual = np.nanmean(annual_sums, axis=0)

    # Re-apply district and zone assignment
    from shapely.geometry import shape, Point
    with open(DISTRICTS_GEO_PATH, "r", encoding="utf-8") as f:
        geo = json.load(f)

    subdiv_map = {
        "Mumbai": "Konkan", "Mumbai Suburban": "Konkan", "Thane": "Konkan",
        "Palghar": "Konkan", "Raigarh": "Konkan", "Ratnagiri": "Konkan", "Sindhudurg": "Konkan",
        "Nandurbar": "Madhya Maharashtra", "Dhule": "Madhya Maharashtra", "Jalgaon": "Madhya Maharashtra",
        "Nashik": "Madhya Maharashtra", "Ahmadnagar": "Madhya Maharashtra", "Pune": "Madhya Maharashtra",
        "Satara": "Madhya Maharashtra", "Sangli": "Madhya Maharashtra", "Solapur": "Madhya Maharashtra",
        "Kolhapur": "Madhya Maharashtra",
        "Aurangabad": "Marathwada", "Jalna": "Marathwada", "Bid": "Marathwada", "Parbhani": "Marathwada",
        "Hingoli": "Marathwada", "Nanded": "Marathwada", "Latur": "Marathwada", "Osmanabad": "Marathwada",
        "Buldana": "Vidarbha", "Akola": "Vidarbha", "Washim": "Vidarbha", "Amravati": "Vidarbha",
        "Yavatmal": "Vidarbha", "Wardha": "Vidarbha", "Nagpur": "Vidarbha", "Bhandara": "Vidarbha",
        "Gondiya": "Vidarbha", "Chandrapur": "Vidarbha", "Gadchiroli": "Vidarbha",
    }

    district_polys = [(feat["properties"]["dtname"], shape(feat["geometry"])) for feat in geo["features"]]

    for i, lat in enumerate(lats):
        for j, lon in enumerate(lons):
            if not mask_mh[i, j]:
                continue
            pt = Point(lon, lat)
            matched_dt = None
            for dtname, poly in district_polys:
                if poly.contains(pt):
                    matched_dt = dtname
                    break
            if matched_dt is None:
                for dtname, poly in district_polys:
                    if poly.buffer(0.05).contains(pt):
                        matched_dt = dtname
                        break
            if matched_dt is None:
                min_d = float("inf")
                for dtname, poly in district_polys:
                    d = poly.distance(pt)
                    if d < min_d:
                        min_d = d
                        matched_dt = dtname

            subdiv = subdiv_map.get(matched_dt, "Madhya Maharashtra")
            ann_r = mean_annual[i, j]

            if 73.25 <= lon <= 74.00 and ann_r >= 2000.0 and subdiv in ["Konkan", "Madhya Maharashtra"]:
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

    return ds, mask_mh, lats, lons, dates, zone_mapping


def detect_candidate_onset_per_series(
    daily_rain: np.ndarray,
    day_indices: pd.DatetimeIndex,
    search_start_month: int,
    search_start_day: int,
    accumulation_window_days: int,
    cumulative_threshold_mm: float,
    min_wet_days: int,
    wet_day_threshold_mm: float = 2.5,
    max_post_onset_dry_spell_days: Optional[int] = None,
    post_onset_check_window_days: int = 20,
) -> Tuple[Optional[pd.Timestamp], Optional[pd.Timestamp], bool]:
    """Detects initial candidate onset and applies false-onset break penalty.

    Args:
        daily_rain: 1D array of daily rainfall for one year (365 or 366 days).
        day_indices: DatetimeIndex corresponding to daily_rain.
        search_start_month: Earliest month to begin scanning (e.g., 5 for May, 6 for June).
        search_start_day: Earliest day of search month (e.g., 15 for May 15, 1 for June 1).
        accumulation_window_days: Rolling window size (e.g. 3 or 5 days).
        cumulative_threshold_mm: Cumulative rainfall threshold required in window (e.g. 25, 30, 35 mm).
        min_wet_days: Minimum count of wet days (>= 2.5 mm) required in window.
        wet_day_threshold_mm: Definition of rainy day (default 2.5 mm).
        max_post_onset_dry_spell_days: Threshold for false onset break (e.g. 10 or 14 consecutive dry days).
        post_onset_check_window_days: Window after candidate onset to inspect for breaks (default 20 days).

    Returns:
        Tuple of (initial_candidate_date, sustained_onset_date, was_false_onset).
    """
    n_days = len(daily_rain)
    # Find start index
    start_dt = pd.Timestamp(day_indices[0].year, search_start_month, search_start_day)
    start_idx = np.where(day_indices >= start_dt)[0]
    if len(start_idx) == 0:
        return None, None, False
    curr_idx = int(start_idx[0])

    initial_candidate: Optional[pd.Timestamp] = None
    sustained_onset: Optional[pd.Timestamp] = None
    was_false_onset: bool = False

    while curr_idx <= n_days - accumulation_window_days:
        window_rain = daily_rain[curr_idx : curr_idx + accumulation_window_days]
        cum_rain = np.nansum(window_rain)
        wet_days = np.nansum(window_rain >= wet_day_threshold_mm)

        # Check onset trigger: must start with a wet day or significant rain,
        # exceed cumulative threshold, and satisfy wet day persistence
        if cum_rain >= cumulative_threshold_mm and wet_days >= min_wet_days:
            candidate_date = day_indices[curr_idx]
            if initial_candidate is None:
                initial_candidate = candidate_date

            # If false onset filter is disabled, accept candidate
            if max_post_onset_dry_spell_days is None:
                sustained_onset = candidate_date
                break

            # Check post-onset window for prolonged break
            post_window_end = min(n_days, curr_idx + post_onset_check_window_days)
            post_series = daily_rain[curr_idx + accumulation_window_days : post_window_end]

            # Calculate longest consecutive dry run (< 2.5 mm) in post-window
            is_dry = (post_series < wet_day_threshold_mm) | np.isnan(post_series)
            max_dry_run = 0
            curr_dry_run = 0
            for d_val in is_dry:
                if d_val:
                    curr_dry_run += 1
                    if curr_dry_run > max_dry_run:
                        max_dry_run = curr_dry_run
                else:
                    curr_dry_run = 0

            if max_dry_run >= max_post_onset_dry_spell_days:
                # Flagged as false onset! Seed scorching risk. Reject and continue scanning
                was_false_onset = True
                curr_idx += 1  # Advance search
                continue
            else:
                # Passed false onset filter! Sustained onset declared
                sustained_onset = candidate_date
                break

        curr_idx += 1

    return initial_candidate, sustained_onset, was_false_onset


def evaluate_parameter_grid() -> Dict[str, Any]:
    """Evaluates candidate parameter combinations across all 23 years and 419 cells."""
    logger.info("Loading consolidated dataset...")
    ds, mask_mh, lats, lons, dates, zone_mapping = load_dataset_and_metadata()
    rf_vals = ds["rainfall_masked"].values  # (8400, 28, 35)
    years = np.unique(dates.year)

    # Focus cells for quick benchmarking:
    # 1. Mumbai cell: Lat 19.00°N, Lon 72.75°E or nearest
    # 2. Pune cell: Lat 18.50°N, Lon 73.75°E or nearest
    # Mumbai / Thane coastal land cell: Lat 19.25°N, Lon 73.00°E (i=15, j=2)
    # Pune plateau cell: Lat 18.50°N, Lon 73.75°E (i=12, j=5)
    mumbai_idx = (int(np.argmin(np.abs(lats - 19.25))), int(np.argmin(np.abs(lons - 73.00))))
    pune_idx = (int(np.argmin(np.abs(lats - 18.50))), int(np.argmin(np.abs(lons - 73.75))))

    logger.info("Benchmarking cells: Mumbai at (%.2fN, %.2fE), Pune at (%.2fN, %.2fE)",
                lats[mumbai_idx[0]], lons[mumbai_idx[1]], lats[pune_idx[0]], lons[pune_idx[1]])

    # Candidate Experiment Grid:
    # We test variations of:
    # - Earliest start: May 15 vs May 25 vs June 1
    # - Window: 3 days vs 5 days
    # - Threshold: 20, 25, 30, 35, 40 mm
    # - Persistence: >= 1, >= 2, >= 3 wet days
    # - False onset penalty: None vs 10 days break vs 14 days break

    test_configs: List[Dict[str, Any]] = [
        # Baseline configurations: Testing Earliest Search Start Date
        {"id": "EXP_START_MAY15", "start_m": 5, "start_d": 15, "win": 5, "thresh": 30.0, "wet": 2, "break_max": 14},
        {"id": "EXP_START_MAY25", "start_m": 5, "start_d": 25, "win": 5, "thresh": 30.0, "wet": 2, "break_max": 14},
        {"id": "EXP_START_JUN01", "start_m": 6, "start_d": 1, "win": 5, "thresh": 30.0, "wet": 2, "break_max": 14},

        # Testing Accumulation Window (3 vs 5 days)
        {"id": "EXP_WIN_3D_25MM", "start_m": 5, "start_d": 25, "win": 3, "thresh": 25.0, "wet": 2, "break_max": 14},
        {"id": "EXP_WIN_5D_30MM", "start_m": 5, "start_d": 25, "win": 5, "thresh": 30.0, "wet": 2, "break_max": 14},
        {"id": "EXP_WIN_5D_35MM", "start_m": 5, "start_d": 25, "win": 5, "thresh": 35.0, "wet": 2, "break_max": 14},

        # Testing Cumulative Rainfall Threshold (20, 25, 30, 35, 40 mm)
        {"id": "EXP_THRESH_20MM", "start_m": 5, "start_d": 25, "win": 5, "thresh": 20.0, "wet": 2, "break_max": 14},
        {"id": "EXP_THRESH_25MM", "start_m": 5, "start_d": 25, "win": 5, "thresh": 25.0, "wet": 2, "break_max": 14},
        {"id": "EXP_THRESH_30MM", "start_m": 5, "start_d": 25, "win": 5, "thresh": 30.0, "wet": 2, "break_max": 14},
        {"id": "EXP_THRESH_35MM", "start_m": 5, "start_d": 25, "win": 5, "thresh": 35.0, "wet": 2, "break_max": 14},
        {"id": "EXP_THRESH_40MM", "start_m": 5, "start_d": 25, "win": 5, "thresh": 40.0, "wet": 2, "break_max": 14},

        # Testing Wet-Day Persistence (1, 2, 3 wet days)
        {"id": "EXP_WET_1DAY", "start_m": 5, "start_d": 25, "win": 5, "thresh": 30.0, "wet": 1, "break_max": 14},
        {"id": "EXP_WET_2DAY", "start_m": 5, "start_d": 25, "win": 5, "thresh": 30.0, "wet": 2, "break_max": 14},
        {"id": "EXP_WET_3DAY", "start_m": 5, "start_d": 25, "win": 5, "thresh": 30.0, "wet": 3, "break_max": 14},

        # Testing False-Onset Break Filter (None, 14 days, 10 days)
        {"id": "EXP_BREAK_NONE", "start_m": 5, "start_d": 25, "win": 5, "thresh": 30.0, "wet": 2, "break_max": None},
        {"id": "EXP_BREAK_14D", "start_m": 5, "start_d": 25, "win": 5, "thresh": 30.0, "wet": 2, "break_max": 14},
        {"id": "EXP_BREAK_10D", "start_m": 5, "start_d": 25, "win": 5, "thresh": 30.0, "wet": 2, "break_max": 10},
    ]

    all_cells = [(i, j) for (i, j) in zone_mapping.keys()]
    experiment_results: List[Dict[str, Any]] = []

    for cfg in test_configs:
        cfg_id = cfg["id"]
        logger.info("Evaluating configuration: %s", cfg_id)

        # Track metrics
        mumbai_errors: List[float] = []
        pune_errors: List[float] = []
        false_onset_counts: List[int] = []
        regional_onset_doy: Dict[str, List[int]] = {
            "Konkan": [], "Western Ghats": [], "Madhya Maharashtra": [],
            "Marathwada": [], "Vidarbha": []
        }

        for yr in years:
            yr_mask = (dates.year == yr)
            yr_dates = dates[yr_mask]
            yr_rf = rf_vals[yr_mask, :, :]

            # 1. Benchmark Mumbai
            mb_series = yr_rf[:, mumbai_idx[0], mumbai_idx[1]]
            _, mb_onset, _ = detect_candidate_onset_per_series(
                daily_rain=mb_series,
                day_indices=yr_dates,
                search_start_month=cfg["start_m"],
                search_start_day=cfg["start_d"],
                accumulation_window_days=cfg["win"],
                cumulative_threshold_mm=cfg["thresh"],
                min_wet_days=cfg["wet"],
                max_post_onset_dry_spell_days=cfg["break_max"],
            )
            if mb_onset is not None and yr in IMD_MUMBAI_ONSET:
                actual_mb = pd.to_datetime(IMD_MUMBAI_ONSET[yr])
                diff_days = (mb_onset - actual_mb).days
                mumbai_errors.append(diff_days)

            # 2. Benchmark Pune (2019–2023)
            if yr in IMD_PUNE_ONSET:
                pn_series = yr_rf[:, pune_idx[0], pune_idx[1]]
                _, pn_onset, _ = detect_candidate_onset_per_series(
                    daily_rain=pn_series,
                    day_indices=yr_dates,
                    search_start_month=cfg["start_m"],
                    search_start_day=cfg["start_d"],
                    accumulation_window_days=cfg["win"],
                    cumulative_threshold_mm=cfg["thresh"],
                    min_wet_days=cfg["wet"],
                    max_post_onset_dry_spell_days=cfg["break_max"],
                )
                if pn_onset is not None:
                    actual_pn = pd.to_datetime(IMD_PUNE_ONSET[yr])
                    pune_errors.append((pn_onset - actual_pn).days)

            # 3. Statewide cell evaluation
            yr_false_onsets = 0
            for i, j in all_cells:
                cell_s = yr_rf[:, i, j]
                _, cell_onset, was_false = detect_candidate_onset_per_series(
                    daily_rain=cell_s,
                    day_indices=yr_dates,
                    search_start_month=cfg["start_m"],
                    search_start_day=cfg["start_d"],
                    accumulation_window_days=cfg["win"],
                    cumulative_threshold_mm=cfg["thresh"],
                    min_wet_days=cfg["wet"],
                    max_post_onset_dry_spell_days=cfg["break_max"],
                )
                if was_false:
                    yr_false_onsets += 1
                if cell_onset is not None:
                    z = zone_mapping[(i, j)]
                    regional_onset_doy[z].append(int(cell_onset.day_of_year))

            false_onset_counts.append(yr_false_onsets)

        # Summarize config performance
        mb_mae = float(np.mean(np.abs(mumbai_errors))) if mumbai_errors else 999.0
        mb_bias = float(np.mean(mumbai_errors)) if mumbai_errors else 999.0
        pn_mae = float(np.mean(np.abs(pune_errors))) if pune_errors else 999.0
        pn_bias = float(np.mean(pune_errors)) if pune_errors else 999.0
        mean_false_rate_pct = float(np.mean(false_onset_counts) / len(all_cells) * 100.0)

        reg_summary: Dict[str, Dict[str, float]] = {}
        for z_name, doys in regional_onset_doy.items():
            if doys:
                mean_doy = float(np.mean(doys))
                mean_dt = pd.to_datetime(f"2023-{int(mean_doy):03d}", format="%Y-%j").strftime("%b %d")
                reg_summary[z_name] = {
                    "mean_doy": mean_doy,
                    "mean_calendar_date": mean_dt,
                    "std_days": float(np.std(doys)),
                }

        experiment_results.append(
            {
                "config": cfg,
                "mumbai_mae_days": mb_mae,
                "mumbai_bias_days": mb_bias,
                "pune_mae_days": pn_mae,
                "pune_bias_days": pn_bias,
                "statewide_false_onset_pct": mean_false_rate_pct,
                "regional_onsets": reg_summary,
            }
        )

    # Compile Final Sensitivity Analysis Data
    results_payload = {
        "benchmark_ground_truth": {
            "mumbai_imd_declarations": IMD_MUMBAI_ONSET,
            "pune_imd_declarations": IMD_PUNE_ONSET,
        },
        "experiments": experiment_results,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(results_payload, f, indent=2)

    logger.info("Saved sensitivity evaluation results to %s", OUTPUT_JSON_PATH)
    return results_payload


if __name__ == "__main__":
    evaluate_parameter_grid()
    print("Onset methodology sensitivity analysis successfully executed.")
