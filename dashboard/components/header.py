"""Premium product header for the MonsoonIQ dashboard."""

from __future__ import annotations

import streamlit as st

from dashboard.utils.constants import DATA_RESOLUTION, TOTAL_CELLS, TOTAL_YEARS


def render_header() -> None:
    """Render the hero header (decorative sky layers are CSS-only) and study context."""
    st.markdown(
        f"""
        <header class="miq-header">
            <div class="miq-sky" aria-hidden="true">
                <span class="miq-rain"></span>
                <span class="miq-cloud c1"></span>
                <span class="miq-cloud c2"></span>
            </div>
            <div>
                <div class="miq-eyebrow">Maharashtra · Research intelligence</div>
                <div class="miq-title">MonsoonIQ</div>
                <p class="miq-subtitle">Hyperlocal monsoon onset dynamics and regime-aware agricultural advisory intelligence.</p>
            </div>
            <div class="miq-context" aria-label="Study context">
                <span class="miq-context-item"><strong>2001–2023</strong> · study period</span>
                <span class="miq-context-item"><strong>{DATA_RESOLUTION}</strong></span>
                <span class="miq-context-item"><strong>{TOTAL_CELLS}</strong> grid cells</span>
                <span class="miq-context-item"><strong>{TOTAL_YEARS}</strong> seasons</span>
            </div>
        </header>
        """,
        unsafe_allow_html=True,
    )
