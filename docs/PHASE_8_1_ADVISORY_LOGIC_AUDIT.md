# MonsoonIQ – Phase 8.1: Advisory Engine Logic, Threshold and Data Provenance Audit

## Executive Summary & Final Verdict

**FINAL VERDICT: READY WITH DOCUMENTED LIMITATIONS**

The MonsoonIQ Phase 8 regime-aware sowing advisory engine has undergone a rigorous, independent verification audit. The advisory architecture is verified to be scientifically sound, mathematically reproducible, and agriculturally aligned with State Agricultural University (SAU) protocols across Maharashtra. A critical implementation discrepancy in the Rain-Shadow two-stage verification logic was detected and corrected. Furthermore, data provenance tracking has been formalized, cumulative rainfall definitions and soil-water balance limitations have been documented, historical risk denominators have been clarified, and maritime precipitation hazard indicators have been appropriately categorized.

---

## 1. Rain-Shadow Two-Stage Trigger Audit and Correction

### 1.1 Discrepancy Identification in Phase 8 Baseline Implementation
During code inspection of `src/advisory/decision_engine.py` (Phase 8), the verification condition for candidate trigger persistence was defined as:
```python
# PREVIOUS FLAWED IMPLEMENTATION (Phase 8):
verif_pass = verif_wet_days >= 1 or metrics.rainy_days_count >= 3
```
**Root Cause Analysis:** 
`metrics.rainy_days_count` counts the total number of rainy days ($\ge 2.5\text{ mm}$) accumulated across the *entire season* from June 1 to the current evaluation date. Under this flawed logic, if a grid cell accumulated 3 isolated, light rainy days early in June (e.g., June 2, June 6, June 12), and then received a single isolated convective thunderstorm of 70 mm on June 28 without any secondary rainfall, `verif_pass` evaluated to `True`. This allowed an isolated convective storm to satisfy the two-stage criteria, directly violating the scientific requirement established in Phase 7.1 that **both qualifying rainy days must occur within a contiguous 5-day verification window**.

### 1.2 Corrective Implementation
The logic was rewritten in `src/advisory/rainfall_monitor.py` and `src/advisory/decision_engine.py` to calculate `qualifying_5d_wet_days` using a sliding 5-day window centered on/overlapping the candidate trigger date:
```python
# CORRECTED IMPLEMENTATION (Phase 8.1):
if regime == RegimeName.RAIN_SHADOW.value:
    # Rain-Shadow strictly requires BOTH qualifying rainy days within a 5-day verification window
    verif_pass = metrics.qualifying_5d_wet_days >= 2
```
If `verif_pass` is false, the engine refuses `RAINFALL_CRITERIA_MET` and returns `CAUTION` with an explicit reason:
> *"Rain-Shadow Two-Stage Verification Rule: Cumulative rainfall reached {metrics.cumulative_rainfall_mm:.1f} mm, but only {metrics.qualifying_5d_wet_days} wet day(s) occurred within any 5-day verification window (requires >= 2 distinct rainy days >= 2.5 mm). Suggests an isolated convective thunderstorm rather than sustained monsoon flow."*

### 1.3 Audit Test Cases & Empirical Results
Six targeted test cases were audited via `tests/test_advisory_audit.py` and `scripts/audit_advisory_logic.py`. All 6 passed:

| Test Case | Rainfall Profile | Expected State | Actual State | Qualifying 5d Wet Days | Audit Verdict |
| :--- | :--- | :--- | :--- | :---: | :---: |
| **Case 1: Two rainy days inside 5 days** | Day 1: 40 mm, Day 3: 40 mm (80 mm total) | `RAINFALL_CRITERIA_MET` | `RAINFALL_CRITERIA_MET` | 2 | **PASSED** |
| **Case 2: Two rainy days outside 5 days** | Day 1: 40 mm, 8 dry days, Day 10: 40 mm (80 mm total) | `CAUTION` | `CAUTION` | 1 | **PASSED** |
| **Case 3: Single very heavy rainfall day** | Day 1: 80 mm, Days 2–5: 0 mm (80 mm total) | `CAUTION` | `CAUTION` | 1 | **PASSED** |
| **Case 4: Exactly 75.0 mm threshold** | Day 1: 37.5 mm, Day 3: 37.5 mm (75.0 mm total) | `RAINFALL_CRITERIA_MET` | `RAINFALL_CRITERIA_MET` | 2 | **PASSED** |
| **Case 5: Sub-threshold 74.9 mm** | Day 1: 37.4 mm, Day 3: 37.5 mm (74.9 mm total) | `CAUTION` | `CAUTION` | 2 | **PASSED** |
| **Case 6: Missing data inside verification window** | Day 1: 40 mm, Day 2: NaN, Day 3: 40 mm (15 days total) | `INSUFFICIENT_DATA` | `INSUFFICIENT_DATA` | N/A | **PASSED** |

---

## 2. Cumulative Rainfall Definition & Soil-Water Balance Limitation

### 2.1 Operational Definitions
- **Operational Season Start:** Fixed at **June 1** (Day of Year 152 in non-leap years, 153 in leap years), representing the institutional commencement of the Indian Kharif agricultural season.
- **Exclusion of May Rainfall:** May pre-monsoon convective rainfall is intentionally excluded from Kharif sowing accumulation. May events in semi-arid Maharashtra are characterized by extreme atmospheric vapor pressure deficits (VPD), high surface temperatures (>40°C), and potential evapotranspiration rates exceeding $8\text{--}10\text{ mm/day}$. Profile water storage from May showers evaporates within 48–72 hours, offering zero effective moisture for June-sown crops.
- **Accumulation Methodology:** Primary triggers utilize continuous cumulative summation ($\sum_{t=\text{June 1}}^{T} R_t$) rather than fixed rolling windows. Rolling 3-day and 5-day sums are reserved for short-term intensity checks (heavy rainfall hazards and verification window multi-day persistence).
- **IMD 08:30 IST Timestamping Standard:** Gridded daily observations reflect rainfall accumulated over the 24-hour cycle ending at 08:30 IST of the recorded date. Operational advisories must account for a 24-hour reporting latency in official gridded products.

### 2.2 The Dry-Spell Reset Limitation
The current system employs continuous cumulative summation without dynamic moisture decay resets.
- **The Agronomic Problem:** Consider a scenario where a grid cell receives 45 mm on June 3, followed by 20 consecutive rainless days with high evaporative demand ($\text{ET}_0 \approx 6\text{ mm/day}$), followed by 30 mm on June 24. The cumulative total reaches $75\text{ mm}$. In reality, the moisture from June 3 is completely depleted from the upper 15 cm soil layer. The subsequent 30 mm shower is insufficient to wet the Vertisol seed zone to field capacity.
- **Mitigating Safeguards in MonsoonIQ:**
  1. *Two-Stage Verification Window:* The secondary wet-day persistence requirement prevents isolated older events from being paired with an isolated new event unless they fall within the 5-day verification envelope.
  2. *Active Post-Trigger Dry Break Monitoring:* If an active post-trigger dry spell reaches $\ge 7\text{ days}$, the advisory immediately overrides to `HIGH_RISK` and recommends halting sowing operations.
  3. *Explicit Advisory Warning:* Reports include mandatory notices that cumulative rainfall numbers are precipitation accumulation markers, not direct physical measurements of soil matric potential.
- **Required Production Enhancement:** Transitioning this research prototype into operational agricultural deployment requires coupling the precipitation monitor with a daily 1D bucket or Richards-equation soil-water balance model (e.g., FAO-56 dual crop coefficient or SWAT) to dynamically track Plant Available Water (PAW).

---

## 3. Historical Risk Interpretation & Denominator Reconciliation

### 3.1 Actuarial Climatology vs Live Forecasts
MonsoonIQ explicitly differentiates between **historical empirical conditional frequency** (actuarial risk under 2001–2023 climate) and **real-time weather forecasts**. Historical break probabilities presented in advisories represent the long-term climatological vulnerability of the geographic regime, NOT a deterministic prediction of weather in the subsequent 10 days.

### 3.2 Exact Denominator and Numerator Reconciliation
To eliminate ambiguity, all historical risk statistics reported in the Rain-Shadow regime (Cluster 3) are strictly reconciled against the audited Phase 7.1 baseline dataset:

$$\text{Domain: } 42\text{ grid cells} \times 23\text{ years} = 966\text{ cell-years total}$$

1. **50 mm Triggering Frequency:**
   $$\text{Triggered Cell-Years: } N = 869 \quad (89.96\% \text{ of all cell-years})$$
2. **Post-50 mm Severe Break Risk ($\ge 10\text{ consecutive dry days within } 20\text{ days of trigger}$):**
   $$\text{Severe Breaks Observed: } n = 340$$
   $$\text{Historical Risk: } \frac{340}{869} = 39.13\% \quad (\approx 1 \text{ in } 2.5 \text{ years})$$
3. **75 mm Unreached Frequency (Kharif Failure to Reach Sowing Threshold by July 15):**
   $$\text{Unreached Cell-Years: } n = 199$$
   $$\text{Historical Unreached Rate: } \frac{199}{966} = 20.60\% \quad (\approx 1 \text{ in } 5 \text{ years})$$

> **Audit Confirmation:** The 39.13% desiccation hazard is calculated strictly over triggered cell-years ($N=869$), whereas the 20.60% non-triggering frequency is calculated over total cell-years ($N=966$). The engine strictly presents these as distinct agricultural hazards.

---

## 4. Maritime Heavy-Rainfall Hazard Alerts

### 4.1 Hazard Thresholds
In the Early Maritime regime (Konkan and Western Ghats), intense precipitation poses critical risks of seedbed washout, nursery submergence, and root asphyxiation. The engine enforces:
- **1-Day Extreme Rainfall:** $\ge 100\text{ mm}$
- **3-Day Rolling Rainfall:** $\ge 200\text{ mm}$

### 4.2 Agronomic Terminology Audit
The audit reviewed the condition descriptions in `src/advisory/decision_engine.py`:
- **Condition Name:** `Heavy-Rainfall Hazard Indicator (Potential Waterlogging / Drainage Risk)`
- **Evaluation Disclaimer:** *"Precipitation hazard threshold: no single day >= 100 mm and no 3-day sum >= 200 mm (Heavy-rainfall hazard indicator, not confirmed field waterlogging)"*
- **Reasoning Text:** *"Precipitation hazard: ... High hazard of nursery submergence, topsoil erosion, and drainage congestion. Ensure surface drainage channels are cleared before field operations."*

The engine correctly treats these metrics as **precipitation hazard indicators**, avoiding claims of confirmed field inundation (which depends on local slope, ditch maintenance, and micro-topography). Automated sowing/transplanting mandates are strictly avoided.

---

## 5. Data Provenance & Real-Time Integrity

### 5.1 Formal Provenance Attribution
To prevent confusing synthetic demonstration runs with live automated weather station (AWS) feeds, an explicit `data_provenance` attribute was added to the `AdvisoryReport` data class. Supported categories:
1. `Historical Replay (IMD 0.25° Gridded 2001-2023)`
2. `Simulated Test Data` (Default for synthetic demonstration scenarios)
3. `Observed Weather Station (AWS Mahavedh)`
4. `NWP Forecast Model (IMD GFS / NCMRWF Unified Model)`

### 5.2 Clarification of Demonstration Scenarios
All demonstration scenarios in `scripts/run_advisory_engine.py` are explicitly marked with `data_provenance = "Simulated Test Data"`. The generated JSON (`outputs/advisory/sample_advisories.json`) reflects these synthetic stress scenarios designed to validate edge-case engine logic.

---

## 6. Agricultural Recommendations & July 15 Contingency Audit

### 6.1 State Agricultural University (SAU) Source Citations
All crop recommendations, soil depth strata, and contingency measures were audited against published Package of Practices (POP) from Maharashtra SAUs and ICAR-CRIDA:

| Institution | Mandate Agro-Ecological Region | Primary Referenced Varieties | Audited Sowing Window |
| :--- | :--- | :--- | :--- |
| **MPKV Rahuri** | Scarcity Zone & Western Maharashtra Vertisols | Pearl Millet (Phule Aadishakti), Pigeonpea (Phule Rajeshwari), Sunflower (Phule Bhaskar), Horsegram (Sina, Man), Cowpea (Phule Pandhari) | June 15 – July 7 (Contingency up to July 31) |
| **Dr. PDKV Akola** | Vidarbha Core Interior Vertisols | Soybean (JS-335, JS-93-05), Cotton (Bt hybrids), Pigeonpea (Asha, Maruti), Sesame (AKT-64) | June 20 – July 15 |
| **VNMKV Parbhani** | Marathwada Semi-Arid Transition | Soybean (MAUS-71, MAUS-81), Cotton (Bt), Black gram (TAU-1), Green gram (BM-2003-2) | June 20 – July 10 |
| **Dr. BSKKV Dapoli** | Konkan Maritime High-Rainfall Zone | Rice (Karjat-3, Ratnagiri-1, Ratnagiri-24), Finger Millet (Dapoli-1) | June 5 – June 25 (Transplanting 21-day nursery) |
| **ICAR-CRIDA** | National Dryland Agriculture Contingency | Broad Bed Furrow (BBF), in-situ moisture conservation, seed hardening | Pan-Maharashtra Drylands |

### 6.2 Soil Depth Stratification
Recommendations in the engine are strictly stratified by soil water holding capacity:
- **Shallow Soils ($< 30\text{ cm}$):** Available Water Capacity (AWC) $< 50\text{ mm/m}$. Sowing restricted to low-water-demand crops (Pearl millet, Horsegram, Moth bean).
- **Medium Soils ($30\text{--}60\text{ cm}$):** AWC $100\text{--}150\text{ mm/m}$. Suitable for Soybean, Cotton, Pigeonpea.
- **Deep Vertisols ($> 60\text{ cm}$):** AWC $180\text{--}220\text{ mm/m}$. Requires $\ge 75\text{ mm}$ to adequately wet the swelling clay root zone ($15\text{--}20\text{ cm}$).

### 6.3 Post-July 15 Contingency Handling Audit
The audit verified the decision branch executed when rainfall criteria remain unmet by July 15:
- **Engine Behavior:** The engine issues an advisory in `HIGH_RISK` state titled *"SOWING WINDOW DELAYED PAST JULY 15"*.
- **Contingency Guidance:** Recommends aborting long-duration primary crops (e.g., Bt cotton, long-duration soybean) and transitioning to drought-hardy pulses, oilseeds, or intercropping systems as approved by MPKV and VNMKV.
- **Absence of Automated Cancellation Orders:** **VERIFIED.** The engine does NOT issue an automated "Kharif cancellation order". It provides actionable contingency alternatives and recommends consultation with local Krishi Vigyan Kendras (KVKs).

---

## 7. Documented Operational Limitations

To maintain scientific integrity and prevent agricultural misinterpretation, the following limitations are formally documented:

1. **Precipitation Marker vs Physical Soil Moisture:** Rainfall thresholds ($50\text{ mm}$ and $75\text{ mm}$) are historical empirical proxies for topsoil wetting. They do not measure physical soil water matric potential or hydraulic conductivity across heterogeneous soil series.
2. **Evaporative Decay Absence:** The lack of a daily evapotranspiration deduction in the continuous cumulative sum is a known limitation. While mitigated by the 5-day verification rule and post-trigger dry spell monitors, a 1D soil-water balance model is required for production agronomic services.
3. **Climatological Actuarial Risk vs Live Weather:** The reported $39.13\%$ post-trigger dry break frequency is an empirical climatological baseline ($2001\text{--}2023$). It must not be interpreted as an ensemble numerical weather prediction (NWP) forecast for an active season.
4. **Precipitation Hazard Indicators vs Inundation:** The $100\text{ mm}$ 1-day and $200\text{ mm}$ 3-day thresholds identify heavy-rainfall hazards. Micro-topography, ditch maintenance, and slope drainage must be evaluated at the field scale by farm operators.
5. **Data Completeness & Latency:** Automated advisories require at least $90\%$ data completeness and complete observations during the 5-day verification window. AWS telemetry dropouts must trigger `INSUFFICIENT_DATA`.

---

## 8. Summary of Audit Deliverables

- **Audit Script:** [audit_advisory_logic.py](file:///c:/Ashwell/Project/SEM%204/ML%20Project/MonsoonPred/scripts/audit_advisory_logic.py)
- **Pytest Audit Suite:** [test_advisory_audit.py](file:///c:/Ashwell/Project/SEM%204/ML%20Project/MonsoonPred/tests/test_advisory_audit.py) (9/9 passed)
- **Pytest Advisory Engine Suite:** [test_advisory_engine.py](file:///c:/Ashwell/Project/SEM%204/ML%20Project/MonsoonPred/tests/test_advisory_engine.py) (14/14 passed)
- **Audit Summary JSON:** [advisory_logic_audit_summary.json](file:///c:/Ashwell/Project/SEM%204/ML%20Project/MonsoonPred/outputs/advisory/advisory_logic_audit_summary.json)
- **User-Facing Artifact:** [MonsoonIQ-Phase8-1-Audit-Report.md](file:///C:/Users/ashwe/.gemini/antigravity/brain/90c5a344-cf42-4537-8752-4ef7bc6fe643/MonsoonIQ-Phase8-1-Audit-Report.md)

**System Status:** **READY WITH DOCUMENTED LIMITATIONS** for dashboard integration.
