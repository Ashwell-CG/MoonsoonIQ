"""MonsoonIQ - Unit Tests for Phase 5A Monsoon Onset Methodology & Sensitivity Analysis.

Validates:
1. Presence and schema integrity of outputs/eda/onset_sensitivity_results.json.
2. Verified benchmark ground-truth dates for Mumbai (2001–2023) and Pune (2019–2023).
3. Execution and metrics completeness of all 17 experimental sensitivity configurations.
4. Physical validity of the false-onset penalty filter across break thresholds.
5. Regional progression gradients (Western Ghats & Konkan earlier than interior plateau).
6. Alignment with IMD operational declarations (Mumbai MAE < 7 days).
"""

from pathlib import Path
import json
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
SENSITIVITY_JSON_PATH = BASE_DIR / "outputs" / "eda" / "onset_sensitivity_results.json"


@pytest.fixture(scope="module")
def sensitivity_data():
    """Loads the pre-computed onset sensitivity analysis results JSON."""
    assert SENSITIVITY_JSON_PATH.exists(), f"Missing sensitivity results file: {SENSITIVITY_JSON_PATH}"
    with open(SENSITIVITY_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def test_sensitivity_data_structure(sensitivity_data):
    """Verifies that the sensitivity results contain benchmarks and all 17 experiment configs."""
    assert "benchmark_ground_truth" in sensitivity_data
    assert "experiments" in sensitivity_data

    benchmarks = sensitivity_data["benchmark_ground_truth"]
    assert "mumbai_imd_declarations" in benchmarks
    assert "pune_imd_declarations" in benchmarks

    # 23 years of Mumbai ground truth
    assert len(benchmarks["mumbai_imd_declarations"]) == 23
    assert benchmarks["mumbai_imd_declarations"]["2001"] == "2001-06-07"
    assert benchmarks["mumbai_imd_declarations"]["2005"] == "2005-06-08"
    assert benchmarks["mumbai_imd_declarations"]["2023"] == "2023-06-25"

    # 5 years of Pune ground truth
    assert len(benchmarks["pune_imd_declarations"]) == 5
    assert benchmarks["pune_imd_declarations"]["2019"] == "2019-06-24"
    assert benchmarks["pune_imd_declarations"]["2023"] == "2023-06-24"

    # Exactly 17 experiments evaluated
    assert len(sensitivity_data["experiments"]) == 17


def test_false_onset_break_filter_dynamics(sensitivity_data):
    """Verifies that the false-onset filter functions as mathematically designed."""
    exp_dict = {exp["config"]["id"]: exp for exp in sensitivity_data["experiments"]}

    # Without break filter, 0% false onsets flagged
    assert exp_dict["EXP_BREAK_NONE"]["statewide_false_onset_pct"] == 0.0

    # With 14-day break filter, ~2.25% false onsets flagged statewide
    assert 1.0 < exp_dict["EXP_BREAK_14D"]["statewide_false_onset_pct"] < 4.0

    # With strict 10-day break filter, false onsets jump to > 8%
    assert exp_dict["EXP_BREAK_10D"]["statewide_false_onset_pct"] > 8.0


def test_regional_onset_chronology(sensitivity_data):
    """Verifies that coastal and Ghats regions precede interior regions in declared onset."""
    exp_dict = {exp["config"]["id"]: exp for exp in sensitivity_data["experiments"]}
    baseline = exp_dict["EXP_WIN_5D_30MM"]["regional_onsets"]

    # Western Ghats must be earliest
    ghats_doy = baseline["Western Ghats"]["mean_doy"]
    konkan_doy = baseline["Konkan"]["mean_doy"]
    vidarbha_doy = baseline["Vidarbha"]["mean_doy"]
    marathwada_doy = baseline["Marathwada"]["mean_doy"]
    madhya_mh_doy = baseline["Madhya Maharashtra"]["mean_doy"]

    # Chronological progression: Ghats <= Konkan < Vidarbha <= Marathwada <= Madhya MH
    assert ghats_doy <= konkan_doy
    assert konkan_doy < vidarbha_doy
    assert vidarbha_doy <= marathwada_doy
    assert marathwada_doy <= madhya_mh_doy


def test_mumbai_ground_truth_alignment(sensitivity_data):
    """Verifies that the algorithm achieves high accuracy against official Mumbai declarations."""
    exp_dict = {exp["config"]["id"]: exp for exp in sensitivity_data["experiments"]}

    # Top configurations should achieve MAE < 6.5 days against official Mumbai declarations
    assert exp_dict["EXP_WIN_3D_25MM"]["mumbai_mae_days"] < 5.5
    assert exp_dict["EXP_WIN_5D_30MM"]["mumbai_mae_days"] < 6.5
    assert exp_dict["EXP_WET_3DAY"]["mumbai_mae_days"] < 5.5


def test_wet_day_persistence_impact(sensitivity_data):
    """Verifies that requiring wet-day persistence improves accuracy and filters isolated storms."""
    exp_dict = {exp["config"]["id"]: exp for exp in sensitivity_data["experiments"]}

    mae_1day = exp_dict["EXP_WET_1DAY"]["mumbai_mae_days"]
    mae_2day = exp_dict["EXP_WET_2DAY"]["mumbai_mae_days"]
    mae_3day = exp_dict["EXP_WET_3DAY"]["mumbai_mae_days"]

    # Requiring 2 or 3 wet days significantly outperforms a 1-day isolated burst
    assert mae_2day < mae_1day
    assert mae_3day < mae_1day
