"""MonsoonIQ - Test Suite for Phase 8.2 Rainfall Accumulation and Trigger Consistency Audit.

Validates the 7 required scenario tests:
1. 60 mm early rainfall followed by 18-20 dry days and two small rainy days.
2. 60 mm early rainfall followed by two recent rainy days where recent 5-day total < 75 mm.
3. 75 mm accumulated within qualifying window across >= 2 rainy days.
4. 80 mm falling on one day only.
5. Two qualifying rainy days separated by > 5 calendar days.
6. Missing rainfall observations inside qualifying window.
7. Exactly 75.0 mm vs 74.9 mm boundary conditions.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple

import pandas as pd
import pytest

# Ensure project root is in sys.path
BASE_DIR: Path = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.advisory import (
    AdvisoryDecisionEngine,
    AdvisoryReport,
    AdvisoryState,
    RegimeLookupService,
    RegimeName,
)


@pytest.fixture
def advisory_engine() -> AdvisoryDecisionEngine:
    """Fixture providing initialized AdvisoryDecisionEngine."""
    return AdvisoryDecisionEngine()


@pytest.fixture
def rs_cell_id(advisory_engine: AdvisoryDecisionEngine) -> str:
    """Fixture providing a known Rain-Shadow grid cell ID (e.g. cell_020 in Sangli/Solapur)."""
    cells = advisory_engine.lookup.get_regime_cells(RegimeName.RAIN_SHADOW.value)
    return cells[0][0].cell_id


# =========================================================================
# Scenario 1 & 2: Prolonged Dry Spell Moisture Depletion Tests
# =========================================================================


def test_scenario_1_early_60mm_followed_by_18_dry_days_and_two_small_rainy_days(
    advisory_engine: AdvisoryDecisionEngine, rs_cell_id: str
) -> None:
    """Test 1: 60 mm early in June + 18 consecutive dry days + 2 small rainy days (8 mm + 8 mm).

    Verifies that early rainfall depleted by an intervening prolonged dry spell cannot
    be combined with small recent showers to satisfy the 75 mm sowing threshold.
    Expected State: CAUTION (or HIGH_RISK).
    """
    # June 1: 30 mm, June 2: 30 mm (60 mm total)
    # June 3-20: 0.0 mm (18 consecutive dry days)
    # June 21: 8.0 mm, June 22: 8.0 mm (recent showers summing to 16 mm)
    dates = pd.date_range("2024-06-01", "2024-06-22", freq="D")
    data = [(dt.strftime("%Y-%m-%d"), 0.0) for dt in dates]
    data[0] = (dates[0].strftime("%Y-%m-%d"), 30.0)
    data[1] = (dates[1].strftime("%Y-%m-%d"), 30.0)
    data[20] = (dates[20].strftime("%Y-%m-%d"), 8.0)
    data[21] = (dates[21].strftime("%Y-%m-%d"), 8.0)

    report = advisory_engine.generate_advisory(rs_cell_id, data, as_of_date="2024-06-22")

    # Seasonal cumulative is 76 mm, BUT effective cumulative in active wetting cycle is only 16 mm
    assert report.current_metrics.cumulative_rainfall_mm == pytest.approx(76.0, abs=0.01)
    assert report.current_metrics.effective_cumulative_rainfall_mm == pytest.approx(16.0, abs=0.01)
    assert report.current_metrics.has_intervening_prolonged_dry_spell is True
    assert report.current_metrics.max_intervening_dry_spell_days == 18

    # Must NOT be RAINFALL_CRITERIA_MET
    assert report.advisory_state != AdvisoryState.RAINFALL_CRITERIA_MET
    assert report.advisory_state == AdvisoryState.CAUTION

    # Verify Condition 1 recorded failure of active cycle rainfall
    cond1 = next(c for c in report.condition_evaluations if "Cumulative Rainfall" in c.condition_name)
    assert cond1.passed is False
    assert "Moisture Depletion Alert" in " ".join(report.state_reasoning)


def test_scenario_2_recent_five_day_total_below_75mm_after_early_rain(
    advisory_engine: AdvisoryDecisionEngine, rs_cell_id: str
) -> None:
    """Test 2: 60 mm early rainfall followed by two recent rainy days where recent 5-day total < 75 mm.

    Expected State: CAUTION.
    """
    # June 1: 40 mm, June 2: 20 mm (60 mm early)
    # June 3-21: 0.0 mm (19 consecutive dry days)
    # June 22: 10.0 mm, June 23: 10.0 mm (5-day total as of June 23 = 20 mm < 75 mm)
    dates = pd.date_range("2024-06-01", "2024-06-23", freq="D")
    data = [(dt.strftime("%Y-%m-%d"), 0.0) for dt in dates]
    data[0] = (dates[0].strftime("%Y-%m-%d"), 40.0)
    data[1] = (dates[1].strftime("%Y-%m-%d"), 20.0)
    data[21] = (dates[21].strftime("%Y-%m-%d"), 10.0)
    data[22] = (dates[22].strftime("%Y-%m-%d"), 10.0)

    report = advisory_engine.generate_advisory(rs_cell_id, data, as_of_date="2024-06-23")

    assert report.current_metrics.current_5day_rainfall_mm == pytest.approx(20.0, abs=0.01)
    assert report.current_metrics.effective_cumulative_rainfall_mm == pytest.approx(20.0, abs=0.01)
    assert report.advisory_state == AdvisoryState.CAUTION
    assert report.advisory_state != AdvisoryState.RAINFALL_CRITERIA_MET


# =========================================================================
# Scenario 3: Legitimate 75 mm Sustained Event
# =========================================================================


def test_scenario_3_sustained_75mm_within_qualifying_window(
    advisory_engine: AdvisoryDecisionEngine, rs_cell_id: str
) -> None:
    """Test 3: 75 mm accumulated within defined qualifying window across >= 2 rainy days.

    Expected State: RAINFALL_CRITERIA_MET.
    """
    # June 10: 40.0 mm, June 12: 40.0 mm (80 mm total in 3 days, 2 distinct wet days)
    dates = pd.date_range("2024-06-01", "2024-06-13", freq="D")
    data = [(dt.strftime("%Y-%m-%d"), 0.0) for dt in dates]
    data[9] = (dates[9].strftime("%Y-%m-%d"), 40.0)
    data[11] = (dates[11].strftime("%Y-%m-%d"), 40.0)

    report = advisory_engine.generate_advisory(rs_cell_id, data, as_of_date="2024-06-13")

    assert report.advisory_state == AdvisoryState.RAINFALL_CRITERIA_MET
    assert report.current_metrics.cumulative_rainfall_mm == 80.0
    assert report.current_metrics.effective_cumulative_rainfall_mm == 80.0
    assert report.current_metrics.qualifying_5d_wet_days == 2

    cond1 = next(c for c in report.condition_evaluations if "Cumulative Rainfall" in c.condition_name)
    assert cond1.passed is True
    cond_verif = next(c for c in report.condition_evaluations if "Two-Stage" in c.condition_name)
    assert cond_verif.passed is True


# =========================================================================
# Scenario 4 & 5: Multi-Day Distribution & Window Boundary Tests
# =========================================================================


def test_scenario_4_single_heavy_rain_day_80mm(
    advisory_engine: AdvisoryDecisionEngine, rs_cell_id: str
) -> None:
    """Test 4: 80 mm falling on one day only (isolated convective burst).

    Expected State: CAUTION (fails 2 wet days requirement).
    """
    dates = pd.date_range("2024-06-01", "2024-06-05", freq="D")
    data = [(dt.strftime("%Y-%m-%d"), 0.0) for dt in dates]
    data[0] = (dates[0].strftime("%Y-%m-%d"), 80.0)

    report = advisory_engine.generate_advisory(rs_cell_id, data, as_of_date="2024-06-05")

    assert report.advisory_state == AdvisoryState.CAUTION
    assert report.current_metrics.qualifying_5d_wet_days == 1

    cond_verif = next(c for c in report.condition_evaluations if "Two-Stage" in c.condition_name)
    assert cond_verif.passed is False
    assert "isolated convective thunderstorm" in " ".join(report.state_reasoning).lower()


def test_scenario_5_two_wet_days_separated_by_more_than_five_days(
    advisory_engine: AdvisoryDecisionEngine, rs_cell_id: str
) -> None:
    """Test 5: Two qualifying rainy days separated by more than 5 calendar days.

    Expected State: CAUTION.
    """
    # Day 1: 40 mm, Days 2-9: 0.0 mm (8 dry days), Day 10: 40 mm (cumulative = 80 mm)
    dates = pd.date_range("2024-06-01", periods=10, freq="D")
    data = [(dt.strftime("%Y-%m-%d"), 0.0) for dt in dates]
    data[0] = (dates[0].strftime("%Y-%m-%d"), 40.0)
    data[9] = (dates[9].strftime("%Y-%m-%d"), 40.0)

    report = advisory_engine.generate_advisory(rs_cell_id, data, as_of_date="2024-06-10")

    assert report.advisory_state == AdvisoryState.CAUTION
    assert report.current_metrics.qualifying_5d_wet_days == 1

    cond_verif = next(c for c in report.condition_evaluations if "Two-Stage" in c.condition_name)
    assert cond_verif.passed is False


# =========================================================================
# Scenario 6: Missing Observation in Qualifying Window
# =========================================================================


def test_scenario_6_missing_observation_in_qualifying_window(
    advisory_engine: AdvisoryDecisionEngine, rs_cell_id: str
) -> None:
    """Test 6: Missing rainfall observation inside qualifying window.

    Expected State: INSUFFICIENT_DATA.
    """
    # 15 days total (completeness = 14/15 = 93.3% > 90%)
    # Day 1: 40 mm, Day 2: None (missing in 5-day verification window), Day 3: 40 mm
    dates = pd.date_range("2024-06-01", periods=15, freq="D")
    data: List[Tuple[str, float | None]] = [(dt.strftime("%Y-%m-%d"), 0.0) for dt in dates]
    data[0] = (dates[0].strftime("%Y-%m-%d"), 40.0)
    data[1] = (dates[1].strftime("%Y-%m-%d"), None)
    data[2] = (dates[2].strftime("%Y-%m-%d"), 40.0)

    report = advisory_engine.generate_advisory(rs_cell_id, data, as_of_date="2024-06-15")

    assert report.advisory_state == AdvisoryState.INSUFFICIENT_DATA
    assert report.current_metrics.verification_window_has_missing is True
    assert "verification window" in " ".join(report.state_reasoning).lower()


# =========================================================================
# Scenario 7: Boundary Conditions (75.0 mm vs 74.9 mm)
# =========================================================================


def test_scenario_7_boundary_conditions_75mm_and_74_9mm(
    advisory_engine: AdvisoryDecisionEngine, rs_cell_id: str
) -> None:
    """Test 7: Boundary conditions: exactly 75.0 mm (PASS) vs 74.9 mm (FAIL).

    Expected State:
        - 75.0 mm -> RAINFALL_CRITERIA_MET
        - 74.9 mm -> CAUTION
    """
    dates = pd.date_range("2024-06-01", periods=5, freq="D")

    # Case 7A: Exactly 75.0 mm (Day 1: 37.5 mm, Day 3: 37.5 mm)
    data_75 = [(dt.strftime("%Y-%m-%d"), 0.0) for dt in dates]
    data_75[0] = (dates[0].strftime("%Y-%m-%d"), 37.5)
    data_75[2] = (dates[2].strftime("%Y-%m-%d"), 37.5)
    report_75 = advisory_engine.generate_advisory(rs_cell_id, data_75, as_of_date="2024-06-05")

    assert report_75.advisory_state == AdvisoryState.RAINFALL_CRITERIA_MET
    assert report_75.current_metrics.cumulative_rainfall_mm == pytest.approx(75.0, abs=0.01)
    cond_75 = next(c for c in report_75.condition_evaluations if "Cumulative" in c.condition_name)
    assert cond_75.passed is True

    # Case 7B: Sub-threshold 74.9 mm (Day 1: 37.4 mm, Day 3: 37.5 mm)
    data_74_9 = [(dt.strftime("%Y-%m-%d"), 0.0) for dt in dates]
    data_74_9[0] = (dates[0].strftime("%Y-%m-%d"), 37.4)
    data_74_9[2] = (dates[2].strftime("%Y-%m-%d"), 37.5)
    report_74_9 = advisory_engine.generate_advisory(rs_cell_id, data_74_9, as_of_date="2024-06-05")

    assert report_74_9.advisory_state == AdvisoryState.CAUTION
    assert report_74_9.current_metrics.cumulative_rainfall_mm == pytest.approx(74.9, abs=0.01)
    cond_74_9 = next(c for c in report_74_9.condition_evaluations if "Cumulative" in c.condition_name)
    assert cond_74_9.passed is False
