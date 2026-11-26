"""MonsoonIQ Dashboard – Monsoon Onset Analysis Component.

Renders onset history timeline, distribution, and detection summary for a cell.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.services.data_loader import get_cell_onset_history, load_baselines
from dashboard.utils.chart_theme import PLOTLY_LAYOUT, render_chart
from dashboard.utils.formatting import doy_to_date_str


def render_onset_analysis(cell_lat: float, cell_lon: float, cell_id: str, *, show_heading: bool = True) -> None:
    """Render monsoon onset analysis section for a selected cell.

    Args:
        cell_lat: Grid cell latitude.
        cell_lon: Grid cell longitude.
        cell_id: Cell identifier string.
    """
    if show_heading:
        st.markdown(f"### Monsoon onset analysis · {cell_id}")

    # Load cell baselines
    df_base = load_baselines()
    cell_row = df_base[df_base["cell_id"] == cell_id]
    if cell_row.empty:
        st.warning(f"Cell {cell_id} not found in baselines.")
        return
    cell = cell_row.iloc[0]

    # Load onset history
    history = get_cell_onset_history(cell_lat, cell_lon)

    # Explanation
    with st.expander("How local onset is detected", expanded=False):
        st.markdown("""
        **Candidate Onset** is the first date when cumulative rainfall reaches the
        regional threshold (5-day accumulation window). **Confirmed Onset** requires
        passing a 20-day verification period with no break exceeding 14 consecutive
        dry days. If the verification fails, the candidate is **rejected** and the
        algorithm searches for the next candidate.

        This is a *rainfall-based local sustained onset* — not the official IMD
        monsoon-advance declaration, which uses different synoptic criteria.
        """)

    tab_timeline, tab_stats = st.tabs(["Year by year", "Summary"])

    with tab_timeline:
        _render_onset_timeline(history, cell)

    with tab_stats:
        _render_onset_stats(history, cell)


def _render_onset_timeline(history: pd.DataFrame, cell: pd.Series) -> None:
    """Render year-by-year onset timeline chart."""
    median_doy = cell["median_onset_doy"]

    fig = go.Figure()

    # Confirmed onsets
    confirmed = history.dropna(subset=["confirmed_onset_doy"])
    if not confirmed.empty:
        fig.add_trace(go.Scatter(
            x=confirmed["year"],
            y=confirmed["confirmed_onset_doy"],
            mode="markers+lines",
            marker=dict(size=9, color="#86C9C2", symbol="circle", line=dict(color="#E4EEE7", width=1.2)),
            line=dict(color="#639C94", width=1.4),
            name="Confirmed Onset",
            hovertemplate="Year %{x}: DOY %{y:.0f} (" +
                          confirmed["confirmed_onset_doy"].apply(
                              lambda d: doy_to_date_str(d) if d == d else "—"
                          ) + ")<extra></extra>",
        ))

    # No-detection markers
    no_det = history[history["no_detection"] == 1]
    if not no_det.empty:
        fig.add_trace(go.Scatter(
            x=no_det["year"],
            y=[212] * len(no_det),  # July 31 DOY as placeholder
            mode="markers",
            marker=dict(size=10, color="#DC2626", symbol="x"),
            name="No Detection",
            hovertemplate="Year %{x}: No confirmed onset detected<extra></extra>",
        ))

    # Median line
    fig.add_hline(y=median_doy, line_dash="dash", line_color="#D97706",
                  annotation_text=f"Median {doy_to_date_str(median_doy)} · DOY {median_doy:.0f}")

    fig.update_layout(
        **PLOTLY_LAYOUT,
        title="Local onset date by year, 2001–2023",
        yaxis=dict(
            title="Local onset date",
            range=[140, 220],
            tickmode="array",
            tickvals=list(range(140, 221, 10)),
            ticktext=[doy_to_date_str(d) for d in range(140, 221, 10)],
            gridcolor="#F1F5F9",
            linecolor="#E2E8F0",
        ),
        xaxis=dict(title="Year", gridcolor="#F1F5F9", linecolor="#E2E8F0"),
        height=390,
        margin=dict(l=58, r=28, t=56, b=56),
    )
    render_chart(fig)


def _render_onset_stats(history: pd.DataFrame, cell: pd.Series) -> None:
    """Render onset summary statistics."""
    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Median onset", doy_to_date_str(cell["median_onset_doy"]),
              help=f"DOY {cell['median_onset_doy']:.0f}")
    c2.metric("Mean onset", doy_to_date_str(cell["mean_onset_doy"]),
              help=f"DOY {cell['mean_onset_doy']:.1f}")
    c3.metric("Standard deviation", f"{cell['std_onset_doy']:.1f} days")
    c4.metric("IQR", f"{cell['iqr_onset_doy']:.1f} days")

    st.markdown("---")

    c5, c6, c7, c8 = st.columns(4)
    early_pct = cell["early_onset_freq"] * 100 if cell["early_onset_freq"] <= 1 else cell["early_onset_freq"]
    delayed_pct = cell["delayed_onset_freq"] * 100 if cell["delayed_onset_freq"] <= 1 else cell["delayed_onset_freq"]
    rejected_pct = cell["rejected_candidate_freq"] * 100 if cell["rejected_candidate_freq"] <= 1 else cell["rejected_candidate_freq"]
    detect_pct = cell["onset_detection_freq"] * 100 if cell["onset_detection_freq"] <= 1 else cell["onset_detection_freq"]

    c5.metric("Early onset", f"{early_pct:.1f}%", help="Onset before median - 7 days")
    c6.metric("Delayed onset", f"{delayed_pct:.1f}%", help="Onset after July 1")
    c7.metric("Rejected candidates", f"{rejected_pct:.1f}%")
    c8.metric("Detection rate", f"{detect_pct:.1f}%")

    # No-detection years
    no_det_years = history[history["no_detection"] == 1]["year"].tolist()
    if no_det_years:
        st.warning(f"No confirmed onset in {', '.join(str(y) for y in no_det_years)}")
    else:
        st.success("Onset detected in all 23 study years for this cell.")
