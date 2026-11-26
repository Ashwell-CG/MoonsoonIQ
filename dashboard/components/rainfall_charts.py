"""MonsoonIQ Dashboard – Rainfall Charts Component.

Renders daily rainfall timeseries, monthly distribution, annual JJAS trends,
wet-day counts, and dry-spell analysis using Plotly.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.services.data_loader import get_cell_rainfall_series, get_jjas_rainfall
from dashboard.services.dashboard_service import get_monthly_rainfall
from dashboard.utils.chart_theme import PLOTLY_LAYOUT, render_chart
from dashboard.utils.formatting import format_mm


def render_rainfall_charts(
    cell_lat: float, cell_lon: float,
    cell_id: str, year: int, *, show_heading: bool = True
) -> None:
    """Render all rainfall monitoring charts for a selected cell and year.

    Args:
        cell_lat: Grid cell latitude.
        cell_lon: Grid cell longitude.
        cell_id: Cell identifier string.
        year: Selected year (2001-2023).
    """
    if show_heading:
        st.markdown(f"### Rainfall monitoring · {cell_id} · {year}")
    st.caption(
        f"Selected cell at {cell_lat:.2f}°N, {cell_lon:.2f}°E. "
        "Rainfall values are IMD 0.25° gridded estimates, not direct station measurements."
    )

    tab_daily, tab_monthly, tab_annual, tab_dryspell = st.tabs(
        ["Daily Rainfall", "Monthly Distribution", "Annual JJAS Trend", "Dry Spell Analysis"]
    )

    with tab_daily:
        _render_daily_chart(cell_lat, cell_lon, year)

    with tab_monthly:
        _render_monthly_chart(cell_lat, cell_lon, year)

    with tab_annual:
        _render_jjas_trend(cell_lat, cell_lon)

    with tab_dryspell:
        _render_dryspell_chart(cell_lat, cell_lon, year)


def _render_daily_chart(lat: float, lon: float, year: int) -> None:
    """Render daily rainfall bar chart for JJAS period."""
    daily = get_cell_rainfall_series(lat, lon, year)
    jjas = daily.loc[f"{year}-05-15":f"{year}-10-15"]
    df = jjas.reset_index()
    df.columns = ["date", "rainfall_mm"]
    df["date"] = pd.to_datetime(df["date"])

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["date"], y=df["rainfall_mm"].clip(lower=0),
        marker_color="#0284C7",
        name="Daily Rainfall",
        hovertemplate="%{x|%b %d}: %{y:.1f} mm<extra></extra>",
    ))

    # Annotate wet day threshold
    fig.add_hline(y=2.5, line_dash="dot", line_color="#D97706",
                  annotation_text="Wet day (2.5 mm)", annotation_position="top left")

    fig.update_layout(
        **PLOTLY_LAYOUT,
        title=f"Daily rainfall · 15 May – 15 Oct {year}",
        xaxis_title="Date",
        yaxis_title="Rainfall (mm)",
        height=350,
    )
    render_chart(fig)

    # Summary metrics
    valid = df["rainfall_mm"].dropna()
    wet_days = int((valid >= 2.5).sum())
    total = float(valid.sum())
    max_1d = float(valid.max()) if len(valid) > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total rainfall", format_mm(total, 0))
    c2.metric("Wet days (≥ 2.5 mm)", str(wet_days))
    c3.metric("Wettest day", format_mm(max_1d, 1))
    c4.metric("Missing days", str(int(df["rainfall_mm"].isna().sum())))


def _render_monthly_chart(lat: float, lon: float, year: int) -> None:
    """Render monthly rainfall distribution."""
    monthly = get_monthly_rainfall(lat, lon, year)
    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    monthly["month_name"] = monthly["month"].apply(lambda m: month_labels[m - 1])

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=monthly["month_name"], y=monthly["total_mm"],
        marker_color="#0284C7",
        name="Total Rainfall",
        hovertemplate="%{x}: %{y:.0f} mm<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=monthly["month_name"], y=monthly["wet_days"],
        mode="markers+lines",
        marker=dict(color="#D97706", size=8),
        line=dict(color="#D97706", width=2),
        name="Wet Days",
        yaxis="y2",
        hovertemplate="%{x}: %{y} wet days<extra></extra>",
    ))

    fig.update_layout(
        **PLOTLY_LAYOUT,
        title=f"Monthly rainfall · {year}",
        yaxis_title="Rainfall (mm)",
        yaxis2=dict(title="Wet days", overlaying="y", side="right", gridcolor="rgba(0,0,0,0)"),
        height=350,
    )
    render_chart(fig)


def _render_jjas_trend(lat: float, lon: float) -> None:
    """Render annual JJAS rainfall trend."""
    jjas = get_jjas_rainfall(lat, lon)

    mean_val = jjas["jjas_rainfall_mm"].mean()

    fig = go.Figure()
    colors = ["#0284C7" if v >= mean_val else "#BAE6FD" for v in jjas["jjas_rainfall_mm"]]

    fig.add_trace(go.Bar(
        x=jjas["year"], y=jjas["jjas_rainfall_mm"],
        marker_color=colors,
        hovertemplate="%{x}: %{y:.0f} mm<extra></extra>",
    ))
    fig.add_hline(y=mean_val, line_dash="dash", line_color="#D97706",
                  annotation_text=f"Mean {mean_val:,.0f} mm")

    fig.update_layout(
        **PLOTLY_LAYOUT,
        title="June–September rainfall by year, 2001–2023",
        xaxis_title="Year",
        yaxis_title="June–September rainfall (mm)",
        height=350,
    )
    render_chart(fig)


def _render_dryspell_chart(lat: float, lon: float, year: int) -> None:
    """Render dry-spell duration analysis for June-July."""
    daily = get_cell_rainfall_series(lat, lon, year)
    jj = daily.loc[f"{year}-06-01":f"{year}-07-31"]
    vals = jj.values

    # Calculate consecutive dry spells
    spells = []
    current_spell = 0
    for v in vals:
        if np.isnan(v) or v < 2.5:
            current_spell += 1
        else:
            if current_spell > 0:
                spells.append(current_spell)
            current_spell = 0
    if current_spell > 0:
        spells.append(current_spell)

    if spells:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=list(range(1, len(spells) + 1)),
            y=spells,
            marker_color=["#DC2626" if s >= 7 else "#D97706" if s >= 4 else "#0284C7" for s in spells],
            hovertemplate="Spell %{x}: %{y} dry days<extra></extra>",
        ))
        fig.add_hline(y=7, line_dash="dot", line_color="#DC2626",
                      annotation_text="Desiccation risk, 7 days")

        fig.update_layout(
            **PLOTLY_LAYOUT,
            title=f"Dry spells · June–July {year}",
            xaxis_title="Spell",
            yaxis_title="Duration (days)",
            height=300,
        )
        render_chart(fig)

        c1, c2, c3 = st.columns(3)
        c1.metric("Longest dry spell", f"{max(spells)} days")
        c2.metric("Mean dry spell", f"{np.mean(spells):.1f} days")
        c3.metric("Spells of 7+ days", str(sum(1 for s in spells if s >= 7)))
    else:
        st.info("No distinct dry spells detected in June–July.")
