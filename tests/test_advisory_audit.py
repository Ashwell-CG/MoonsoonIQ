"""MonsoonIQ - Test Suite for Phase 8.1 Advisory Logic, Threshold and Data Provenance Audit.

Targets:
1. Rain-Shadow Two-Stage Trigger:
   - Two rainy days inside five days (PASS).
   - Two rainy days outside five days (FAIL verification).
   - One very heavy rainfall day (FAIL verification).
   - Exactly 75.0 mm (PASS).
   - 74.9 mm (FAIL cumulative).
   - Missing rainfall inside verification window (INSUFFICIENT DATA).
2. Data Provenance tracking ('Historical Replay', 'Simulated Test Data', 'Observed Weather Station').
3. Maritime heavy rainfall hazard indicator labeling (precipitation hazard vs confirmed waterlogging).
4. July 15 contingency handling without automated Kharif abandonment.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import List, Tuple

import numpy as np
import pandas as pd
import pytest

# Base directory setup
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
def lookup_service() -> RegimeLookupService:
    """Fixture providing an initialized RegimeLookupService."""
    return RegimeLookupService()


@pytest.fixture
def advisory_engine(lookup_service: RegimeLookupService) -> AdvisoryDecisionEngine:
    """Fixture providing an initialized AdvisoryDecisionEngine."""
    return AdvisoryDecisionEngine(lookup_service=lookup_service)


@pytest.fixture
def rs_cell_id(lookup_service: RegimeLookupService) -> str:
    """Returns a valid Rain-Shadow grid cell ID (e.g. Solapur/Sangli)."""
    return lookup_service.get_regime_cells(RegimeName.RAIN_SHADOW.value)[0][0].cell_id


@pytest.fixture
def mar_cell_id(lookup_service: RegimeLookupService) -> str:
    """Returns a valid Early Maritime grid cell ID (Konkan)."""
    return lookup_service.get_regime_cells(RegimeName.EARLY_MARITIME.value)[0][0].cell_id


# =========================================================================
# 1. Rain-Shadow Two-Stage Trigger Verification Tests
# =========================================================================

def test_two_rainy_days_inside_five_days(
    advisory_engine: AdvisoryDecisionEngine, rs_cell_id: str
) -> None:
    """Test 1: Two distinct rainy days occurring within a 5-day window summing to >= 75 mm."""
    # Day 1: 40.0 mm, Day 2: 0.0, Day 3: 40.0 mm, Day 4: 0.0, Day 5: 0.0
    dates = pd.date_range("2024-06-01", periods=5, freq="D")
    data = [
        (dates[0].strftime("%Y-%m-%d"), 40.0),
        (dates[1].strftime("%Y-%m-%d"), 0.0),
        (dates[2].strftime("%Y-%m-%d"), 40.0),
        (dates[3].strftime("%Y-%m-%d"), 0.0),
        (dates[4].strftime("%Y-%m-%d"), 0.0),
    ]
    report = advisory_engine.generate_advisory(rs_cell_id, data, as_of_date="2024-06-05")

    assert report.advisory_state == AdvisoryState.RAINFALL_CRITERIA_MET
    assert report.current_metrics.cumulative_rainfall_mm == 80.0
    assert report.current_metrics.qualifying_5d_wet_days == 2

    # Verify verification condition passed
    cond = next(c for c in report.condition_evaluations if "Two-Stage" in c.condition_name)
    assert cond.passed is True


def test_two_rainy_days_outside_five_days(
    advisory_engine: AdvisoryDecisionEngine, rs_cell_id: str
) -> None:
    """Test 2: Two rainy days separated by more than 5 days summing to >= 75 mm must FAIL verification."""
    # Day 1: 40.0 mm, Days 2-9: 0.0 mm (8 dry days), Day 10: 40.0 mm
    dates = pd.date_range("2024-06-01", periods=10, freq="D")
    data = [(dt.strftime("%Y-%m-%d"), 0.0) for dt in dates]
    data[0] = (dates[0].strftime("%Y-%m-%d"), 40.0)
    data[9] = (dates[9].strftime("%Y-%m-%d"), 40.0)

    report = advisory_engine.generate_advisory(rs_cell_id, data, as_of_date="2024-06-10")

    # Cumulative is 80 mm, but they are NOT inside a 5-day window
    assert report.advisory_state != AdvisoryState.RAINFALL_CRITERIA_MET
    assert report.advisory_state == AdvisoryState.CAUTION
    assert report.current_metrics.qualifying_5d_wet_days == 1

    cond = next(c for c in report.condition_evaluations if "Two-Stage" in c.condition_name)
    assert cond.passed is False
    assert "Two-Stage Verification Rule" in " ".join(report.state_reasoning)


def test_one_very_heavy_rainfall_day(
    advisory_engine: AdvisoryDecisionEngine, rs_cell_id: str
) -> None:
    """Test 3: Single very heavy rainfall day (80 mm) without secondary rain must FAIL verification."""
    # Day 1: 80.0 mm, Days 2-5: 0.0 mm
    dates = pd.date_range("2024-06-01", periods=5, freq="D")
    data = [
        (dates[0].strftime("%Y-%m-%d"), 80.0),
        (dates[1].strftime("%Y-%m-%d"), 0.0),
        (dates[2].strftime("%Y-%m-%d"), 0.0),
        (dates[3].strftime("%Y-%m-%d"), 0.0),
        (dates[4].strftime("%Y-%m-%d"), 0.0),
    ]
    report = advisory_engine.generate_advisory(rs_cell_id, data, as_of_date="2024-06-05")

    assert report.advisory_state != AdvisoryState.RAINFALL_CRITERIA_MET
    assert report.advisory_state == AdvisoryState.CAUTION
    assert report.current_metrics.qualifying_5d_wet_days == 1

    cond = next(c for c in report.condition_evaluations if "Two-Stage" in c.condition_name)
    assert cond.passed is False
    assert "isolated convective thunderstorm" in " ".join(report.state_reasoning).lower()


def test_exactly_75mm_threshold(
    advisory_engine: AdvisoryDecisionEngine, rs_cell_id: str
) -> None:
    """Test 4: Exactly 75.0 mm with two wet days in 5 days must PASS."""
    # Day 1: 37.5 mm, Day 2: 0.0 mm, Day 3: 37.5 mm, Day 4: 0.0, Day 5: 0.0
    dates = pd.date_range("2024-06-01", periods=5, freq="D")
    data = [
        (dates[0].strftime("%Y-%m-%d"), 37.5),
        (dates[1].strftime("%Y-%m-%d"), 0.0),
        (dates[2].strftime("%Y-%m-%d"), 37.5),
        (dates[3].strftime("%Y-%m-%d"), 0.0),
        (dates[4].strftime("%Y-%m-%d"), 0.0),
    ]
    report = advisory_engine.generate_advisory(rs_cell_id, data, as_of_date="2024-06-05")

    assert report.advisory_state == AdvisoryState.RAINFALL_CRITERIA_MET
    assert report.current_metrics.cumulative_rainfall_mm == pytest.approx(75.0, abs=0.01)
    cond_cum = next(c for c in report.condition_evaluations if "Cumulative" in c.condition_name)
    assert cond_cum.passed is True


def test_sub_threshold_74_9mm(
    advisory_engine: AdvisoryDecisionEngine, rs_cell_id: str
) -> None:
    """Test 5: Sub-threshold 74.9 mm must FAIL cumulative condition."""
    # Day 1: 37.4 mm, Day 2: 0.0 mm, Day 3: 37.5 mm, Day 4: 0.0, Day 5: 0.0
    dates = pd.date_range("2024-06-01", periods=5, freq="D")
    data = [
        (dates[0].strftime("%Y-%m-%d"), 37.4),
        (dates[1].strftime("%Y-%m-%d"), 0.0),
        (dates[2].strftime("%Y-%m-%d"), 37.5),
        (dates[3].strftime("%Y-%m-%d"), 0.0),
        (dates[4].strftime("%Y-%m-%d"), 0.0),
    ]
    report = advisory_engine.generate_advisory(rs_cell_id, data, as_of_date="2024-06-05")

    assert report.advisory_state != AdvisoryState.RAINFALL_CRITERIA_MET
    assert report.current_metrics.cumulative_rainfall_mm == pytest.approx(74.9, abs=0.01)
    cond_cum = next(c for c in report.condition_evaluations if "Cumulative" in c.condition_name)
    assert cond_cum.passed is False


def test_missing_rainfall_inside_verification_window(
    advisory_engine: AdvisoryDecisionEngine, rs_cell_id: str
) -> None:
    """Test 6: Missing observations inside the 5-day verification window trigger INSUFFICIENT DATA."""
    # 15 days total to satisfy overall completeness (14/15 = 93.3% > 90%)
    # Day 1: 40.0 mm, Day 2: None (missing in 5-day verification window), Day 3: 40.0 mm, Days 4-15: 0.0 mm
    dates = pd.date_range("2024-06-01", periods=15, freq="D")
    data = [(dt.strftime("%Y-%m-%d"), 0.0) for dt in dates]
    data[0] = (dates[0].strftime("%Y-%m-%d"), 40.0)
    data[1] = (dates[1].strftime("%Y-%m-%d"), None)  # Missing observation in window
    data[2] = (dates[2].strftime("%Y-%m-%d"), 40.0)

    report = advisory_engine.generate_advisory(rs_cell_id, data, as_of_date="2024-06-15")

    assert report.advisory_state == AdvisoryState.INSUFFICIENT_DATA
    assert report.current_metrics.verification_window_has_missing is True
    assert "verification window" in " ".join(report.state_reasoning).lower()


# =========================================================================
# 2. Data Provenance Tests
# =========================================================================

def test_data_provenance_explicit_labeling(
    advisory_engine: AdvisoryDecisionEngine, rs_cell_id: str
) -> None:
    """Verifies that advisory reports explicitly label data provenance."""
    dates = pd.date_range("2024-06-01", periods=5, freq="D")
    data = [(dt.strftime("%Y-%m-%d"), 10.0) for dt in dates]

    # Default provenance
    rep1 = advisory_engine.generate_advisory(rs_cell_id, data, as_of_date="2024-06-05")
    assert rep1.data_provenance == "Simulated Test Data"
    assert "Data Provenance: [Simulated Test Data]" in rep1.format_display()

    # Custom provenance: Historical Replay
    rep2 = advisory_engine.generate_advisory(
        rs_cell_id, data, as_of_date="2024-06-05", data_provenance="Historical Replay (2001-2023)"
    )
    assert rep2.data_provenance == "Historical Replay (2001-2023)"
    assert "Data Provenance: [Historical Replay (2001-2023)]" in rep2.format_display()


# =========================================================================
# 3. Maritime Heavy-Rainfall Hazard Labeling Tests
# =========================================================================

def test_maritime_heavy_rainfall_hazard_label(
    advisory_engine: AdvisoryDecisionEngine, mar_cell_id: str
) -> None:
    """Verifies that maritime extreme rainfall is labeled as a hazard indicator, not confirmed waterlogging."""
    dates = pd.date_range("2024-06-01", periods=5, freq="D")
    data = [
        (dates[0].strftime("%Y-%m-%d"), 120.0),  # Extreme 1-day > 100 mm
        (dates[1].strftime("%Y-%m-%d"), 50.0),
        (dates[2].strftime("%Y-%m-%d"), 40.0),
        (dates[3].strftime("%Y-%m-%d"), 0.0),
        (dates[4].strftime("%Y-%m-%d"), 0.0),
    ]
    report = advisory_engine.generate_advisory(mar_cell_id, data, as_of_date="2024-06-05")

    assert report.advisory_state == AdvisoryState.CAUTION
    cond = next(c for c in report.condition_evaluations if "Heavy-Rainfall Hazard" in c.condition_name)
    assert "Hazard Indicator" in cond.condition_name
    assert "not confirmed" in cond.threshold_description.lower()
    assert "safe to sow" not in report.format_display().lower()


# =========================================================================
# 4. July 15 Contingency Alert Tests
# =========================================================================

def test_july15_contingency_alert_no_auto_cancel(
    advisory_engine: AdvisoryDecisionEngine, rs_cell_id: str
) -> None:
    """Verifies that July 15 unmet criteria issues HIGH RISK without automated Kharif cancellation."""
    dates = pd.date_range("2024-06-01", "2024-07-20", freq="D")
    data = [(dt.strftime("%Y-%m-%d"), 1.0) for dt in dates]  # Drizzle only, total ~50 mm

    report = advisory_engine.generate_advisory(rs_cell_id, data, as_of_date="2024-07-20")

    assert report.advisory_state == AdvisoryState.HIGH_RISK
    reasoning_text = " ".join(report.state_reasoning).lower()
    assert "delayed past july 15" in reasoning_text
    assert "deficit" in reasoning_text

    # Must provide contingency options (Rabi preparation and short-duration pulses)
    contingency_text = " ".join(report.contingency_recommendations).lower()
    assert "rabi" in contingency_text
    assert "contingency" in contingency_text
    assert "safe to sow" not in report.format_display().lower()
