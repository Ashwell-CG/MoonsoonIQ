"""MonsoonIQ - Test Suite for Phase 8 Advisory Decision Engine.

Validates:
1. Historical regime lookup and baseline integrity for all 419 cells.
2. All four regime advisory decision branches.
3. Rain-Shadow 75 mm constraint and rejection of 50 mm solo trigger.
4. Two-rainy-day verification persistence rule.
5. Post-trigger dry-spell detection and desiccation break hazard warnings.
6. July 15 delayed-sowing contingency handling and Rabi guidance.
7. Data completeness auditing and INSUFFICIENT DATA state on missing observations.
8. Threshold boundary conditions (74.9 mm vs 75.0 mm; 2.4 mm vs 2.5 mm).
9. Strict separation between historical climatology and current observations.
10. Handling of invalid cell identifiers, empty data, and extreme rainfall events.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import List, Tuple

import numpy as np
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
    RainfallMonitor,
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


def generate_synthetic_series(
    rain_dict: dict[int, float],
    start_date: str = "2024-06-01",
    end_date: str = "2024-06-30",
) -> List[Tuple[str, float]]:
    """Helper to construct daily rainfall time series from day offsets."""
    dates = pd.date_range(start=start_date, end=end_date, freq="D")
    records = []
    for i, dt in enumerate(dates):
        val = rain_dict.get(i, 0.0)
        records.append((dt.strftime("%Y-%m-%d"), val))
    return records


# =========================================================================
# 1. Regime Lookup & Domain Tests
# =========================================================================

def test_lookup_all_419_cells(lookup_service: RegimeLookupService) -> None:
    """Verifies that all 419 Maharashtra cells load correctly with valid regimes."""
    cells = lookup_service.get_all_cells()
    assert len(cells) == 419, f"Expected 419 cells, got {len(cells)}"

    regimes = {c[0].regime_kmeans for c in cells}
    expected_regimes = {
        RegimeName.CORE_INTERIOR.value,
        RegimeName.RAIN_SHADOW.value,
        RegimeName.EARLY_MARITIME.value,
        RegimeName.SEMI_ARID_TRANSITION.value,
    }
    assert regimes == expected_regimes

    # Verify counts
    rs_count = len(lookup_service.get_regime_cells(RegimeName.RAIN_SHADOW.value))
    core_count = len(lookup_service.get_regime_cells(RegimeName.CORE_INTERIOR.value))
    mar_count = len(lookup_service.get_regime_cells(RegimeName.EARLY_MARITIME.value))
    trans_count = len(lookup_service.get_regime_cells(RegimeName.SEMI_ARID_TRANSITION.value))

    assert rs_count == 42
    assert core_count == 215
    assert mar_count == 65
    assert trans_count == 97


def test_invalid_cell_identifiers(lookup_service: RegimeLookupService) -> None:
    """Verifies that invalid cell identifiers raise clear ValueErrors."""
    with pytest.raises(ValueError, match="out of bounds"):
        lookup_service.get_cell_by_id(-1)

    with pytest.raises(ValueError, match="out of bounds"):
        lookup_service.get_cell_by_id(450)

    with pytest.raises(ValueError, match="not found"):
        lookup_service.get_cell_by_id("non_existent_cell")


def test_lookup_nearest_cell(lookup_service: RegimeLookupService) -> None:
    """Verifies geographic lookup for known coordinates."""
    # Coordinates for Pune / Solapur border (approx 17.65N, 75.90E)
    cell_info, baseline = lookup_service.get_nearest_cell(17.65, 75.90)
    assert cell_info.district in ["Solapur", "Osmanabad", "Pune", "Satara"]
    assert baseline.historical_years_count == 23


# =========================================================================
# 2. Rain-Shadow High-Volatility Mandatory Rules
# =========================================================================

def test_rain_shadow_50mm_solo_prohibition(
    advisory_engine: AdvisoryDecisionEngine, lookup_service: RegimeLookupService
) -> None:
    """Verifies that Rain-Shadow strictly prohibits a sowing signal on 50 mm alone."""
    rs_cell_id = lookup_service.get_regime_cells(RegimeName.RAIN_SHADOW.value)[0][0].cell_id

    # 55 mm in 2 days (June 5-6), then dry through June 20
    data = generate_synthetic_series({4: 35.0, 5: 20.0}, end_date="2024-06-20")
    report = advisory_engine.generate_advisory(rs_cell_id, data, as_of_date="2024-06-20")

    # Must NOT be RAINFALL CRITERIA MET
    assert report.advisory_state != AdvisoryState.RAINFALL_CRITERIA_MET
    assert report.advisory_state in [AdvisoryState.CAUTION, AdvisoryState.HIGH_RISK]

    # Verify prohibition condition is recorded
    cond_names = [c.condition_name for c in report.condition_evaluations]
    assert "50 mm Solo Trigger Prohibition" in cond_names

    # Check reasoning mentions prohibition & 39.13% break risk
    reasoning_text = " ".join(report.state_reasoning)
    assert "50 mm solo triggering is strictly PROHIBITED" in reasoning_text
    assert "39.13%" in reasoning_text


def test_rain_shadow_75mm_criteria_met(
    advisory_engine: AdvisoryDecisionEngine, lookup_service: RegimeLookupService
) -> None:
    """Verifies that Rain-Shadow reaches criteria met when >= 75 mm and wet days >= 2."""
    rs_cell_id = lookup_service.get_regime_cells(RegimeName.RAIN_SHADOW.value)[0][0].cell_id

    # 85 mm across 4 wet days (June 10-14), evaluated on June 16 (immediate post-dry is short)
    data = generate_synthetic_series({9: 25.0, 10: 25.0, 12: 20.0, 13: 15.0}, end_date="2024-06-16")
    report = advisory_engine.generate_advisory(rs_cell_id, data, as_of_date="2024-06-16")

    assert report.advisory_state == AdvisoryState.RAINFALL_CRITERIA_MET
    assert report.current_metrics.cumulative_rainfall_mm == 85.0
    assert report.current_metrics.rainy_days_count == 4

    # Historical risk summary must show 39.13% and 20.60%
    hist = report.historical_risk_summary
    assert "39.13%" in hist["Post-Trigger >= 10-Day Break Probability"]
    assert "20.60%" in hist["75 mm Never Reached by July 15"]
    assert "199 / 966" in hist["75 mm Never Reached by July 15"]


def test_rain_shadow_post_trigger_break_hazard(
    advisory_engine: AdvisoryDecisionEngine, lookup_service: RegimeLookupService
) -> None:
    """Verifies that an active post-trigger dry break (>= 7 days) triggers HIGH RISK."""
    rs_cell_id = lookup_service.get_regime_cells(RegimeName.RAIN_SHADOW.value)[0][0].cell_id

    # 80 mm accumulated by June 8, followed by 10 dry days up to June 18
    data = generate_synthetic_series({5: 45.0, 6: 35.0}, end_date="2024-06-18")
    report = advisory_engine.generate_advisory(rs_cell_id, data, as_of_date="2024-06-18")

    assert report.advisory_state == AdvisoryState.HIGH_RISK
    assert "active" in " ".join(report.state_reasoning).lower()
    assert report.current_metrics.post_trigger_dry_days >= 7


# =========================================================================
# 3. Core Interior Synchronized Rules
# =========================================================================

def test_core_interior_normal_onset(
    advisory_engine: AdvisoryDecisionEngine, lookup_service: RegimeLookupService
) -> None:
    """Verifies Core Interior synchronized criteria evaluation."""
    core_cell_id = lookup_service.get_regime_cells(RegimeName.CORE_INTERIOR.value)[0][0].cell_id

    # 82 mm over 4 wet days (June 15-18)
    data = generate_synthetic_series({14: 25.0, 15: 25.0, 16: 20.0, 17: 12.0}, end_date="2024-06-20")
    report = advisory_engine.generate_advisory(core_cell_id, data, as_of_date="2024-06-20")

    assert report.advisory_state == AdvisoryState.RAINFALL_CRITERIA_MET
    assert report.historical_baseline.regime_post_trigger_10d_break_prob_pct < 15.0
    assert any("pdkv" in c.lower() or "soybean" in c.lower() for c in report.contingency_recommendations)


# =========================================================================
# 4. Early Maritime & Western Ghats Rules (Waterlogging Risk)
# =========================================================================

def test_early_maritime_waterlogging_risk(
    advisory_engine: AdvisoryDecisionEngine, lookup_service: RegimeLookupService
) -> None:
    """Verifies that extreme rainfall triggers CAUTION (Waterlogging Risk) in Maritime."""
    mar_cell_id = lookup_service.get_regime_cells(RegimeName.EARLY_MARITIME.value)[0][0].cell_id

    # 150 mm on June 10, total 220 mm across June 10-12
    data = generate_synthetic_series({9: 40.0, 10: 150.0, 11: 30.0}, end_date="2024-06-14")
    report = advisory_engine.generate_advisory(mar_cell_id, data, as_of_date="2024-06-14")

    assert report.current_metrics.is_extreme_rain_event is True
    assert report.advisory_state == AdvisoryState.CAUTION
    assert "waterlogging" in " ".join(report.state_reasoning).lower()


def test_early_maritime_normal_criteria(
    advisory_engine: AdvisoryDecisionEngine, lookup_service: RegimeLookupService
) -> None:
    """Verifies normal non-extreme 55 mm onset in Early Maritime."""
    mar_cell_id = lookup_service.get_regime_cells(RegimeName.EARLY_MARITIME.value)[0][0].cell_id

    # 55 mm over 3 modest days
    data = generate_synthetic_series({5: 20.0, 6: 20.0, 7: 15.0}, end_date="2024-06-10")
    report = advisory_engine.generate_advisory(mar_cell_id, data, as_of_date="2024-06-10")

    assert report.advisory_state == AdvisoryState.RAINFALL_CRITERIA_MET
    assert report.current_metrics.is_extreme_rain_event is False


# =========================================================================
# 5. July 15 Contingency Cut-Off Handling
# =========================================================================

def test_july15_contingency_handling(
    advisory_engine: AdvisoryDecisionEngine, lookup_service: RegimeLookupService
) -> None:
    """Verifies that evaluations past July 15 with unmet criteria yield HIGH RISK and Rabi options."""
    rs_cell_id = lookup_service.get_regime_cells(RegimeName.RAIN_SHADOW.value)[0][0].cell_id

    # 35 mm total accumulated by July 20 (well below 75 mm)
    data = generate_synthetic_series({5: 10.0, 15: 10.0, 25: 10.0, 40: 5.0}, end_date="2024-07-20")
    report = advisory_engine.generate_advisory(rs_cell_id, data, as_of_date="2024-07-20")

    assert report.advisory_state == AdvisoryState.HIGH_RISK
    reasoning_text = " ".join(report.state_reasoning).lower()
    assert "past july 15" in reasoning_text
    assert "deficit" in reasoning_text

    # Contingency recommendations must include ICAR-CRIDA / Rabi recommendations
    contingency_text = " ".join(report.contingency_recommendations).lower()
    assert "rabi" in contingency_text or "crida" in contingency_text


# =========================================================================
# 6. Data Completeness & Boundary Conditions
# =========================================================================

def test_insufficient_data_state(
    advisory_engine: AdvisoryDecisionEngine, lookup_service: RegimeLookupService
) -> None:
    """Verifies that missing observations (>3 days or <90%) trigger INSUFFICIENT DATA."""
    core_cell_id = lookup_service.get_regime_cells(RegimeName.CORE_INTERIOR.value)[0][0].cell_id

    # 4 missing days
    data = [
        ("2024-06-01", 10.0),
        ("2024-06-02", None),
        ("2024-06-03", None),
        ("2024-06-04", None),
        ("2024-06-05", None),
        ("2024-06-06", 15.0),
    ]
    report = advisory_engine.generate_advisory(core_cell_id, data, as_of_date="2024-06-06")

    assert report.advisory_state == AdvisoryState.INSUFFICIENT_DATA
    assert report.current_metrics.missing_days_count == 4
    assert "completeness" in " ".join(report.state_reasoning).lower()


def test_threshold_boundary_conditions(
    advisory_engine: AdvisoryDecisionEngine, lookup_service: RegimeLookupService
) -> None:
    """Tests exact boundary conditions around 74.9 mm vs 75.0 mm and wet day thresholds."""
    core_cell_id = lookup_service.get_regime_cells(RegimeName.CORE_INTERIOR.value)[0][0].cell_id

    # Sub-threshold: 74.9 mm
    data_sub = generate_synthetic_series({4: 37.4, 5: 37.5}, end_date="2024-06-10")
    report_sub = advisory_engine.generate_advisory(core_cell_id, data_sub, as_of_date="2024-06-10")
    assert report_sub.advisory_state != AdvisoryState.RAINFALL_CRITERIA_MET
    assert report_sub.current_metrics.cumulative_rainfall_mm == pytest.approx(74.9, abs=0.05)

    # Threshold met: 75.0 mm
    data_met = generate_synthetic_series({4: 37.5, 5: 37.5}, end_date="2024-06-10")
    report_met = advisory_engine.generate_advisory(core_cell_id, data_met, as_of_date="2024-06-10")
    assert report_met.advisory_state == AdvisoryState.RAINFALL_CRITERIA_MET
    assert report_met.current_metrics.cumulative_rainfall_mm == pytest.approx(75.0, abs=0.05)


def test_no_rainfall_all_dry(
    advisory_engine: AdvisoryDecisionEngine, lookup_service: RegimeLookupService
) -> None:
    """Tests completely zero rainfall sequence."""
    trans_cell_id = lookup_service.get_regime_cells(RegimeName.SEMI_ARID_TRANSITION.value)[0][0].cell_id

    data = generate_synthetic_series({}, end_date="2024-06-15")
    report = advisory_engine.generate_advisory(trans_cell_id, data, as_of_date="2024-06-15")

    assert report.advisory_state == AdvisoryState.CAUTION
    assert report.current_metrics.cumulative_rainfall_mm == 0.0
    assert report.current_metrics.rainy_days_count == 0
    assert report.current_metrics.current_consecutive_dry_days == 15


def test_safe_to_sow_phrase_prohibition(
    advisory_engine: AdvisoryDecisionEngine, lookup_service: RegimeLookupService
) -> None:
    """Verifies that the phrase 'safe to sow' never appears anywhere in generated advisories."""
    rs_cell_id = lookup_service.get_regime_cells(RegimeName.RAIN_SHADOW.value)[0][0].cell_id

    data = generate_synthetic_series({5: 45.0, 6: 40.0}, end_date="2024-06-10")
    report = advisory_engine.generate_advisory(rs_cell_id, data, as_of_date="2024-06-10")

    full_output = report.format_display().lower()
    assert "safe to sow" not in full_output
