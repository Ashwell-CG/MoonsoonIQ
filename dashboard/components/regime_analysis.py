"""MonsoonIQ Dashboard – Regime Analysis Component.

Renders regime comparison charts and statistics across the four K-Means K=4 regimes.
"""

from __future__ import annotations

from html import escape
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.services.dashboard_service import get_regime_summary
from dashboard.utils.chart_theme import PLOTLY_LAYOUT, render_chart
from dashboard.utils.constants import REGIME_COLORS, REGIME_SHORT_NAMES
from dashboard.utils.formatting import doy_to_date_str

REGIME_CHART_LABELS = {
    "Core Interior Synchronized": "Core Interior",
    "Interior Semi-Arid Transition": "Semi-Arid",
    "Early Maritime & Western Ghats": "Maritime",
    "Rain-Shadow High-Volatility": "Rain-Shadow",
}


def render_regime_analysis(*, show_heading: bool = True) -> None:
    """Render the full regime comparison section."""
    if show_heading:
        st.markdown("### Regime analysis · Maharashtra")

    st.caption(
        "Four K-Means onset regimes discovered from nine historical onset-dynamics features "
        "across the 419-cell Maharashtra study domain."
    )

    regimes = get_regime_summary()

    tab_overview, tab_onset, tab_rainfall = st.tabs(
        ["Overview", "Onset timing", "Rainfall and dry spells"]
    )

    with tab_overview:
        _render_overview(regimes)

    with tab_onset:
        _render_onset_comparison(regimes)

    with tab_rainfall:
        _render_rainfall_comparison(regimes)


def _render_overview(regimes: pd.DataFrame) -> None:
    """Render regime overview table and cell count chart.

    Args:
        regimes: DataFrame from get_regime_summary().
    """
    # Share of the 419 cells: one stacked bar, each segment in its regime colour.
    total = int(regimes["cell_count"].sum())
    fig = go.Figure()
    for row in regimes.to_dict("records"):
        name = row["regime_kmeans"]
        fig.add_trace(go.Bar(
            y=[""], x=[row["cell_count"]], orientation="h",
            name=REGIME_SHORT_NAMES.get(name, name),
            marker=dict(color=REGIME_COLORS.get(name, "#9db0a6"), line=dict(width=1, color="#28322e")),
            hovertemplate=f"{REGIME_SHORT_NAMES.get(name, name)}: %{{x}} cells ({float(row['pct_of_total']):.1f}%)<extra></extra>",
        ))
    fig.update_layout(
        **PLOTLY_LAYOUT,
        title=f"Share of {total} grid cells by onset regime",
        barmode="stack", height=152, showlegend=False,
        margin=dict(l=16, r=16, t=48, b=24),
        xaxis=dict(range=[0, total], showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False, showticklabels=False),
    )
    render_chart(fig)

    cards = []
    for row in regimes.to_dict("records"):
        name = row["regime_kmeans"]
        color = REGIME_COLORS.get(name, "#9db0a6")
        cards.append(
            f'<article class="miq-regime-card" style="--miq-regime:{color};">'
            f'<div class="miq-regime-name">{escape(REGIME_SHORT_NAMES.get(name, name))}</div>'
            f'<div class="miq-regime-meta">{int(row["cell_count"])} cells · {float(row["pct_of_total"]):.1f}%<br>'
            f'Median onset {escape(str(row["median_onset_date"]))}</div>'
            '</article>'
        )
    st.markdown(f'<div class="miq-regime-summary">{"".join(cards)}</div>', unsafe_allow_html=True)
    with st.expander("Regional interpretation", expanded=False):
        st.markdown("""
        - **Core Interior Synchronized:** Vidarbha and eastern Marathwada; reliable Bay of Bengal surge onset with lower onset variability.
        - **Interior Semi-Arid Transition:** Central transition belt with intermediate onset timing and rainfall volatility.
        - **Early Maritime & Western Ghats:** Coastal and Ghats cells with earlier onset and orographic rainfall influence.
        - **Rain-Shadow High-Volatility:** Western Ghats lee with elevated post-onset dry-spell risk; see the historical risk summaries for measured frequencies.
        """)

    # Summary table
    display = regimes[[
        "regime_kmeans", "cell_count", "pct_of_total",
        "median_onset_date", "mean_std_onset", "mean_detection_freq"
    ]].copy()
    display.columns = [
        "Regime", "Cells", "Share", "Median onset",
        "Onset σ", "Detection rate"
    ]
    display["Detection rate"] = display["Detection rate"].apply(
        lambda x: f"{x * 100:.1f}%" if x <= 1 else f"{x:.1f}%"
    )
    display["Onset σ"] = display["Onset σ"].apply(lambda x: f"±{x:.1f} days")
    display["Share"] = display["Share"].apply(lambda x: f"{x:.1f}%")
    display["Regime"] = display["Regime"].map(REGIME_SHORT_NAMES)

    st.dataframe(display, use_container_width=True, hide_index=True)


def _render_onset_comparison(regimes: pd.DataFrame) -> None:
    """Render onset characteristics comparison across regimes.

    Args:
        regimes: DataFrame from get_regime_summary().
    """
    short_names = [REGIME_SHORT_NAMES.get(r, r) for r in regimes["regime_kmeans"]]
    chart_names = [REGIME_CHART_LABELS.get(r, r) for r in regimes["regime_kmeans"]]
    colors = [REGIME_COLORS.get(r, "#9E9E9E") for r in regimes["regime_kmeans"]]

    c1, c2 = st.columns(2)

    with c1:
        # Median onset DOY grouped bar
        fig1 = go.Figure()
        fig1.add_trace(go.Bar(
            x=chart_names,
            y=regimes["median_onset_doy"],
            marker_color=colors,
            customdata=short_names,
            text=[doy_to_date_str(d) for d in regimes["median_onset_doy"]],
            textposition="outside",
            hovertemplate="%{customdata}: DOY %{y:.0f} (%{text})<extra></extra>",
        ))
        fig1.update_layout(
            **PLOTLY_LAYOUT,
            title="Median onset date",
            yaxis_title="Day of year",
            xaxis=dict(title="Regime", tickangle=0, tickfont=dict(size=11), automargin=True),
            height=340,
        )
        render_chart(fig1)

    with c2:
        # Onset variability (mean standard deviation in days)
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=chart_names,
            y=regimes["mean_std_onset"],
            marker_color=colors,
            customdata=short_names,
            text=[f"±{v:.1f} days" for v in regimes["mean_std_onset"]],
            textposition="outside",
            hovertemplate="%{customdata}: ±%{y:.1f} days<extra></extra>",
        ))
        fig2.update_layout(
            **PLOTLY_LAYOUT,
            title="Historical onset variability",
            yaxis_title="Standard deviation (days)",
            xaxis=dict(title="Regime", tickangle=0, tickfont=dict(size=11), automargin=True),
            height=340,
        )
        render_chart(fig2)


def _render_rainfall_comparison(regimes: pd.DataFrame) -> None:
    """Render rainfall and dry spell comparisons across regimes.

    Args:
        regimes: DataFrame from get_regime_summary().
    """
    short_names = [REGIME_SHORT_NAMES.get(r, r) for r in regimes["regime_kmeans"]]
    chart_names = [REGIME_CHART_LABELS.get(r, r) for r in regimes["regime_kmeans"]]
    colors = [REGIME_COLORS.get(r, "#9E9E9E") for r in regimes["regime_kmeans"]]

    c1, c2 = st.columns(2)

    with c1:
        # June Mean Rainfall
        fig1 = go.Figure()
        fig1.add_trace(go.Bar(
            x=chart_names,
            y=regimes["mean_june_rain"],
            marker_color=colors,
            customdata=short_names,
            text=[f"{v:.0f} mm" for v in regimes["mean_june_rain"]],
            textposition="outside",
            hovertemplate="%{customdata}: %{y:.1f} mm<extra></extra>",
        ))
        fig1.update_layout(
            **PLOTLY_LAYOUT,
            title="Mean June rainfall",
            yaxis_title="Rainfall (mm)",
            xaxis=dict(title="Regime", tickangle=0, tickfont=dict(size=11), automargin=True),
            height=340,
        )
        render_chart(fig1)

    with c2:
        # Early-Season Dry Spell Mean Duration
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=chart_names,
            y=regimes["mean_dry_spell"],
            marker_color=colors,
            customdata=short_names,
            text=[f"{v:.1f} days" for v in regimes["mean_dry_spell"]],
            textposition="outside",
            hovertemplate="%{customdata}: %{y:.1f} days<extra></extra>",
        ))
        fig2.update_layout(
            **PLOTLY_LAYOUT,
            title="Mean post-onset dry spell",
            yaxis_title="Consecutive dry days",
            xaxis=dict(title="Regime", tickangle=0, tickfont=dict(size=11), automargin=True),
            height=340,
        )
        render_chart(fig2)

    # Highlight agricultural risk caveat
    st.info(
        "Rain-Shadow High-Volatility has the highest post-candidate break frequency: "
        "39.13% historical break probability after 50 mm. This is why its sowing trigger "
        "uses the two-stage 75 mm active wetting-cycle requirement."
    )
