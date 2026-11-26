"""MonsoonIQ - Grid-Cell Level Monsoon Onset Feature Engineering Pipeline.

Extracts spatial-temporal onset dynamics across 419 Maharashtra 0.25-degree IMD
grid cells over the 23-year historical record (2001-2023) for unsupervised machine
learning clustering.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from shapely.geometry import Point, shape
from sklearn.preprocessing import RobustScaler, StandardScaler
import xarray as xr

# Base and File Paths
BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_ONSET_NC: Path = BASE_DIR / "data" / "processed" / "maharashtra_onset_2001_2023.nc"
GEO_DISTRICTS: Path = BASE_DIR / "data" / "geo" / "maharashtra_districts.geojson"
OUTPUT_DIR: Path = BASE_DIR / "outputs" / "clustering"
PROCESSED_DATA_DIR: Path = BASE_DIR / "data" / "processed"
FEATURES_CSV_PATH: Path = PROCESSED_DATA_DIR / "monsoon_onset_features.csv"
CORRELATION_HEATMAP_PATH: Path = OUTPUT_DIR / "feature_correlation_heatmap.png"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("MonsoonIQ.FeatureEngineering")

# Constants
EXPECTED_CELL_COUNT: int = 419
EXPECTED_YEARS: int = 23
EARLY_ONSET_THRESHOLD_DOY: int = 156  # June 5 (IMD maritime benchmark window)
DELAYED_ONSET_THRESHOLD_DOY: int = 172  # June 21 (Summer solstice / late boundary)

FEATURE_COLUMNS: List[str] = [
    "median_onset_doy",
    "mean_onset_doy",
    "std_onset_doy",
    "iqr_onset_doy",
    "early_onset_freq",
    "delayed_onset_freq",
    "rejected_candidate_freq",
    "mean_max_dry_spell",
    "onset_detection_freq",
]

SUBDIV_MAP: Dict[str, str] = {
    "Mumbai": "Konkan",
    "Mumbai Suburban": "Konkan",
    "Thane": "Konkan",
    "Palghar": "Konkan",
    "Raigarh": "Konkan",
    "Ratnagiri": "Konkan",
    "Sindhudurg": "Konkan",
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
    "Aurangabad": "Marathwada",
    "Jalna": "Marathwada",
    "Bid": "Marathwada",
    "Parbhani": "Marathwada",
    "Hingoli": "Marathwada",
    "Nanded": "Marathwada",
    "Latur": "Marathwada",
    "Osmanabad": "Marathwada",
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

ZONE_NAME_MAP: Dict[int, str] = {
    1: "Western Ghats",
    2: "Konkan",
    3: "Madhya Maharashtra",
    4: "Marathwada",
    5: "Vidarbha",
}


def load_spatial_metadata(
    lats: np.ndarray,
    lons: np.ndarray,
    mask_mh: np.ndarray,
) -> Tuple[List[str], List[str]]:
    """Assigns district and subdivision names to all valid Maharashtra grid cells.

    Args:
        lats: 1D array of latitude coordinates.
        lons: 1D array of longitude coordinates.
        mask_mh: 2D boolean mask of Maharashtra land cells.

    Returns:
        Tuple containing list of district names and list of subdivision names.
    """
    logger.info("Loading district polygon boundaries from %s...", GEO_DISTRICTS)
    with open(GEO_DISTRICTS, "r", encoding="utf-8") as f:
        geo = json.load(f)

    district_polys = [
        (feat["properties"]["dtname"], shape(feat["geometry"]))
        for feat in geo["features"]
    ]

    lat_indices, lon_indices = np.where(mask_mh)
    districts: List[str] = []
    subdivisions: List[str] = []

    for lat_idx, lon_idx in zip(lat_indices, lon_indices):
        lat = float(lats[lat_idx])
        lon = float(lons[lon_idx])
        pt = Point(lon, lat)

        matched_dt: str | None = None
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

        dt_name_str = matched_dt if matched_dt is not None else "Unknown"
        districts.append(dt_name_str)
        subdivisions.append(SUBDIV_MAP.get(dt_name_str, "Madhya Maharashtra"))

    return districts, subdivisions


def extract_onset_features(nc_path: Path = DATA_ONSET_NC) -> pd.DataFrame:
    """Extracts 9 onset dynamics features across all 419 Maharashtra cells.

    Args:
        nc_path: Path to the consolidated onset NetCDF dataset.

    Returns:
        pandas DataFrame containing spatial metadata and 9 engineered features.

    Raises:
        FileNotFoundError: If the onset NetCDF file does not exist.
        ValueError: If cell count or dimensions do not match expectations.
    """
    if not nc_path.exists():
        raise FileNotFoundError(f"Onset NetCDF file not found at {nc_path}")

    logger.info("Opening onset dataset from %s...", nc_path)
    ds = xr.open_dataset(nc_path)

    mask_mh = ds["mask_maharashtra"].values
    lats = ds["lat"].values
    lons = ds["lon"].values
    years = ds["year"].values
    num_years = len(years)

    if num_years != EXPECTED_YEARS:
        raise ValueError(
            f"Expected {EXPECTED_YEARS} years, but found {num_years} in dataset."
        )

    lat_indices, lon_indices = np.where(mask_mh)
    num_cells = len(lat_indices)
    if num_cells != EXPECTED_CELL_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_CELL_COUNT} cells, but found {num_cells}."
        )

    districts, subdivisions = load_spatial_metadata(lats, lons, mask_mh)

    # Extract 3D arrays sliced to the 419 valid cells: shape (23, 419)
    confirmed_doy = ds["confirmed_onset_doy"].values[:, mask_mh]
    max_dry_spell = ds["max_post_candidate_dry_spell"].values[:, mask_mh]
    has_rejected = ds["has_rejected_candidate"].values[:, mask_mh]
    zone_ids = ds["zone_id"].values[mask_mh]

    records: List[Dict[str, Any]] = []

    for cell_idx in range(num_cells):
        lat_val = float(lats[lat_indices[cell_idx]])
        lon_val = float(lons[lon_indices[cell_idx]])
        cell_id = f"cell_{cell_idx:03d}"
        zid = int(zone_ids[cell_idx])
        zname = ZONE_NAME_MAP.get(zid, subdivisions[cell_idx])

        doys = confirmed_doy[:, cell_idx]
        valid_mask = ~np.isnan(doys)
        valid_doys = doys[valid_mask]
        n_valid = len(valid_doys)

        if n_valid == 0:
            raise ValueError(
                f"Cell {cell_id} at ({lat_val:.2f}, {lon_val:.2f}) has 0 valid onsets!"
            )

        # 1. Climatological Median Onset DOY
        med_doy = float(np.median(valid_doys))

        # 2. Climatological Mean Onset DOY
        mean_doy = float(np.mean(valid_doys))

        # 3. Interannual Standard Deviation of Onset DOY (Onset Volatility)
        std_doy = float(np.std(valid_doys, ddof=1)) if n_valid > 1 else 0.0

        # 4. Interquartile Range (75th - 25th percentile)
        iqr_doy = float(
            np.percentile(valid_doys, 75) - np.percentile(valid_doys, 25)
        )

        # 5. Frequency of Early Onset (<= DOY 156 / June 5)
        early_freq = float(
            np.sum(valid_doys <= EARLY_ONSET_THRESHOLD_DOY) / n_valid
        )

        # 6. Frequency of Delayed Onset (>= DOY 172 / June 21)
        delayed_freq = float(
            np.sum(valid_doys >= DELAYED_ONSET_THRESHOLD_DOY) / n_valid
        )

        # 7. False Onset Risk: Frequency of years with >= 1 rejected candidate
        rej_freq = float(np.sum(has_rejected[:, cell_idx] == 1) / num_years)

        # 8. Post-Onset Dry Spell Severity (mean max dry spell across confirmed years)
        mean_dry = float(np.mean(max_dry_spell[valid_mask, cell_idx]))

        # 9. Onset Detection Reliability Frequency (confirmed years / total years)
        det_freq = float(n_valid / num_years)

        record = {
            "cell_id": cell_id,
            "lat_idx": int(lat_indices[cell_idx]),
            "lon_idx": int(lon_indices[cell_idx]),
            "latitude": round(lat_val, 2),
            "longitude": round(lon_val, 2),
            "district": districts[cell_idx],
            "zone_id": zid,
            "zone_name": zname,
            "median_onset_doy": round(med_doy, 2),
            "mean_onset_doy": round(mean_doy, 2),
            "std_onset_doy": round(std_doy, 2),
            "iqr_onset_doy": round(iqr_doy, 2),
            "early_onset_freq": round(early_freq, 4),
            "delayed_onset_freq": round(delayed_freq, 4),
            "rejected_candidate_freq": round(rej_freq, 4),
            "mean_max_dry_spell": round(mean_dry, 2),
            "onset_detection_freq": round(det_freq, 4),
        }
        records.append(record)

    df_features = pd.DataFrame(records)

    # Integrity Validation
    assert len(df_features) == EXPECTED_CELL_COUNT, (
        f"Expected {EXPECTED_CELL_COUNT} rows, got {len(df_features)}"
    )
    assert not df_features[FEATURE_COLUMNS].isna().any().any(), (
        "Engineered features contain NaNs!"
    )
    assert (df_features["onset_detection_freq"] >= 0.85).all(), (
        "Some cells have abnormal detection failures (<85%)"
    )

    logger.info("Successfully engineered features for all %d cells.", len(df_features))
    return df_features


def plot_feature_correlation_heatmap(
    df: pd.DataFrame,
    output_path: Path = CORRELATION_HEATMAP_PATH,
) -> None:
    """Generates and saves correlation heatmap of the engineered onset features.

    Args:
        df: DataFrame containing the engineered feature columns.
        output_path: Path where the PNG image will be saved.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    corr = df[FEATURE_COLUMNS].corr()

    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
    cax = ax.imshow(corr, cmap="RdBu_r", vmin=-1.0, vmax=1.0)
    fig.colorbar(cax, ax=ax, fraction=0.046, pad=0.04, label="Pearson Correlation")

    labels = [
        "Median DOY",
        "Mean DOY",
        "Std DOY (Volatility)",
        "IQR DOY",
        "Early Onset Freq (<=Jun 5)",
        "Delayed Onset Freq (>=Jun 21)",
        "Rejected Cand Freq",
        "Mean Post-Cand Dry Spell",
        "Onset Detection Freq",
    ]

    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9, fontweight="medium")
    ax.set_yticklabels(labels, fontsize=9, fontweight="medium")

    # Annotate correlation numbers
    for i in range(len(labels)):
        for j in range(len(labels)):
            val = corr.iloc[i, j]
            text_color = "white" if abs(val) > 0.55 else "black"
            ax.text(
                j,
                i,
                f"{val:.2f}",
                ha="center",
                va="center",
                color=text_color,
                fontsize=8.5,
                fontweight="bold" if abs(val) > 0.6 else "normal",
            )

    ax.set_title(
        "MonsoonIQ Phase 6A: Feature Correlation Matrix (419 Maharashtra Grid Cells)",
        fontsize=12,
        fontweight="bold",
        pad=15,
    )
    plt.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    logger.info("Saved feature correlation heatmap to %s", output_path)


def evaluate_scalers(df: pd.DataFrame) -> Dict[str, Any]:
    """Compares StandardScaler and RobustScaler transformations across features.

    Args:
        df: DataFrame containing the 9 feature columns.

    Returns:
        Dict summarizing mean, std, median, and IQR across features.
    """
    X = df[FEATURE_COLUMNS].values
    std_scaler = StandardScaler()
    X_std = std_scaler.fit_transform(X)

    robust_scaler = RobustScaler()
    X_robust = robust_scaler.fit_transform(X)

    comparison = {
        "features": FEATURE_COLUMNS,
        "standard_scaler": {
            "mean": std_scaler.mean_.tolist(),
            "scale": std_scaler.scale_.tolist(),
        },
        "robust_scaler": {
            "center": robust_scaler.center_.tolist(),
            "scale": robust_scaler.scale_.tolist(),
        },
    }
    return comparison


def main() -> None:
    """Execution entry point for Stage 1 & 2 feature engineering."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    df_features = extract_onset_features(DATA_ONSET_NC)
    df_features.to_csv(FEATURES_CSV_PATH, index=False)
    logger.info("Saved onset features to %s (%d rows)", FEATURES_CSV_PATH, len(df_features))

    plot_feature_correlation_heatmap(df_features, CORRELATION_HEATMAP_PATH)

    scaler_eval = evaluate_scalers(df_features)
    logger.info(
        "Feature scaling evaluation complete. RobustScaler center: %s",
        [round(c, 2) for c in scaler_eval["robust_scaler"]["center"]],
    )


if __name__ == "__main__":
    main()
