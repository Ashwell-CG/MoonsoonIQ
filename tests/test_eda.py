"""MonsoonIQ - Unit Tests for Phase 4 Historical Rainfall Exploratory Data Analysis.

Validates:
1. Presence and integrity of outputs/eda/eda_summary_metrics.json.
2. Presence and file size validity of all 8 generated publication plots.
3. Climatological normals (Statewide Annual ~1159 mm, JJAS ~1029 mm, JJAS % ~88.8%).
4. Identified extreme years (2015 driest, 2005 wettest).
5. Cross-regional gradients (Western Ghats > 3000 mm vs. Marathwada < 800 mm).
6. Intra-seasonal dry spell break durations and agricultural risk metrics.
7. Top historical extreme rainfall events and physical validity.
8. Trend analysis statistics and scientific neutrality.
"""

from pathlib import Path
import json
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "outputs" / "eda"
METRICS_JSON_PATH = OUTPUT_DIR / "eda_summary_metrics.json"

EXPECTED_PLOTS = [
    "map_mean_annual_rainfall.png",
    "map_rainfall_cv.png",
    "map_wet_days_frequency.png",
    "chart_annual_jjas_timeseries.png",
    "chart_monthly_regime.png",
    "chart_subdivision_comparison.png",
    "chart_dry_spell_distribution.png",
    "chart_extreme_events_timeline.png",
]


@pytest.fixture(scope="module")
def eda_metrics():
    """Loads the pre-computed EDA summary metrics JSON."""
    assert METRICS_JSON_PATH.exists(), f"Missing EDA metrics file: {METRICS_JSON_PATH}"
    with open(METRICS_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def test_eda_metrics_structure(eda_metrics):
    """Verifies the core structural schema of the EDA summary metrics."""
    assert eda_metrics["study_period"] == "2001–2023"
    assert eda_metrics["total_days"] == 8400
    assert eda_metrics["total_years"] == 23
    assert eda_metrics["valid_land_cells"] == 419
    assert "statewide" in eda_metrics
    assert "monthly_climatology_mm" in eda_metrics
    assert "yearly_jjas" in eda_metrics
    assert "regional_metrics" in eda_metrics
    assert "top_20_extremes" in eda_metrics
    assert "trends" in eda_metrics


def test_generated_plots_exist():
    """Verifies that all 8 publication-grade charts exist and have valid file sizes."""
    for plot_name in EXPECTED_PLOTS:
        plot_path = OUTPUT_DIR / plot_name
        assert plot_path.exists(), f"Plot not found: {plot_path}"
        # Ensure file is non-empty and of substantial size (> 100 KB for 300 DPI figures)
        file_size_kb = plot_path.stat().st_size / 1024
        assert file_size_kb > 100, f"Plot {plot_name} is too small ({file_size_kb:.1f} KB)"


def test_statewide_climatology(eda_metrics):
    """Verifies statewide annual and JJAS rainfall climatological values."""
    sw = eda_metrics["statewide"]
    assert 1100.0 < sw["mean_annual_rainfall_mm"] < 1200.0
    assert 980.0 < sw["mean_jjas_rainfall_mm"] < 1080.0
    assert 85.0 < sw["jjas_pct_of_annual"] < 92.0
    assert sw["driest_year"] == 2015
    assert sw["driest_year_rainfall_mm"] < 900.0
    assert sw["wettest_year"] == 2005
    assert sw["wettest_year_rainfall_mm"] > 1500.0
    assert 55.0 < sw["mean_annual_rainy_days"] < 65.0
    assert 2.0 < sw["mean_annual_heavy_days"] < 3.5


def test_monthly_monsoon_regime(eda_metrics):
    """Verifies monthly progression showing July peak and JJAS dominance."""
    m_clim = eda_metrics["monthly_climatology_mm"]
    assert len(m_clim) == 12

    # JJAS months must dominate
    jjas_sum = sum(m_clim[str(m)] for m in [6, 7, 8, 9])
    annual_sum = sum(m_clim[str(m)] for m in range(1, 13))
    assert (jjas_sum / annual_sum) > 0.85

    # July must be the climatological peak month
    assert m_clim["7"] > m_clim["6"]
    assert m_clim["7"] > m_clim["8"]
    assert m_clim["7"] > m_clim["9"]

    # Pre-monsoon dry season
    assert m_clim["1"] < 10.0
    assert m_clim["2"] < 10.0
    assert m_clim["12"] < 10.0


def test_cross_regional_gradients(eda_metrics):
    """Verifies physical orographic gradients and rainfall contrasts."""
    reg = eda_metrics["regional_metrics"]
    assert "Western Ghats" in reg
    assert "Konkan" in reg
    assert "Madhya Maharashtra" in reg
    assert "Marathwada" in reg
    assert "Vidarbha" in reg

    # Western Ghats must have highest rainfall
    assert reg["Western Ghats"]["mean_annual_mm"] > 3000.0
    assert reg["Western Ghats"]["mean_jjas_mm"] > 2800.0
    assert reg["Western Ghats"]["mean_wet_days"] > 100.0

    # Marathwada and Madhya Maharashtra in rain shadow
    assert reg["Marathwada"]["mean_annual_mm"] < 850.0
    assert reg["Madhya Maharashtra"]["mean_annual_mm"] < 900.0

    # Madhya Maharashtra and Marathwada have highest CV %
    assert reg["Madhya Maharashtra"]["mean_cv_pct"] > 35.0
    assert reg["Marathwada"]["mean_cv_pct"] > 25.0


def test_dry_spell_break_risks(eda_metrics):
    """Verifies that interior rain-shadow regions experience longer breaks than coastal/Ghats."""
    reg = eda_metrics["regional_metrics"]

    # Rain shadow regions experience much longer annual maximum breaks
    assert reg["Madhya Maharashtra"]["mean_annual_max_break_days"] > 15.0
    assert reg["Marathwada"]["mean_annual_max_break_days"] > 14.0

    # Coastal/Ghats have shorter breaks
    assert reg["Western Ghats"]["mean_annual_max_break_days"] < 10.0
    assert reg["Konkan"]["mean_annual_max_break_days"] < 12.0

    # Agricultural stress breaks (>= 14 days) are much more frequent in Madhya MH / Marathwada
    assert reg["Madhya Maharashtra"]["mean_breaks_ge_14_per_yr"] > 0.7
    assert reg["Marathwada"]["mean_breaks_ge_14_per_yr"] > 0.5
    assert reg["Western Ghats"]["mean_breaks_ge_14_per_yr"] < 0.2


def test_top_20_extreme_events(eda_metrics):
    """Verifies top historical extreme events and physical plausibility."""
    top_20 = eda_metrics["top_20_extremes"]
    assert len(top_20) == 20

    # Check top event: 639.27 mm on 2001-08-09
    top_1 = top_20[0]
    assert top_1["date"] == "2001-08-09"
    assert pytest.approx(top_1["rainfall_mm"], 0.1) == 639.27

    # Check Mumbai Deluge event: 2005-07-27
    dates = [ev["date"] for ev in top_20]
    assert "2005-07-27" in dates

    # Check that all top 20 are extreme (> 390 mm)
    for ev in top_20:
        assert ev["rainfall_mm"] >= 390.0


def test_trend_analysis_neutrality(eda_metrics):
    """Verifies statistical trend results without causal claims."""
    trends = eda_metrics["trends"]
    assert "Statewide_Annual" in trends
    assert "Statewide_JJAS" in trends

    # Statewide annual and JJAS trends over 2001-2023 must not be statistically significant (p > 0.05)
    assert not trends["Statewide_Annual"]["is_significant_5pct"]
    assert trends["Statewide_Annual"]["mk_p_val"] > 0.05
    assert not trends["Statewide_JJAS"]["is_significant_5pct"]
    assert trends["Statewide_JJAS"]["mk_p_val"] > 0.05
