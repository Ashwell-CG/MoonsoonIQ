"""Historical replay overview for one place and one day."""

from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from dashboard.components.advisory_panel import _get_engine
from dashboard.components.provenance import PROVENANCE_SOURCES, render_data_integrity_notice
from dashboard.components.rainfall_atlas import atlas_rows, render_atlas, replay_day
from dashboard.services.dashboard_service import get_cell_advisory_data
from dashboard.services.data_loader import load_onset_dataset
from dashboard.utils.constants import ADVISORY_STATE_COLORS, STUDY_YEAR_END, STUDY_YEAR_START
from dashboard.utils.formatting import doy_to_date_str, format_cell_dropdown_label, format_mm


def render_record(row, day):
    district = str(row.district)
    place = district if pd.notna(row.district) and district != "Unknown" else row.cell_id
    st.html(f'<header class="guide-record"><small>Selected grid cell</small><h2>{escape(place)}</h2>'
            f'<div>{row.cell_id} &nbsp;·&nbsp; {row.latitude:.2f}°N, {row.longitude:.2f}°E</div></header>')
    iso = day.isoformat()
    observations = [(d, r) for d, r in get_cell_advisory_data(row.cell_id, day.year) if d <= iso]
    report = None
    if observations:
        report = _get_engine().generate_advisory(
            row.cell_id, observations, as_of_date=iso,
            data_provenance="Historical Replay (IMD 0.25° Gridded 2001-2023)",
        )
    status = report.advisory_state.value.capitalize() if report else "No observations available"
    color = ADVISORY_STATE_COLORS.get(report.advisory_state.value, "#9db0a6") if report else "#9db0a6"
    st.html(f'<section class="guide-advice" style="--state:{color}"><small>Sowing advisory · {day:%d %b %Y}</small>'
            f'<strong>{escape(status)}</strong>'
            '<p>Rainfall thresholds are experimental proxies for topsoil wetting and cannot guarantee crop establishment. Use local KVK and SAU guidance.</p></section>')
    if report:
        with st.expander("Reasoning and conditions"):
            metrics = report.current_metrics
            st.html(
                '<dl class="guide-values" aria-label="Advisory rainfall totals">'
                f'<div><dt>Cumulative rainfall · since 1 Jun</dt><dd>{format_mm(metrics.cumulative_rainfall_mm)}</dd></div>'
                f'<div><dt>Active-cycle rain · current wetting cycle</dt><dd>{format_mm(metrics.effective_cumulative_rainfall_mm)}</dd></div>'
                '</dl>'
            )
            for reason in report.state_reasoning:
                st.write(reason)
            st.html('<ul class="miq-conditions">' + "".join(
                f'<li class="{"passed" if c.passed else "unmet"}"><div class="head">{escape(c.condition_name)}'
                f'<span class="verdict">{"Passed" if c.passed else "Unmet"}</span></div>'
                f'<p>{escape(str(c.actual_value))}</p><p class="src">{escape(str(c.source_citation))}</p></li>'
                for c in report.condition_evaluations) + '</ul>')
            for recommendation in report.contingency_recommendations or []:
                st.write(recommendation)

    onset = load_onset_dataset().confirmed_onset_doy.sel(year=day.year, lat=row.latitude, lon=row.longitude).item()
    onset_label = doy_to_date_str(onset, day.year) if pd.notna(onset) else "No confirmed onset"
    st.html(f'<dl class="guide-values"><div><dt>Daily rainfall · {day:%d %b}</dt><dd>{row.amount}</dd></div>'
            f'<div><dt>{day.year} onset · retrospective</dt><dd>{onset_label}</dd></div>'
            f'<div><dt>Historical median onset</dt><dd>{row.median_onset_date}</dd></div>'
            f'<div><dt>Onset variability</dt><dd>±{row.std_onset_doy:.1f} days</dd></div>'
            f'<div><dt>Regime</dt><dd>{escape(row.regime)}</dd></div></dl>')


def render_field_guide(selector, total_confirmed):
    st.html(Path(__file__).with_name("field_guide.css"))
    st.html('<header class="guide-title"><div>MonsoonIQ &nbsp;/&nbsp; Historical replay</div>'
            '<h1>Maharashtra monsoon field guide</h1>'
            '<p>IMD 0.25° gridded rainfall &nbsp;·&nbsp; 2001–2023</p></header>')
    with st.container(key="guide_controls"):
        place, season, replay, filters = st.columns([2.3, 1, 1, .8], vertical_alignment="bottom")
        with filters.popover("Filters"):
            district = st.selectbox("District", ["All", *sorted(selector.district.dropna().unique())])
            regime = st.selectbox("Onset regime", ["All", *sorted(selector.regime.dropna().unique())])
    rows = selector.set_index("cell_id", drop=False)
    if district != "All":
        rows = rows.loc[rows.district == district]
    if regime != "All":
        rows = rows.loc[rows.regime == regime]
    if rows.empty:
        st.info("No grid cells match this district and regime. Change either filter.")
        return
    rows = rows.copy()
    labels = {r.cell_id: format_cell_dropdown_label(r.cell_id, r.district, r.latitude, r.longitude)
              for r in rows.itertuples()}
    current = st.session_state.selected_cell_id
    if st.session_state.get("guide_place") not in labels:
        st.session_state.guide_place = current if current in labels else rows.index[0]
    selected = place.selectbox("Place or grid cell", options=list(labels), format_func=labels.get, key="guide_place")
    years = list(range(STUDY_YEAR_END, STUDY_YEAR_START - 1, -1))
    year = season.selectbox("Study year", years, index=years.index(st.session_state.selected_year), key="guide_year")
    day = replay_day(replay, year)
    st.session_state.selected_cell_id = selected
    st.session_state.selected_year = year
    rows = atlas_rows(rows, day)
    with st.container(key="guide_spread"):
        record, atlas = st.columns([1, 1.9], gap="medium")
        with record, st.container(key="guide_record"):
            render_record(rows.loc[selected], day)
        with atlas, st.container(key="guide_atlas"):
            render_atlas(rows, selected, day)
    with st.expander("Data sources and availability"):
        st.write(f"{len(selector)} grid cells · {len(years)} study years · {selector.regime.nunique()} onset regimes · "
                 f"{total_confirmed:,} confirmed onsets across {len(selector) * len(years):,} cell-years.")
        for key, source in PROVENANCE_SOURCES.items():
            suffix = " · disconnected from dashboard" if key == "simulated_test" else ""
            st.write(f"{source['title']} · {source['status'].capitalize()}{suffix}")
    render_data_integrity_notice()
