"""MonsoonIQ - Advisory Data Models and Schemas.

Defines the core data structures, enums, and reports for the MonsoonIQ
Regime-Aware Experimental Sowing Advisory Engine.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import json
from typing import Any, Dict, List, Optional


class AdvisoryState(str, Enum):
    """Permitted experimental advisory states.

    Note: The phrase 'safe to sow' is strictly prohibited across all states.
    """

    HIGH_RISK = "HIGH RISK"
    CAUTION = "CAUTION"
    RAINFALL_CRITERIA_MET = "RAINFALL CRITERIA MET"
    INSUFFICIENT_DATA = "INSUFFICIENT DATA"


class RegimeName(str, Enum):
    """The four validated K-Means onset regimes across Maharashtra."""

    CORE_INTERIOR = "Core Interior Synchronized"
    RAIN_SHADOW = "Rain-Shadow High-Volatility"
    EARLY_MARITIME = "Early Maritime & Western Ghats"
    SEMI_ARID_TRANSITION = "Interior Semi-Arid Transition"


@dataclass
class GridCellInfo:
    """Geospatial and administrative metadata for a Maharashtra IMD grid cell.

    Attributes:
        cell_id: Standard cell identifier string (e.g. 'cell_000').
        cell_index: Zero-based integer index (0 to 418).
        latitude: Latitude coordinate in degrees north.
        longitude: Longitude coordinate in degrees east.
        district: Administrative district name.
        zone_id: Meteorological zone numeric identifier.
        zone_name: Meteorological zone name.
        regime_kmeans: Associated K-Means K=4 onset regime.
    """

    cell_id: str
    cell_index: int
    latitude: float
    longitude: float
    district: str
    zone_id: int
    zone_name: str
    regime_kmeans: str


@dataclass
class HistoricalRegimeBaseline:
    """Historical onset and rainfall climatology for the regime and cell (2001-2023).

    Attributes:
        historical_years_count: Total years in baseline (23 years, 2001-2023).
        regime_cell_count: Total grid cells assigned to this regime.
        regime_total_cell_years: Total cell-year observations in regime.
        median_onset_doy: Cell median sustained onset DOY.
        mean_onset_doy: Cell mean sustained onset DOY.
        std_onset_doy: Cell standard deviation of onset DOY.
        iqr_onset_doy: Cell interquartile range of onset DOY.
        early_onset_freq: Frequency of early onset (DOY < 157).
        delayed_onset_freq: Frequency of delayed onset (DOY > 172).
        rejected_candidate_freq: Frequency of rejected candidate onsets.
        onset_detection_freq: Frequency of successfully detected onsets.
        june_mean_rainfall_mm: Mean historical June rainfall (mm).
        june_rainfall_cv_pct: Interannual coefficient of variation of June rainfall (%).
        jj_mean_rainfall_mm: Mean June-July cumulative rainfall (mm).
        may_mean_rainfall_mm: Mean May pre-monsoon rainfall (mm).
        june_mean_wet_days: Mean June wet days (>= 2.5 mm).
        sowing_50mm_median_doy: Historical median DOY for 50 mm accumulation.
        sowing_50mm_delay_freq: Frequency of 50 mm reaching after July 1 or never.
        early_dry_spell_mean_days: Mean max dry spell in early season (June 1 - July 15).
        early_dry_spell_max_days: Worst single-season dry spell in early season.
        severe_dry_spell_10d_freq: Frequency of early dry spells >= 10 days.
        regime_50mm_delayed_pct: Regime-level delayed sowing rate for 50 mm (%).
        regime_50mm_unreached_pct: Regime-level rate of 50 mm never reached by July 15 (%).
        regime_75mm_delayed_pct: Regime-level delayed sowing rate for 75 mm (%).
        regime_75mm_unreached_pct: Regime-level rate of 75 mm never reached by July 15 (%).
        regime_75mm_median_doy: Regime-level median DOY for 75 mm accumulation.
        regime_rolling_3d_50mm_reach_pct: Percentage reaching 50 mm in rolling 3-day window.
        regime_rolling_5d_50mm_reach_pct: Percentage reaching 50 mm in rolling 5-day window.
        regime_post_trigger_10d_break_prob_pct: Historical probability of >=10-day dry spell post-trigger (%).
        regime_post_trigger_7d_break_prob_pct: Historical probability of >=7-day dry spell post-trigger (%).
        regime_mean_immediate_dry_spell_days: Average consecutive dry days immediately following trigger.
        regime_post_trigger_5d_rain_mm: Average cumulative rainfall in 5 days following trigger (mm).
        regime_post_trigger_10d_rain_mm: Average cumulative rainfall in 10 days following trigger (mm).
    """

    historical_years_count: int
    regime_cell_count: int
    regime_total_cell_years: int
    median_onset_doy: float
    mean_onset_doy: float
    std_onset_doy: float
    iqr_onset_doy: float
    early_onset_freq: float
    delayed_onset_freq: float
    rejected_candidate_freq: float
    onset_detection_freq: float
    june_mean_rainfall_mm: float
    june_rainfall_cv_pct: float
    jj_mean_rainfall_mm: float
    may_mean_rainfall_mm: float
    june_mean_wet_days: float
    sowing_50mm_median_doy: float
    sowing_50mm_delay_freq: float
    early_dry_spell_mean_days: float
    early_dry_spell_max_days: float
    severe_dry_spell_10d_freq: float
    regime_50mm_delayed_pct: float
    regime_50mm_unreached_pct: float
    regime_75mm_delayed_pct: float
    regime_75mm_unreached_pct: float
    regime_75mm_median_doy: float
    regime_rolling_3d_50mm_reach_pct: float
    regime_rolling_5d_50mm_reach_pct: float
    regime_post_trigger_10d_break_prob_pct: float
    regime_post_trigger_7d_break_prob_pct: float
    regime_mean_immediate_dry_spell_days: float
    regime_post_trigger_5d_rain_mm: float
    regime_post_trigger_10d_rain_mm: float


@dataclass
class CurrentRainfallMetrics:
    """Monitored rainfall measurements and empirical indicators for the ongoing season.

    Attributes:
        as_of_date: Date of latest available observation (YYYY-MM-DD).
        season_start_date: Start date of accumulation window (default YYYY-06-01).
        total_days_observed: Calendar days in the current monitoring window.
        valid_days_count: Number of days with verified valid observations.
        missing_days_count: Number of days with missing or null observations.
        data_completeness_pct: Percentage of valid days in window (%).
        cumulative_rainfall_mm: Total accumulated rainfall from season start (mm).
        rainy_days_count: Number of days with daily rainfall >= 2.5 mm.
        current_3day_rainfall_mm: Cumulative rainfall in the most recent 3 days (mm).
        current_5day_rainfall_mm: Cumulative rainfall in the most recent 5 days (mm).
        max_rolling_3day_mm: Highest 3-day rolling rainfall observed this season (mm).
        max_rolling_5day_mm: Highest 5-day rolling rainfall observed this season (mm).
        max_single_day_rain_mm: Highest single-day rainfall observed this season (mm).
        current_consecutive_dry_days: Number of consecutive days < 2.5 mm up to as_of_date.
        candidate_trigger_date: Date on which the cumulative rainfall threshold was first reached.
        candidate_trigger_doy: Day of year on which threshold was reached.
        is_triggered: True if cumulative rainfall threshold was attained.
        verification_window_wet_days: Wet days in the 5 days following candidate trigger.
        post_trigger_dry_days: Consecutive dry days observed after candidate trigger.
        post_trigger_5d_rain_mm: Total rainfall accumulated in 5 days post-trigger.
        is_extreme_rain_event: True if 1-day rain >= 100 mm or 3-day rain >= 200 mm.
        effective_cumulative_rainfall_mm: Cumulative rainfall in active wetting cycle resetting after >=10-day dry spell (mm).
        has_intervening_prolonged_dry_spell: True if a dry spell >= 10 days occurred prior to recent rain.
        max_intervening_dry_spell_days: Maximum consecutive dry days prior to current wetting cycle.
    """

    as_of_date: str
    season_start_date: str
    total_days_observed: int
    valid_days_count: int
    missing_days_count: int
    data_completeness_pct: float
    cumulative_rainfall_mm: float
    rainy_days_count: int
    current_3day_rainfall_mm: float
    current_5day_rainfall_mm: float
    max_rolling_3day_mm: float
    max_rolling_5day_mm: float
    max_single_day_rain_mm: float
    current_consecutive_dry_days: int
    candidate_trigger_date: Optional[str] = None
    candidate_trigger_doy: Optional[int] = None
    is_triggered: bool = False
    verification_window_wet_days: Optional[int] = None
    qualifying_5d_wet_days: int = 0
    verification_window_has_missing: bool = False
    post_trigger_dry_days: Optional[int] = None
    post_trigger_5d_rain_mm: Optional[float] = None
    is_extreme_rain_event: bool = False
    effective_cumulative_rainfall_mm: float = 0.0
    has_intervening_prolonged_dry_spell: bool = False
    max_intervening_dry_spell_days: int = 0


@dataclass
class ConditionEvaluation:
    """Transparent audit of a specific experimental advisory condition.

    Attributes:
        condition_name: Short identifier of the evaluated criterion.
        passed: Boolean evaluation result (True = met, False = unmet).
        threshold_description: Specification of required threshold or rule.
        actual_value: Empirical value observed from current rainfall data.
        rule_type: 'Institutionally Supported' vs 'Research-Derived Experimental'.
        source_citation: Scientific paper or university package of practices reference.
    """

    condition_name: str
    passed: bool
    threshold_description: str
    actual_value: Any
    rule_type: str
    source_citation: str


@dataclass
class AdvisoryReport:
    """Consolidated regime-aware experimental sowing advisory report.

    Contains all required fields mandated by the MonsoonIQ Phase 8 specification.
    """

    grid_cell: GridCellInfo
    historical_baseline: HistoricalRegimeBaseline
    current_metrics: CurrentRainfallMetrics
    advisory_state: AdvisoryState
    state_reasoning: List[str]
    condition_evaluations: List[ConditionEvaluation]
    post_trigger_dry_spell_status: str
    historical_risk_summary: Dict[str, Any]
    contingency_recommendations: List[str]
    data_freshness_and_completeness: Dict[str, Any]
    data_provenance: str = "Simulated Test Data"
    limitations_disclaimer: List[str] = field(
        default_factory=lambda: [
            "Rainfall accumulation is an imperfect proxy for soil profile moisture; it does not measure plant available water capacity.",
            "Attaining rainfall criteria does NOT guarantee successful crop establishment or protection against subsequent dry spells.",
            "This advisory is experimental research output; it is NOT an official government declaration and does NOT substitute for IMD or State Department of Agriculture advisories.",
            "Local soil type (shallow Inceptisols vs deep Vertisols), terrain slope, and farm-level irrigation infrastructure must dictate final operational sowing decisions.",
        ]
    )

    def to_dict(self) -> Dict[str, Any]:
        """Converts report into a clean, serializable dictionary."""
        d = asdict(self)
        d["advisory_state"] = self.advisory_state.value
        return d

    def to_json(self, indent: int = 2) -> str:
        """Converts report into a formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def format_display(self) -> str:
        """Generates human-readable formatted summary string."""
        lines = [
            f"=== MonsoonIQ Experimental Sowing Advisory ===",
            f"Grid Cell: {self.grid_cell.cell_id} (Lat: {self.grid_cell.latitude:.2f}°N, Lon: {self.grid_cell.longitude:.2f}°E) | District: {self.grid_cell.district}",
            f"Classification Regime: {self.grid_cell.regime_kmeans} (Zone: {self.grid_cell.zone_name})",
            f"As-of Date: {self.current_metrics.as_of_date} (Completeness: {self.current_metrics.data_completeness_pct:.1f}%)",
            f"Data Provenance: [{self.data_provenance}]",
            f"Advisory State: [{self.advisory_state.value}]",
            f"---------------------------------------------",
            f"Current Rainfall Observations:",
            f"  Cumulative (from June 1): {self.current_metrics.cumulative_rainfall_mm:.1f} mm",
            f"  Rainy Days (>= 2.5 mm): {self.current_metrics.rainy_days_count} days",
            f"  Rolling 3-Day Rain: {self.current_metrics.current_3day_rainfall_mm:.1f} mm (Season Max: {self.current_metrics.max_rolling_3day_mm:.1f} mm)",
            f"  Rolling 5-Day Rain: {self.current_metrics.current_5day_rainfall_mm:.1f} mm (Season Max: {self.current_metrics.max_rolling_5day_mm:.1f} mm)",
            f"  Current Dry Run (< 2.5 mm): {self.current_metrics.current_consecutive_dry_days} days",
            f"  Post-Trigger Dry Spell Status: {self.post_trigger_dry_spell_status}",
            f"---------------------------------------------",
            f"Condition Evaluations:",
        ]
        for c in self.condition_evaluations:
            status = "PASS" if c.passed else "FAIL"
            lines.append(
                f"  [{status}] {c.condition_name}: {c.actual_value} (Req: {c.threshold_description}) [{c.rule_type}]"
            )
        lines.append(f"---------------------------------------------")
        lines.append(f"Reasoning:")
        for r in self.state_reasoning:
            lines.append(f"  * {r}")
        lines.append(f"---------------------------------------------")
        lines.append(f"Historical Regime Risk Profile (2001-2023, N={self.historical_baseline.regime_total_cell_years} cell-years):")
        for k, v in self.historical_risk_summary.items():
            lines.append(f"  * {k}: {v}")
        lines.append(f"---------------------------------------------")
        lines.append(f"Contingency Recommendations:")
        for c in self.contingency_recommendations:
            lines.append(f"  * {c}")
        lines.append(f"---------------------------------------------")
        lines.append(f"Disclaimers & Limitations:")
        for lim in self.limitations_disclaimer:
            lines.append(f"  ! {lim}")
        lines.append(f"=============================================")
        return "\n".join(lines)
