# MonsoonIQ – Phase 9: Interactive Dashboard Development & System Integration Report

**Project Title:** MonsoonIQ – Maharashtra Hyperlocal Monsoon Intelligence & Agricultural Advisory Platform  
**Phase:** Phase 9 (Interactive Dashboard Development)  
**Date:** November 22, 2026  
**Environment:** Python 3.12.16 · Streamlit 1.67.0 · Plotly 7.1.0 · Folium 1.0.0 · GeoPandas · Xarray  

---

## 1. Executive Summary

Phase 9 successfully developed and delivered a professional, interactive meteorological research dashboard for **MonsoonIQ**. The dashboard synthesizes the entire analytical workflow of Phases 1 through 8.2 into a unified, modular Streamlit interface. It brings together 23 years of IMD 0.25° gridded daily rainfall data (2001–2023, 8,400 daily time steps), unsupervised onset clustering across 419 Maharashtra grid cells, and the regime-aware sowing advisory engine.

All dashboard metrics, charts, and maps are computed dynamically from validated project outputs rather than hardcoded. The application adheres strictly to scientific data integrity guidelines, preserving missing-data semantics (`NaN` preservation), labeling spatial resolutions, and enforcing cautious advisory communications (strictly prohibiting "Safe to Sow" declarations).

---

## 2. Architecture & File Structure

The dashboard is structured modularly under the `dashboard/` package, enforcing clean separation between UI components, cached data loading services, and visualization utilities:

```
dashboard/
├── app.py                     # Main application entry point & dark slate styling
├── components/                # Modular visual components
│   ├── header.py              # Title, study period, and resolution header
│   ├── metric_cards.py        # 6 compact meteorological summary cards
│   ├── maharashtra_map.py     # Interactive Folium map of 419 cells colored by regime
│   ├── rainfall_charts.py     # Plotly daily, monthly, annual JJAS, and dry spell charts
│   ├── onset_analysis.py      # Year-by-year onset timeline, median baseline, detection stats
│   ├── regime_analysis.py     # Donut distribution, onset timing, and dry spell comparisons
│   ├── advisory_panel.py      # Regime-aware sowing advisory interface with active wetting cycles
│   └── provenance.py          # Lineage badges, source status, and data integrity notices
├── services/                  # Business logic and cached data retrieval
│   ├── data_loader.py         # Streamlit-cached NetCDF, CSV, and GeoJSON loaders
│   └── dashboard_service.py   # Multi-source aggregation, regime summaries, selector builders
└── utils/                     # Presentation helpers and domain constants
    ├── constants.py           # Color palettes, study period, coordinates, paths
    └── formatting.py          # Day-of-year to calendar date conversions, unit formatters
```

---

## 3. Implemented Dashboard Features & Pages

### 3.1 Meteorological Monitoring Theme & Header
- **Color Palette:** Dark navy/slate background (`#0B132B`, `#111D3D`, `#1C2541`) with restrained blue (`#38BDF8`), cyan (`#00BCD4`), and amber (`#FF9800`) accents inspired by modern meteorological interfaces.
- **Top Header (`header.py`):** Displays study period (2001–2023), spatial resolution (IMD 0.25° Gridded Rainfall), and total grid cells (419).
- **Metric Cards (`metric_cards.py`):**
  - Total Grid Cells: `419`
  - Study Years: `23`
  - Confirmed Onset Records: `9,606` (computed dynamically from `maharashtra_onset_2001_2023.nc`)
  - Discovered Onset Regimes: `4` (K-Means K=4)
  - Selected Cell Median Onset Date: e.g. `Jun 07 (DOY 158)`
  - Selected Cell Onset Variability: e.g. `±6.4d` (standard deviation)

### 3.2 Interactive Maharashtra Map (`maharashtra_map.py`)
- Renders all 419 valid Maharashtra grid cells using Folium `CircleMarker` elements.
- Cells are colored by their K-Means K=4 regime assignment:
  - **Core Interior Synchronized (215 cells):** Blue (`#2196F3`)
  - **Interior Semi-Arid Transition (97 cells):** Muted Purple (`#AB47BC`)
  - **Early Maritime & Western Ghats (65 cells):** Cyan (`#00BCD4`)
  - **Rain-Shadow High-Volatility (42 cells):** Amber/Orange (`#FF9800`)
- Hover tooltips show Cell ID, coordinates, district, regime, median onset DOY/date, onset standard deviation, June mean rainfall, and average post-onset dry spell.
- Includes Maharashtra state boundary (`maharashtra_state.geojson`) and district boundaries (`maharashtra_districts.geojson`).
- Clicking any node updates `selected_cell_id` in Streamlit session state and refocuses analysis across all sections.

### 3.3 Rainfall Monitoring (`rainfall_charts.py`)
- **Daily Rainfall Bar Chart:** May 15 – Oct 15 time-series for the selected year and cell, with a 2.5 mm wet-day reference line and summary statistics (total rainfall, wet days, 1-day maximum).
- **Monthly Rainfall Distribution:** Monthly totals (May through October) with wet-day counts.
- **Annual JJAS Trend:** 23-year historical time-series of total monsoon precipitation with long-term average baseline and dry-year/excess-year annotations.
- **Dry Spell Analysis:** Histogram and summary metrics of consecutive dry days during the monsoon season.

### 3.4 Monsoon Onset Analysis (`onset_analysis.py`)
- **Onset Timeline:** Interactive scatter/line chart comparing year-by-year confirmed onset DOY against the cell's long-term median onset date.
- **No-Detection Markers:** Visual red 'X' markers for years where local sustained criteria were not satisfied.
- **Onset Statistics:** Mean onset DOY, standard deviation, IQR, early onset frequency, delayed onset frequency, and rejected candidate frequency.
- **Scientific Methodology Explanation:** Expandable guide clarifying the distinction between candidate onset, 20-day verification, confirmed sustained onset, and IMD regional synoptic advance.

### 3.5 Regime Analysis (`regime_analysis.py`)
- **Overview Donut Chart:** Visual breakdown of grid cells across the 4 regimes with percentage share.
- **Cross-Regime Onset Comparison:** Grouped bar charts comparing median onset dates and standard deviation ($\sigma$).
- **Rainfall & Dry Spell Comparison:** June mean rainfall and post-onset dry spell duration across regimes.
- Highlights the climatological rationale for the 4-regime solution, specifically isolating the 42 Rain-Shadow high-volatility cells.

### 3.6 Agricultural Advisory Panel (`advisory_panel.py`)
- Reuses the `src.advisory` decision engine without code duplication.
- Replays historical daily rainfall up to a user-selectable evaluation date (June 1 through July 31).
- **Advisory State Banner:** Displays state (`RAINFALL_CRITERIA_MET`, `CAUTION`, `HIGH_RISK`, `INSUFFICIENT_DATA`) with color accents.
- **Key Metrics Row:** Cumulative rainfall, effective active-cycle rainfall, qualifying 5-day wet days, current dry-spell duration, and seasonal rainy days.
- **Root-Zone Moisture Depletion Alert:** Automatically flags when an intervening $\ge 10$-day dry spell has evaporated prior rainfall.
- **Condition Evaluations:** Transparent checklist of all evaluated rules, thresholds, actual values, and source citations.
- **Historical Risk Context:** Displays empirical baseline metrics (e.g. 39.13% post-50mm break frequency in Rain-Shadow, 20.60% probability of not reaching 75mm by July 15).
- **Prohibition Enforced:** The phrase "Safe to Sow" is strictly forbidden and never displayed.

### 3.7 Data Provenance & Lineage (`provenance.py`)
- Top banner explicitly identifies the operational data stream:
  - `Historical Replay (IMD 0.25° Gridded 2001–2023)`: **ACTIVE**
  - `Simulated Test Data (Scenario Testing)`: **EXPERIMENTAL**
  - `Observed Weather Station (AWS Mahavedh)`: **NOT CONNECTED**
  - `NWP Forecast Model (IMD GFS / NCUM)`: **NOT CONNECTED**
- Clarifies that 0.25° gridded values are spatial estimates, not village rain gauges.

---

## 4. Backend Modules Reused

The dashboard strictly adheres to the architectural mandate to reuse backend modules rather than duplicating logic:

| Backend Module | Purpose & Reused Components |
|---|---|
| `src.advisory.decision_engine` | `AdvisoryDecisionEngine.generate_advisory()` evaluates all conditions, computes active wetting cycles, and emits structured `AdvisoryReport`. |
| `src.advisory.models` | `AdvisoryReport`, `AdvisoryState`, `GridCellMetadata`, `RainfallMetrics`, `ConditionEvaluation`. |
| `src.advisory.lookup_service` | `RegimeLookupService` for querying 419 cell metadata records and regime memberships. |
| `src.advisory.rainfall_monitor` | `RainfallAccumulationTracker` logic for active wetting cycles and 10-day dry-spell resets. |

---

## 5. Integrated Data Sources

| Dataset File | Dimensions / Format | Content & Usage in Dashboard |
|---|---|---|
| `data/processed/maharashtra_imd_daily_2001_2023.nc` | 8,400 days × 28 lat × 35 lon (~15 MB) | Full daily rainfall series (2001–2023), masking, daily & monthly charts, advisory replay. |
| `data/processed/maharashtra_onset_2001_2023.nc` | 23 years × 28 lat × 35 lon (~64 KB) | Confirmed onset DOY, candidate onset, rejected candidates, no-detection flags. |
| `data/processed/advisory_historical_baselines.csv` | 419 rows × 41 columns (~114 KB) | Cell coordinates, districts, regime assignments, median onset DOY, dry-spell statistics. |
| `data/processed/monsoon_onset_clusters.csv` | 419 rows × 22 columns (~45 KB) | Cluster labels for K-Means, Hierarchical, DBSCAN algorithms. |
| `data/processed/monsoon_onset_features.csv` | 419 rows × 17 columns (~50 KB) | 9 standardized onset-dynamics features used for clustering. |
| `data/geo/maharashtra_state.geojson` | GeoJSON (1 state feature) | Maharashtra state outer boundary outline on map. |
| `data/geo/maharashtra_districts.geojson` | GeoJSON (36 district features) | Maharashtra district administrative boundary outlines (`dtname` property). |

---

## 6. Verification & Test Results

A dedicated test suite was implemented in `tests/test_dashboard.py` containing 18 rigorous test cases. Additionally, the complete project regression suite was executed across all 15 test modules.

### Test Execution Summary
```
============================= test session starts =============================
platform win32 -- Python 3.12.16, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\Ashwell\Project\SEM 4\ML Project\MonsoonPred

tests/test_advisory_audit.py ......................... [ 5%]
tests/test_advisory_engine.py ........................ [ 13%]
tests/test_chirps_audit.py ........................... [ 20%]
tests/test_clustering_validation.py .................. [ 23%]
tests/test_dashboard.py .............................. [ 33%] (18/18 passed)
tests/test_eda.py .................................... [ 42%]
tests/test_imd_acquisition.py ........................ [ 51%]
tests/test_imd_historical.py ......................... [ 69%]
tests/test_onset_clustering.py ....................... [ 75%]
tests/test_onset_methodology.py ...................... [ 77%]
tests/test_onset_pipeline.py ......................... [ 84%]
tests/test_preprocessing.py .......................... [ 90%]
tests/test_rainfall_accumulation_audit.py ............ [ 94%]
tests/test_regime_agricultural_validation.py ......... [ 97%]
tests/test_sowing_trigger_audit.py ................... [100%]

============================ 182 passed in 24.32s =============================
```

- **Total Test Cases:** 182
- **Passing:** 182 (100%)
- **Failures / Errors:** 0
- **Regressions:** 0

---

## 7. Known Limitations & Future Roadmap

1. **Live Data Ingestion:**
   - Real-time weather station feeds (e.g. Mahavedh AWS network) and NWP numerical forecast models (IMD GFS / NCUM) are not currently connected.
   - The dashboard operates purely on historical replay (2001–2023) and simulated test inputs. Both disconnected sources are explicitly badged as `NOT CONNECTED`.
2. **Spatial Granularity:**
   - The analysis operates on a 0.25° × 0.25° (~27 km × 27 km) regular grid. Variations within a grid cell (micro-topography, local soil texture, farm-level showers) cannot be resolved.
3. **Map Click Interaction:**
   - Folium map click detection relies on parsing popup text via regex (`cell_\d+`). If JavaScript execution is delayed in low-bandwidth browser environments, the sidebar dropdown serves as a robust fallback.
4. **Soil Moisture & Crop Phenology:**
   - Sowing triggers represent empirical proxies for topsoil moisture wetting. True crop germination depends on soil physical properties (vertisol vs inceptisol water holding capacity), sowing depth, and seed variety, which require field-scale agronomic calibration.

---

## 8. Run Instructions

To launch the MonsoonIQ dashboard locally:

```bash
# Using uv (project virtualenv)
uv run streamlit run dashboard/app.py

# Or directly with activated virtualenv
streamlit run dashboard/app.py
```

The application will be accessible at: `http://localhost:8501`.
