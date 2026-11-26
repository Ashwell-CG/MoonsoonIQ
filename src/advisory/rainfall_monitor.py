"""MonsoonIQ - Current Rainfall Monitoring Service.

Ingests daily rainfall observations, tracks data completeness, computes cumulative
and rolling rainfall metrics, detects candidate triggers, and audits post-trigger dry spells.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from src.advisory.models import CurrentRainfallMetrics

logger = logging.getLogger("MonsoonIQ.RainfallMonitor")

# Agronomic Constants
WET_DAY_THRESHOLD_MM: float = 2.5
EXTREME_1DAY_THRESHOLD_MM: float = 100.0
EXTREME_3DAY_THRESHOLD_MM: float = 200.0


class RainfallMonitor:
    """Monitors daily rainfall observations for an active Kharif season."""

    def __init__(
        self,
        wet_day_threshold_mm: float = WET_DAY_THRESHOLD_MM,
        extreme_1day_threshold_mm: float = EXTREME_1DAY_THRESHOLD_MM,
        extreme_3day_threshold_mm: float = EXTREME_3DAY_THRESHOLD_MM,
    ) -> None:
        """Initializes the rainfall monitoring service.

        Args:
            wet_day_threshold_mm: Daily rainfall threshold for a wet day (default 2.5 mm).
            extreme_1day_threshold_mm: 1-day extreme threshold for waterlogging risk (100 mm).
            extreme_3day_threshold_mm: 3-day extreme threshold for waterlogging risk (200 mm).
        """
        self.wet_day_thresh = wet_day_threshold_mm
        self.extreme_1day_thresh = extreme_1day_threshold_mm
        self.extreme_3day_thresh = extreme_3day_threshold_mm

    def _normalize_series(
        self,
        daily_rainfall: Union[pd.Series, pd.DataFrame, List[Tuple[str, Optional[float]]]],
        as_of_date: Optional[str] = None,
        season_start: Optional[str] = None,
    ) -> pd.Series:
        """Normalizes various input formats into a clean pandas Series with DatetimeIndex.

        Args:
            daily_rainfall: Input daily rainfall observations.
            as_of_date: Optional upper bound cutoff date (YYYY-MM-DD).
            season_start: Optional lower bound start date (default June 1 of target year).

        Returns:
            pd.Series indexed by pd.DatetimeIndex sorted chronologically.
        """
        if isinstance(daily_rainfall, pd.Series):
            s = daily_rainfall.copy()
            s.index = pd.to_datetime(s.index)
        elif isinstance(daily_rainfall, pd.DataFrame):
            # Expecting columns 'date' and 'rainfall' (or 'rainfall_mm')
            df = daily_rainfall.copy()
            date_col = next(
                (c for c in df.columns if "date" in c.lower() or "time" in c.lower()),
                df.columns[0],
            )
            rain_col = next(
                (c for c in df.columns if "rain" in c.lower() or "precip" in c.lower()),
                df.columns[1],
            )
            df[date_col] = pd.to_datetime(df[date_col])
            s = pd.Series(df[rain_col].values, index=df[date_col])
        elif isinstance(daily_rainfall, list):
            dates = [pd.to_datetime(item[0]) for item in daily_rainfall]
            values = [
                float(item[1]) if item[1] is not None and not np.isnan(item[1]) else np.nan
                for item in daily_rainfall
            ]
            s = pd.Series(values, index=dates)
        else:
            raise TypeError(
                f"Unsupported daily_rainfall type: {type(daily_rainfall)}. Expected Series, DataFrame, or list of tuples."
            )

        s = s.sort_index()

        # Handle start date (default June 1 of the earliest year if not provided)
        if season_start is not None:
            start_dt = pd.to_datetime(season_start)
        else:
            year = s.index[0].year if len(s) > 0 else 2024
            start_dt = pd.to_datetime(f"{year}-06-01")

        # Handle cutoff date
        if as_of_date is not None:
            end_dt = pd.to_datetime(as_of_date)
        else:
            end_dt = s.index[-1] if len(s) > 0 else start_dt

        # Ensure all continuous calendar days exist in index
        full_idx = pd.date_range(start=start_dt, end=end_dt, freq="D")
        s = s.reindex(full_idx)
        return s

    def evaluate_observations(
        self,
        daily_rainfall: Union[pd.Series, pd.DataFrame, List[Tuple[str, Optional[float]]]],
        target_threshold_mm: float,
        as_of_date: Optional[str] = None,
        season_start: Optional[str] = None,
    ) -> CurrentRainfallMetrics:
        """Evaluates daily rainfall observations up to as_of_date against a target threshold.

        Args:
            daily_rainfall: Daily rainfall inputs.
            target_threshold_mm: Cumulative rainfall threshold to track (e.g. 75 mm or 50 mm).
            as_of_date: Optional cutoff date string (YYYY-MM-DD).
            season_start: Optional season start date string (YYYY-06-01).

        Returns:
            CurrentRainfallMetrics containing verified empirical indicators.
        """
        s = self._normalize_series(
            daily_rainfall, as_of_date=as_of_date, season_start=season_start
        )

        total_days = len(s)
        missing_count = int(s.isna().sum())
        valid_count = total_days - missing_count
        completeness_pct = (valid_count / total_days * 100.0) if total_days > 0 else 0.0

        as_of_str = s.index[-1].strftime("%Y-%m-%d") if len(s) > 0 else "N/A"
        start_str = s.index[0].strftime("%Y-%m-%d") if len(s) > 0 else "N/A"

        # Compute valid metrics treating missing explicitly (never treating missing as 0 in statistics)
        # For cumulative sum, dropna or fillna(0) for accumulation tracking while preserving missing flag
        rain_values = s.values.astype(float)
        valid_rain = np.where(np.isnan(rain_values), 0.0, rain_values)

        cumulative_mm = float(np.nansum(rain_values))
        rainy_days_count = int(np.nansum(rain_values >= self.wet_day_thresh))

        # Rolling 3-day and 5-day rainfall
        # Rolling on valid_rain
        roll_3 = pd.Series(valid_rain).rolling(3, min_periods=1).sum().values
        roll_5 = pd.Series(valid_rain).rolling(5, min_periods=1).sum().values

        current_3d = float(roll_3[-1]) if len(roll_3) > 0 else 0.0
        current_5d = float(roll_5[-1]) if len(roll_5) > 0 else 0.0
        max_roll_3d = float(np.max(roll_3)) if len(roll_3) > 0 else 0.0
        max_roll_5d = float(np.max(roll_5)) if len(roll_5) > 0 else 0.0
        max_1d = float(np.nanmax(rain_values)) if len(rain_values) > 0 and not np.all(np.isnan(rain_values)) else 0.0

        # Current consecutive dry spell (from end backwards)
        curr_dry = 0
        for val in reversed(rain_values):
            if np.isnan(val) or val < self.wet_day_thresh:
                curr_dry += 1
            else:
                break

        # Intervening dry-spell reset tracking (prolonged dry spell >= 10 days)
        # Evaluates whether an extended dry break occurred between rainfall pulses
        prolonged_dry_threshold = 10
        running_dry_days = 0
        current_cycle_rain = 0.0
        max_intervening_dry = 0
        has_intervening_prolonged_dry = False
        had_prior_rain = False

        for r_val in valid_rain:
            if r_val < self.wet_day_thresh:
                if had_prior_rain:
                    running_dry_days += 1
                    if running_dry_days > max_intervening_dry:
                        max_intervening_dry = running_dry_days
            else:
                # Rainy day (>= 2.5 mm)
                if had_prior_rain and running_dry_days >= prolonged_dry_threshold:
                    # Intervening dry spell >= 10 days occurred AFTER prior rain!
                    # Prior moisture evaporated; reset active wetting cycle accumulation
                    has_intervening_prolonged_dry = True
                    current_cycle_rain = r_val
                else:
                    current_cycle_rain += r_val
                had_prior_rain = True
                running_dry_days = 0

        effective_cum_mm = float(current_cycle_rain) if had_prior_rain else 0.0

        # Candidate trigger detection
        cum_running = np.cumsum(valid_rain)
        hit_indices = np.where(cum_running >= target_threshold_mm)[0]

        is_triggered = len(hit_indices) > 0
        cand_date_str: Optional[str] = None
        cand_doy: Optional[int] = None
        post_trigger_dry: Optional[int] = None
        post_5d_wet_days: Optional[int] = None
        post_5d_rain_mm: Optional[float] = None
        qualifying_5d_wet_days: int = 0
        verif_has_missing: bool = False

        if is_triggered:
            t0_idx = hit_indices[0]
            t0_dt = s.index[t0_idx]
            cand_date_str = t0_dt.strftime("%Y-%m-%d")
            cand_doy = int(t0_dt.day_of_year)

            # Check 5-day verification window around candidate trigger
            # We inspect all 5-day windows containing t0 or overlapping with the trigger
            if total_days >= 5:
                start_k = max(0, t0_idx - 4)
                end_k = min(total_days - 4, t0_idx + 1)
                for k in range(start_k, end_k + 1):
                    win = rain_values[k : k + 5]
                    if np.any(np.isnan(win)):
                        verif_has_missing = True
                    wet_c = int(np.nansum(win >= self.wet_day_thresh))
                    if wet_c > qualifying_5d_wet_days:
                        qualifying_5d_wet_days = wet_c
            else:
                if np.any(np.isnan(rain_values)):
                    verif_has_missing = True
                qualifying_5d_wet_days = int(np.nansum(rain_values >= self.wet_day_thresh))

            # Post-trigger observations (days strictly after t0_idx)
            post_slice = rain_values[t0_idx + 1 :]
            if len(post_slice) > 0:
                # Immediate dry days starting from day after trigger
                imm_dry = 0
                for d_val in post_slice:
                    if np.isnan(d_val) or d_val < self.wet_day_thresh:
                        imm_dry += 1
                    else:
                        break
                post_trigger_dry = imm_dry

                # 5-day verification window post-trigger (first 5 days after trigger)
                window_5d = post_slice[:5]
                post_5d_wet_days = int(np.nansum(window_5d >= self.wet_day_thresh))
                post_5d_rain_mm = float(np.nansum(window_5d))
                if np.any(np.isnan(window_5d)):
                    verif_has_missing = True
            else:
                post_trigger_dry = 0
                post_5d_wet_days = 0
                post_5d_rain_mm = 0.0
        else:
            # If not triggered, also check if there is any 5-day window with wet days
            if total_days >= 5:
                for k in range(total_days - 4):
                    win = rain_values[k : k + 5]
                    wet_c = int(np.nansum(win >= self.wet_day_thresh))
                    if wet_c > qualifying_5d_wet_days:
                        qualifying_5d_wet_days = wet_c
            else:
                qualifying_5d_wet_days = int(np.nansum(rain_values >= self.wet_day_thresh))

            # If there's missing data in the observation window
            if missing_count > 0:
                verif_has_missing = True

        # Extreme rainfall indicator
        is_extreme = (max_1d >= self.extreme_1day_thresh) or (
            max_roll_3d >= self.extreme_3day_thresh
        )

        return CurrentRainfallMetrics(
            as_of_date=as_of_str,
            season_start_date=start_str,
            total_days_observed=total_days,
            valid_days_count=valid_count,
            missing_days_count=missing_count,
            data_completeness_pct=round(completeness_pct, 2),
            cumulative_rainfall_mm=round(cumulative_mm, 2),
            rainy_days_count=rainy_days_count,
            current_3day_rainfall_mm=round(current_3d, 2),
            current_5day_rainfall_mm=round(current_5d, 2),
            max_rolling_3day_mm=round(max_roll_3d, 2),
            max_rolling_5day_mm=round(max_roll_5d, 2),
            max_single_day_rain_mm=round(max_1d, 2),
            current_consecutive_dry_days=curr_dry,
            candidate_trigger_date=cand_date_str,
            candidate_trigger_doy=cand_doy,
            is_triggered=is_triggered,
            verification_window_wet_days=post_5d_wet_days,
            qualifying_5d_wet_days=qualifying_5d_wet_days,
            verification_window_has_missing=verif_has_missing,
            post_trigger_dry_days=post_trigger_dry,
            post_trigger_5d_rain_mm=round(post_5d_rain_mm, 2)
            if post_5d_rain_mm is not None
            else None,
            is_extreme_rain_event=is_extreme,
            effective_cumulative_rainfall_mm=round(effective_cum_mm, 2),
            has_intervening_prolonged_dry_spell=has_intervening_prolonged_dry,
            max_intervening_dry_spell_days=max_intervening_dry,
        )
