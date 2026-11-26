"""Data lineage and scientific integrity components."""

from __future__ import annotations

from html import escape
from typing import Optional

import streamlit as st

PROVENANCE_SOURCES = {
    "historical_replay": {
        "title": "Historical replay · IMD 0.25° gridded rainfall, 2001–2023",
        "description": "Validated historical daily rainfall baseline.",
        "status": "ACTIVE",
    },
    "simulated_test": {
        "title": "Simulated test data · scenario testing",
        "description": "Controlled sequences used only to verify edge cases and state transitions.",
        "status": "EXPERIMENTAL",
    },
    "observed_aws": {
        "title": "Observed weather station · AWS Mahavedh",
        "description": "Real-time station network integration is planned and is not currently connected.",
        "status": "NOT CONNECTED",
    },
    "nwp_forecast": {
        "title": "NWP forecast model · IMD GFS / NCUM",
        "description": "Numerical weather prediction integration is planned and is not currently connected.",
        "status": "NOT CONNECTED",
    },
}


def render_provenance_banner(
    source_key: str = "historical_replay",
    custom_note: Optional[str] = None,
) -> None:
    """Render the active data source and its context."""
    info = PROVENANCE_SOURCES.get(source_key, PROVENANCE_SOURCES["historical_replay"])
    note = custom_note or info["description"]
    st.markdown(
        f"""
        <div class="miq-provenance" role="note" data-status="{escape(info['status'])}">
            <div>
                <div class="miq-provenance-title">{escape(info['title'])}</div>
                <div class="miq-provenance-note">{escape(note)}</div>
            </div>
            <span class="miq-status">{escape(info['status'])}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_data_modes(active_key: str = "historical_replay") -> None:
    """List every supported data mode and which one is in use, so nothing reads as live."""
    items = "".join(
        f'<li class="{"on" if k == active_key else ""}"><span class="dot"></span>'
        f'{escape(v["title"].split(" · ")[0])}<small>{"In use" if k == active_key else escape(v["status"].capitalize())}</small></li>'
        for k, v in PROVENANCE_SOURCES.items()
    )
    st.markdown(f'<ul class="miq-modes" aria-label="Data modes">{items}</ul>', unsafe_allow_html=True)


def render_data_integrity_notice() -> None:
    """Explain the key boundaries of the research products."""
    with st.expander("Data integrity and spatial resolution"):
        st.markdown("""
        - **Spatial nature:** Rainfall values are spatial averages over 0.25° × 0.25° (~27 km × 27 km) grid boxes produced by IMD's gridded rainfall interpolation. They do not represent point measurements from single village rain gauges.
        - **Missing value semantics:** Missing observations are strictly preserved as `NaN` and are never imputed as zero.
        - **Detection method:** Onset represents rainfall-based local sustained monsoon onset (5-day accumulation + 20-day verification), which differs from synoptic regional IMD declarations.
        - **Advisory status:** Sowing indicators are research prototypes. Topsoil moisture thresholds are necessary physical proxies but cannot guarantee germination or crop establishment.
        """)
