"""MonsoonIQ - Phase 7 Regime Interpretation & Agricultural Relevance Validation.

Performs independent scientific interpretation and agricultural relevance validation
of the four discovered Maharashtra monsoon onset regimes:
1. Calculates complete profile statistics across the four regimes.
2. Extracts independent historical agricultural rainfall indicators from raw daily NetCDF:
   - June rainfall total (mm) and June interannual CV (%)
   - June-July rainfall and rainy day counts
   - Early-season (June 1 - July 15) maximum dry spells (< 2.5 mm)
   - 50 mm cumulative sowing trigger DOY and delay frequency past July 1
   - Decadal volatility persistence (2001-2011 vs 2012-2023)
3. Dedicated audit of the 42-cell High-Volatility Rain-Shadow regime.
4. Generates high-resolution geospatial classification, frequency, and focus maps.
5. Saves consolidated validation dataset and summary JSON.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

import matplotlib.colors as mcolors
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.collections import PatchCollection
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from shapely.geometry import shape
import xarray as xr

# Base and File Paths
BASE_DIR: Path = Path(__file__).resolve().parent.parent
PROCESSED_DATA_DIR: Path = BASE_DIR / "data" / "processed"
ONSET_CLUSTERS_CSV: Path = PROCESSED_DATA_DIR / "monsoon_onset_clusters.csv"
ONSET_NC_PATH: Path = PROCESSED_DATA_DIR / "maharashtra_onset_2001_2023.nc"
DAILY_RAIN_NC_PATH: Path = PROCESSED_DATA_DIR / "maharashtra_imd_daily_2001_2023.nc"
GEO_DISTRICTS: Path = BASE_DIR / "data" / "geo" / "maharashtra_districts.geojson"
OUTPUT_DIR: Path = BASE_DIR / "outputs" / "regime_validation"
VALIDATION_CSV_PATH: Path = PROCESSED_DATA_DIR / "regime_agricultural_validation.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / "regime_agricultural_summary.json"

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("MonsoonIQ.AgriculturalValidation")

# Constants
RANDOM_STATE: int = 42
SOWING_RAIN_THRESHOLD_MM: float = 50.0  # Agronomic rainfed sowing requirement (ICAR-CRIDA / MPKV)
WET_DAY_THRESHOLD_MM: float = 2.5      # IMD standard rainy day threshold

REGIME_ORDER: List[str] = [
    "Core Interior Synchronized",
    "Rain-Shadow High-Volatility",
    "Early Maritime & Western Ghats",
    "Interior Semi-Arid Transition",
]

REGIME_COLORS: Dict[str, str] = {
    "Core Interior Synchronized": "#1f77b4",       # Blue
    "Rain-Shadow High-Volatility": "#d62728",     # Red
    "Early Maritime & Western Ghats": "#2ca02c",  # Green
    "Interior Semi-Arid Transition": "#ff7f0e",   # Orange
}

LANDMARKS: List[Tuple[str, float, float]] = [
    ("Mumbai", 72.88, 19.07),
    ("Pune", 73.85, 18.52),
    ("Nagpur", 79.08, 21.15),
    ("Aurangabad", 75.34, 19.88),
    ("Kolhapur", 74.24, 16.70),
    ("Solapur", 75.91, 17.68),
    ("Nashik", 73.78, 19.99),
    ("Amravati", 77.75, 20.93),
]


class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder for NumPy scalars and arrays."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def load_district_polygons() -> List[MplPolygon]:
    """Loads district polygon boundaries for spatial mapping."""
    with open(GEO_DISTRICTS, "r", encoding="utf-8") as f:
        geo = json.load(f)

    polys: List[MplPolygon] = []
    for feat in geo["features"]:
        geom = shape(feat["geometry"])
        if geom.geom_type == "Polygon":
            polys.append(MplPolygon(np.array(geom.exterior.coords), closed=True))
        elif geom.geom_type == "MultiPolygon":
            for part in geom.geoms:
                polys.append(MplPolygon(np.array(part.exterior.coords), closed=True))
    return polys


def add_map_decorations(
    ax: plt.Axes,
    district_polys: List[MplPolygon],
    title: str,
    zoom_rain_shadow: bool = False,
) -> None:
    """Adds district borders, landmark labels, and coordinates to spatial maps."""
    patches = [MplPolygon(p.get_xy(), closed=True) for p in district_polys]
    coll = PatchCollection(
        patches,
        facecolor="none",
        edgecolor="#333333",
        linewidth=0.6,
        alpha=0.65,
        zorder=5,
    )
    ax.add_collection(coll)

    for name, lon_p, lat_p in LANDMARKS:
        if zoom_rain_shadow and not (73.2 <= lon_p <= 77.2 and 16.2 <= lat_p <= 20.8):
            continue
        ax.plot(lon_p, lat_p, "k^", markersize=4.5, zorder=6)
        ax.text(
            lon_p + 0.08,
            lat_p + 0.04,
            name,
            fontsize=8,
            fontweight="bold",
            color="#222222",
            zorder=7,
        )

    ax.set_title(title, fontsize=11, fontweight="bold", pad=12)
    ax.set_xlabel("Longitude (°E)", fontsize=9.5)
    ax.set_ylabel("Latitude (°N)", fontsize=9.5)
    if zoom_rain_shadow:
        ax.set_xlim(73.4, 76.8)
        ax.set_ylim(16.4, 20.4)
    else:
        ax.set_xlim(72.4, 81.1)
        ax.set_ylim(15.5, 22.3)
    ax.grid(True, linestyle=":", alpha=0.4, zorder=1)


def compute_independent_agricultural_metrics(
    df_clusters: pd.DataFrame,
) -> pd.DataFrame:
    """Extracts independent agricultural rainfall indicators from daily NetCDF.

    Args:
        df_clusters: DataFrame containing grid coordinates and regime labels.

    Returns:
        DataFrame enriched with independent agricultural variables.
    """
    logger.info("Extracting independent agricultural metrics from %s...", DAILY_RAIN_NC_PATH)
    ds_rain = xr.open_dataset(DAILY_RAIN_NC_PATH)
    rain_masked = ds_rain["rainfall_masked"].values  # (8400, 28, 35)
    times = pd.DatetimeIndex(ds_rain["time"].values)
    years = np.unique(times.year)
    num_years = len(years)

    lat_idx = df_clusters["lat_idx"].values
    lon_idx = df_clusters["lon_idx"].values
    num_cells = len(df_clusters)

    # Slice daily rainfall for the 419 cells: shape (8400, 419)
    cell_rain = rain_masked[:, lat_idx, lon_idx]

    # Initialize accumulation arrays
    june_totals = np.zeros((num_years, num_cells))
    june_wet_days = np.zeros((num_years, num_cells))
    jj_totals = np.zeros((num_years, num_cells))
    may_totals = np.zeros((num_years, num_cells))

    # Early-season (June 1 - July 15 = 45 days) metrics
    sowing_50mm_doys = np.zeros((num_years, num_cells))
    sowing_delayed_past_july1 = np.zeros((num_years, num_cells))
    early_max_dry_spells = np.zeros((num_years, num_cells))
    severe_dry_spell_10d_flag = np.zeros((num_years, num_cells))

    for y_i, yr in enumerate(years):
        # May
        may_mask = (times.year == yr) & (times.month == 5)
        may_totals[y_i, :] = np.nansum(cell_rain[may_mask, :], axis=0)

        # June
        june_mask = (times.year == yr) & (times.month == 6)
        june_daily = cell_rain[june_mask, :]
        june_totals[y_i, :] = np.nansum(june_daily, axis=0)
        june_wet_days[y_i, :] = np.nansum(june_daily >= WET_DAY_THRESHOLD_MM, axis=0)

        # June + July
        jj_mask = (times.year == yr) & ((times.month == 6) | (times.month == 7))
        jj_totals[y_i, :] = np.nansum(cell_rain[jj_mask, :], axis=0)

        # Early season: June 1 to July 15 (45 days)
        early_season_mask = (times.year == yr) & (
            (times.month == 6) | ((times.month == 7) & (times.day <= 15))
        )
        early_daily = cell_rain[early_season_mask, :]
        early_dates = times[early_season_mask]

        # 50 mm Sowing Trigger DOY
        cum_rain = np.cumsum(early_daily, axis=0)
        for c in range(num_cells):
            hit = np.where(cum_rain[:, c] >= SOWING_RAIN_THRESHOLD_MM)[0]
            if len(hit) > 0:
                sowing_50mm_doys[y_i, c] = early_dates[hit[0]].day_of_year
                if early_dates[hit[0]].month >= 7:
                    sowing_delayed_past_july1[y_i, c] = 1.0
            else:
                sowing_50mm_doys[y_i, c] = np.nan
                sowing_delayed_past_july1[y_i, c] = 1.0  # Not reached even by July 15

            # Maximum consecutive dry spell (< 2.5 mm) in early season window
            dry_days = (early_daily[:, c] < WET_DAY_THRESHOLD_MM).astype(int)
            max_dry_run = 0
            curr_dry_run = 0
            for d_val in dry_days:
                if d_val == 1:
                    curr_dry_run += 1
                    if curr_dry_run > max_dry_run:
                        max_dry_run = curr_dry_run
                else:
                    curr_dry_run = 0
            early_max_dry_spells[y_i, c] = max_dry_run
            if max_dry_run >= 10:
                severe_dry_spell_10d_flag[y_i, c] = 1.0

    # Aggregate cell-level statistics across 23 years
    mean_june_mm = np.mean(june_totals, axis=0)
    std_june_mm = np.std(june_totals, axis=0, ddof=1)
    cv_june_pct = (std_june_mm / mean_june_mm) * 100.0

    mean_jj_mm = np.mean(jj_totals, axis=0)
    mean_may_mm = np.mean(may_totals, axis=0)
    mean_june_wet_days = np.mean(june_wet_days, axis=0)

    median_sowing_doy = np.nanmedian(sowing_50mm_doys, axis=0)
    sowing_delay_freq = np.mean(sowing_delayed_past_july1, axis=0)

    mean_early_dry_spell_days = np.mean(early_max_dry_spells, axis=0)
    max_early_dry_spell_days = np.max(early_max_dry_spells, axis=0)
    severe_dry_spell_freq = np.mean(severe_dry_spell_10d_flag, axis=0)

    # Decadal Volatility Persistence (from onset NetCDF)
    ds_onset = xr.open_dataset(ONSET_NC_PATH)
    mask_mh = ds_onset["mask_maharashtra"].values
    onset_doy = ds_onset["confirmed_onset_doy"].values[:, mask_mh]
    onset_std_p1 = np.nanstd(onset_doy[:11, :], axis=0, ddof=1)   # 2001-2011 (11 yrs)
    onset_std_p2 = np.nanstd(onset_doy[11:, :], axis=0, ddof=1)  # 2012-2023 (12 yrs)

    # Assign to DataFrame
    df = df_clusters.copy()
    df["june_mean_rainfall_mm"] = np.round(mean_june_mm, 2)
    df["june_rainfall_cv_pct"] = np.round(cv_june_pct, 2)
    df["jj_mean_rainfall_mm"] = np.round(mean_jj_mm, 2)
    df["may_mean_rainfall_mm"] = np.round(mean_may_mm, 2)
    df["june_mean_wet_days"] = np.round(mean_june_wet_days, 2)
    df["sowing_trigger_median_doy"] = np.round(median_sowing_doy, 2)
    df["sowing_delay_past_july1_freq"] = np.round(sowing_delay_freq, 4)
    df["early_dry_spell_mean_days"] = np.round(mean_early_dry_spell_days, 2)
    df["early_dry_spell_max_days"] = np.round(max_early_dry_spell_days, 2)
    df["severe_dry_spell_10d_freq"] = np.round(severe_dry_spell_freq, 4)
    df["onset_std_p1_2001_2011"] = np.round(onset_std_p1, 2)
    df["onset_std_p2_2012_2023"] = np.round(onset_std_p2, 2)

    return df


def generate_regime_comparison_tables(df: pd.DataFrame) -> Dict[str, Any]:
    """Generates comparative statistical tables across the 4 onset regimes.

    Args:
        df: Enriched validation DataFrame.

    Returns:
        Dict summarizing regime profile metrics and independent agricultural metrics.
    """
    logger.info("Generating comparative statistical tables across 4 regimes...")

    # 1. Onset Dynamics Profile
    onset_summary: Dict[str, Any] = {}
    for r in REGIME_ORDER:
        sub = df[df["regime_kmeans"] == r]
        onset_summary[r] = {
            "cell_count": len(sub),
            "state_percentage": round(len(sub) / len(df) * 100, 2),
            "median_onset_doy": round(float(sub["median_onset_doy"].mean()), 2),
            "mean_onset_doy": round(float(sub["mean_onset_doy"].mean()), 2),
            "std_onset_doy": round(float(sub["std_onset_doy"].mean()), 2),
            "iqr_onset_doy": round(float(sub["iqr_onset_doy"].mean()), 2),
            "early_onset_freq": round(float(sub["early_onset_freq"].mean()), 4),
            "delayed_onset_freq": round(float(sub["delayed_onset_freq"].mean()), 4),
            "rejected_candidate_freq": round(float(sub["rejected_candidate_freq"].mean()), 4),
            "mean_max_dry_spell": round(float(sub["mean_max_dry_spell"].mean()), 2),
            "onset_detection_freq": round(float(sub["onset_detection_freq"].mean()), 4),
        }

    # 2. Independent Agricultural Metrics
    agri_summary: Dict[str, Any] = {}
    for r in REGIME_ORDER:
        sub = df[df["regime_kmeans"] == r]
        agri_summary[r] = {
            "june_mean_rainfall_mm": round(float(sub["june_mean_rainfall_mm"].mean()), 2),
            "june_rainfall_cv_pct": round(float(sub["june_rainfall_cv_pct"].mean()), 2),
            "jj_mean_rainfall_mm": round(float(sub["jj_mean_rainfall_mm"].mean()), 2),
            "may_mean_rainfall_mm": round(float(sub["may_mean_rainfall_mm"].mean()), 2),
            "june_mean_wet_days": round(float(sub["june_mean_wet_days"].mean()), 2),
            "sowing_trigger_median_doy": round(float(sub["sowing_trigger_median_doy"].mean()), 2),
            "sowing_delay_past_july1_freq": round(float(sub["sowing_delay_past_july1_freq"].mean()), 4),
            "early_dry_spell_mean_days": round(float(sub["early_dry_spell_mean_days"].mean()), 2),
            "early_dry_spell_max_days": round(float(sub["early_dry_spell_max_days"].mean()), 2),
            "severe_dry_spell_10d_freq": round(float(sub["severe_dry_spell_10d_freq"].mean()), 4),
            "onset_std_p1_2001_2011": round(float(sub["onset_std_p1_2001_2011"].mean()), 2),
            "onset_std_p2_2012_2023": round(float(sub["onset_std_p2_2012_2023"].mean()), 2),
        }

    # 3. High-Volatility vs Transition Deep-Dive
    vol_sub = df[df["regime_kmeans"] == "Rain-Shadow High-Volatility"]
    trans_sub = df[df["regime_kmeans"] == "Interior Semi-Arid Transition"]

    vol_audit = {
        "cell_count": len(vol_sub),
        "district_distribution": vol_sub["district"].value_counts().to_dict(),
        "lat_bounds": [float(vol_sub["latitude"].min()), float(vol_sub["latitude"].max())],
        "lon_bounds": [float(vol_sub["longitude"].min()), float(vol_sub["longitude"].max())],
        "decadal_persistence": {
            "period_1_std_days": round(float(vol_sub["onset_std_p1_2001_2011"].mean()), 2),
            "period_2_std_days": round(float(vol_sub["onset_std_p2_2012_2023"].mean()), 2),
        },
        "comparison_vs_transition": {
            "onset_std_ratio": round(float(vol_sub["std_onset_doy"].mean() / trans_sub["std_onset_doy"].mean()), 2),
            "false_onset_ratio": round(float(vol_sub["rejected_candidate_freq"].mean() / trans_sub["rejected_candidate_freq"].mean()), 2),
            "june_cv_volatile": round(float(vol_sub["june_rainfall_cv_pct"].mean()), 2),
            "june_cv_transition": round(float(trans_sub["june_rainfall_cv_pct"].mean()), 2),
            "sowing_delay_volatile": round(float(vol_sub["sowing_delay_past_july1_freq"].mean()), 4),
            "sowing_delay_transition": round(float(trans_sub["sowing_delay_past_july1_freq"].mean()), 4),
            "early_dry_spell_max_volatile": round(float(vol_sub["early_dry_spell_max_days"].mean()), 2),
            "early_dry_spell_max_transition": round(float(trans_sub["early_dry_spell_max_days"].mean()), 2),
        },
    }

    return {
        "onset_profile_summary": onset_summary,
        "agricultural_validation_summary": agri_summary,
        "high_volatility_audit": vol_audit,
    }


def generate_all_geospatial_and_diagnostic_plots(
    df: pd.DataFrame,
) -> None:
    """Renders high-resolution geospatial and diagnostic validation figures."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    district_polys = load_district_polygons()

    # -------------------------------------------------------------
    # Plot 1: Four-Regime Maharashtra Classification Map
    # -------------------------------------------------------------
    logger.info("Generating Plot 1: map_regime_classification.png...")
    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)

    for r_name in REGIME_ORDER:
        sub = df[df["regime_kmeans"] == r_name]
        ax.scatter(
            sub["longitude"],
            sub["latitude"],
            c=REGIME_COLORS[r_name],
            s=85,
            edgecolors="#222222",
            linewidth=0.7,
            label=f"{r_name} (n={len(sub)}, {len(sub)/len(df)*100:.1f}%)",
            zorder=3,
        )

    add_map_decorations(
        ax,
        district_polys,
        "MonsoonIQ: Four Discovered Monsoon Onset Regimes across Maharashtra\nK-Means (k=4) Physical Climatological Classification (419 IMD 0.25° Grid Cells)",
    )
    ax.legend(loc="lower left", fontsize=8.5, framealpha=0.92, facecolor="white")
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "map_regime_classification.png", dpi=300)
    plt.close(fig)

    # -------------------------------------------------------------
    # Plot 2: Early-Onset Frequency Map (<= June 5 / DOY 156)
    # -------------------------------------------------------------
    logger.info("Generating Plot 2: map_early_onset_frequency.png...")
    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
    sc = ax.scatter(
        df["longitude"],
        df["latitude"],
        c=df["early_onset_freq"] * 100,
        cmap="YlGnBu",
        s=85,
        edgecolors="#333333",
        linewidth=0.5,
        vmin=0,
        vmax=65,
        zorder=3,
    )
    cbar = fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Early Onset Frequency (% of Years <= June 5)", fontsize=10, fontweight="bold")
    add_map_decorations(
        ax,
        district_polys,
        "MonsoonIQ: Early Monsoon Onset Frequency (<= June 5 / DOY 156)\nHigh Frequency Along Western Coast and Orographic Ghats Escarpment",
    )
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "map_early_onset_frequency.png", dpi=300)
    plt.close(fig)

    # -------------------------------------------------------------
    # Plot 3: Delayed-Onset Frequency Map (>= June 21 / DOY 172)
    # -------------------------------------------------------------
    logger.info("Generating Plot 3: map_delayed_onset_frequency.png...")
    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
    sc = ax.scatter(
        df["longitude"],
        df["latitude"],
        c=df["delayed_onset_freq"] * 100,
        cmap="YlOrRd",
        s=85,
        edgecolors="#333333",
        linewidth=0.5,
        vmin=0,
        vmax=65,
        zorder=3,
    )
    cbar = fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Delayed Onset Frequency (% of Years >= June 21)", fontsize=10, fontweight="bold")
    add_map_decorations(
        ax,
        district_polys,
        "MonsoonIQ: Delayed Monsoon Onset Frequency (>= June 21 / DOY 172)\nPronounced Onset Stagnation Across Marathwada & Northern Khandesh",
    )
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "map_delayed_onset_frequency.png", dpi=300)
    plt.close(fig)

    # -------------------------------------------------------------
    # Plot 4: Onset Variability Map (Standard Deviation in Days)
    # -------------------------------------------------------------
    logger.info("Generating Plot 4: map_onset_variability.png...")
    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
    sc = ax.scatter(
        df["longitude"],
        df["latitude"],
        c=df["std_onset_doy"],
        cmap="magma",
        s=85,
        edgecolors="#333333",
        linewidth=0.5,
        vmin=5,
        vmax=38,
        zorder=3,
    )
    cbar = fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Onset Standard Deviation (Days)", fontsize=10, fontweight="bold")
    add_map_decorations(
        ax,
        district_polys,
        "MonsoonIQ: Interannual Monsoon Onset Variability (Standard Deviation in Days)\nSharp Contrast: Stable Coastal Strip (<9d) vs Hyper-Volatile Rain Shadow (>30d)",
    )
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "map_onset_variability.png", dpi=300)
    plt.close(fig)

    # -------------------------------------------------------------
    # Plot 5: High-Volatility Regime Focus Map (Zoomed on Rain Shadow)
    # -------------------------------------------------------------
    logger.info("Generating Plot 5: map_high_volatility_focus.png...")
    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)

    # Plot all cells in background with faint styling
    for r_name in ["Early Maritime & Western Ghats", "Core Interior Synchronized"]:
        sub = df[df["regime_kmeans"] == r_name]
        ax.scatter(sub["longitude"], sub["latitude"], c="#d3d3d3", s=60, alpha=0.4, zorder=2)

    # Transition buffer cells
    sub_trans = df[df["regime_kmeans"] == "Interior Semi-Arid Transition"]
    ax.scatter(
        sub_trans["longitude"],
        sub_trans["latitude"],
        c="#ffbb78",
        s=80,
        alpha=0.7,
        edgecolors="#8c564b",
        linewidth=0.6,
        label=f"Transition Buffer (n={len(sub_trans)})",
        zorder=3,
    )

    # High-Volatility Focus Cells
    sub_vol = df[df["regime_kmeans"] == "Rain-Shadow High-Volatility"]
    ax.scatter(
        sub_vol["longitude"],
        sub_vol["latitude"],
        c="#d62728",
        s=120,
        edgecolors="black",
        linewidth=1.2,
        label=f"High-Volatility Rain Shadow Core (n={len(sub_vol)})",
        zorder=4,
    )

    add_map_decorations(
        ax,
        district_polys,
        "MonsoonIQ: Geographic Deep-Dive — The 42-Cell High-Volatility Rain Shadow\nCompact Leeward Belt Across Solapur, Sangli, Satara, Pune, & Ahmadnagar",
        zoom_rain_shadow=True,
    )
    ax.legend(loc="lower right", fontsize=8.5, framealpha=0.92, facecolor="white")
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "map_high_volatility_focus.png", dpi=300)
    plt.close(fig)

    # -------------------------------------------------------------
    # Plot 6: Independent Agricultural Validation Metrics (Grouped Boxplots)
    # -------------------------------------------------------------
    logger.info("Generating Plot 6: chart_independent_agricultural_metrics.png...")
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10), dpi=300)

    box_data_june_rain = [df[df["regime_kmeans"] == r]["june_mean_rainfall_mm"].values for r in REGIME_ORDER]
    box_data_june_cv = [df[df["regime_kmeans"] == r]["june_rainfall_cv_pct"].values for r in REGIME_ORDER]
    box_data_dry_spell = [df[df["regime_kmeans"] == r]["early_dry_spell_mean_days"].values for r in REGIME_ORDER]
    box_data_sowing_doy = [df[df["regime_kmeans"] == r]["sowing_trigger_median_doy"].values for r in REGIME_ORDER]

    short_regimes = ["Core Interior", "Rain-Shadow Volatile", "Early Maritime", "Semi-Arid Transition"]

    # 1. June Total Rainfall
    bp1 = ax1.boxplot(box_data_june_rain, tick_labels=short_regimes, patch_artist=True)
    ax1.set_title("Independent Metric 1: Mean June Rainfall Total (mm)", fontsize=10.5, fontweight="bold")
    ax1.set_ylabel("Rainfall (mm)", fontsize=9.5)
    ax1.grid(True, linestyle=":", alpha=0.4)

    # 2. June Rainfall CV
    bp2 = ax2.boxplot(box_data_june_cv, tick_labels=short_regimes, patch_artist=True)
    ax2.set_title("Independent Metric 2: Interannual June Rainfall CV (%)", fontsize=10.5, fontweight="bold")
    ax2.set_ylabel("Coefficient of Variation (%)", fontsize=9.5)
    ax2.grid(True, linestyle=":", alpha=0.4)

    # 3. Early Season Mean Max Dry Spell
    bp3 = ax3.boxplot(box_data_dry_spell, tick_labels=short_regimes, patch_artist=True)
    ax3.set_title("Independent Metric 3: Early-Season Max Dry Spell (June 1 - July 15)", fontsize=10.5, fontweight="bold")
    ax3.set_ylabel("Consecutive Dry Days (< 2.5 mm)", fontsize=9.5)
    ax3.grid(True, linestyle=":", alpha=0.4)

    # 4. Sowing Opportunity Trigger DOY (50 mm Cumulative)
    bp4 = ax4.boxplot(box_data_sowing_doy, tick_labels=short_regimes, patch_artist=True)
    ax4.set_title("Independent Metric 4: 50 mm Sowing Trigger Date (DOY)", fontsize=10.5, fontweight="bold")
    ax4.set_ylabel("Day of Year (DOY)", fontsize=9.5)
    ax4.grid(True, linestyle=":", alpha=0.4)

    # Color boxplots
    palette = [REGIME_COLORS[r] for r in REGIME_ORDER]
    for bp in [bp1, bp2, bp3, bp4]:
        for patch, color in zip(bp["boxes"], palette):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

    plt.suptitle(
        "MonsoonIQ: Independent Agricultural Relevance Validation Across Discovered Onset Regimes\nComparing External Rainfall Indicators Never Used in the Clustering Algorithm",
        fontsize=12,
        fontweight="bold",
        y=0.995,
    )
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "chart_independent_agricultural_metrics.png", dpi=300)
    plt.close(fig)

    # -------------------------------------------------------------
    # Plot 7: Sowing Opportunity Delay Frequency Map
    # -------------------------------------------------------------
    logger.info("Generating Plot 7: map_sowing_opportunity_delay.png...")
    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
    sc = ax.scatter(
        df["longitude"],
        df["latitude"],
        c=df["sowing_delay_past_july1_freq"] * 100,
        cmap="copper_r",
        s=85,
        edgecolors="#222222",
        linewidth=0.5,
        vmin=0,
        vmax=35,
        zorder=3,
    )
    cbar = fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Sowing Delay Frequency (% Years without 50 mm by July 1)", fontsize=10, fontweight="bold")
    add_map_decorations(
        ax,
        district_polys,
        "MonsoonIQ: Agronomic Sowing Delay Risk (Cumulative 50 mm Not Reached by July 1)\nSevere Exposure in Central Rain-Shadow Core (Up to 35% of Historical Years)",
    )
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "map_sowing_opportunity_delay.png", dpi=300)
    plt.close(fig)


def run_agricultural_relevance_validation() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Executes the full Phase 7 agricultural relevance validation pipeline."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load clusters
    logger.info("Loading onset clusters from %s...", ONSET_CLUSTERS_CSV)
    df_clusters = pd.read_csv(ONSET_CLUSTERS_CSV)

    # 2. Compute Independent Agricultural Metrics
    df_validated = compute_independent_agricultural_metrics(df_clusters)

    # 3. Save Enriched Dataset
    df_validated.to_csv(VALIDATION_CSV_PATH, index=False)
    logger.info("Saved validated agricultural dataset to %s (%d rows)", VALIDATION_CSV_PATH, len(df_validated))

    # 4. Generate Comparative Tables and Statistics
    summary = generate_regime_comparison_tables(df_validated)

    # 5. Generate All Geospatial Maps and Diagnostic Figures
    generate_all_geospatial_and_diagnostic_plots(df_validated)

    # 6. Save Summary JSON
    with open(SUMMARY_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, cls=NumpyEncoder)
    logger.info("Saved agricultural validation summary to %s", SUMMARY_JSON_PATH)

    return df_validated, summary


def main() -> None:
    """Execution entry point."""
    run_agricultural_relevance_validation()


if __name__ == "__main__":
    main()
