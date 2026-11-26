"""A tile-free atlas drawn from the project's Maharashtra boundaries and IMD cells."""

from bisect import bisect_left
from datetime import date, timedelta
from math import cos, radians

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from shapely.geometry import shape

from dashboard.services.data_loader import load_daily_rainfall, load_geojson
from dashboard.utils.constants import REGIME_COLORS, REGIME_SHORT_NAMES


RAIN_KEY = {
    "No data": "#a4979e", "0": "#596360", ">0–5": "#38625e",
    ">5–20": "#488e88", ">20–50": "#72bfb5", ">50–100": "#a6ded1",
    ">100": "#e0f7de",
}
MAP_BG = "#222f30"


@st.cache_data(max_entries=16, show_spinner=False)
def rainfall_on(day):
    rainfall = load_daily_rainfall()["rainfall_masked"].sel(time=day)
    return rainfall.transpose("lat", "lon").to_pandas()


def replay_day(control, year):
    first = date(year, 6, 1)
    offset = control.selectbox("Replay day", range(61), index=24,
                               format_func=lambda i: (first + timedelta(days=i)).strftime("%d %b"),
                               key="guide_day")
    return first + timedelta(days=offset)


def atlas_rows(rows, day):
    rows = rows.copy()
    grid = rainfall_on(day.isoformat())
    rows["rain"] = [grid.at[r.latitude, r.longitude] for r in rows.itertuples()]
    rows["amount"] = rows.rain.map(lambda value: "No data" if pd.isna(value) else f"{value:,.1f} mm")
    return rows


@st.cache_data(show_spinner=False)
def boundary_paths(filename):
    paths = []
    for feature in (load_geojson(filename) or {}).get("features", []):
        geometry = shape(feature["geometry"]).simplify(0.012, preserve_topology=True)
        polygons = geometry.geoms if geometry.geom_type == "MultiPolygon" else [geometry]
        for polygon in polygons:
            paths.append("M" + " L".join(f"{x:.3f},{y:.3f}" for x, y in polygon.exterior.coords) + " Z")
    return " ".join(paths)


def rain_color(mm):
    colors = list(RAIN_KEY.values())
    return colors[0] if pd.isna(mm) else colors[1 + bisect_left([0, 5, 20, 50, 100], mm)]


def atlas_figure(rows, selected_id, show_rain):
    fig = go.Figure()
    for filename, edge, fill, weight in (
        ("maharashtra_state.geojson", "#889693", "#32423f", 1.4),
        ("maharashtra_districts.geojson", "#53635d", "rgba(0,0,0,0)", 0.65),
    ):
        path = boundary_paths(filename)
        if path:
            fig.add_shape(type="path", path=path, line=dict(color=edge, width=weight),
                          fillcolor=fill, layer="below")
    colors = rows.rain.map(rain_color) if show_rain else rows.regime.map(REGIME_COLORS)
    fig.add_trace(go.Scatter(
        x=rows.longitude, y=rows.latitude, mode="markers",
        marker=dict(color=list(colors), size=7, symbol="square", line=dict(width=0.5, color=MAP_BG)),
        customdata=rows[["cell_id", "district", "amount", "regime"]].values.tolist(),
        hovertemplate="%{customdata[1]} · %{customdata[0]}<br>Daily rain: %{customdata[2]}<br>%{customdata[3]}<extra></extra>",
        unselected=dict(marker=dict(opacity=1)),
    ))
    selected = rows.loc[selected_id]
    fig.add_trace(go.Scatter(
        x=[selected.longitude], y=[selected.latitude], mode="markers",
        marker=dict(size=15, symbol="square-open", color="#ffdf98", line=dict(width=2)),
        customdata=[[selected_id]], hoverinfo="skip",
    ))
    def label(x, y, name, color, size):
        fig.add_annotation(x=x, y=y, text=name, showarrow=False, captureevents=False,
                           font=dict(size=size, color=color, family="Georgia"),
                           bgcolor=MAP_BG if name != "Arabian Sea" else "rgba(0,0,0,0)")

    label(72.8, 17.1, "Arabian Sea", "#9db0a6", 13)
    for feature in (load_geojson("maharashtra_district_hq.geojson") or {}).get("features", []):
        name = feature["properties"]["DIST_HQ"]
        if name in {"Mumbai", "Nagpur", "Nanded"}:
            x, y = feature["geometry"]["coordinates"][:2]
            label(x, y + 0.16, name, "#c4d0c8", 12)
    axis = dict(showgrid=True, gridcolor="#354241", gridwidth=1, zeroline=False,
                tickfont=dict(color="#9db0a6", size=11), dtick=2, fixedrange=False)
    fig.update_layout(
        height=405, template="none", margin=dict(l=28, r=12, t=12, b=25),
        paper_bgcolor=MAP_BG, plot_bgcolor=MAP_BG, showlegend=False,
        clickmode="event+select", dragmode="pan", hovermode="closest",
        xaxis=dict(**axis, range=[71.4,81.4], ticksuffix="°E", constrain="domain"),
        yaxis=dict(**axis, range=[15.25,22.4], ticksuffix="°N", scaleanchor="x",
                   scaleratio=1 / cos(radians(19)), constrain="domain"),
        hoverlabel=dict(bgcolor="#182522", font_color="#ecf3ef"),
    )
    return fig


def render_atlas(rows, selected_id, day, *, place_key="guide_place", default_layer=0):
    st.html(f'<header class="atlas-title"><small>{len(rows)} grid cells · {day:%d %B %Y}</small>'
            '<h2>Maharashtra rainfall map</h2></header>')
    layer = st.radio("Map layer", ["Daily rainfall", "Onset regimes"], horizontal=True, index=default_layer,
                     key="guide_layer", label_visibility="collapsed")
    show_rain = layer == "Daily rainfall"
    legend = RAIN_KEY if show_rain else {REGIME_SHORT_NAMES[k]: v for k, v in REGIME_COLORS.items()}
    def sync_selection():
        points = st.session_state.guide_map.selection.points
        if points and points[-1].get("customdata"):
            cell = points[-1]["customdata"][0]
            if cell in rows.index:
                st.session_state[place_key] = cell
                st.session_state.selected_cell_id = cell

    st.plotly_chart(atlas_figure(rows, selected_id, show_rain), key="guide_map",
                    theme=None, on_select=sync_selection, selection_mode="points",
                    config={"displaylogo": False, "scrollZoom": False,
                            "modeBarButtonsToRemove": ["toImage", "select2d", "lasso2d"]})
    items = "".join(f'<span><i style="background:{color}"></i>{name}</span>' for name, color in legend.items())
    title = "Daily rainfall (mm)" if show_rain else "Historical onset regime"
    st.html(f'<div class="atlas-key"><b>{title}</b><div>{items}<span><i class="selected-square"></i>Selected cell</span></div></div>')
