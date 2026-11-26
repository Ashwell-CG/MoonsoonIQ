"""Shared Plotly styling for consistent dashboard analytics.

A registered ``miq`` template carries axis, grid, legend and title defaults so
every chart looks the same while callers remain free to override per-axis
settings (template values merge; they do not clash with explicit kwargs).
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

FONT_FAMILY = "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"

# Chart palette (kept in step with the dashboard CSS tokens).
CHART_PRIMARY = "#0284C7"
CHART_PRIMARY_SOFT = "#7DD3FC"
CHART_MUTED = "#94A3B8"
CHART_WARNING = "#D97706"
CHART_DANGER = "#DC2626"

_AXIS = dict(
    gridcolor="#EEF2F7",
    linecolor="#E2E8F0",
    zerolinecolor="#E2E8F0",
    tickfont=dict(size=11, color="#64748B"),
    title=dict(font=dict(size=11.5, color="#475569")),
    ticks="outside",
    automargin=True,
    tickcolor="#E2E8F0",
)

pio.templates["miq"] = go.layout.Template(
    layout=dict(
        font=dict(family=FONT_FAMILY, color="#334155", size=11),
        title=dict(font=dict(size=14, color="#0F172A", family=FONT_FAMILY), x=0.01, xanchor="left"),
        colorway=[CHART_PRIMARY, CHART_WARNING, "#16A34A", "#7C3AED", CHART_DANGER],
        xaxis=_AXIS,
        yaxis=_AXIS,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(255,255,255,0)",
            font=dict(size=11, color="#475569"),
        ),
        margin=dict(l=56, r=28, t=56, b=60),
        hoverlabel=dict(
            bgcolor="#0F172A",
            bordercolor="#0F172A",
            font=dict(color="#FFFFFF", size=12, family=FONT_FAMILY),
        ),
    )
)

PLOTLY_LAYOUT = {
    "template": "plotly_white+miq",
    "paper_bgcolor": "rgba(255, 255, 255, 0)",
    "plot_bgcolor": "rgba(255, 255, 255, 0)",
    "font": {"family": FONT_FAMILY, "color": "#334155", "size": 11},
}


def render_chart(fig):
    import streamlit as st
    from dashboard.utils.constants import FIELD_GUIDE_ANALYSIS_PAGES

    if st.session_state.get("dashboard_section") not in FIELD_GUIDE_ANALYSIS_PAGES:
        st.plotly_chart(fig, use_container_width=True)
        return
    fig.update_layout(template="plotly_dark", paper_bgcolor="#28322e", plot_bgcolor="#28322e",
                      font=dict(family=FONT_FAMILY, color="#c4d0c8", size=12),
                      title_font=dict(family=FONT_FAMILY, size=14, color="#edf1ec"),
                      margin=dict(l=48, r=24, t=56, b=48), legend=dict(orientation="h", y=-0.25),
                      hoverlabel=dict(bgcolor="#1a221f", bordercolor="#1a221f", font_color="#edf1ec"))
    axis = dict(gridcolor="rgba(237,241,236,0.08)", linecolor="rgba(237,241,236,0.18)",
                zerolinecolor="rgba(237,241,236,0.18)", tickfont=dict(color="#9db0a6", size=11),
                title_font=dict(color="#9db0a6", size=12), automargin=True)
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    fig.update_annotations(font_color="#c4d0c8")
    # Light-theme chart colours mapped to the field-guide palette (display only).
    dark = {CHART_PRIMARY: "#86c9c2", "#BAE6FD": "#4d6a64", CHART_WARNING: "#d9a54a",
            CHART_DANGER: "#e0705f", "#DC2626": "#e0705f", "#D97706": "#d9a54a"}
    for trace in fig.data:
        marker = getattr(trace, "marker", None)
        if marker is not None and isinstance(marker.color, str):
            marker.color = dark.get(marker.color, marker.color)
        elif marker is not None and marker.color is not None and not isinstance(marker.color, str):
            marker.color = [dark.get(c, c) for c in marker.color]
        line = getattr(trace, "line", None)
        if line is not None and isinstance(line.color, str):
            line.color = dark.get(line.color, line.color)
    for shape in fig.layout.shapes:
        if isinstance(shape.line.color, str):
            shape.line.color = dark.get(shape.line.color, shape.line.color)
    st.plotly_chart(fig, theme=None, use_container_width=True)
