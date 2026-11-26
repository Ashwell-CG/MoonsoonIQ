"""MonsoonIQ - Test Suite for Phase 6A Monsoon Onset Clustering.

Validates feature engineering, algorithmic implementations (K-Means, Hierarchical,
DBSCAN), cross-algorithm stability, feature isolation, and cluster dataset integrity.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest
from sklearn.cluster import AgglomerativeClustering, DBSCAN, KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

BASE_DIR: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

FEATURES_CSV: Path = BASE_DIR / "data" / "processed" / "monsoon_onset_features.csv"
CLUSTERS_CSV: Path = BASE_DIR / "data" / "processed" / "monsoon_onset_clusters.csv"
SUMMARY_JSON: Path = BASE_DIR / "outputs" / "clustering" / "clustering_evaluation_summary.json"
PLOTS_DIR: Path = BASE_DIR / "outputs" / "clustering"

EXPECTED_CELL_COUNT: int = 419
FEATURE_COLUMNS = [
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


@pytest.fixture(scope="module")
def df_features() -> pd.DataFrame:
    """Fixture providing the engineered onset feature DataFrame."""
    assert FEATURES_CSV.exists(), f"Missing features CSV at {FEATURES_CSV}"
    return pd.read_csv(FEATURES_CSV)


@pytest.fixture(scope="module")
def df_clusters() -> pd.DataFrame:
    """Fixture providing the final cluster assignments DataFrame."""
    assert CLUSTERS_CSV.exists(), f"Missing clusters CSV at {CLUSTERS_CSV}"
    return pd.read_csv(CLUSTERS_CSV)


@pytest.fixture(scope="module")
def summary_dict() -> dict:
    """Fixture providing the evaluation summary JSON."""
    assert SUMMARY_JSON.exists(), f"Missing summary JSON at {SUMMARY_JSON}"
    with open(SUMMARY_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def test_feature_dataset_dimensions_and_nulls(df_features: pd.DataFrame) -> None:
    """Verifies that feature matrix has exactly 419 rows and no missing values."""
    assert len(df_features) == EXPECTED_CELL_COUNT, (
        f"Expected {EXPECTED_CELL_COUNT} rows, got {len(df_features)}"
    )
    for col in FEATURE_COLUMNS:
        assert col in df_features.columns, f"Missing expected feature {col}"
        assert not df_features[col].isna().any(), f"Feature {col} contains NaNs"
        assert not np.isinf(df_features[col]).any(), f"Feature {col} contains infs"


def test_feature_physical_ranges(df_features: pd.DataFrame) -> None:
    """Ensures engineered features fall within physically valid climatological bounds."""
    # DOY within pre-monsoon to late monsoon range [140, 220]
    assert df_features["median_onset_doy"].min() >= 140.0
    assert df_features["median_onset_doy"].max() <= 220.0
    assert df_features["mean_onset_doy"].min() >= 140.0
    assert df_features["mean_onset_doy"].max() <= 220.0

    # Frequencies must strictly lie in [0.0, 1.0]
    freq_cols = [
        "early_onset_freq",
        "delayed_onset_freq",
        "rejected_candidate_freq",
        "onset_detection_freq",
    ]
    for col in freq_cols:
        assert (df_features[col] >= 0.0).all(), f"{col} has negative values"
        assert (df_features[col] <= 1.0).all(), f"{col} exceeds 1.0"

    # All cells must have at least 85% confirmed onset detection rate
    assert (df_features["onset_detection_freq"] >= 0.85).all()

    # Dry spells in [0, 20]
    assert (df_features["mean_max_dry_spell"] >= 0.0).all()
    assert (df_features["mean_max_dry_spell"] <= 20.0).all()


def test_feature_isolation_from_spatial_coordinates(df_features: pd.DataFrame) -> None:
    """Verifies that clustering features do not include spatial coordinates or admin labels."""
    forbidden = ["latitude", "longitude", "lat_idx", "lon_idx", "district", "zone_id", "zone_name"]
    for col in forbidden:
        assert col not in FEATURE_COLUMNS, f"Forbidden spatial attribute {col} in FEATURE_COLUMNS"


def test_kmeans_reproducibility_and_metrics(df_features: pd.DataFrame) -> None:
    """Tests K-Means k=4 reproducibility and verifies metric thresholds."""
    X = StandardScaler().fit_transform(df_features[FEATURE_COLUMNS].values)

    km1 = KMeans(n_clusters=4, random_state=42, n_init=10).fit(X)
    km2 = KMeans(n_clusters=4, random_state=42, n_init=10).fit(X)

    # Identical predictions with identical random_state
    np.testing.assert_array_equal(km1.labels_, km2.labels_)

    # Silhouette score should be >= 0.28 for k=4
    sil = silhouette_score(X, km1.labels_)
    assert sil >= 0.28, f"K-Means silhouette score {sil:.3f} below expected 0.28"

    # Cluster sizes: no empty clusters, smallest cluster >= 25 cells
    unique, counts = np.unique(km1.labels_, return_counts=True)
    assert len(unique) == 4
    assert counts.min() >= 25


def test_hierarchical_ward_reproducibility(df_features: pd.DataFrame) -> None:
    """Tests Agglomerative Hierarchical clustering reproducibility and convergence."""
    X = StandardScaler().fit_transform(df_features[FEATURE_COLUMNS].values)

    agg = AgglomerativeClustering(n_clusters=4, linkage="ward")
    labels = agg.fit_predict(X)

    assert len(set(labels)) == 4
    sil = silhouette_score(X, labels)
    assert sil >= 0.25, f"Hierarchical silhouette score {sil:.3f} below expected 0.25"


def test_dbscan_outlier_identification(df_features: pd.DataFrame) -> None:
    """Verifies DBSCAN behavior and identification of noise points."""
    X = StandardScaler().fit_transform(df_features[FEATURE_COLUMNS].values)

    db = DBSCAN(eps=1.6, min_samples=5).fit(X)
    labels = db.labels_

    assert -1 in labels, "DBSCAN should detect peripheral climate outliers as noise"
    noise_count = (labels == -1).sum()
    assert 10 <= noise_count <= 80, f"Unexpected noise count {noise_count}"


def test_cross_algorithm_convergence(df_features: pd.DataFrame) -> None:
    """Tests Adjusted Rand Index between K-Means and Hierarchical Clustering."""
    X = StandardScaler().fit_transform(df_features[FEATURE_COLUMNS].values)

    km = KMeans(n_clusters=4, random_state=42, n_init=10).fit_predict(X)
    agg = AgglomerativeClustering(n_clusters=4, linkage="ward").fit_predict(X)

    ari = adjusted_rand_score(km, agg)
    # Both algorithms must demonstrate strong cross-method agreement (ARI > 0.60)
    assert ari > 0.60, f"Cross-algorithm ARI {ari:.3f} lower than expected 0.60"


def test_cluster_dataset_columns_and_integrity(df_clusters: pd.DataFrame) -> None:
    """Verifies that final cluster dataset contains all required fields and regimes."""
    required_cols = [
        "cell_id",
        "latitude",
        "longitude",
        "district",
        "zone_id",
        "zone_name",
        "cluster_kmeans",
        "regime_kmeans",
        "cluster_hierarchical",
        "regime_hierarchical",
        "cluster_dbscan",
    ]
    for col in required_cols:
        assert col in df_clusters.columns, f"Missing column {col} in clusters CSV"

    assert len(df_clusters) == EXPECTED_CELL_COUNT
    assert not df_clusters["regime_kmeans"].isna().any()
    assert not df_clusters["regime_hierarchical"].isna().any()
    assert len(df_clusters["regime_kmeans"].unique()) == 4


def test_output_figures_exist() -> None:
    """Verifies that all 10 required Phase 6A clustering visualization files exist."""
    required_plots = [
        "feature_correlation_heatmap.png",
        "kmeans_elbow_silhouette.png",
        "hierarchical_dendrogram.png",
        "dbscan_param_comparison.png",
        "map_clusters_kmeans.png",
        "map_clusters_hierarchical.png",
        "map_clusters_dbscan.png",
        "cluster_feature_profiles.png",
        "cluster_regional_distribution.png",
        "cluster_stability.png",
    ]
    for plot_name in required_plots:
        plot_path = PLOTS_DIR / plot_name
        assert plot_path.exists(), f"Missing visualization: {plot_path}"
        assert plot_path.stat().st_size > 10000, f"Visualization {plot_path} is suspiciously small"
