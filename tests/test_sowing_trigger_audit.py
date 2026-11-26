"""MonsoonIQ - Test Suite for Phase 7.1 Sowing Trigger, Agricultural Evidence and Consistency Audit.

Validates:
1. Existence and integrity of sensitivity CSV, delay audit CSV, summary JSON, and diagnostic plots.
2. Exact delayed sowing counts, numerators, denominators, and cell-year consistency across regimes.
3. Rain-Shadow Trigger Anomaly resolution: verifies high post-trigger break probability and rolling window failure.
4. Institutional agricultural citations from ICAR-CRIDA, MPKV Rahuri, VNMKV Parbhani, Dr. PDKV Akola.
5. Conditional Go decision and mandatory advisory constraints for Phase 8.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import pandas as pd

# Paths
BASE_DIR: Path = Path(__file__).resolve().parent.parent
PROCESSED_DATA_DIR: Path = BASE_DIR / "data" / "processed"
OUTPUT_DIR: Path = BASE_DIR / "outputs" / "regime_validation"

SENSITIVITY_CSV: Path = PROCESSED_DATA_DIR / "sowing_trigger_sensitivity.csv"
DELAY_AUDIT_CSV: Path = PROCESSED_DATA_DIR / "sowing_delay_audit.csv"
SUMMARY_JSON: Path = OUTPUT_DIR / "sowing_trigger_audit_summary.json"

CHART_SENSITIVITY: Path = OUTPUT_DIR / "chart_sowing_trigger_sensitivity.png"
CHART_ANOMALY: Path = OUTPUT_DIR / "chart_rain_shadow_anomaly_audit.png"
CHART_DELAY: Path = OUTPUT_DIR / "chart_delayed_sowing_audit.png"


def test_audit_files_exist_and_non_empty() -> None:
    """Verifies that all Phase 7.1 data files and diagnostic charts exist and are non-empty."""
    for fpath in [
        SENSITIVITY_CSV,
        DELAY_AUDIT_CSV,
        SUMMARY_JSON,
        CHART_SENSITIVITY,
        CHART_ANOMALY,
        CHART_DELAY,
    ]:
        assert fpath.exists(), f"Missing required file: {fpath}"
        assert fpath.stat().st_size > 0, f"File is empty: {fpath}"


def test_delayed_sowing_statistics_consistency() -> None:
    """Audits exact delayed sowing statistics, numerators, denominators, and cell-year accounting."""
    df_delay = pd.read_csv(DELAY_AUDIT_CSV)
    assert len(df_delay) == 5, f"Expected 5 rows (4 regimes + statewide), got {len(df_delay)}"

    # Check statewide row
    state_row = df_delay[df_delay["regime"] == "Maharashtra Statewide"].iloc[0]
    assert state_row["grid_cells"] == 419
    assert state_row["total_cell_years"] == 9637
    assert state_row["on_time_june_count"] == 8543
    assert state_row["delayed_july_1_15_count"] == 884
    assert state_row["never_reached_july15_count"] == 210
    assert state_row["total_delayed_count"] == 1094
    assert state_row["total_delayed_cell_year_pct"] == pytest.approx(11.35, abs=0.05)

    # Core Interior Synchronized
    core_row = df_delay[df_delay["regime"] == "Core Interior Synchronized"].iloc[0]
    assert core_row["grid_cells"] == 215
    assert core_row["total_cell_years"] == 4945
    assert core_row["on_time_june_count"] == 4559
    assert core_row["delayed_july_1_15_count"] == 330
    assert core_row["never_reached_july15_count"] == 56
    assert core_row["total_delayed_count"] == 386
    assert core_row["total_delayed_cell_year_pct"] == pytest.approx(7.81, abs=0.05)

    # Rain-Shadow High-Volatility
    rain_row = df_delay[df_delay["regime"] == "Rain-Shadow High-Volatility"].iloc[0]
    assert rain_row["grid_cells"] == 42
    assert rain_row["total_cell_years"] == 966
    assert rain_row["on_time_june_count"] == 730
    assert rain_row["delayed_july_1_15_count"] == 139
    assert rain_row["never_reached_july15_count"] == 97
    assert rain_row["total_delayed_count"] == 236
    assert rain_row["total_delayed_cell_year_pct"] == pytest.approx(24.43, abs=0.05)

    # Early Maritime & Western Ghats
    mar_row = df_delay[df_delay["regime"] == "Early Maritime & Western Ghats"].iloc[0]
    assert mar_row["grid_cells"] == 65
    assert mar_row["total_cell_years"] == 1495
    assert mar_row["on_time_june_count"] == 1456
    assert mar_row["delayed_july_1_15_count"] == 36
    assert mar_row["never_reached_july15_count"] == 3
    assert mar_row["total_delayed_count"] == 39
    assert mar_row["total_delayed_cell_year_pct"] == pytest.approx(2.61, abs=0.05)

    # Interior Semi-Arid Transition
    trans_row = df_delay[df_delay["regime"] == "Interior Semi-Arid Transition"].iloc[0]
    assert trans_row["grid_cells"] == 97
    assert trans_row["total_cell_years"] == 2231
    assert trans_row["on_time_june_count"] == 1798
    assert trans_row["delayed_july_1_15_count"] == 379
    assert trans_row["never_reached_july15_count"] == 54
    assert trans_row["total_delayed_count"] == 433
    assert trans_row["total_delayed_cell_year_pct"] == pytest.approx(19.41, abs=0.05)

    # Exact conservation laws
    for _, row in df_delay.iterrows():
        assert (
            row["on_time_june_count"] + row["total_delayed_count"]
            == row["total_cell_years"]
        )
        assert (
            row["delayed_july_1_15_count"] + row["never_reached_july15_count"]
            == row["total_delayed_count"]
        )


def test_rain_shadow_anomaly_resolution() -> None:
    """Verifies that the Rain-Shadow anomaly is resolved by high post-trigger break risk."""
    with open(SUMMARY_JSON, "r", encoding="utf-8") as f:
        summary = json.load(f)

    metrics = summary["rain_shadow_anomaly_diagnosis"]["regime_anomaly_metrics"]

    # Rain Shadow post-trigger break probability must be > 35% (approx 39.1%)
    rs_break_10d = metrics["Rain-Shadow High-Volatility"]["post_trigger_10d_break_prob_pct"]
    assert rs_break_10d > 35.0, f"Expected RS break risk > 35%, got {rs_break_10d}"

    # Core Interior break risk must be low (< 15%)
    core_break_10d = metrics["Core Interior Synchronized"]["post_trigger_10d_break_prob_pct"]
    assert core_break_10d < 15.0, f"Expected Core break risk < 15%, got {core_break_10d}"

    # Maritime break risk must be very low (< 10%)
    mar_break_10d = metrics["Early Maritime & Western Ghats"]["post_trigger_10d_break_prob_pct"]
    assert mar_break_10d < 10.0, f"Expected Maritime break risk < 10%, got {mar_break_10d}"

    # Rain Shadow immediate dry spell days must exceed Core Interior
    rs_imm_dry = metrics["Rain-Shadow High-Volatility"]["mean_immediate_dry_spell_days"]
    core_imm_dry = metrics["Core Interior Synchronized"]["mean_immediate_dry_spell_days"]
    assert rs_imm_dry > core_imm_dry, f"Expected RS immediate dry ({rs_imm_dry}) > Core ({core_imm_dry})"


def test_rolling_window_reachability() -> None:
    """Verifies rolling window reachability differences between Rain Shadow and other regimes."""
    df_sens = pd.read_csv(SENSITIVITY_CSV)

    # Rolling 3-day 50 mm
    r3_50 = df_sens[(df_sens["method"] == "rolling_3d") & (df_sens["threshold_mm"] == 50.0)]
    rs_r3 = r3_50[r3_50["regime"] == "Rain-Shadow High-Volatility"]["reached_pct"].iloc[0]
    core_r3 = r3_50[r3_50["regime"] == "Core Interior Synchronized"]["reached_pct"].iloc[0]

    assert rs_r3 < 50.0, f"Expected RS 3-day reach < 50%, got {rs_r3}%"
    assert core_r3 > 80.0, f"Expected Core 3-day reach > 80%, got {core_r3}%"

    # Rolling 5-day 50 mm
    r5_50 = df_sens[(df_sens["method"] == "rolling_5d") & (df_sens["threshold_mm"] == 50.0)]
    rs_r5 = r5_50[r5_50["regime"] == "Rain-Shadow High-Volatility"]["reached_pct"].iloc[0]
    assert rs_r5 < 65.0, f"Expected RS 5-day reach < 65%, got {rs_r5}%"


def test_institutional_evidence_and_conditional_go() -> None:
    """Verifies institutional citations and CONDITIONAL GO decision in summary JSON."""
    with open(SUMMARY_JSON, "r", encoding="utf-8") as f:
        summary = json.load(f)

    institutions = [item["institution"] for item in summary["institutional_evidence"]]
    assert any("CRIDA" in inst for inst in institutions)
    assert any("MPKV" in inst for inst in institutions)
    assert any("VNMKV" in inst for inst in institutions)
    assert any("PDKV" in inst for inst in institutions)

    decision_info = summary["phase_8_decision"]
    assert decision_info["decision"] == "CONDITIONAL GO"
    constraints = decision_info["mandatory_phase_8_constraints"]
    assert any("75 mm" in c for c in constraints)
    assert any("Two-Stage" in c for c in constraints)
