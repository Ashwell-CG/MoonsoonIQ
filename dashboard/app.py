"""MonsoonIQ – Hyperlocal Monsoon Onset & Agricultural Advisory Dashboard.

Main Streamlit Application.
Integrates historical IMD 0.25° daily rainfall datasets (2001–2023), unsupervised
onset clustering results, and the regime-aware sowing advisory engine.
"""

from __future__ import annotations

import sys
from html import escape
from pathlib import Path
from typing import Optional

# Ensure project root is in sys.path
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import streamlit as st

# Configure page layout and visual metadata
st.set_page_config(
    page_title="MonsoonIQ – Maharashtra Monsoon Intelligence",
    page_icon=":material/rainy:",
    layout="wide",
    initial_sidebar_state="auto",
)

from dashboard.components.advisory_panel import render_advisory_panel
from dashboard.components.header import render_header
from dashboard.components.field_guide import render_field_guide
from dashboard.components.rainfall_atlas import atlas_rows, render_atlas, replay_day
from dashboard.components.metric_cards import render_metric_cards
from dashboard.components.onset_analysis import render_onset_analysis
from dashboard.components.provenance import (
    render_data_integrity_notice,
    render_provenance_banner,
)
from dashboard.components.rainfall_charts import render_rainfall_charts
from dashboard.components.regime_analysis import render_regime_analysis
from dashboard.services.dashboard_service import (
    build_cell_selector_df,
    get_confirmed_onset_counts,
)
from dashboard.services.data_loader import load_baselines
from dashboard.utils.constants import (
    ALL_SECTIONS,
    FIELD_GUIDE_ANALYSIS_PAGES,
    DEFAULT_YEAR,
    STUDY_YEAR_END,
    STUDY_YEAR_START,
)
from dashboard.utils.formatting import doy_to_date_str, format_cell_dropdown_label
from dashboard.utils.theme import apply_theme

def init_session_state() -> None:
    """Initialize persistent session state variables."""
    if "selected_cell_id" not in st.session_state:
        st.session_state["selected_cell_id"] = "cell_001"
    if "selected_year" not in st.session_state:
        st.session_state["selected_year"] = DEFAULT_YEAR


def main() -> None:
    """Main application loop."""
    init_session_state()

    # Load baseline metadata for selectors
    df_baselines = load_baselines()
    df_selector = build_cell_selector_df()
    total_confirmed = get_confirmed_onset_counts()

    # -----------------------------------------------------------------------
    # Sidebar Filters and Controls
    # -----------------------------------------------------------------------
    with st.sidebar:
        st.markdown(
            """
            <div class="miq-brand">
                <div class="miq-brand-mark">MonsoonIQ</div>
                <div class="miq-brand-subtitle">Maharashtra field guide</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### Explore")
        nav_options = [
            "Overview & Map",
            "Rainfall Monitoring",
            "Monsoon Onset Analysis",
            "Regime Analysis",
            "Agricultural Advisory",
            ALL_SECTIONS,
        ]
        default_nav_idx = 0
        if "section" in st.query_params:
            sec_param = st.query_params.get("section")
            if sec_param in nav_options:
                default_nav_idx = nav_options.index(sec_param)

        nav_section = st.radio(
            "Select Section",
            nav_options,
            index=default_nav_idx,
            label_visibility="collapsed",
            key="dashboard_section",
            format_func=lambda s: {"Overview & Map": "Overview and map", ALL_SECTIONS: "All sections"}.get(s, s.capitalize()),
        )
        if nav_section != nav_options[default_nav_idx]:
            st.query_params["section"] = nav_section

    if nav_section == "Overview & Map":
        render_field_guide(df_selector, total_confirmed)
        return

    comprehensive = nav_section == ALL_SECTIONS
    guide_analysis = nav_section in FIELD_GUIDE_ANALYSIS_PAGES
    if guide_analysis:
        styles = PROJECT_ROOT / "dashboard" / "components"
        st.html(styles / "field_guide.css")
        st.html(styles / "all_sections.css")
    else:
        apply_theme()
    with st.sidebar:
        st.markdown("---")
        st.markdown("### Filters")

        # Year selector
        years = list(range(STUDY_YEAR_START, STUDY_YEAR_END + 1))
        selected_year = st.selectbox(
            "Study year",
            years,
            index=years.index(st.session_state["selected_year"]),
            help="Select year for historical daily rainfall replay (2001–2023).",
        )
        st.session_state["selected_year"] = selected_year
        if comprehensive:
            map_day = replay_day(st.sidebar, selected_year)

        # Regime filter
        regimes = ["All"] + sorted(df_baselines["regime_kmeans"].unique().tolist())
        selected_regime = st.selectbox("Onset regime", regimes, index=0)

        # District filter
        districts = ["All"] + sorted(
            [d for d in df_baselines["district"].dropna().unique().tolist() if d != "Unknown"]
        )
        selected_district = st.selectbox("District", districts, index=0)

        # Filtered cell selection options
        filtered_df = df_selector.copy()
        if selected_regime != "All":
            filtered_df = filtered_df[filtered_df["regime"] == selected_regime]
        if selected_district != "All":
            filtered_df = filtered_df[filtered_df["district"] == selected_district]

        cell_options = filtered_df["cell_id"].tolist()
        if not cell_options:
            st.warning("No cells match current filter criteria.")
            if comprehensive:
                st.info("Change the district or regime filter to display matching cells.")
                return
            cell_options = df_selector["cell_id"].tolist()

        current_cell = st.session_state["selected_cell_id"]
        default_idx = cell_options.index(current_cell) if current_cell in cell_options else 0

        # Full label is 'District · cell_XXX · lat°N, lon°E'; the sidebar is too
        # narrow for one line, so the select shows 'District · cell_XXX' and the
        # coordinates sit on their own line below it.
        def format_cell_label(c_id: str) -> str:
            row = df_selector[df_selector["cell_id"] == c_id].iloc[0]
            return format_cell_dropdown_label(
                c_id,
                row.get("district", ""),
                row["latitude"],
                row["longitude"],
            )

        selected_cell = st.selectbox(
            "Grid cell",
            cell_options,
            index=default_idx,
            format_func=lambda c_id: format_cell_label(c_id).rsplit(" · ", 1)[0],
            key="all_place" if comprehensive else None,
            help="Select a 0.25° x 0.25° grid cell for detailed hyperlocal analysis.",
        )
        st.html(f'<div class="miq-cell-coords">{escape(format_cell_label(selected_cell).rsplit(" · ", 1)[-1])}</div>')
        st.session_state["selected_cell_id"] = selected_cell

        st.markdown("---")
        # Sidebar Provenance & Attribution
        st.markdown(
            """
            <div class="miq-sidebar-footnote">
                IMD 0.25° gridded rainfall<br>
                419 cells · 2001–2023
            </div>
            """,
            unsafe_allow_html=True,
        )

    # -----------------------------------------------------------------------
    # Main Page Rendering
    # -----------------------------------------------------------------------
    # 2. Selected Cell Metadata Retrieval
    cell_info = df_baselines[df_baselines["cell_id"] == selected_cell].iloc[0]
    cell_lat = float(cell_info["latitude"])
    cell_lon = float(cell_info["longitude"])
    cell_onset = float(cell_info["median_onset_doy"])
    cell_std = float(cell_info["std_onset_doy"])

    # 3. Provenance Banner
    if guide_analysis:
        section_label = "All sections" if comprehensive else "Maharashtra field guide"
        title = "Maharashtra monsoon field guide" if comprehensive else nav_section.capitalize()
        period = "Onset history 2001–2023" if nav_section == "Monsoon Onset Analysis" else f"Study year {selected_year}"
        context = (f"{len(df_baselines)} grid cells across Maharashtra"
                   if nav_section == "Regime Analysis"
                   else f"{escape(str(cell_info['district']))} · {selected_cell} · {period}")
        st.html(
            f'<header class="guide-title all-guide"><div>MonsoonIQ &nbsp;/&nbsp; {section_label}</div>'
            f'<h1>{title}</h1>'
            '<p>Historical replay · IMD 0.25° gridded rainfall · 2001–2023</p>'
            f'<div class="all-place">{context}</div></header>'
        )
    else:
        render_header()
        render_provenance_banner(
            source_key="historical_replay",
            custom_note=f"Evaluation active for Study Year {selected_year} · Selected Cell: {selected_cell} ({cell_info['district']})",
        )

    if nav_section in ("Rainfall Monitoring", ALL_SECTIONS):
        render_rainfall_charts(cell_lat=cell_lat, cell_lon=cell_lon, cell_id=selected_cell,
                               year=selected_year, show_heading=comprehensive)

    if comprehensive:
        render_metric_cards(
            confirmed_onsets=total_confirmed,
            selected_cell_onset=cell_onset,
            selected_cell_std=cell_std,
        )

    # -----------------------------------------------------------------------
    # Section Routing
    # -----------------------------------------------------------------------
    if comprehensive:
        with st.container(key="guide_atlas"):
            rows = atlas_rows(filtered_df.set_index("cell_id", drop=False), map_day)
            render_atlas(rows, selected_cell, map_day, place_key="all_place", default_layer=1)

        # Display Selected Cell Details Card
        st.markdown(
            f"""
            <div class="miq-selected-cell">
                <div class="miq-selected-title">Selected cell · {selected_cell}</div>
                <div class="miq-selected-detail">
                    {cell_info['district']} · {cell_lat:.2f}°N, {cell_lon:.2f}°E
                    · {cell_info['regime_kmeans']}
                    · median onset {doy_to_date_str(cell_onset)}
                    · variability ±{cell_std:.1f} days
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        render_data_integrity_notice()

    if nav_section in ("Monsoon Onset Analysis", ALL_SECTIONS):
        if comprehensive:
            st.markdown("---")
        render_onset_analysis(
            show_heading=comprehensive,
            cell_lat=cell_lat,
            cell_lon=cell_lon,
            cell_id=selected_cell,
        )

    if nav_section in ("Regime Analysis", ALL_SECTIONS):
        if comprehensive:
            st.markdown("---")
        render_regime_analysis(show_heading=comprehensive)

    if nav_section in ("Agricultural Advisory", ALL_SECTIONS):
        if comprehensive:
            st.markdown("---")
        render_advisory_panel(
            show_heading=comprehensive,
            cell_id=selected_cell,
            year=selected_year,
        )

    # -----------------------------------------------------------------------
    # Footer
    # -----------------------------------------------------------------------
    st.markdown(
        """
        <footer class="miq-footer">
            <p>MonsoonIQ · IMD 0.25° gridded rainfall, 2001–2023 · historical replay for research, not a forecast</p>
            <p>Rainfall thresholds are topsoil-moisture proxies, not guarantees of germination or yield</p>
        </footer>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
