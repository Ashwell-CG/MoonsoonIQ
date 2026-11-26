"""MonsoonIQ - Advisory Decision Engine.

Evaluates current rainfall observations against regime-specific experimental criteria,
handles July 15 contingency cutoffs, and generates transparent advisory reports.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

from src.advisory.models import (
    AdvisoryReport,
    AdvisoryState,
    ConditionEvaluation,
    CurrentRainfallMetrics,
    GridCellInfo,
    HistoricalRegimeBaseline,
    RegimeName,
)
from src.advisory.rainfall_monitor import RainfallMonitor
from src.advisory.regime_lookup import RegimeLookupService

logger = logging.getLogger("MonsoonIQ.DecisionEngine")


class AdvisoryDecisionEngine:
    """Regime-aware decision engine for evaluating Kharif sowing rainfall conditions."""

    def __init__(
        self,
        lookup_service: Optional[RegimeLookupService] = None,
        rainfall_monitor: Optional[RainfallMonitor] = None,
        min_completeness_pct: float = 90.0,
        max_missing_days: int = 3,
    ) -> None:
        """Initializes the decision engine.

        Args:
            lookup_service: Historical regime lookup service instance.
            rainfall_monitor: Current rainfall monitor instance.
            min_completeness_pct: Minimum required percentage of valid observations (90%).
            max_missing_days: Maximum allowable missing days before flagging insufficient data (3).
        """
        self.lookup = lookup_service or RegimeLookupService()
        self.monitor = rainfall_monitor or RainfallMonitor()
        self.min_completeness_pct = min_completeness_pct
        self.max_missing_days = max_missing_days

        # Configurable regime-specific target thresholds
        self.regime_thresholds: Dict[str, float] = {
            RegimeName.CORE_INTERIOR.value: 75.0,        # PDKV Akola / VNMKV Parbhani Vertisol POP
            RegimeName.RAIN_SHADOW.value: 75.0,         # MPKV Rahuri Scarcity Zone 75 mm Rule
            RegimeName.EARLY_MARITIME.value: 50.0,       # Early high-intensity maritime onset
            RegimeName.SEMI_ARID_TRANSITION.value: 75.0, # Transition Vertisols
        }

    def generate_advisory(
        self,
        cell_id: Union[str, int],
        daily_rainfall: Any,
        as_of_date: Optional[str] = None,
        custom_threshold_mm: Optional[float] = None,
        data_provenance: str = "Simulated Test Data",
    ) -> AdvisoryReport:
        """Generates a complete regime-aware advisory report for a specific grid cell.

        Args:
            cell_id: Cell identifier (e.g. 'cell_042' or 42).
            daily_rainfall: Daily rainfall series, dataframe, or list of tuples.
            as_of_date: Date of observation cutoff (YYYY-MM-DD).
            custom_threshold_mm: Optional override for cumulative rainfall threshold.
            data_provenance: Provenance label ('Historical Replay', 'Simulated Test Data', 'Observed Weather Station', 'NWP Forecast Model').

        Returns:
            AdvisoryReport with verified advisory state, conditions, and risk disclaimers.
        """
        # 1. Historical Regime Lookup
        cell_info, baseline = self.lookup.get_cell_by_id(cell_id)
        regime = cell_info.regime_kmeans

        # 2. Determine target threshold
        threshold_mm = (
            custom_threshold_mm
            if custom_threshold_mm is not None
            else self.regime_thresholds.get(regime, 75.0)
        )

        # 3. Monitor Current Rainfall
        metrics = self.monitor.evaluate_observations(
            daily_rainfall=daily_rainfall,
            target_threshold_mm=threshold_mm,
            as_of_date=as_of_date,
        )

        # 4. Evaluate Advisory Decision Logic
        return self._evaluate_advisory_state(
            cell_info, baseline, metrics, threshold_mm, data_provenance=data_provenance
        )

    def _evaluate_advisory_state(
        self,
        cell_info: GridCellInfo,
        baseline: HistoricalRegimeBaseline,
        metrics: CurrentRainfallMetrics,
        threshold_mm: float,
        data_provenance: str = "Simulated Test Data",
    ) -> AdvisoryReport:
        """Evaluates empirical evidence and constructs the final AdvisoryReport."""
        regime = cell_info.regime_kmeans
        conditions: List[ConditionEvaluation] = []
        reasoning: List[str] = []
        contingency: List[str] = []

        # Parse observation date
        as_of_dt = pd.to_datetime(metrics.as_of_date) if metrics.as_of_date != "N/A" else None
        is_past_july15 = as_of_dt is not None and (as_of_dt.month > 7 or (as_of_dt.month == 7 and as_of_dt.day > 15))

        # Exact cell-year counts for historical risk profile
        tot_cy = baseline.regime_total_cell_years
        unreached_75_count = int(round(baseline.regime_75mm_unreached_pct / 100.0 * tot_cy))
        unreached_50_count = int(round(baseline.regime_50mm_unreached_pct / 100.0 * tot_cy))
        delayed_50_count = int(round(baseline.regime_50mm_delayed_pct / 100.0 * tot_cy))
        
        # Triggered cell-years denominator for post-trigger dry spell risk (2001-2023)
        triggered_cy = tot_cy - unreached_50_count
        break_10d_count = int(round(baseline.regime_post_trigger_10d_break_prob_pct / 100.0 * triggered_cy))
        break_7d_count = int(round(baseline.regime_post_trigger_7d_break_prob_pct / 100.0 * triggered_cy))

        # Build Historical Risk Summary
        historical_risk = {
            "Regime Name": regime,
            "Baseline Sample Size": f"{baseline.historical_years_count} years (2001-2023), {baseline.regime_cell_count} cells, {tot_cy} cell-years",
            "June Rainfall Mean / CV": f"{baseline.june_mean_rainfall_mm:.1f} mm (CV: {baseline.june_rainfall_cv_pct:.1f}%)",
            "Historical Onset DOY (Median +/- Std)": f"DOY {baseline.median_onset_doy:.1f} (+/- {baseline.std_onset_doy:.1f} days)",
            "50 mm Sowing Delay Frequency (> July 1 or Never)": f"{baseline.regime_50mm_delayed_pct:.2f}% ({delayed_50_count} / {tot_cy} cell-years)",
            "50 mm Never Reached by July 15": f"{baseline.regime_50mm_unreached_pct:.2f}% ({unreached_50_count} / {tot_cy} cell-years)",
            "75 mm Never Reached by July 15": f"{baseline.regime_75mm_unreached_pct:.2f}% ({unreached_75_count} / {tot_cy} cell-years)",
            "Post-Trigger >= 10-Day Break Probability": f"{baseline.regime_post_trigger_10d_break_prob_pct:.2f}% ({break_10d_count} / {triggered_cy} triggered cell-years over 20-day window)",
            "Post-Trigger >= 7-Day Break Probability": f"{baseline.regime_post_trigger_7d_break_prob_pct:.2f}% ({break_7d_count} / {triggered_cy} triggered cell-years)",
            "Mean Immediate Dry Spell Post-Trigger": f"{baseline.regime_mean_immediate_dry_spell_days:.2f} consecutive dry days",
        }

        # Check Condition 0: Data Completeness
        completeness_pass = (
            metrics.data_completeness_pct >= self.min_completeness_pct
            and metrics.missing_days_count <= self.max_missing_days
        )
        conditions.append(
            ConditionEvaluation(
                condition_name="Data Completeness",
                passed=completeness_pass,
                threshold_description=f">={self.min_completeness_pct:.0f}% completeness (max {self.max_missing_days} missing days)",
                actual_value=f"{metrics.data_completeness_pct:.1f}% ({metrics.missing_days_count} missing days)",
                rule_type="Scientific Integrity Requirement",
                source_citation="MonsoonIQ Data Quality Framework; IMD Gridded Rainfall Guidelines",
            )
        )

        if not completeness_pass:
            advisory_state = AdvisoryState.INSUFFICIENT_DATA
            reasoning.append(
                f"Rainfall observation completeness ({metrics.data_completeness_pct:.1f}%) is below required operational threshold ({self.min_completeness_pct:.0f}%). "
                f"Missing {metrics.missing_days_count} days in the observation window. Missing days cannot be assumed to be dry or wet."
            )
            contingency.append("Verify local automated weather station (AWS) connectivity before evaluating sowing readiness.")
            post_trigger_status = "Evaluation suspended due to incomplete observations."

            return AdvisoryReport(
                grid_cell=cell_info,
                historical_baseline=baseline,
                current_metrics=metrics,
                advisory_state=advisory_state,
                state_reasoning=reasoning,
                condition_evaluations=conditions,
                post_trigger_dry_spell_status=post_trigger_status,
                historical_risk_summary=historical_risk,
                contingency_recommendations=contingency,
                data_freshness_and_completeness={
                    "start_date": metrics.season_start_date,
                    "as_of_date": metrics.as_of_date,
                    "total_days": metrics.total_days_observed,
                    "valid_days": metrics.valid_days_count,
                    "missing_days": metrics.missing_days_count,
                    "completeness_pct": metrics.data_completeness_pct,
                },
                data_provenance=data_provenance,
            )

        # Condition 1: Cumulative Rainfall Threshold
        if regime == RegimeName.RAIN_SHADOW.value and metrics.has_intervening_prolonged_dry_spell:
            # Rain-Shadow Root-Zone Moisture Persistence Rule:
            # If an intervening prolonged dry spell >= 10 days occurred between earlier rain and recent rain,
            # moisture from earlier rain has evaporated. Sowing requires >= 75 mm in the active wetting cycle.
            cum_pass = metrics.effective_cumulative_rainfall_mm >= threshold_mm
            cum_cond_name = f"Cumulative Rainfall >= {threshold_mm:.1f} mm (Active Wetting Cycle)"
            cum_cond_desc = f">={threshold_mm:.1f} mm accumulated in active cycle (prior rain depleted by >=10d dry break)"
            cum_cond_actual = f"{metrics.effective_cumulative_rainfall_mm:.1f} mm in active cycle ({metrics.cumulative_rainfall_mm:.1f} mm total since June 1, {metrics.max_intervening_dry_spell_days}d dry break intervened)"
        else:
            cum_pass = metrics.cumulative_rainfall_mm >= threshold_mm
            cum_cond_name = f"Cumulative Rainfall >= {threshold_mm:.1f} mm"
            cum_cond_desc = f">={threshold_mm:.1f} mm accumulated from June 1"
            cum_cond_actual = f"{metrics.cumulative_rainfall_mm:.1f} mm"

        conditions.append(
            ConditionEvaluation(
                condition_name=cum_cond_name,
                passed=cum_pass,
                threshold_description=cum_cond_desc,
                actual_value=cum_cond_actual,
                rule_type="Institutionally Supported",
                source_citation="MPKV Rahuri / Dr. PDKV Akola / VNMKV Parbhani Vertisol POP (2020-2022)",
            )
        )

        # Condition 2: Rainy Day Count
        rainy_day_req = 2
        rainy_pass = metrics.rainy_days_count >= rainy_day_req
        conditions.append(
            ConditionEvaluation(
                condition_name=f"Season Rainy Days >= {rainy_day_req}",
                passed=rainy_pass,
                threshold_description=f">={rainy_day_req} distinct days with >= 2.5 mm",
                actual_value=f"{metrics.rainy_days_count} days",
                rule_type="Research-Derived Experimental",
                source_citation="MonsoonIQ Two-Stage Onset Detection Protocol; IMD Rainy Day Standard",
            )
        )

        # Condition 3: Rain-Shadow 50 mm Solo Prohibition
        if regime == RegimeName.RAIN_SHADOW.value:
            prohibition_pass = not (50.0 <= metrics.cumulative_rainfall_mm < 75.0)
            conditions.append(
                ConditionEvaluation(
                    condition_name="50 mm Solo Trigger Prohibition",
                    passed=prohibition_pass,
                    threshold_description="Rain-Shadow strictly requires >= 75 mm (50 mm solo trigger prohibited)",
                    actual_value="Enforced (75 mm required)" if metrics.cumulative_rainfall_mm >= 75.0 else f"{metrics.cumulative_rainfall_mm:.1f} mm (Below 75 mm)",
                    rule_type="Research-Derived Experimental & Institutional",
                    source_citation="Phase 7.1 Sowing Trigger Audit; MPKV Rahuri Scarcity Zone Guidelines (2021)",
                )
            )

        # Condition 4: Two-Stage Verification Window Persistence
        if metrics.is_triggered:
            if regime == RegimeName.RAIN_SHADOW.value:
                # Rain-Shadow strictly requires BOTH qualifying rainy days within a 5-day verification window
                verif_pass = metrics.qualifying_5d_wet_days >= 2
                verif_desc = "Both qualifying rainy days (>= 2.5 mm) must occur within the specified 5-day verification window"
                verif_actual = f"{metrics.qualifying_5d_wet_days} wet days in 5-day verification window"
            else:
                verif_wet_days = metrics.verification_window_wet_days if metrics.verification_window_wet_days is not None else 0
                verif_pass = metrics.qualifying_5d_wet_days >= 2 or verif_wet_days >= 1
                verif_desc = "At least 2 distinct rainy days within 5 days confirming sustained monsoon flow"
                verif_actual = f"{metrics.qualifying_5d_wet_days} wet days in 5-day window"

            conditions.append(
                ConditionEvaluation(
                    condition_name="Two-Stage Verification Window Persistence",
                    passed=verif_pass,
                    threshold_description=verif_desc,
                    actual_value=verif_actual,
                    rule_type="Research-Derived Experimental",
                    source_citation="MonsoonIQ Two-Stage Sustained Onset Architecture (Phase 5B/7.1/8.1)",
                )
            )
        else:
            verif_pass = False

        # Condition 5: Heavy-Rainfall Hazard Check (Maritime & Ghats)
        if regime == RegimeName.EARLY_MARITIME.value:
            extreme_pass = not metrics.is_extreme_rain_event
            conditions.append(
                ConditionEvaluation(
                    condition_name="Heavy-Rainfall Hazard Indicator (Potential Waterlogging / Drainage Risk)",
                    passed=extreme_pass,
                    threshold_description="Precipitation hazard threshold: no single day >= 100 mm and no 3-day sum >= 200 mm (Heavy-rainfall hazard indicator, not confirmed field waterlogging)",
                    actual_value=f"1-Day Max: {metrics.max_single_day_rain_mm:.1f} mm, 3-Day Max: {metrics.max_rolling_3day_mm:.1f} mm",
                    rule_type="Agronomic Drainage Safety Indicator",
                    source_citation="Dr. BSKKV Dapoli Konkan Kharif Guidelines; CRIDA Drainage Protocols",
                )
            )
        else:
            extreme_pass = True

        # Check for missing observations inside the 5-day verification window
        if metrics.verification_window_has_missing and metrics.is_triggered:
            advisory_state = AdvisoryState.INSUFFICIENT_DATA
            reasoning.append(
                "Missing or unverified rainfall observations occurred inside the 5-day verification window. "
                "Cannot confirm whether qualifying rainfall criteria were met without complete observations."
            )
            contingency.append("Await verified rainfall data before taking operational sowing decisions.")
            post_trigger_status = "Verification suspended due to missing observations inside verification window."

            return AdvisoryReport(
                grid_cell=cell_info,
                historical_baseline=baseline,
                current_metrics=metrics,
                advisory_state=advisory_state,
                state_reasoning=reasoning,
                condition_evaluations=conditions,
                post_trigger_dry_spell_status=post_trigger_status,
                historical_risk_summary=historical_risk,
                contingency_recommendations=contingency,
                data_freshness_and_completeness={
                    "start_date": metrics.season_start_date,
                    "as_of_date": metrics.as_of_date,
                    "total_days": metrics.total_days_observed,
                    "valid_days": metrics.valid_days_count,
                    "missing_days": metrics.missing_days_count,
                    "completeness_pct": metrics.data_completeness_pct,
                },
                data_provenance=data_provenance,
            )

        # Post-Trigger Dry Spell Status String
        if metrics.is_triggered:
            post_dry = metrics.post_trigger_dry_days or 0
            post_trigger_status = (
                f"Candidate trigger reached on {metrics.candidate_trigger_date} (DOY {metrics.candidate_trigger_doy}). "
                f"Post-trigger dry spell: {post_dry} consecutive dry days. "
                f"Historical >=10-day break probability in this regime is {baseline.regime_post_trigger_10d_break_prob_pct:.1f}%."
            )
        else:
            post_trigger_status = (
                f"Cumulative rainfall ({metrics.cumulative_rainfall_mm:.1f} mm) has not reached the {threshold_mm:.1f} mm threshold. "
                f"Current dry spell: {metrics.current_consecutive_dry_days} days."
            )

        # ----------------------------------------------------
        # DECISION BRANCH 1: Post-July 15 Contingency Handling
        # ----------------------------------------------------
        if is_past_july15 and not cum_pass:
            advisory_state = AdvisoryState.HIGH_RISK
            deficit = threshold_mm - metrics.cumulative_rainfall_mm
            reasoning.append(
                f"SOWING WINDOW DELAYED PAST JULY 15: Cumulative rainfall is {metrics.cumulative_rainfall_mm:.1f} mm, "
                f"representing an early-season moisture deficit of {deficit:.1f} mm from the {threshold_mm:.1f} mm requirement."
            )
            reasoning.append(
                f"Historically, {baseline.regime_75mm_unreached_pct:.1f}% of years in this regime fail to accumulate 75 mm by July 15. "
                f"Sowing long-duration Kharif crops past mid-July incurs severe terminal moisture stress during September grain-filling."
            )

            # District / Regime Specific Contingency Alternatives
            if regime == RegimeName.RAIN_SHADOW.value:
                contingency.append(
                    "ICAR-CRIDA Solapur Contingency Guidance: Cease normal Kharif sowing of long-duration crops. "
                    "Conserve soil profile moisture for Rabi season (Rabi Sorghum cv. Maldandi M 35-1, Chickpea cv. Vijay, Safflower cv. Bhima)."
                )
                contingency.append(
                    "MPKV Rahuri Contingency Alternative: If rainfall arrives before late July, plant only early-maturing contingency crops "
                    "(Horsegram cv. Sina / Man, Cowpea cv. Phule Pandhari, or Sunflower cv. Phule Bhaskar)."
                )
            elif regime == RegimeName.SEMI_ARID_TRANSITION.value:
                contingency.append(
                    "VNMKV Parbhani Contingency Advice: Abort standard Bt Cotton and long-duration Soybean sowing. "
                    "Shift to short-duration pulses (Black gram cv. TAU-1, Green gram cv. BM-2003-2) or Pigeonpea + Bajra intercropping."
                )
            else:
                contingency.append(
                    "Consult local Krishi Vigyan Kendra (KVK) and State Department of Agriculture contingency advisories for mid-season alternative crops."
                )

            return AdvisoryReport(
                grid_cell=cell_info,
                historical_baseline=baseline,
                current_metrics=metrics,
                advisory_state=advisory_state,
                state_reasoning=reasoning,
                condition_evaluations=conditions,
                post_trigger_dry_spell_status=post_trigger_status,
                historical_risk_summary=historical_risk,
                contingency_recommendations=contingency,
                data_freshness_and_completeness={
                    "start_date": metrics.season_start_date,
                    "as_of_date": metrics.as_of_date,
                    "total_days": metrics.total_days_observed,
                    "valid_days": metrics.valid_days_count,
                    "missing_days": metrics.missing_days_count,
                    "completeness_pct": metrics.data_completeness_pct,
                },
                data_provenance=data_provenance,
            )

        # ----------------------------------------------------
        # DECISION BRANCH 2: Pre-July 15 or Criteria Evaluation
        # ----------------------------------------------------
        if regime == RegimeName.RAIN_SHADOW.value:
            # Rain Shadow Logic
            if not cum_pass:
                if metrics.has_intervening_prolonged_dry_spell and metrics.cumulative_rainfall_mm >= 75.0:
                    advisory_state = AdvisoryState.CAUTION
                    reasoning.append(
                        f"Rain-Shadow Root-Zone Moisture Depletion Alert: Cumulative rainfall since June 1 is {metrics.cumulative_rainfall_mm:.1f} mm, "
                        f"BUT an intervening prolonged dry spell of {metrics.max_intervening_dry_spell_days} consecutive dry days occurred "
                        f"between earlier rainfall ({metrics.cumulative_rainfall_mm - metrics.effective_cumulative_rainfall_mm:.1f} mm) and recent showers ({metrics.effective_cumulative_rainfall_mm:.1f} mm). "
                        f"Under high summer evaporative demand (ET0 > 5 mm/day), moisture from early June has completely evaporated from the Vertisol root zone. "
                        f"Recent rainfall ({metrics.effective_cumulative_rainfall_mm:.1f} mm) is insufficient to wet the 15-20 cm seedbed. Sowing now risks severe seedling desiccation."
                    )
                    contingency.append("Hold sowing. Await a sustained wetting pulse of >= 75 mm in the active wetting cycle to replenish depleted root-zone moisture.")
                elif metrics.cumulative_rainfall_mm >= 50.0:
                    advisory_state = AdvisoryState.CAUTION
                    reasoning.append(
                        f"Cumulative rainfall reached {metrics.cumulative_rainfall_mm:.1f} mm (exceeding 50 mm), BUT 50 mm solo triggering is strictly PROHIBITED in the Rain Shadow. "
                        f"MPKV Rahuri and MonsoonIQ Phase 7.1 research enforce a minimum of 75 mm to wet 15-20 cm of heavy Vertisol root zone."
                    )
                    reasoning.append(
                        f"Historically, 39.13% of 50 mm triggers in this regime were followed by a >= 10-day severe dry spell, causing widespread seedling desiccation."
                    )
                    contingency.append("Hold dryland sowing. Wait for cumulative rainfall to reach >= 75 mm with verified secondary rain.")
                else:
                    if metrics.current_consecutive_dry_days >= 7:
                        advisory_state = AdvisoryState.HIGH_RISK
                        reasoning.append(
                            f"Cumulative rainfall is only {metrics.cumulative_rainfall_mm:.1f} mm with an active {metrics.current_consecutive_dry_days}-day dry spell. Sowing criteria unmet."
                        )
                    else:
                        advisory_state = AdvisoryState.CAUTION
                        reasoning.append(
                            f"Cumulative rainfall is {metrics.cumulative_rainfall_mm:.1f} mm (requires 75 mm). Sowing criteria pending."
                        )
                    contingency.append("Prepare land; avoid premature dry seeding in dry Vertisols prone to crusting.")
            else:
                # Cumulative >= 75 mm reached
                post_dry = metrics.post_trigger_dry_days or 0
                if post_dry >= 7:
                    advisory_state = AdvisoryState.HIGH_RISK
                    reasoning.append(
                        f"Cumulative rainfall criteria reached ({metrics.cumulative_rainfall_mm:.1f} mm), BUT field is experiencing an active {post_dry}-day dry break following the trigger date. "
                        f"Desiccation hazard is acute in this regime (39.13% historical probability of >=10-day break)."
                    )
                    if not verif_pass:
                        reasoning.append(
                            "Additionally, lack of secondary rainfall confirms an isolated pre-monsoon convective burst rather than sustained monsoon progression."
                        )
                    contingency.append("Postpone sowing until active dry break breaks with new rainfall.")
                elif not verif_pass:
                    advisory_state = AdvisoryState.CAUTION
                    reasoning.append(
                        f"Rain-Shadow Two-Stage Verification Rule: Cumulative rainfall reached {metrics.cumulative_rainfall_mm:.1f} mm, "
                        f"but only {metrics.qualifying_5d_wet_days} wet day(s) occurred within any 5-day verification window "
                        "(requires >= 2 distinct rainy days >= 2.5 mm). Suggests an isolated convective thunderstorm rather than sustained monsoon flow."
                    )
                    contingency.append("Wait for secondary shower (>= 2.5 mm) confirming active monsoon circulation before sowing.")
                elif post_dry >= 4:
                    advisory_state = AdvisoryState.CAUTION
                    reasoning.append(
                        f"Cumulative threshold reached ({metrics.cumulative_rainfall_mm:.1f} mm), but current dry run has reached {post_dry} days. Monitor soil moisture closely."
                    )
                    contingency.append("If sowing, apply dust mulch / inter-cultivation to conserve profile moisture. Prepare contingency seed.")
                else:
                        advisory_state = AdvisoryState.RAINFALL_CRITERIA_MET
                        reasoning.append(
                            f"Experimental rainfall threshold achieved ({metrics.cumulative_rainfall_mm:.1f} mm >= 75.0 mm) with {metrics.rainy_days_count} wet days. "
                            f"Note: This indicates historical rainfall accumulation criteria have been satisfied; it does NOT guarantee crop establishment."
                        )
                        reasoning.append(
                            f"HIGH DESICCATION ALERT: Historically in this regime, 39.13% of triggered years experienced a >= 10-day break within 20 days. "
                            f"Sow drought-tolerant crops (Bajra cv. Phule Aadishakti, Pigeonpea cv. Phule Rajeshwari, Sunflower cv. Phule Bhaskar)."
                        )
                        contingency.append("Adopt broad bed furrow (BBF) or ridges and furrows for in-situ moisture conservation.")

        elif regime == RegimeName.EARLY_MARITIME.value:
            # Maritime & Western Ghats Logic
            if not cum_pass:
                advisory_state = AdvisoryState.CAUTION
                reasoning.append(f"Cumulative rainfall is {metrics.cumulative_rainfall_mm:.1f} mm (threshold 50.0 mm). Onset criteria pending.")
                contingency.append("Complete pre-sowing nursery preparation for paddy.")
            else:
                if not extreme_pass:
                    advisory_state = AdvisoryState.CAUTION
                    reasoning.append(
                        f"Cumulative rainfall reached ({metrics.cumulative_rainfall_mm:.1f} mm), BUT extreme rainfall detected: "
                        f"1-day max of {metrics.max_single_day_rain_mm:.1f} mm or 3-day sum of {metrics.max_rolling_3day_mm:.1f} mm. "
                        f"Severe waterlogging, topsoil erosion, and seed rot hazard present."
                    )
                    contingency.append("Ensure drainage channels are clear before direct seeding; delay sowing until standing water recedes.")
                else:
                    advisory_state = AdvisoryState.RAINFALL_CRITERIA_MET
                    reasoning.append(
                        f"Experimental rainfall criteria met ({metrics.cumulative_rainfall_mm:.1f} mm >= 50.0 mm). "
                        f"Maritime onset is highly reliable with low historical dry-break risk ({baseline.regime_post_trigger_10d_break_prob_pct:.1f}%)."
                    )
                    contingency.append("Proceed with paddy nursery sowing or direct seeded rice according to Dr. BSKKV Dapoli package of practices.")

        elif regime == RegimeName.CORE_INTERIOR.value:
            # Core Interior Synchronized Logic
            if not cum_pass:
                if metrics.current_consecutive_dry_days >= 7:
                    advisory_state = AdvisoryState.CAUTION
                    reasoning.append(f"Cumulative rainfall is {metrics.cumulative_rainfall_mm:.1f} mm with {metrics.current_consecutive_dry_days} consecutive dry days. Criteria pending.")
                else:
                    advisory_state = AdvisoryState.CAUTION
                    reasoning.append(f"Cumulative rainfall is {metrics.cumulative_rainfall_mm:.1f} mm (requires 75.0 mm). Criteria pending.")
                contingency.append("Prepare land for Soybean / Cotton; wait for soaking rain wetting 15-20 cm soil layer.")
            else:
                post_dry = metrics.post_trigger_dry_days or 0
                if post_dry >= 7:
                    advisory_state = AdvisoryState.HIGH_RISK
                    reasoning.append(f"Cumulative criteria met ({metrics.cumulative_rainfall_mm:.1f} mm), but an active {post_dry}-day dry spell is ongoing.")
                    contingency.append("Wait for rainfall resumption before sowing Soybean to prevent seed desiccation.")
                else:
                    advisory_state = AdvisoryState.RAINFALL_CRITERIA_MET
                    reasoning.append(
                        f"Experimental rainfall criteria met ({metrics.cumulative_rainfall_mm:.1f} mm >= 75.0 mm). "
                        f"Vidarbha synchronized onset regime exhibits high reliability and low historical break risk ({baseline.regime_post_trigger_10d_break_prob_pct:.1f}%)."
                    )
                    contingency.append("Sow recommended Soybean (PDKV AMS-100-39, JS-335) or Cotton (AKH-081) varieties as per Dr. PDKV Akola guidelines.")

        else:
            # Interior Semi-Arid Transition Logic
            if not cum_pass:
                advisory_state = AdvisoryState.CAUTION
                reasoning.append(
                    f"Cumulative rainfall is {metrics.cumulative_rainfall_mm:.1f} mm (requires 75.0 mm). "
                    f"Historical delay risk in this transition regime is elevated ({baseline.regime_75mm_delayed_pct:.1f}% delayed past July 1)."
                )
                contingency.append("Avoid premature sowing; monitor soil depth and moisture retention in mixed soil types.")
            else:
                post_dry = metrics.post_trigger_dry_days or 0
                if post_dry >= 7:
                    advisory_state = AdvisoryState.HIGH_RISK
                    reasoning.append(
                        f"Cumulative rainfall criteria reached ({metrics.cumulative_rainfall_mm:.1f} mm), but active {post_dry}-day post-trigger dry spell creates desiccation risk. "
                        f"Historical break risk in transition regime is {baseline.regime_post_trigger_10d_break_prob_pct:.1f}%."
                    )
                    contingency.append("Pause sowing operations until dry spell is broken by fresh rainfall.")
                else:
                    advisory_state = AdvisoryState.RAINFALL_CRITERIA_MET
                    reasoning.append(
                        f"Experimental rainfall criteria met ({metrics.cumulative_rainfall_mm:.1f} mm >= 75.0 mm). "
                        f"Historical post-trigger break risk is moderate ({baseline.regime_post_trigger_10d_break_prob_pct:.1f}%)."
                    )
                    contingency.append("Adopt Soybean (MAUS-71) or Pigeonpea (BDN-711) intercropping as per VNMKV Parbhani advisories.")

        return AdvisoryReport(
            grid_cell=cell_info,
            historical_baseline=baseline,
            current_metrics=metrics,
            advisory_state=advisory_state,
            state_reasoning=reasoning,
            condition_evaluations=conditions,
            post_trigger_dry_spell_status=post_trigger_status,
            historical_risk_summary=historical_risk,
            contingency_recommendations=contingency,
            data_freshness_and_completeness={
                "start_date": metrics.season_start_date,
                "as_of_date": metrics.as_of_date,
                "total_days": metrics.total_days_observed,
                "valid_days": metrics.valid_days_count,
                "missing_days": metrics.missing_days_count,
                "completeness_pct": metrics.data_completeness_pct,
            },
            data_provenance=data_provenance,
        )
