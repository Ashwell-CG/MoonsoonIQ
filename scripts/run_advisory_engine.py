"""MonsoonIQ - Run Advisory Engine & Scenario Demonstrator.

Executes representative agricultural advisory scenarios across all four Maharashtra
monsoon onset regimes, validates mandatory constraints, and exports sample advisories.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple

import pandas as pd

# Base Directory and sys.path setup
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

OUTPUT_DIR: Path = BASE_DIR / "outputs" / "advisory"
SAMPLE_JSON_PATH: Path = OUTPUT_DIR / "sample_advisories.json"

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("MonsoonIQ.RunAdvisory")


def build_scenario_data(
    scenario_type: str,
    start_date: str = "2024-06-01",
    end_date: str = "2024-06-25",
) -> List[Tuple[str, float]]:
    """Generates synthetic but realistic daily rainfall time series for testing scenarios.

    Args:
        scenario_type: Scenario identifier.
        start_date: First date of sequence (YYYY-MM-DD).
        end_date: Final date of sequence (YYYY-MM-DD).

    Returns:
        List of (date_str, rainfall_mm) tuples.
    """
    dates = pd.date_range(start=start_date, end=end_date, freq="D")
    n = len(dates)
    rain = [0.0] * n

    if scenario_type == "rain_shadow_thunderstorm_55mm":
        # Solapur thunderstorm: 55 mm in 2 days (June 8-9), then dry through June 25
        # June 8 (idx 7): 35 mm, June 9 (idx 8): 20 mm
        if n > 8:
            rain[7] = 35.0
            rain[8] = 20.0
    elif scenario_type == "rain_shadow_sustained_85mm":
        # Rain Shadow sustained event: 85 mm across 4 wet days (June 10-14)
        if n > 13:
            rain[9] = 22.0
            rain[10] = 30.0
            rain[12] = 18.0
            rain[13] = 15.0
            rain[15] = 5.0
    elif scenario_type == "rain_shadow_drought_post_july15":
        # Evaluated on July 20: total 32 mm accumulated by July 20
        # Sparse drizzle
        for i in range(n):
            if i in [5, 12, 22, 35]:
                rain[i] = 8.0
    elif scenario_type == "core_interior_normal_82mm":
        # Vidarbha normal synchronized onset: 82 mm over 5 wet days (June 15-20)
        if n > 19:
            rain[14] = 18.0
            rain[15] = 25.0
            rain[16] = 15.0
            rain[18] = 14.0
            rain[19] = 10.0
    elif scenario_type == "early_maritime_normal_65mm":
        # Konkan normal onset: 65 mm by June 10
        if n > 9:
            rain[6] = 25.0
            rain[7] = 22.0
            rain[9] = 18.0
    elif scenario_type == "early_maritime_extreme_waterlogging":
        # Konkan deluge: 160 mm in 1 day (June 12), 240 mm in 3 days
        if n > 13:
            rain[10] = 40.0
            rain[11] = 160.0
            rain[12] = 40.0
    elif scenario_type == "transition_normal_78mm":
        # Marathwada Transition: 78 mm over 4 wet days (June 18-23)
        if n > 22:
            rain[17] = 18.0
            rain[18] = 28.0
            rain[20] = 17.0
            rain[22] = 15.0
    elif scenario_type == "incomplete_data_missing_days":
        # 5 missing days in middle of observation period
        for i in range(n):
            if i in [8, 9, 10, 11, 12]:
                rain[i] = None  # Missing observation
            elif i in [5, 14]:
                rain[i] = 15.0

    return [(dt.strftime("%Y-%m-%d"), val) for dt, val in zip(dates, rain)]


def run_demonstration_scenarios() -> List[AdvisoryReport]:
    """Runs the full suite of advisory scenarios and logs outputs."""
    logger.info("Initializing AdvisoryDecisionEngine...")
    engine = AdvisoryDecisionEngine()
    lookup = engine.lookup

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    reports: List[AdvisoryReport] = []

    # Find sample cells for each regime
    rs_cells = lookup.get_regime_cells(RegimeName.RAIN_SHADOW.value)
    core_cells = lookup.get_regime_cells(RegimeName.CORE_INTERIOR.value)
    mar_cells = lookup.get_regime_cells(RegimeName.EARLY_MARITIME.value)
    trans_cells = lookup.get_regime_cells(RegimeName.SEMI_ARID_TRANSITION.value)

    rs_cell_id = rs_cells[0][0].cell_id      # Solapur / Ahmednagar area
    core_cell_id = core_cells[0][0].cell_id  # Vidarbha area
    mar_cell_id = mar_cells[0][0].cell_id    # Konkan area
    trans_cell_id = trans_cells[0][0].cell_id # Marathwada area

    logger.info(f"Target sample cells: RS={rs_cell_id}, Core={core_cell_id}, Mar={mar_cell_id}, Trans={trans_cell_id}")

    # SCENARIO 1: Rain-Shadow Convective Thunderstorm (55 mm solo trigger rejection)
    logger.info("--- Scenario 1: Rain-Shadow Convective Thunderstorm (55 mm) ---")
    data_s1 = build_scenario_data("rain_shadow_thunderstorm_55mm", end_date="2024-06-20")
    rep_s1 = engine.generate_advisory(rs_cell_id, data_s1, as_of_date="2024-06-20")
    reports.append(rep_s1)
    print(rep_s1.format_display())
    print("\n" + "=" * 80 + "\n")

    # SCENARIO 2: Rain-Shadow Sustained Onset (85 mm >= 75 mm requirement met)
    logger.info("--- Scenario 2: Rain-Shadow Sustained Onset (85 mm) ---")
    data_s2 = build_scenario_data("rain_shadow_sustained_85mm", end_date="2024-06-20")
    rep_s2 = engine.generate_advisory(rs_cell_id, data_s2, as_of_date="2024-06-20")
    reports.append(rep_s2)
    print(rep_s2.format_display())
    print("\n" + "=" * 80 + "\n")

    # SCENARIO 3: Rain-Shadow Post-July 15 Drought (Contingency Transition)
    logger.info("--- Scenario 3: Rain-Shadow Post-July 15 Delayed Sowing ---")
    data_s3 = build_scenario_data("rain_shadow_drought_post_july15", end_date="2024-07-20")
    rep_s3 = engine.generate_advisory(rs_cell_id, data_s3, as_of_date="2024-07-20")
    reports.append(rep_s3)
    print(rep_s3.format_display())
    print("\n" + "=" * 80 + "\n")

    # SCENARIO 4: Core Interior Synchronized (82 mm normal Vidarbha onset)
    logger.info("--- Scenario 4: Core Interior Synchronized (82 mm) ---")
    data_s4 = build_scenario_data("core_interior_normal_82mm", end_date="2024-06-22")
    rep_s4 = engine.generate_advisory(core_cell_id, data_s4, as_of_date="2024-06-22")
    reports.append(rep_s4)
    print(rep_s4.format_display())
    print("\n" + "=" * 80 + "\n")

    # SCENARIO 5: Early Maritime Normal Onset (65 mm Konkan paddy nursery)
    logger.info("--- Scenario 5: Early Maritime Normal Onset (65 mm) ---")
    data_s5 = build_scenario_data("early_maritime_normal_65mm", end_date="2024-06-15")
    rep_s5 = engine.generate_advisory(mar_cell_id, data_s5, as_of_date="2024-06-15")
    reports.append(rep_s5)
    print(rep_s5.format_display())
    print("\n" + "=" * 80 + "\n")

    # SCENARIO 6: Early Maritime Extreme Deluge (160 mm single-day waterlogging risk)
    logger.info("--- Scenario 6: Early Maritime Extreme Deluge (Waterlogging Risk) ---")
    data_s6 = build_scenario_data("early_maritime_extreme_waterlogging", end_date="2024-06-16")
    rep_s6 = engine.generate_advisory(mar_cell_id, data_s6, as_of_date="2024-06-16")
    reports.append(rep_s6)
    print(rep_s6.format_display())
    print("\n" + "=" * 80 + "\n")

    # SCENARIO 7: Interior Semi-Arid Transition (78 mm Marathwada onset)
    logger.info("--- Scenario 7: Interior Semi-Arid Transition (78 mm) ---")
    data_s7 = build_scenario_data("transition_normal_78mm", end_date="2024-06-25")
    rep_s7 = engine.generate_advisory(trans_cell_id, data_s7, as_of_date="2024-06-25")
    reports.append(rep_s7)
    print(rep_s7.format_display())
    print("\n" + "=" * 80 + "\n")

    # SCENARIO 8: Incomplete Data (5 missing observations)
    logger.info("--- Scenario 8: Incomplete Observations (Missing Data) ---")
    data_s8 = build_scenario_data("incomplete_data_missing_days", end_date="2024-06-20")
    rep_s8 = engine.generate_advisory(core_cell_id, data_s8, as_of_date="2024-06-20")
    reports.append(rep_s8)
    print(rep_s8.format_display())
    print("\n" + "=" * 80 + "\n")

    # Export sample JSON
    serialized = [rep.to_dict() for rep in reports]
    with open(SAMPLE_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(serialized, f, indent=2)
    logger.info(f"Saved {len(serialized)} sample advisories to {SAMPLE_JSON_PATH}")

    return reports


def main() -> None:
    """Executes the Phase 8 advisory demonstration script."""
    logger.info("Running MonsoonIQ Phase 8 Advisory Engine Demonstration...")
    run_demonstration_scenarios()
    logger.info("Advisory engine demonstration finished successfully.")


if __name__ == "__main__":
    main()
