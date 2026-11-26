"""Compact, responsive summary metrics for the dashboard overview."""

from __future__ import annotations

from typing import Optional

import streamlit as st

from dashboard.utils.constants import TOTAL_CELLS, TOTAL_YEARS
from dashboard.utils.formatting import doy_to_date_str


def render_metric_cards(
    confirmed_onsets: int,
    selected_cell_onset: Optional[float] = None,
    selected_cell_std: Optional[float] = None,
) -> None:
    """Render existing project metrics without changing their calculations."""
    onset = (
        doy_to_date_str(selected_cell_onset)
        if selected_cell_onset is not None and selected_cell_onset == selected_cell_onset
        else "—"
    )
    variability = (
        f"±{selected_cell_std:.1f} d"
        if selected_cell_std is not None and selected_cell_std == selected_cell_std
        else "—"
    )
    metrics = [
        ("Grid cells", f"{TOTAL_CELLS}", "IMD 0.25° domain"),
        ("Study years", f"{TOTAL_YEARS}", "2001–2023"),
        ("Confirmed onsets", f"{confirmed_onsets:,}", f"of {TOTAL_CELLS * TOTAL_YEARS:,} cell-years"),
        ("Onset regimes", "4", "K-Means · K=4"),
        ("Selected cell onset", onset, "Historical median"),
        ("Onset variability", variability, "Standard deviation"),
    ]
    cards = "".join(
        f'<article class="miq-metric"><div class="miq-metric-label">{label}</div>'
        f'<div class="miq-metric-value">{value}</div>'
        f'<div class="miq-metric-detail">{detail}</div></article>'
        for label, value, detail in metrics
    )
    st.markdown(
        f'<section class="miq-metrics" aria-label="Monsoon study metrics">{cards}</section>',
        unsafe_allow_html=True,
    )
