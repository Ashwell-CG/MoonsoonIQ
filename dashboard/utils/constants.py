"""MonsoonIQ Dashboard – Constants and color palette.

Defines regime colors, map settings, and display constants.
"""

from __future__ import annotations

from typing import Dict

# ── Regime Color Palette ─────────────────────────────────────────────────────
# Regime palette: four clearly separable hues on a light basemap.
REGIME_COLORS: Dict[str, str] = {
    "Core Interior Synchronized": "#7fa8c9",        # basalt slate blue
    "Rain-Shadow High-Volatility": "#d0875c",       # laterite
    "Early Maritime & Western Ghats": "#5fae94",    # Ghats forest
    "Interior Semi-Arid Transition": "#c8b26a",     # ochre
}

REGIME_SHORT_NAMES: Dict[str, str] = {
    "Core Interior Synchronized": "Core Interior",
    "Rain-Shadow High-Volatility": "Rain-Shadow",
    "Early Maritime & Western Ghats": "Maritime & Ghats",
    "Interior Semi-Arid Transition": "Semi-Arid Transition",
}

# Advisory state colors
ADVISORY_STATE_COLORS: Dict[str, str] = {
    "RAINFALL CRITERIA MET": "#6cc08f",
    "CAUTION": "#d9a54a",
    "HIGH RISK": "#e0705f",
    "INSUFFICIENT DATA": "#9db0a6",
    "MONITORING": "#86c9c2",
}

# ── Map Settings ─────────────────────────────────────────────────────────────
MAHARASHTRA_CENTER_LAT: float = 19.0
MAHARASHTRA_CENTER_LON: float = 76.0
DEFAULT_ZOOM: int = 7

# ── Data Paths (relative to project root) ────────────────────────────────────
DAILY_RAINFALL_NC: str = "data/processed/maharashtra_imd_daily_2001_2023.nc"
ONSET_NC: str = "data/processed/maharashtra_onset_2001_2023.nc"
BASELINES_CSV: str = "data/processed/advisory_historical_baselines.csv"
CLUSTERS_CSV: str = "data/processed/monsoon_onset_clusters.csv"
FEATURES_CSV: str = "data/processed/monsoon_onset_features.csv"
STATE_GEOJSON: str = "data/geo/maharashtra_state.geojson"
DISTRICTS_GEOJSON: str = "data/geo/maharashtra_districts.geojson"

# ── Study Period ─────────────────────────────────────────────────────────────
STUDY_YEAR_START: int = 2001
STUDY_YEAR_END: int = 2023
DEFAULT_YEAR: int = 2023
STUDY_YEARS = list(range(STUDY_YEAR_START, STUDY_YEAR_END + 1))
TOTAL_CELLS: int = 419
TOTAL_YEARS: int = 23
DATA_RESOLUTION: str = "IMD 0.25° Gridded Rainfall"

# ── Expected Regime Counts (from Phase 6B/7 K-Means K=4) ──────────────────────
EXPECTED_REGIME_COUNTS: Dict[str, int] = {
    "Core Interior Synchronized": 215,
    "Interior Semi-Arid Transition": 97,
    "Early Maritime & Western Ghats": 65,
    "Rain-Shadow High-Volatility": 42,
}

# ── DOY / Date Helpers ───────────────────────────────────────────────────────
MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]
ALL_SECTIONS = "All Sections (Comprehensive)"
FIELD_GUIDE_ANALYSIS_PAGES = (ALL_SECTIONS, "Rainfall Monitoring", "Monsoon Onset Analysis", "Regime Analysis", "Agricultural Advisory")
