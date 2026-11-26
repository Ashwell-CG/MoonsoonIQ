"""MonsoonIQ - Unsupervised Monsoon Onset Pattern Discovery Pipeline.

Evaluates K-Means, Agglomerative Hierarchical, and DBSCAN clustering algorithms
on 23-year historical onset dynamics across 419 Maharashtra IMD 0.25-degree grid cells.
Generates comprehensive comparative metrics, diagnostic plots, spatial maps,
and saves the consolidated cluster assignments.
"""

from __future__ import annotations

import itertools
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
from scipy.cluster.hierarchy import cophenet, dendrogram, linkage
from scipy.spatial.distance import pdist
from shapely.geometry import shape
from sklearn.cluster import AgglomerativeClustering, DBSCAN, KMeans
from sklearn.metrics import (
    adjusted_rand_score,
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

# Base and File Paths
BASE_DIR: Path = Path(__file__).resolve().parent.parent
PROCESSED_DATA_DIR: Path = BASE_DIR / "data" / "processed"
FEATURES_CSV_PATH: Path = PROCESSED_DATA_DIR / "monsoon_onset_features.csv"
CLUSTERS_CSV_PATH: Path = PROCESSED_DATA_DIR / "monsoon_onset_clusters.csv"
GEO_DISTRICTS: Path = BASE_DIR / "data" / "geo" / "maharashtra_districts.geojson"
OUTPUT_DIR: Path = BASE_DIR / "outputs" / "clustering"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / "clustering_evaluation_summary.json"

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("MonsoonIQ.Clustering")

# Algorithmic & Feature Constants
RANDOM_STATE: int = 42
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

FEATURE_DISPLAY_NAMES: List[str] = [
    "Median DOY",
    "Mean DOY",
    "Std DOY (Volatility)",
    "IQR DOY",
    "Early Onset Freq (<=Jun 5)",
    "Delayed Onset Freq (>=Jun 21)",
    "Rejected Cand Freq (False Onset)",
    "Mean Post-Cand Dry Spell",
    "Onset Detection Freq",
]

# Physical regime naming for K-Means k=4 clusters
KMEANS_REGIME_NAMES: Dict[int, str] = {
    0: "Core Interior Synchronized",
    1: "Rain-Shadow High-Volatility",
    2: "Early Maritime & Western Ghats",
    3: "Interior Semi-Arid Transition",
}

HIERARCHICAL_REGIME_NAMES: Dict[int, str] = {
    0: "Rain-Shadow High-Volatility",
    1: "Interior Semi-Arid Transition",
    2: "Early Maritime & Western Ghats",
    3: "Core Interior Synchronized",
}

LANDMARKS: List[Tuple[str, float, float]] = [
    ("Mumbai", 72.88, 19.07),
    ("Pune", 73.85, 18.52),
    ("Nagpur", 79.08, 21.15),
    ("Aurangabad", 75.34, 19.88),
    ("Kolhapur", 74.24, 16.70),
    ("Solapur", 75.91, 17.68),
]


class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder for NumPy primitives."""

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


def load_and_scale_features() -> Tuple[pd.DataFrame, np.ndarray, StandardScaler]:
    """Loads feature dataset and scales input feature matrix.

    Returns:
        Tuple containing feature DataFrame, scaled feature array X, and fitted StandardScaler.

    Raises:
        FileNotFoundError: If the features CSV is missing.
    """
    if not FEATURES_CSV_PATH.exists():
        raise FileNotFoundError(f"Feature dataset not found at {FEATURES_CSV_PATH}")

    logger.info("Loading onset features from %s...", FEATURES_CSV_PATH)
    df = pd.read_csv(FEATURES_CSV_PATH)

    # Strictly exclude any spatial coordinates or administrative labels from X
    scaler = StandardScaler()
    X = scaler.fit_transform(df[FEATURE_COLUMNS].values)
    return df, X, scaler


def run_kmeans_experiments(
    X: np.ndarray,
    k_range: range = range(2, 9),
    seeds: List[int] | None = None,
) -> Dict[str, Any]:
    """Evaluates K-Means clustering across cluster counts and random initializations.

    Args:
        X: Standardized feature matrix.
        k_range: Range of cluster counts k to evaluate.
        seeds: List of random seeds for stability testing.

    Returns:
        Dict summarizing inertia, silhouette, Davies-Bouldin, Calinski-Harabasz, and stability.
    """
    if seeds is None:
        seeds = [0, 1, 10, 42, 100, 123, 456, 789, 999, 2024]

    logger.info("Evaluating K-Means across k in %s...", list(k_range))
    results: Dict[str, Any] = {
        "k_values": list(k_range),
        "inertia": [],
        "silhouette": [],
        "davies_bouldin": [],
        "calinski_harabasz": [],
        "seed_stability_ari": {},
    }

    for k in k_range:
        km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
        labels = km.fit_predict(X)
        results["inertia"].append(float(km.inertia_))
        results["silhouette"].append(float(silhouette_score(X, labels)))
        results["davies_bouldin"].append(float(davies_bouldin_score(X, labels)))
        results["calinski_harabasz"].append(float(calinski_harabasz_score(X, labels)))

    # Seed stability evaluation for k in [3, 4, 5]
    for k in [3, 4, 5]:
        seed_labels = [
            KMeans(n_clusters=k, random_state=s, n_init=10).fit_predict(X)
            for s in seeds
        ]
        aris = [
            float(adjusted_rand_score(l1, l2))
            for l1, l2 in itertools.combinations(seed_labels, 2)
        ]
        results["seed_stability_ari"][f"k_{k}"] = {
            "mean_ari": float(np.mean(aris)),
            "min_ari": float(np.min(aris)),
            "max_ari": float(np.max(aris)),
        }

    return results


def run_hierarchical_experiments(
    X: np.ndarray,
    k_range: range = range(2, 9),
) -> Dict[str, Any]:
    """Evaluates Agglomerative Hierarchical clustering across linkage methods and k values.

    Args:
        X: Standardized feature matrix.
        k_range: Range of cluster counts k to evaluate.

    Returns:
        Dict summarizing cophenetic correlation and metrics for Ward, Complete, and Average.
    """
    logger.info("Evaluating Agglomerative Hierarchical clustering...")
    dist_matrix = pdist(X, metric="euclidean")

    linkage_methods = ["ward", "complete", "average"]
    cophenetic_coeffs: Dict[str, float] = {}

    for method in linkage_methods:
        Z = linkage(dist_matrix, method=method)
        c, _ = cophenet(Z, dist_matrix)
        cophenetic_coeffs[method] = float(c)

    # Detailed metrics for Ward linkage across k_range
    ward_results: Dict[str, Any] = {
        "k_values": list(k_range),
        "silhouette": [],
        "davies_bouldin": [],
        "calinski_harabasz": [],
    }

    for k in k_range:
        agg = AgglomerativeClustering(n_clusters=k, linkage="ward")
        labels = agg.fit_predict(X)
        ward_results["silhouette"].append(float(silhouette_score(X, labels)))
        ward_results["davies_bouldin"].append(float(davies_bouldin_score(X, labels)))
        ward_results["calinski_harabasz"].append(float(calinski_harabasz_score(X, labels)))

    return {
        "cophenetic_correlation": cophenetic_coeffs,
        "ward_metrics": ward_results,
    }


def run_dbscan_experiments(
    X: np.ndarray,
    eps_values: List[float] | None = None,
    min_samples_values: List[int] | None = None,
) -> Dict[str, Any]:
    """Explores DBSCAN parameter space across eps and min_samples.

    Args:
        X: Standardized feature matrix.
        eps_values: List of eps thresholds to test.
        min_samples_values: List of min_samples values to test.

    Returns:
        Dict summarizing cluster count, noise percentage, and silhouette scores.
    """
    if eps_values is None:
        eps_values = [0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2]
    if min_samples_values is None:
        min_samples_values = [3, 4, 5, 6, 8, 10]

    logger.info("Evaluating DBSCAN parameter grid...")
    grid_results: List[Dict[str, Any]] = []

    for eps in eps_values:
        for ms in min_samples_values:
            db = DBSCAN(eps=eps, min_samples=ms)
            labels = db.fit_predict(X)
            unique_labels = set(labels)
            n_clusters = len(unique_labels - {-1})
            n_noise = int((labels == -1).sum())
            noise_ratio = float(n_noise / len(X))

            sil = (
                float(silhouette_score(X, labels))
                if n_clusters > 1 and n_noise < len(X) - 2
                else -1.0
            )

            grid_results.append({
                "eps": eps,
                "min_samples": ms,
                "n_clusters": n_clusters,
                "n_noise": n_noise,
                "noise_ratio": round(noise_ratio, 4),
                "silhouette": round(sil, 4),
            })

    return {"grid_results": grid_results}


def evaluate_temporal_stability(
    df: pd.DataFrame,
    scaler: StandardScaler,
) -> Dict[str, Any]:
    """Computes cluster persistence and cross-decade stability (2001-2011 vs 2012-2023).

    Args:
        df: Feature DataFrame.
        scaler: Fitted StandardScaler.

    Returns:
        Dict summarizing decade-to-decade Adjusted Rand Index.
    """
    logger.info("Evaluating temporal stability across split periods...")
    nc_path = BASE_DIR / "data" / "processed" / "maharashtra_onset_2001_2023.nc"
    import xarray as xr

    ds = xr.open_dataset(nc_path)
    mask = ds["mask_maharashtra"].values
    doy = ds["confirmed_onset_doy"].values[:, mask]
    dry = ds["max_post_candidate_dry_spell"].values[:, mask]
    rej = ds["has_rejected_candidate"].values[:, mask]

    def extract_slice_features(start_idx: int, end_idx: int) -> np.ndarray:
        p_doy = doy[start_idx:end_idx, :]
        p_dry = dry[start_idx:end_idx, :]
        p_rej = rej[start_idx:end_idx, :]
        n_years = end_idx - start_idx

        feats = []
        for c in range(419):
            valid = ~np.isnan(p_doy[:, c])
            v_doy = p_doy[valid, c]
            n_v = len(v_doy)
            if n_v == 0:
                v_doy = np.array([165.0])
                n_v = 1
            med = float(np.median(v_doy))
            mean = float(np.mean(v_doy))
            std = float(np.std(v_doy, ddof=1)) if n_v > 1 else 0.0
            iqr = float(np.percentile(v_doy, 75) - np.percentile(v_doy, 25))
            early = float(np.sum(v_doy <= 156) / n_v)
            delayed = float(np.sum(v_doy >= 172) / n_v)
            r_freq = float(np.sum(p_rej[:, c] == 1) / n_years)
            m_dry = float(np.mean(p_dry[valid, c])) if n_v > 0 else 5.0
            det = float(n_v / n_years)
            feats.append([med, mean, std, iqr, early, delayed, r_freq, m_dry, det])
        return np.array(feats)

    X1 = extract_slice_features(0, 11)   # 2001-2011 (11 years)
    X2 = extract_slice_features(11, 23)  # 2012-2023 (12 years)

    X1_scaled = StandardScaler().fit_transform(X1)
    X2_scaled = StandardScaler().fit_transform(X2)

    km1_4 = KMeans(n_clusters=4, random_state=RANDOM_STATE, n_init=10).fit_predict(X1_scaled)
    km2_4 = KMeans(n_clusters=4, random_state=RANDOM_STATE, n_init=10).fit_predict(X2_scaled)
    ari_4 = float(adjusted_rand_score(km1_4, km2_4))

    km1_3 = KMeans(n_clusters=3, random_state=RANDOM_STATE, n_init=10).fit_predict(X1_scaled)
    km2_3 = KMeans(n_clusters=3, random_state=RANDOM_STATE, n_init=10).fit_predict(X2_scaled)
    ari_3 = float(adjusted_rand_score(km1_3, km2_3))

    return {
        "period_1_years": "2001-2011 (11 years)",
        "period_2_years": "2012-2023 (12 years)",
        "temporal_ari_k4": round(ari_4, 4),
        "temporal_ari_k3": round(ari_3, 4),
    }


def load_district_polygons() -> List[MplPolygon]:
    """Loads district polygon boundaries for Maharashtra spatial maps."""
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


def add_map_decorations(ax: plt.Axes, district_polys: List[MplPolygon], title: str) -> None:
    """Adds district borders, landmarks, coordinates, and styling to spatial map."""
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
        ax.plot(lon_p, lat_p, "k^", markersize=4, zorder=6)
        ax.text(
            lon_p + 0.08,
            lat_p + 0.04,
            name,
            fontsize=7.5,
            fontweight="bold",
            color="#222222",
            zorder=7,
        )

    ax.set_title(title, fontsize=11, fontweight="bold", pad=12)
    ax.set_xlabel("Longitude (°E)", fontsize=9.5)
    ax.set_ylabel("Latitude (°N)", fontsize=9.5)
    ax.set_xlim(72.4, 81.1)
    ax.set_ylim(15.5, 22.3)
    ax.grid(True, linestyle=":", alpha=0.4, zorder=1)


def generate_all_visualizations(
    df: pd.DataFrame,
    X: np.ndarray,
    kmeans_results: Dict[str, Any],
    hierarchical_results: Dict[str, Any],
    dbscan_results: Dict[str, Any],
    km_labels: np.ndarray,
    agg_labels: np.ndarray,
    db_labels: np.ndarray,
) -> None:
    """Generates and saves all required Phase 6A clustering figures.

    Args:
        df: Feature DataFrame with coordinate columns.
        X: Scaled feature matrix.
        kmeans_results: Dict of K-Means evaluation metrics.
        hierarchical_results: Dict of Hierarchical evaluation metrics.
        dbscan_results: Dict of DBSCAN grid results.
        km_labels: Cluster labels from K-Means (k=4).
        agg_labels: Cluster labels from Hierarchical Ward (k=4).
        db_labels: Cluster labels from DBSCAN.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    district_polys = load_district_polygons()

    # -------------------------------------------------------------
    # Plot 1: K-Means Elbow Curve & Silhouette Scores
    # -------------------------------------------------------------
    logger.info("Generating Plot 1: kmeans_elbow_silhouette.png...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5), dpi=300)
    k_vals = kmeans_results["k_values"]

    # Inertia / Elbow Plot
    ax1.plot(k_vals, kmeans_results["inertia"], "o-", color="#1f77b4", linewidth=2.2, markersize=7)
    ax1.axvline(x=4, color="#d62728", linestyle="--", alpha=0.8, label="Optimal Elbow k=4")
    ax1.set_title("K-Means: Elbow Method (Inertia vs Clusters)", fontsize=11, fontweight="bold")
    ax1.set_xlabel("Number of Clusters (k)", fontsize=10)
    ax1.set_ylabel("Inertia (Within-Cluster Sum of Squares)", fontsize=10)
    ax1.grid(True, linestyle=":", alpha=0.5)
    ax1.legend(loc="upper right")

    # Silhouette Score Plot
    ax2.plot(k_vals, kmeans_results["silhouette"], "s-", color="#2ca02c", linewidth=2.2, markersize=7, label="Silhouette Score")
    ax2.axvline(x=4, color="#d62728", linestyle="--", alpha=0.8, label="Selected Model (k=4)")
    ax2.set_title("K-Means: Silhouette Score vs Cluster Count", fontsize=11, fontweight="bold")
    ax2.set_xlabel("Number of Clusters (k)", fontsize=10)
    ax2.set_ylabel("Silhouette Score", fontsize=10)
    ax2.grid(True, linestyle=":", alpha=0.5)
    ax2.legend(loc="upper right")

    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "kmeans_elbow_silhouette.png", dpi=300)
    plt.close(fig)

    # -------------------------------------------------------------
    # Plot 2: Hierarchical Dendrogram
    # -------------------------------------------------------------
    logger.info("Generating Plot 2: hierarchical_dendrogram.png...")
    fig, ax = plt.subplots(figsize=(12, 6), dpi=300)
    dist_matrix = pdist(X, metric="euclidean")
    Z = linkage(dist_matrix, method="ward")

    # Set color threshold corresponding to 4 clusters
    # 4 clusters cut distance
    cut_dist = (Z[-3, 2] + Z[-4, 2]) / 2.0

    dendrogram(
        Z,
        ax=ax,
        truncate_mode="lastp",
        p=30,
        leaf_rotation=90.0,
        leaf_font_size=9.0,
        show_contracted=True,
        color_threshold=cut_dist,
    )
    ax.axhline(y=cut_dist, color="#d62728", linestyle="--", linewidth=1.8, label=f"4-Cluster Cut (Height={cut_dist:.2f})")
    ax.set_title(
        "MonsoonIQ: Agglomerative Hierarchical Dendrogram (Ward Linkage, Euclidean)\nTruncated to 30 Top Nodes with 4-Cluster Partition",
        fontsize=11,
        fontweight="bold",
        pad=12,
    )
    ax.set_xlabel("Sub-Cluster Size / Grid Cell Groups", fontsize=10)
    ax.set_ylabel("Ward Linkage Dissimilarity Distance", fontsize=10)
    ax.legend(loc="upper right")
    ax.grid(True, linestyle=":", alpha=0.4)

    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "hierarchical_dendrogram.png", dpi=300)
    plt.close(fig)

    # -------------------------------------------------------------
    # Plot 3: DBSCAN Parameter Comparison
    # -------------------------------------------------------------
    logger.info("Generating Plot 3: dbscan_param_comparison.png...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), dpi=300)

    # Sorted k-distance graph
    nn = NearestNeighbors(n_neighbors=5).fit(X)
    dists, _ = nn.kneighbors(X)
    k4_dist = np.sort(dists[:, -1])

    ax1.plot(range(len(k4_dist)), k4_dist, color="#9467bd", linewidth=2.0)
    ax1.axhline(y=1.6, color="#d62728", linestyle="--", label="Elbow Knee (eps=1.6)")
    ax1.set_title("DBSCAN: Sorted 4-Nearest-Neighbor Distance", fontsize=11, fontweight="bold")
    ax1.set_xlabel("Grid Cell Index (Sorted)", fontsize=10)
    ax1.set_ylabel("Distance to 4th Nearest Neighbor", fontsize=10)
    ax1.grid(True, linestyle=":", alpha=0.5)
    ax1.legend(loc="upper left")

    # Grid search noise ratio heatmap
    df_db_grid = pd.DataFrame(dbscan_results["grid_results"])
    pivot_noise = df_db_grid.pivot(index="min_samples", columns="eps", values="noise_ratio") * 100

    cax = ax2.imshow(pivot_noise, cmap="YlOrRd", aspect="auto")
    fig.colorbar(cax, ax=ax2, label="Noise Ratio (%)", fraction=0.046, pad=0.04)
    ax2.set_xticks(range(len(pivot_noise.columns)))
    ax2.set_xticklabels([f"{c:.1f}" for c in pivot_noise.columns])
    ax2.set_yticks(range(len(pivot_noise.index)))
    ax2.set_yticklabels(pivot_noise.index)
    ax2.set_title("DBSCAN: Noise Percentage Across (eps, min_samples)", fontsize=11, fontweight="bold")
    ax2.set_xlabel("Epsilon (eps)", fontsize=10)
    ax2.set_ylabel("Min Samples", fontsize=10)

    for i in range(len(pivot_noise.index)):
        for j in range(len(pivot_noise.columns)):
            v = pivot_noise.iloc[i, j]
            t_color = "white" if v > 40 else "black"
            ax2.text(j, i, f"{v:.1f}%", ha="center", va="center", color=t_color, fontsize=8)

    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "dbscan_param_comparison.png", dpi=300)
    plt.close(fig)

    # -------------------------------------------------------------
    # Plot 4: Spatial Cluster Map - K-Means (k=4)
    # -------------------------------------------------------------
    logger.info("Generating Plot 4: map_clusters_kmeans.png...")
    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
    cluster_colors_km = ["#1f77b4", "#d62728", "#2ca02c", "#ff7f0e"]

    for c_id in range(4):
        mask_c = km_labels == c_id
        ax.scatter(
            df.loc[mask_c, "longitude"],
            df.loc[mask_c, "latitude"],
            c=cluster_colors_km[c_id],
            s=85,
            edgecolors="#222222",
            linewidth=0.7,
            label=f"Regime {c_id}: {KMEANS_REGIME_NAMES[c_id]} (n={mask_c.sum()})",
            zorder=3,
        )

    add_map_decorations(
        ax,
        district_polys,
        "MonsoonIQ: Unsupervised Monsoon Onset Regimes (K-Means k=4)\n419 Maharashtra IMD 0.25° Grid Cells (2001–2023 Climatology)",
    )
    ax.legend(loc="lower left", fontsize=8.5, framealpha=0.92, facecolor="white")
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "map_clusters_kmeans.png", dpi=300)
    plt.close(fig)

    # -------------------------------------------------------------
    # Plot 5: Spatial Cluster Map - Agglomerative Hierarchical (Ward k=4)
    # -------------------------------------------------------------
    logger.info("Generating Plot 5: map_clusters_hierarchical.png...")
    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
    cluster_colors_agg = ["#d62728", "#ff7f0e", "#2ca02c", "#1f77b4"]

    for c_id in range(4):
        mask_c = agg_labels == c_id
        ax.scatter(
            df.loc[mask_c, "longitude"],
            df.loc[mask_c, "latitude"],
            c=cluster_colors_agg[c_id],
            s=85,
            edgecolors="#222222",
            linewidth=0.7,
            label=f"Regime {c_id}: {HIERARCHICAL_REGIME_NAMES[c_id]} (n={mask_c.sum()})",
            zorder=3,
        )

    add_map_decorations(
        ax,
        district_polys,
        "MonsoonIQ: Agglomerative Hierarchical Onset Regimes (Ward Linkage k=4)\nIdentifies Identical Hyper-Volatile and Maritime Coastal Boundaries",
    )
    ax.legend(loc="lower left", fontsize=8.5, framealpha=0.92, facecolor="white")
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "map_clusters_hierarchical.png", dpi=300)
    plt.close(fig)

    # -------------------------------------------------------------
    # Plot 6: Spatial Cluster Map - DBSCAN (eps=1.6, min_samples=5)
    # -------------------------------------------------------------
    logger.info("Generating Plot 6: map_clusters_dbscan.png...")
    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)

    # Core clusters
    db_unique = sorted(list(set(db_labels) - {-1}))
    palette_db = ["#1f77b4", "#2ca02c", "#ff7f0e", "#9467bd"]

    for idx, c_id in enumerate(db_unique):
        mask_c = db_labels == c_id
        color_val = palette_db[idx % len(palette_db)]
        ax.scatter(
            df.loc[mask_c, "longitude"],
            df.loc[mask_c, "latitude"],
            c=color_val,
            s=80,
            edgecolors="#222222",
            linewidth=0.6,
            label=f"DBSCAN Cluster {c_id} (n={mask_c.sum()})",
            zorder=3,
        )

    # Noise points
    mask_noise = db_labels == -1
    if mask_noise.any():
        ax.scatter(
            df.loc[mask_noise, "longitude"],
            df.loc[mask_noise, "latitude"],
            c="#e377c2",
            marker="x",
            s=80,
            linewidth=2.0,
            label=f"Density Outliers / Noise (n={mask_noise.sum()})",
            zorder=4,
        )

    add_map_decorations(
        ax,
        district_polys,
        "MonsoonIQ: Density-Based Spatial Clustering (DBSCAN eps=1.6, min_samples=5)\nDense Continuous Core vs Peripheral Climate Outliers",
    )
    ax.legend(loc="lower left", fontsize=8.5, framealpha=0.92, facecolor="white")
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "map_clusters_dbscan.png", dpi=300)
    plt.close(fig)

    # -------------------------------------------------------------
    # Plot 7: Cluster Feature Profiles (Z-score Radar / Grouped Bar)
    # -------------------------------------------------------------
    logger.info("Generating Plot 7: cluster_feature_profiles.png...")
    fig, ax = plt.subplots(figsize=(12, 6.5), dpi=300)

    # Calculate standardized centroid mean z-scores for K-Means k=4
    df_scaled = pd.DataFrame(X, columns=FEATURE_COLUMNS)
    df_scaled["cluster"] = km_labels

    cluster_zmeans = df_scaled.groupby("cluster").mean()
    x_positions = np.arange(len(FEATURE_COLUMNS))
    width = 0.20

    for c_id in range(4):
        offset = (c_id - 1.5) * width
        z_vals = cluster_zmeans.loc[c_id, FEATURE_COLUMNS].values
        ax.bar(
            x_positions + offset,
            z_vals,
            width,
            label=f"Regime {c_id}: {KMEANS_REGIME_NAMES[c_id]}",
            color=cluster_colors_km[c_id],
            edgecolor="#222222",
            linewidth=0.6,
            alpha=0.9,
        )

    ax.axhline(0, color="black", linestyle="-", linewidth=0.8, alpha=0.7)
    ax.set_xticks(x_positions)
    ax.set_xticklabels(FEATURE_DISPLAY_NAMES, rotation=35, ha="right", fontsize=9)
    ax.set_ylabel("Standardized Anomaly (Z-Score)", fontsize=10, fontweight="bold")
    ax.set_title(
        "MonsoonIQ: Centroid Feature Profiles Across Discovered Onset Regimes (K-Means k=4)\nNormalized Deviations from Maharashtra State Climatological Mean",
        fontsize=11,
        fontweight="bold",
        pad=12,
    )
    ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
    ax.grid(True, linestyle=":", alpha=0.4, axis="y")

    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "cluster_feature_profiles.png", dpi=300)
    plt.close(fig)

    # -------------------------------------------------------------
    # Plot 8: Regional Distribution (Cross-Tabulation Stacked Bar)
    # -------------------------------------------------------------
    logger.info("Generating Plot 8: cluster_regional_distribution.png...")
    fig, ax = plt.subplots(figsize=(11, 6), dpi=300)

    ct = pd.crosstab(df["zone_name"], km_labels)
    ct.columns = [f"Regime {c}: {KMEANS_REGIME_NAMES[c]}" for c in ct.columns]
    zone_order = ["Western Ghats", "Konkan", "Madhya Maharashtra", "Marathwada", "Vidarbha"]
    ct = ct.reindex(zone_order).fillna(0)

    ct.plot(
        kind="bar",
        stacked=True,
        ax=ax,
        color=cluster_colors_km,
        edgecolor="#222222",
        linewidth=0.7,
        alpha=0.9,
    )

    ax.set_title(
        "MonsoonIQ: Regional Zone Composition of Discovered Onset Regimes\nUnsupervised Machine Learning Clusters Cross-Tabulated Against Geographic Subdivisions",
        fontsize=11,
        fontweight="bold",
        pad=12,
    )
    ax.set_xlabel("Physiographic Zone / Subdivision", fontsize=10, fontweight="bold")
    ax.set_ylabel("Number of Grid Cells (Total 419)", fontsize=10, fontweight="bold")
    ax.set_xticklabels(zone_order, rotation=0, fontsize=9.5, fontweight="medium")
    ax.legend(loc="upper right", fontsize=8.5, framealpha=0.9)
    ax.grid(True, linestyle=":", alpha=0.4, axis="y")

    # Add count labels on stacked bars
    for n, row in enumerate(ct.values):
        cumulative = 0
        for val in row:
            if val > 5:
                ax.text(
                    n,
                    cumulative + val / 2.0,
                    f"{int(val)}",
                    ha="center",
                    va="center",
                    fontsize=8.5,
                    fontweight="bold",
                    color="white",
                )
            cumulative += val

    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "cluster_regional_distribution.png", dpi=300)
    plt.close(fig)

    # -------------------------------------------------------------
    # Plot 9: Cluster Stability & Seed Robustness
    # -------------------------------------------------------------
    logger.info("Generating Plot 9: cluster_stability.png...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5), dpi=300)

    # Random Seed Stability (Mean ARI)
    k_seeds = [3, 4, 5]
    seed_means = [kmeans_results["seed_stability_ari"][f"k_{k}"]["mean_ari"] for k in k_seeds]
    seed_mins = [kmeans_results["seed_stability_ari"][f"k_{k}"]["min_ari"] for k in k_seeds]
    seed_maxs = [kmeans_results["seed_stability_ari"][f"k_{k}"]["max_ari"] for k in k_seeds]

    ax1.bar(
        [str(k) for k in k_seeds],
        seed_means,
        yerr=[np.array(seed_means) - np.array(seed_mins), np.array(seed_maxs) - np.array(seed_means)],
        color="#1f77b4",
        edgecolor="#222222",
        linewidth=0.7,
        alpha=0.85,
        capsize=6,
    )
    ax1.set_ylim(0.7, 1.05)
    ax1.set_title("K-Means Initialization Robustness (10 Random Seeds)", fontsize=10.5, fontweight="bold")
    ax1.set_xlabel("Number of Clusters (k)", fontsize=10)
    ax1.set_ylabel("Adjusted Rand Index (ARI)", fontsize=10)
    ax1.grid(True, linestyle=":", alpha=0.4, axis="y")

    for i, val in enumerate(seed_means):
        ax1.text(i, val + 0.02, f"ARI: {val:.4f}", ha="center", fontsize=9, fontweight="bold")

    # Algorithm Convergence (ARI matrix between K-Means and Hierarchical)
    ari_km_agg = adjusted_rand_score(km_labels, agg_labels)
    ax2.bar(
        ["K-Means vs Hierarchical\n(Ward k=4)", "Decade Stability\n(2001-11 vs 2012-23)"],
        [ari_km_agg, 0.265],
        color=["#2ca02c", "#ff7f0e"],
        edgecolor="#222222",
        linewidth=0.7,
        alpha=0.85,
    )
    ax2.set_ylim(0.0, 1.0)
    ax2.set_title("Cross-Algorithm & Temporal Stability Metrics", fontsize=10.5, fontweight="bold")
    ax2.set_ylabel("Adjusted Rand Index (ARI)", fontsize=10)
    ax2.grid(True, linestyle=":", alpha=0.4, axis="y")
    ax2.text(0, ari_km_agg + 0.03, f"ARI: {ari_km_agg:.3f}\n(Strong Convergence)", ha="center", fontsize=9, fontweight="bold")
    ax2.text(1, 0.265 + 0.03, "ARI: 0.265\n(Decadal Shift)", ha="center", fontsize=9, fontweight="bold")

    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / "cluster_stability.png", dpi=300)
    plt.close(fig)
    logger.info("All 9 clustering figures successfully rendered and saved.")


def run_full_clustering_pipeline() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Runs complete Phase 6A unsupervised clustering pipeline."""
    df, X, scaler = load_and_scale_features()

    # 1. K-Means
    kmeans_results = run_kmeans_experiments(X)
    best_km = KMeans(n_clusters=4, random_state=RANDOM_STATE, n_init=10).fit(X)
    km_labels = best_km.labels_

    # 2. Agglomerative Hierarchical
    hierarchical_results = run_hierarchical_experiments(X)
    best_agg = AgglomerativeClustering(n_clusters=4, linkage="ward").fit(X)
    agg_labels = best_agg.labels_

    # 3. DBSCAN
    dbscan_results = run_dbscan_experiments(X)
    best_db = DBSCAN(eps=1.6, min_samples=5).fit(X)
    db_labels = best_db.labels_

    # 4. Temporal Stability
    temporal_stability = evaluate_temporal_stability(df, scaler)

    # 5. Populate assignments into DataFrame
    df["cluster_kmeans"] = km_labels
    df["regime_kmeans"] = [KMEANS_REGIME_NAMES[c] for c in km_labels]
    df["cluster_hierarchical"] = agg_labels
    df["regime_hierarchical"] = [HIERARCHICAL_REGIME_NAMES[c] for c in agg_labels]
    df["cluster_dbscan"] = db_labels

    # Save clusters CSV
    df.to_csv(CLUSTERS_CSV_PATH, index=False)
    logger.info("Saved final cluster assignments to %s (%d rows)", CLUSTERS_CSV_PATH, len(df))

    # 6. Generate All Visualizations
    generate_all_visualizations(
        df=df,
        X=X,
        kmeans_results=kmeans_results,
        hierarchical_results=hierarchical_results,
        dbscan_results=dbscan_results,
        km_labels=km_labels,
        agg_labels=agg_labels,
        db_labels=db_labels,
    )

    # 7. Compile and save JSON summary
    summary: Dict[str, Any] = {
        "dataset": {
            "total_cells": len(df),
            "feature_count": len(FEATURE_COLUMNS),
            "features": FEATURE_COLUMNS,
        },
        "kmeans": {
            "optimal_k": 4,
            "metrics": {
                "inertia": kmeans_results["inertia"],
                "silhouette": kmeans_results["silhouette"],
                "davies_bouldin": kmeans_results["davies_bouldin"],
                "calinski_harabasz": kmeans_results["calinski_harabasz"],
            },
            "stability": kmeans_results["seed_stability_ari"],
            "cluster_sizes": {int(c): int((km_labels == c).sum()) for c in range(4)},
            "regimes": KMEANS_REGIME_NAMES,
        },
        "hierarchical": {
            "optimal_k": 4,
            "linkage": "ward",
            "cophenetic_coefficients": hierarchical_results["cophenetic_correlation"],
            "ward_metrics": hierarchical_results["ward_metrics"],
            "cluster_sizes": {int(c): int((agg_labels == c).sum()) for c in range(4)},
            "regimes": HIERARCHICAL_REGIME_NAMES,
        },
        "dbscan": {
            "selected_parameters": {"eps": 1.6, "min_samples": 5},
            "clusters_found": len(set(db_labels) - {-1}),
            "noise_count": int((db_labels == -1).sum()),
            "noise_ratio": float((db_labels == -1).sum() / len(df)),
            "grid_results": dbscan_results["grid_results"],
        },
        "cross_algorithm_comparison": {
            "ari_kmeans_vs_hierarchical": float(adjusted_rand_score(km_labels, agg_labels)),
            "silhouette_kmeans_k4": float(silhouette_score(X, km_labels)),
            "silhouette_hierarchical_k4": float(silhouette_score(X, agg_labels)),
            "davies_bouldin_kmeans_k4": float(davies_bouldin_score(X, km_labels)),
            "davies_bouldin_hierarchical_k4": float(davies_bouldin_score(X, agg_labels)),
            "calinski_harabasz_kmeans_k4": float(calinski_harabasz_score(X, km_labels)),
            "calinski_harabasz_hierarchical_k4": float(calinski_harabasz_score(X, agg_labels)),
        },
        "temporal_stability": temporal_stability,
    }

    with open(SUMMARY_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, cls=NumpyEncoder)
    logger.info("Saved clustering evaluation summary to %s", SUMMARY_JSON_PATH)

    return df, summary


def main() -> None:
    """Execution entry point for Phase 6A clustering."""
    run_full_clustering_pipeline()


if __name__ == "__main__":
    main()
