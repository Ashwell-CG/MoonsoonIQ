"""MonsoonIQ Dashboard – Interactive Maharashtra Map Component.

Renders a Folium map with 419 grid cells colored by onset regime,
with hover tooltips and click selection.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import folium
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from dashboard.services.data_loader import load_baselines, load_geojson
from dashboard.utils.constants import (
    DEFAULT_ZOOM,
    MAHARASHTRA_CENTER_LAT,
    MAHARASHTRA_CENTER_LON,
    REGIME_COLORS,
    REGIME_SHORT_NAMES,
)
from dashboard.utils.formatting import doy_to_date_str


def render_maharashtra_map(
    regime_filter: Optional[str] = None,
    district_filter: Optional[str] = None,
    selected_cell_id: Optional[str] = None,
) -> Optional[str]:
    """Render the interactive Maharashtra regime map and return the selected cell_id.

    Args:
        regime_filter: Optional regime name to highlight.
        district_filter: Optional district name to filter.

    Returns:
        Selected cell_id string, or None.
    """
    df = load_baselines()

    # Apply filters
    if regime_filter and regime_filter != "All":
        df = df[df["regime_kmeans"] == regime_filter]
    if district_filter and district_filter != "All":
        df = df[df["district"] == district_filter]

    # Create base map using free, reliable OpenStreetMap with soft meteorological cartography styling
    m = folium.Map(
        location=[MAHARASHTRA_CENTER_LAT, MAHARASHTRA_CENTER_LON],
        zoom_start=DEFAULT_ZOOM,
        tiles="OpenStreetMap",
        control_scale=True,
        prefer_canvas=True,
        min_zoom=4,
        max_zoom=10,
    )

    # Clean, modern map container styling matching the Pinterest weather intelligence layout
    m.get_root().header.add_child(folium.Element("""
        <style>
          .leaflet-container {
            background: #293430 !important;
            font-family: Inter, ui-sans-serif, system-ui, sans-serif !important;
          }
          .leaflet-tile-pane {
            filter: invert(92%) hue-rotate(145deg) saturate(.38) brightness(.8);
          }
          .leaflet-control-scale-line {
            background: rgba(255, 255, 255, 0.92) !important;
            border-color: #CBD5E1 !important;
            color: #475569 !important;
            text-shadow: none !important;
            border-radius: 4px !important;
            font-size: 10px !important;
          }
          .leaflet-control-zoom a {
            background: #FFFFFF !important;
            color: #1E293B !important;
            border-color: #E2E8F0 !important;
            box-shadow: 0 1px 4px rgba(15, 23, 42, 0.08) !important;
          }
          .leaflet-control-zoom a:hover {
            background: #F1F5F9 !important;
            color: #0284C7 !important;
          }
          .leaflet-control-attribution {
            background: rgba(255, 255, 255, 0.85) !important;
            color: #94A3B8 !important;
            font-size: 10px !important;
          }
          .leaflet-control-attribution a { color: #0284C7 !important; }
          @media (max-width: 520px) {
            .miq-legend { bottom: 6px !important; left: 6px !important; min-width: 0 !important;
                          padding: 6px 9px !important; border-radius: 10px !important; }
            .miq-legend ul { display: grid; grid-template-columns: 1fr 1fr; column-gap: 10px; padding-top: 2px !important; }
            .miq-legend li { margin: 2px 0 !important; }
            .miq-legend li span:nth-child(2) { font-size: 9.5px !important; white-space: nowrap; }
            .leaflet-control-scale { display: none; }
          }
        </style>
    """))

    # Add Maharashtra state boundary
    state_geojson = load_geojson("maharashtra_state.geojson")
    if state_geojson:
        folium.GeoJson(
            state_geojson,
            style_function=lambda x: {
                "fillColor": "#E0F2FE",
                "color": "#0284C7",
                "weight": 2.0,
                "fillOpacity": 0.05,
            },
            name="Maharashtra Boundary",
        ).add_to(m)

    # Add district boundaries
    district_geojson = load_geojson("maharashtra_districts.geojson")
    if district_geojson:
        folium.GeoJson(
            district_geojson,
            style_function=lambda x: {
                "fillColor": "transparent",
                "color": "#94A3B8",
                "weight": 0.75,
                "fillOpacity": 0,
            },
            name="District Boundaries",
        ).add_to(m)

    # Add grid cell markers
    for _, row in df.iterrows():
        regime = row["regime_kmeans"]
        color = REGIME_COLORS.get(regime, "#9E9E9E")
        onset_date = doy_to_date_str(row["median_onset_doy"])

        tooltip_html = (
            "<div style=\"font:12px/1.5 Inter,system-ui,sans-serif;color:#0F172A;min-width:210px;\">"
            f"<span style='display:inline-block;width:9px;height:9px;border-radius:50%;background:{color};margin-right:6px;'></span>"
            f"<b>{row['cell_id']}</b> ({row['latitude']:.2f}°N, {row['longitude']:.2f}°E)<br>"
            f"<b>District:</b> {row['district']}<br>"
            f"<b>Regime:</b> {REGIME_SHORT_NAMES.get(regime, regime)}<br>"
            f"<b>Median Onset:</b> {onset_date} (DOY {row['median_onset_doy']:.0f})<br>"
            f"<b>Onset σ:</b> {row['std_onset_doy']:.1f} days<br>"
            f"<b>June Rain:</b> {row['june_mean_rainfall_mm']:.0f} mm<br>"
            f"<b>Dry Spell (mean):</b> {row['early_dry_spell_mean_days']:.1f} d<br>"
            f"<i style='color:#64748B; font-size:0.8em;'>⚠ IMD 0.25° gridded estimate, not station observation</i></div>"
        )

        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=5.5,
            color="#FFFFFF",
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            weight=1.2,
            tooltip=folium.Tooltip(tooltip_html, sticky=True),
            popup=folium.Popup(f"<b>{row['cell_id']}</b><br>{row['district']}", max_width=200),
        ).add_to(m)

    # Highlight the currently selected cell with a non-interactive ring
    # (no popup/tooltip, so it never alters click selection).
    if selected_cell_id:
        sel = df[df["cell_id"] == selected_cell_id]
        if not sel.empty:
            folium.CircleMarker(
                location=[float(sel.iloc[0]["latitude"]), float(sel.iloc[0]["longitude"])],
                radius=11,
                color="#ffdf98",
                weight=2.5,
                fill=True,
                fill_color="#FFFFFF",
                fill_opacity=0.0,
                interactive=False,
            ).add_to(m)

    # Fit the viewport to the cells currently displayed, so Maharashtra stays
    # centered on both wide desktop maps and narrow embedded map panels.
    if not df.empty:
        padding = 0.35
        bounds = [
            [float(df["latitude"].min()) - padding, float(df["longitude"].min()) - padding],
            [float(df["latitude"].max()) + padding, float(df["longitude"].max()) + padding],
        ]
        m.fit_bounds(bounds, padding=(26, 26))
        # The iframe can mount before it has its final size, leaving the map
        # over-zoomed-out; re-fit once the container is laid out and on resize.
        m.get_root().script.add_child(folium.Element(
            f"""
            (function () {{
              var b = {json.dumps(bounds)};
              function refit() {{
                var mp = window["{m.get_name()}"];
                if (mp) {{ mp.invalidateSize(); mp.fitBounds(b, {{padding: [26, 26]}}); }}
              }}
              window.addEventListener("load", function () {{ [100, 400, 1000].forEach(function (t) {{ setTimeout(refit, t); }}); }});
              window.addEventListener("resize", refit);
              if (window.ResizeObserver) {{ new ResizeObserver(refit).observe(document.body); }}
            }})();
            """
        ))

    # Add legend
    legend_html = _build_legend_html(df)
    m.get_root().html.add_child(folium.Element(legend_html))

    # Render map
    map_data = st_folium(
        m,
        width=None,
        height=520,
        returned_objects=["last_object_clicked_popup"],
    )

    # Extract selected cell
    selected_cell = None
    if map_data and map_data.get("last_object_clicked_popup"):
        popup_text = map_data["last_object_clicked_popup"]
        if popup_text and "cell_" in str(popup_text):
            # Extract cell_id from popup HTML
            import re
            match = re.search(r"(cell_\d+)", str(popup_text))
            if match:
                selected_cell = match.group(1)

    return selected_cell


def _build_legend_html(df: pd.DataFrame) -> str:
    """Build HTML for the floating map legend.

    Returns:
        HTML string for Folium Element.
    """
    counts = df["regime_kmeans"].value_counts().to_dict()
    items = ""
    for regime, color in REGIME_COLORS.items():
        short = REGIME_SHORT_NAMES.get(regime, regime)
        count = int(counts.get(regime, 0))
        items += (
            '<li style="display:flex;align-items:center;gap:8px;margin:5px 0;">'
            f'<span style="background:{color};width:9px;height:9px;flex:none;'
            f'border-radius:50%;box-shadow:0 0 0 2px {color}33;"></span>'
            f'<span style="flex:1;color:#334155;font-size:11px;font-weight:550;">{short}</span>'
            f'<strong style="color:#0F172A;font-size:11px;font-weight:700;">{count}</strong></li>'
        )

    return f"""
    <div class="miq-legend" style="position:fixed;bottom:22px;left:22px;z-index:1000;
                background:rgba(255,255,255,0.96);padding:12px 16px;border-radius:14px;
                border:1px solid #E2E8F0;font:12px Inter,system-ui,sans-serif;
                color:#475569;min-width:215px;box-shadow:0 8px 24px rgba(15,23,42,0.08);backdrop-filter:blur(6px);">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:18px;">
          <b style="color:#0F172A;font-size:12px;font-weight:750;">Onset regimes</b>
          <span style="color:#0284C7;font-size:10px;font-weight:750;background:#E0F2FE;padding:2px 7px;border-radius:9999px;">{len(df)} CELLS</span>
        </div>
        <ul style="list-style:none;padding:6px 0 0;margin:0;">
            {items}
        </ul>
    </div>
    """
