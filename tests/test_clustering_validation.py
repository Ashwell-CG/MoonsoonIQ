"""MonsoonIQ - Test Suite for Phase 6B Clustering Robustness and Validation.

Validates K=3 vs K=4 comparisons, feature subset sensitivity, bootstrap temporal
stability, K-Means vs Hierarchical agreement, DBSCAN noise assessment, and spatial contiguity.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

BASE_DIR: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

FEATURES_CSV: Path = BASE_DIR / "data" / "processed" / "monsoon_onset_features.csv"
CLUSTERS_CSV: Path = BASE_DIR / "data" / "processed" / "monsoon_onset_clusters.csv"
SUMMARY_JSON: Path = BASE_DIR / "outputs" / "clustering" / "clustering_validation_summary.json"
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
def validation_summary() -> dict:
    """Fixture providing the validation summary JSON."""
    assert SUMMARY_JSON.exists(), f"Missing validation summary at {SUMMARY_JSON}"
    with open(SUMMARY_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def test_k3_vs_k4_metrics(df_features: pd.DataFrame, validation_summary: dict) -> None:
    """Verifies K=3 and K=4 clustering metrics match audited benchmarks."""
    X = StandardScaler().fit_transform(df_features[FEATURE_COLUMNS].values)

    km3 = KMeans(n_clusters=3, random_state=42, n_init=10).fit(X)
    km4 = KMeans(n_clusters=4, random_state=42, n_init=10).fit(X)

    sil3 = silhouette_score(X, km3.labels_)
    sil4 = silhouette_score(X, km4.labels_)

    # K=3 has higher silhouette score than K=4
    assert sil3 > sil4
    assert sil3 >= 0.34
    assert sil4 >= 0.29

    # Verify cluster size of high-volatility rain-shadow in K=4
    counts_k4 = pd.Series(km4.labels_).value_counts().to_dict()
    assert 42 in counts_k4.values(), "K=4 must isolate the 42-cell high-volatility core"


def test_feature_sensitivity_subsets(df_features: pd.DataFrame, validation_summary: dict) -> None:
    """Verifies that removing redundant features preserves the 4 core regimes."""
    subsets = validation_summary["task_2_feature_sensitivity"]

    # Without detection freq (8 features) should be almost identical to baseline (ARI > 0.90)
    assert subsets["without_detection_freq_8"]["ari_k4"] >= 0.90

    # Reduced non-redundant set (6 features) should have strong similarity (ARI > 0.70)
    assert subsets["reduced_non_redundant_6"]["ari_k4"] >= 0.70

    # Timing-only features should have low ARI (< 0.50), proving that timing alone is insufficient
    assert subsets["timing_only_3"]["ari_k4"] < 0.50


def test_bootstrap_temporal_stability(validation_summary: dict) -> None:
    """Verifies that 100 bootstrap resamples demonstrate stable cluster recovery."""
    boot = validation_summary["task_3_temporal_bootstrap"]
    assert boot["bootstrap_iterations"] == 100
    assert 0.30 <= boot["k4"]["mean_ari"] <= 0.50
    assert boot["k4"]["ci_95"][0] > 0.15
    assert boot["k4"]["ci_95"][1] > 0.50


def test_algorithm_agreement_and_volatile_audit(validation_summary: dict) -> None:
    """Verifies K-Means vs Hierarchical agreement and specific 42-cell audit."""
    agree = validation_summary["task_4_algorithm_agreement"]
    assert agree["exact_agreement_cells"] == 368
    assert agree["exact_agreement_pct"] >= 87.0
    assert agree["ari"] == 0.6803

    # The 42 volatile cells in K-Means must be split strictly between Volatile (30) and Transition (12) in Hierarchical
    vol = agree["volatile_cluster_breakdown"]
    assert vol.get("Rain-Shadow High-Volatility") == 30
    assert vol.get("Interior Semi-Arid Transition") == 12


def test_geographic_spatial_validation(validation_summary: dict) -> None:
    """Verifies spatial contiguity and significant Moran's I spatial autocorrelation."""
    geo = validation_summary["task_6_geographic_validation"]

    # Over 70% of grid neighbors must share the exact same regime
    assert geo["mean_contiguity_8_connected_pct"] >= 70.0
    assert geo["mean_contiguity_4_connected_pct"] >= 70.0

    # Moran's I for all onset dynamics features and regimes must indicate strong spatial clustering (> 0.40)
    for feat_name, moran_val in geo["morans_i"].items():
        assert moran_val > 0.40, f"Low Moran's I for {feat_name}: {moran_val}"


def test_validation_visualizations_exist() -> None:
    """Ensures all Phase 6B validation diagnostic plots are generated and valid."""
    required_plots = [
        "k3_vs_k4_comparison.png",
        "feature_sensitivity_ari.png",
        "bootstrap_stability_analysis.png",
        "algorithm_agreement_map.png",
        "algorithm_contingency_heatmap.png",
        "spatial_contiguity_validation.png",
        "dbscan_sensitivity_reassessment.png",
    ]
    for p_name in required_plots:
        p_path = PLOTS_DIR / p_name
        assert p_path.exists(), f"Missing required validation plot {p_path}"
        assert p_path.stat().st_size > 10000, f"Plot {p_path} is suspiciously small"
