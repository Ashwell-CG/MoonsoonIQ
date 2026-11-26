"""MonsoonIQ Dashboard – Advisory Panel Component.

Integrates the existing Phase 8.2 advisory engine and renders
transparent advisory state, conditions, and risk metrics.
"""

from __future__ import annotations

import sys
from calendar import monthrange
from datetime import date
from html import escape
from pathlib import Path

import streamlit as st

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.advisory import (
    AdvisoryDecisionEngine,
    AdvisoryReport,
    AdvisoryState,
    RegimeName,
)
from dashboard.services.dashboard_service import get_cell_advisory_data
from dashboard.utils.constants import ADVISORY_STATE_COLORS, REGIME_SHORT_NAMES
from dashboard.utils.formatting import doy_to_date_str, format_mm


@st.cache_resource
def _get_engine() -> AdvisoryDecisionEngine:
    """Get cached advisory engine instance."""
    return AdvisoryDecisionEngine()


def render_advisory_panel(cell_id: str, year: int, *, show_heading: bool = True) -> None:
    """Render the agricultural advisory panel for a selected cell and year.

    Args:
        cell_id: Grid cell identifier.
        year: Calendar year for historical replay.
    """
    if show_heading:
        st.markdown(f"### Agricultural advisory · {cell_id} · {year}")

    # The shared page-level provenance banner identifies the historical source.
    provenance = "Historical Replay (IMD 0.25° Gridded 2001-2023)"

    # Important disclaimer
    st.markdown(
        '<div class="miq-analysis-note">Experimental research replay of historical gridded rainfall. '
        'Thresholds are empirical topsoil-wetting indicators and cannot guarantee crop establishment. '
        'Use local KVK and SAU guidance for decisions.</div>',
        unsafe_allow_html=True,
    )

    # Build advisory
    engine = _get_engine()
    data = get_cell_advisory_data(cell_id, year)

    if not data:
        st.warning("No rainfall data available for this cell and year.")
        return

    # Select evaluation date
    with st.container(key="advisory_date"):
        month_col, day_col = st.columns(2)
        eval_month = month_col.selectbox("Evaluation month", ["June", "July"], index=0, key="adv_month")
        month_num = 6 if eval_month == "June" else 7
        eval_day = day_col.slider("Day", 1, monthrange(year, month_num)[1], 25, key="adv_day")
        as_of = f"{year}-{month_num:02d}-{eval_day:02d}"

    # Filter data up to as_of date
    filtered_data = [(d, r) for d, r in data if d <= as_of]

    if not filtered_data:
        st.info("No observations available up to the selected date.")
        return

    try:
        report = engine.generate_advisory(
            cell_id, filtered_data,
            as_of_date=as_of,
            data_provenance=provenance,
        )
    except Exception as e:
        st.error(f"Advisory engine error: {e}")
        return

    _render_advisory_report(report)


def _render_advisory_report(report: AdvisoryReport) -> None:
    """Render a formatted advisory report."""
    state = report.advisory_state
    state_color = ADVISORY_STATE_COLORS.get(state.value, "#9E9E9E")
    regime = report.grid_cell.regime_kmeans
    regime_short = REGIME_SHORT_NAMES.get(regime, regime)

    # State banner
    st.markdown(
        f"""<section class="miq-advisory-status" style="--miq-state:{state_color};">
            <div class="miq-advisory-context">Sowing advisory · {date.fromisoformat(report.current_metrics.as_of_date):%d %b %Y}</div>
            <div class="miq-advisory-state">{escape(state.value.capitalize())}</div>
            <div class="miq-advisory-context">{escape(regime_short)} · {escape(report.grid_cell.district)}</div>
        </section>""",
        unsafe_allow_html=True,
    )

    # Key metrics row
    metrics = report.current_metrics
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Cumulative rainfall", format_mm(metrics.cumulative_rainfall_mm, 1))
    c2.metric("Active-cycle rain", format_mm(metrics.effective_cumulative_rainfall_mm, 1),
              help="Rainfall in active wetting cycle (resets after ≥10d dry break)")
    c3.metric("Wet days in 5-day window", str(metrics.qualifying_5d_wet_days),
              help="Rainy days (≥2.5mm) within 5-day verification window")
    c4.metric("Current dry spell", f"{metrics.current_consecutive_dry_days} days")
    c5.metric("Season rainy days", str(metrics.rainy_days_count))

    # Additional dry-spell reset info
    if metrics.has_intervening_prolonged_dry_spell:
        st.warning(
            f"Root-zone moisture depletion: a prolonged dry spell of "
            f"{metrics.max_intervening_dry_spell_days} consecutive dry days intervened between "
            f"earlier rainfall and recent showers. Prior moisture is treated as evaporated."
        )

    # Reasoning
    st.markdown('<div class="miq-subhead">Advisory reasoning</div>', unsafe_allow_html=True)
    reasons = "".join(f"<li>{escape(str(r))}</li>" for r in report.state_reasoning)
    st.markdown(
        f'<div class="miq-reasoning" style="--miq-state:{state_color};"><ul>{reasons}</ul></div>',
        unsafe_allow_html=True,
    )

    # Condition evaluations
    with st.expander("Condition evaluations", expanded=False):
        items = "".join(
            f'<li class="{"passed" if cond.passed else "unmet"}">'
            f'<div class="head">{escape(cond.condition_name)}'
            f'<span class="verdict">{"Passed" if cond.passed else "Unmet"}</span></div>'
            f'<p>Threshold: {escape(str(cond.threshold_description))}</p>'
            f'<p>Actual: {escape(str(cond.actual_value))}</p>'
            f'<p class="src">{escape(str(cond.rule_type))} · {escape(str(cond.source_citation))}</p></li>'
            for cond in report.condition_evaluations
        )
        st.markdown(f'<ul class="miq-conditions">{items}</ul>', unsafe_allow_html=True)

    # Historical risk summary
    if report.historical_risk_summary:
        with st.expander("Historical regime risk", expanded=False):
            rows = "".join(f"<div><dt>{escape(str(k))}</dt><dd>{escape(str(v))}</dd></div>"
                           for k, v in report.historical_risk_summary.items())
            st.markdown(f'<dl class="guide-values">{rows}</dl>', unsafe_allow_html=True)
            st.caption(
                "These are historical empirical frequencies (2001–2023 climatology), "
                "not live forecasts for the current season."
            )

    # Contingency recommendations
    if report.contingency_recommendations:
        st.markdown('<div class="miq-subhead">Contingency recommendations</div>', unsafe_allow_html=True)
        for rec in report.contingency_recommendations:
            st.markdown(f"- {rec}")

    # Post-trigger dry spell status
    if report.post_trigger_dry_spell_status:
        with st.expander("Post-trigger dry spell"):
            st.markdown(report.post_trigger_dry_spell_status)
