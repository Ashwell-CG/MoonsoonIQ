"""MonsoonIQ Dashboard – Formatting utilities.

Helpers for DOY-to-date conversion, number formatting, and display strings.
"""

from __future__ import annotations

import datetime
from typing import Optional


def doy_to_date_str(doy: float, year: int = 2001) -> str:
    """Convert Day of Year to a readable date string (e.g., 'Jun 09').

    Args:
        doy: Day of Year (1-indexed).
        year: Reference year for leap-year handling.

    Returns:
        Formatted date string or '—' if doy is NaN or invalid.
    """
    try:
        if doy != doy or doy <= 0:  # NaN check
            return "—"
        dt = datetime.datetime(year, 1, 1) + datetime.timedelta(days=int(doy) - 1)
        return dt.strftime("%b %d")
    except (ValueError, OverflowError):
        return "—"


def doy_to_date(doy: float, year: int = 2001) -> Optional[datetime.date]:
    """Convert Day of Year to a datetime.date.

    Args:
        doy: Day of Year (1-indexed).
        year: Reference year.

    Returns:
        datetime.date or None if invalid.
    """
    try:
        if doy != doy or doy <= 0:
            return None
        return (datetime.datetime(year, 1, 1) + datetime.timedelta(days=int(doy) - 1)).date()
    except (ValueError, OverflowError):
        return None


def format_pct(value: float, decimals: int = 1) -> str:
    """Format a percentage value.

    Args:
        value: Percentage as a float (e.g., 0.65 or 65.0).
        decimals: Decimal places.

    Returns:
        Formatted percentage string.
    """
    if value != value:
        return "—"
    # If value looks like a proportion (< 1.5), multiply by 100
    if abs(value) < 1.5 and abs(value) > 0:
        value = value * 100
    return f"{value:.{decimals}f}%"


def format_mm(value: float, decimals: int = 1) -> str:
    """Format a rainfall value in mm.

    Args:
        value: Rainfall in mm.
        decimals: Decimal places.

    Returns:
        Formatted mm string.
    """
    if value != value:
        return "—"
    return f"{value:,.{decimals}f} mm"


def format_cell_dropdown_label(
    cell_id: str,
    district: Optional[str],
    lat: float,
    lon: float,
) -> str:
    """Format grid cell dropdown label with place/district name first.

    Format:
        '{district} · {cell_id} · {latitude:.2f}°N, {longitude:.2f}°E'
    Fallback if district is missing, 'Unknown', or empty:
        '{cell_id} · {latitude:.2f}°N, {longitude:.2f}°E'

    Args:
        cell_id: Grid cell identifier (e.g. 'cell_001').
        district: District name or None/Unknown.
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees.

    Returns:
        Formatted label string.
    """
    if district and str(district).strip() not in ("", "Unknown", "nan", "None"):
        return f"{str(district).strip()} · {cell_id} · {lat:.2f}°N, {lon:.2f}°E"
    return f"{cell_id} · {lat:.2f}°N, {lon:.2f}°E"

