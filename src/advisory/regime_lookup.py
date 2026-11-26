"""MonsoonIQ - Historical Regime Lookup Service.

Retrieves K-Means regime assignments, historical onset statistics, and
climatological risk baselines for Maharashtra IMD 0.25° grid cells.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from src.advisory.models import GridCellInfo, HistoricalRegimeBaseline

logger = logging.getLogger("MonsoonIQ.RegimeLookup")

# Default Base Directory
DEFAULT_BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
DEFAULT_BASELINES_CSV: Path = (
    DEFAULT_BASE_DIR / "data" / "processed" / "advisory_historical_baselines.csv"
)


class RegimeLookupService:
    """Service for looking up historical regime and climatology baselines.

    Attributes:
        baselines_path: Path to advisory_historical_baselines.csv.
        df: Loaded baselines DataFrame.
    """

    def __init__(self, baselines_path: Optional[Path] = None) -> None:
        """Initializes the lookup service and loads baseline data.

        Args:
            baselines_path: Optional custom path to baselines CSV.
        """
        self.baselines_path = baselines_path or DEFAULT_BASELINES_CSV
        if not self.baselines_path.exists():
            raise FileNotFoundError(
                f"Advisory historical baselines not found at {self.baselines_path}."
            )
        self.df: pd.DataFrame = pd.read_csv(self.baselines_path)
        logger.info(
            f"Loaded RegimeLookupService with {len(self.df)} cells from {self.baselines_path.name}"
        )

        # Precompute index lookups
        self._cell_id_map: Dict[str, int] = {
            str(row["cell_id"]).lower(): idx for idx, row in self.df.iterrows()
        }
        self._cell_idx_map: Dict[int, int] = {
            int(row["cell_index"]): idx for idx, row in self.df.iterrows()
        }

    def _row_to_models(
        self, row: pd.Series
    ) -> Tuple[GridCellInfo, HistoricalRegimeBaseline]:
        """Converts a baseline DataFrame row into GridCellInfo and HistoricalRegimeBaseline.

        Args:
            row: Row from advisory_historical_baselines.csv.

        Returns:
            Tuple of (GridCellInfo, HistoricalRegimeBaseline).
        """
        cell_info = GridCellInfo(
            cell_id=str(row["cell_id"]),
            cell_index=int(row["cell_index"]),
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            district=str(row["district"]),
            zone_id=int(row["zone_id"]),
            zone_name=str(row["zone_name"]),
            regime_kmeans=str(row["regime_kmeans"]),
        )

        baseline = HistoricalRegimeBaseline(
            historical_years_count=int(row["historical_years_count"]),
            regime_cell_count=int(row["regime_cell_count"]),
            regime_total_cell_years=int(row["regime_total_cell_years"]),
            median_onset_doy=float(row["median_onset_doy"]),
            mean_onset_doy=float(row["mean_onset_doy"]),
            std_onset_doy=float(row["std_onset_doy"]),
            iqr_onset_doy=float(row["iqr_onset_doy"]),
            early_onset_freq=float(row["early_onset_freq"]),
            delayed_onset_freq=float(row["delayed_onset_freq"]),
            rejected_candidate_freq=float(row["rejected_candidate_freq"]),
            onset_detection_freq=float(row["onset_detection_freq"]),
            june_mean_rainfall_mm=float(row["june_mean_rainfall_mm"]),
            june_rainfall_cv_pct=float(row["june_rainfall_cv_pct"]),
            jj_mean_rainfall_mm=float(row["jj_mean_rainfall_mm"]),
            may_mean_rainfall_mm=float(row["may_mean_rainfall_mm"]),
            june_mean_wet_days=float(row["june_mean_wet_days"]),
            sowing_50mm_median_doy=float(row["sowing_50mm_median_doy"]),
            sowing_50mm_delay_freq=float(row["sowing_50mm_delay_freq"]),
            early_dry_spell_mean_days=float(row["early_dry_spell_mean_days"]),
            early_dry_spell_max_days=float(row["early_dry_spell_max_days"]),
            severe_dry_spell_10d_freq=float(row["severe_dry_spell_10d_freq"]),
            regime_50mm_delayed_pct=float(row["regime_50mm_delayed_pct"]),
            regime_50mm_unreached_pct=float(row["regime_50mm_unreached_pct"]),
            regime_75mm_delayed_pct=float(row["regime_75mm_delayed_pct"]),
            regime_75mm_unreached_pct=float(row["regime_75mm_unreached_pct"]),
            regime_75mm_median_doy=float(row["regime_75mm_median_doy"]),
            regime_rolling_3d_50mm_reach_pct=float(row["regime_rolling_3d_50mm_reach_pct"]),
            regime_rolling_5d_50mm_reach_pct=float(row["regime_rolling_5d_50mm_reach_pct"]),
            regime_post_trigger_10d_break_prob_pct=float(row["regime_post_trigger_10d_break_prob_pct"]),
            regime_post_trigger_7d_break_prob_pct=float(row["regime_post_trigger_7d_break_prob_pct"]),
            regime_mean_immediate_dry_spell_days=float(row["regime_mean_immediate_dry_spell_days"]),
            regime_post_trigger_5d_rain_mm=float(row["regime_post_trigger_5d_rain_mm"]),
            regime_post_trigger_10d_rain_mm=float(row["regime_post_trigger_10d_rain_mm"]),
        )

        return cell_info, baseline

    def get_cell_by_id(
        self, cell_id: Union[str, int]
    ) -> Tuple[GridCellInfo, HistoricalRegimeBaseline]:
        """Looks up a grid cell by its string identifier ('cell_042') or integer index (42).

        Args:
            cell_id: Cell identifier string or integer index.

        Returns:
            Tuple of (GridCellInfo, HistoricalRegimeBaseline).

        Raises:
            ValueError: If cell_id is not found in the valid Maharashtra 419-cell domain.
        """
        if isinstance(cell_id, int):
            if cell_id in self._cell_idx_map:
                row_idx = self._cell_idx_map[cell_id]
                return self._row_to_models(self.df.iloc[row_idx])
            # If int passed as numeric string index
            str_key = f"cell_{cell_id:03d}".lower()
            if str_key in self._cell_id_map:
                row_idx = self._cell_id_map[str_key]
                return self._row_to_models(self.df.iloc[row_idx])
            raise ValueError(
                f"Grid cell index {cell_id} is out of bounds (valid range: 0 to 418)."
            )

        key = str(cell_id).strip().lower()
        if key in self._cell_id_map:
            row_idx = self._cell_id_map[key]
            return self._row_to_models(self.df.iloc[row_idx])

        # Try parsing numeric string
        if key.isdigit():
            return self.get_cell_by_id(int(key))

        raise ValueError(
            f"Grid cell identifier '{cell_id}' not found in the 419-cell Maharashtra domain."
        )

    def get_nearest_cell(
        self, latitude: float, longitude: float
    ) -> Tuple[GridCellInfo, HistoricalRegimeBaseline]:
        """Finds the nearest valid Maharashtra IMD grid cell to given coordinates.

        Args:
            latitude: Target latitude in degrees North.
            longitude: Target longitude in degrees East.

        Returns:
            Tuple of (GridCellInfo, HistoricalRegimeBaseline) for nearest cell.
        """
        lats = self.df["latitude"].values
        lons = self.df["longitude"].values

        # Euclidean approximation for 0.25 deg grid spacing
        dist_sq = (lats - latitude) ** 2 + (lons - longitude) ** 2
        nearest_idx = int(np.argmin(dist_sq))
        return self._row_to_models(self.df.iloc[nearest_idx])

    def get_cells_by_district(
        self, district_name: str
    ) -> List[Tuple[GridCellInfo, HistoricalRegimeBaseline]]:
        """Retrieves all grid cells within a named administrative district.

        Args:
            district_name: Name of district (case-insensitive).

        Returns:
            List of (GridCellInfo, HistoricalRegimeBaseline) tuples.
        """
        name_clean = district_name.strip().lower()
        matches = self.df[self.df["district"].str.lower() == name_clean]
        if len(matches) == 0:
            # Partial match attempt
            matches = self.df[self.df["district"].str.lower().str.contains(name_clean)]
        return [self._row_to_models(row) for _, row in matches.iterrows()]

    def get_regime_cells(
        self, regime_name: str
    ) -> List[Tuple[GridCellInfo, HistoricalRegimeBaseline]]:
        """Retrieves all grid cells assigned to a specific K=4 onset regime.

        Args:
            regime_name: Name of regime (case-insensitive).

        Returns:
            List of (GridCellInfo, HistoricalRegimeBaseline) tuples.
        """
        name_clean = regime_name.strip().lower()
        matches = self.df[self.df["regime_kmeans"].str.lower() == name_clean]
        return [self._row_to_models(row) for _, row in matches.iterrows()]

    def get_all_cells(self) -> List[Tuple[GridCellInfo, HistoricalRegimeBaseline]]:
        """Returns all 419 grid cells in the Maharashtra domain."""
        return [self._row_to_models(row) for _, row in self.df.iterrows()]
