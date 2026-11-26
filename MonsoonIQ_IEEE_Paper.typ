#set document(title: "MonsoonIQ: Hyperlocal Monsoon Onset Dynamics and Regime-Aware Agricultural Advisory Intelligence for Maharashtra, India", author: ("Ashwell Cherian Giji", "Apoorv Dubey"))

#set page(
  paper: "us-letter",
  margin: (top: 19mm, bottom: 25.4mm, left: 15mm, right: 15mm),
  columns: 2,
)

#set text(
  font: "Times New Roman",
  size: 10pt,
  hyphenate: true,
)

#set par(
  justify: true,
  leading: 0.58em,
  first-line-indent: 1.25em,
)

// Document Header (Spans both columns)
#place(
  top,
  float: true,
  scope: "parent",
  clearance: 1.5em,
)[
  #align(center)[
    #v(-8pt)
    #text(size: 18pt, weight: "bold")[
      MonsoonIQ: Hyperlocal Monsoon Onset Dynamics and Regime-Aware Agricultural Advisory Intelligence for Maharashtra, India
    ]
    #v(8pt)
    #grid(
      columns: (1fr, 1fr),
      gutter: 20pt,
      align(center)[
        #text(size: 11pt, weight: "bold")[Ashwell Cherian Giji]\
        #text(size: 9pt, style: "italic")[School of AI and ML and Emerging Technologies]\
        #text(size: 9pt, style: "italic")[Lovely Professional University]\
        #text(size: 9pt)[Phagwara, Punjab, India]\
        #text(size: 9pt, font: "Courier")[ashwellcheriangiji\@gmail.com]
      ],
      align(center)[
        #text(size: 11pt, weight: "bold")[Apoorv Dubey]\
        #text(size: 9pt, style: "italic")[Department of Computer Science and Engineering,]\
        #text(size: 9pt, style: "italic")[School of Computer Science and Engineering]\
        #text(size: 9pt, style: "italic")[Lovely Professional University]\
        #text(size: 9pt)[Phagwara, Punjab, India]\
        #text(size: 9pt, font: "Courier")[apoorvdubey\@gmail.com]
      ]
    )
    #v(10pt)
  ]

  #rect(
    fill: none,
    stroke: none,
    inset: (x: 18pt, y: 0pt),
  )[
    #text(size: 9pt, weight: "bold")[_Abstract_---]
    #text(size: 9pt)[
      In rainfed tropical agriculture, determining the optimal Kharif sowing window is critical to preventing crop failure. In Maharashtra, India, official India Meteorological Department (IMD) monsoon declarations operate at macro-subdivision scales, obscuring extreme orographic and agro-climatic gradients. Farmers adopting simplistic rainfall accumulation thresholds (e.g., sowing after 50 mm of rain) frequently incur severe seedling desiccation when early showers are followed by prolonged dry spells. This paper presents *MonsoonIQ*, an end-to-end computational framework that transforms 23 years (2001--2023) of high-resolution ($0.25^degree times 0.25^degree$) IMD gridded daily rainfall data across 419 valid onshore grid cells (9,637 cell-years) into actionable agricultural intelligence. We propose an objective two-stage Local Sustained Onset Detection Algorithm that filters pre-monsoon convective bursts from genuine monsoonal progression, confirming 9,606 onset events (99.68% detection rate). Using nine engineered onset-dynamics features, unsupervised machine learning ($K$-Means, $K=4$) identifies four distinct agro-climatic regimes: Core Interior Synchronized (51.31%), Interior Semi-Arid Transition (23.15%), Early Maritime & Western Ghats (15.51%), and Rain-Shadow High-Volatility (10.02%). Clustering robustness is validated via Silhouette Analysis (0.2987), Davies-Bouldin Index (1.1948), cross-algorithm agreement with Agglomerative Hierarchical clustering (87.83% agreement, $upright("ARI")=0.6803$), and spatial autocorrelation (Moran's $I > 0.50$, contiguity 75.30%). Crucially, we uncover the ``Rain-Shadow Anomaly'', wherein arid rain-shadow cells satisfy a 50 mm trigger 4--7 days earlier than wetter zones due to convective bursts, yet 39.13% of these trigger events are followed by catastrophic $gt.eq 10$-day dry breaks. To mitigate this hazard, MonsoonIQ implements a regime-aware advisory state machine enforcing an audited 75 mm threshold, a multi-day persistence requirement, and an active wetting-cycle reset mechanism that discounts evaporated moisture following $gt.eq 10$-day dry spells. Evaluated across historical and simulated scenarios without promising deceptive ``safe to sow'' guarantees, MonsoonIQ demonstrates how unsupervised machine learning and empirical agrometeorology bridge the gap between raw climate grids and farm-level risk management.
    ]
    #v(4pt)
    #text(size: 9pt, weight: "bold")[_Index Terms_---]
    #text(size: 9pt)[Monsoon Onset Detection, Rainfall Analysis, K-Means Clustering, Agricultural Decision Support, Maharashtra, Geospatial Analytics, Dry Spell Analysis, Climate Intelligence.]
    #v(8pt)
  ]
]

// Section Headings Styling
#show heading.where(level: 1): it => block(
  above: 12pt, below: 8pt,
  text(size: 10pt, weight: "bold")[
    #align(center)[#smallcaps(it.body)]
  ]
)

#show heading.where(level: 2): it => block(
  above: 9pt, below: 5pt,
  text(size: 10pt, weight: "bold", style: "italic")[
    #it.body
  ]
)

= I. Introduction

#let initial = text(size: 22pt, font: "Times New Roman")[R]
#initial *ainfed* agriculture supports over 60% of India's cultivated area and underpins the livelihoods of millions of smallholder farmers across the semi-arid tropics [1]. In the state of Maharashtra, the southwest monsoon (June--September, JJAS) accounts for upwards of 80% of annual precipitation [2]. Timing the commencement of Kharif (monsoon-season) crop sowing is the single most consequential economic decision a dryland farmer makes. Sowing too early risks fatal seedling mortality if initial rains are followed by a prolonged dry spell; sowing too late shortens the vegetative growth window, induces flowering delays, and exposes crops to terminal moisture stress during September grain-filling [3], [4].

Historically, official monsoon onset declarations issued by the India Meteorological Department (IMD) have focused on large-scale synoptic criteria: kinetic energy increases in lower-tropospheric winds (850 hPa), depth of westerlies, and out-going longwave radiation (OLR) thresholds over the southeastern Arabian Sea and Kerala [5], [6]. While vital for macroeconomic and national planning, these regional declarations are fundamentally unsuited for local farm-level operations [7]. Maharashtra spans a dramatic orographic barrier in the Western Ghats (Sahyadri range), dropping precipitously into an arid rain-shadow plateau before transitioning into the continental black-soil plains of Marathwada and Vidarbha [2], [8]. Consequently, declaring that the ``monsoon has covered Maharashtra'' offers zero operational guidance to a Vertisol farmer in Solapur experiencing an isolated convective burst compared to a coastal rice farmer in Ratnagiri receiving continuous orographic rain.

In response to regional declarations, public extension services have traditionally recommended generic empirical rules, most notably advising farmers to sow once cumulative seasonal rainfall achieves 50 mm [9]. However, empirical evidence demonstrates that topsoil wetting in cracking clay soils (Vertisols) requires substantially more moisture under high pre-monsoon evaporative demand ($upright("ET")_0 > 5" mm/day"$) [10], [11]. Simplistic 50 mm accumulation counters fail to differentiate between sustained monsoonal inflow and transient pre-monsoon thunderstorms, leading to widespread seed desiccation.

To address these limitations, this paper presents *MonsoonIQ*, a comprehensive climatological data engineering and machine learning framework. The primary contributions of this work are:
1. *Hyperlocal Climatological Pipeline:* Standardization of 23 years (2001--2023) of IMD $0.25^degree times 0.25^degree$ daily gridded rainfall across 419 valid onshore Maharashtra cells (9,637 cell-years), preserving raw missing values without artificial zero-imputation.
2. *Local Sustained Onset Algorithm:* Formulation of a two-stage detection algorithm combining running-window accumulation triggers with post-candidate dry-spell filtering, identifying 9,606 confirmed onsets.
3. *Unsupervised Regime Discovery:* Unsupervised clustering ($K$-Means, $K=4$) over nine engineered onset features, identifying four distinct agro-climatic zones validated via cross-algorithm benchmarks, bootstrap resampling, and spatial contiguity metrics.
4. *Empirical Resolution of the Rain-Shadow Paradox:* Detailed mathematical investigation of why arid rain-shadow cells hit simplistic 50 mm triggers prematurely, proving that 39.13% of such triggers encounter fatal $gt.eq 10$-day breaks.
5. *Audited Sowing Advisory Engine:* Implementation of a transparent four-state decision machine incorporating active wetting-cycle resets and strict prohibition of misleading ``safe to sow'' guarantees.

#figure(
  image("figures/fig_system_architecture.png", width: 100%),
  caption: [MonsoonIQ overall system architecture spanning data ingestion, local onset detection, unsupervised ML clustering, decision logic, and presentation layers.],
) <fig_arch>

= II. Related Work

== A. Monsoon Onset Climatology and Local Detection
The onset of the southwest monsoon has been investigated extensively at the continental scale. Ananthakrishnan and Soman [5] established the foundational statistical definition of onset over Kerala based on sharp transitions in 5-day daily rainfall averages. Soman and Kumar [12] and Joseph et al. [13] analyzed the synoptic-scale circulation features accompanying onset transitions across peninsular India. Rajeevan et al. [14] and Pai et al. [6] developed the high-resolution ($0.25^degree times 0.25^degree$) daily gridded rainfall datasets that enabled localized spatial analysis. However, translating synoptic onset into localized agronomic criteria remains challenging; localized definitions must distinguish between transient convective pre-monsoon showers and sustained monsoonal westerlies [2].

== B. Rainfall Variability and Dry Spells in Maharashtra
Rainfall variability in peninsular India is strongly modulated by the Western Ghats orography. Rao et al. [4] analyzed dry spells in the rain-shadow districts of Maharashtra (Solapur, Ahmednagar), demonstrating that early Kharif dry spells exceeding 10 days occur in over 70% of seasons. Wani et al. [8] investigated soil-water balance in semi-arid Vertisols, emphasizing that cracking black soils exhibit high water-holding capacities but require deep wetting pulses ($gt.eq 75" mm"$) to support seedling emergence without surface crusting. Institutional guidelines from ICAR-CRIDA [9] and MPKV Rahuri [11] highlight the necessity of contingency planning when sowing is delayed past July 15.

== C. Machine Learning in Climate Regime Discovery
Unsupervised clustering techniques have been widely applied to climate time series for regionalization. MacQueen's $K$-Means algorithm [15] remains the benchmark for climatological partitioning due to its computational scalability and spherical variance minimization. Cluster validation frameworks proposed by Rousseeuw (Silhouette Analysis) [16], Davies and Bouldin [17], and Caliński and Harabasz [18] provide quantitative criteria for selecting cluster numbers. Spatial autocorrelation measures, notably Moran's $I$ [19], verify that statistical clusters exhibit physical spatial coherence. In agro-meteorology, Stone and Meinke [20] and Hansen et al. [7] emphasized that climate advisory systems must communicate uncertainty transparently rather than delivering deterministic guarantees.

= III. Study Area and Dataset

== A. Geographical and Climatic Profile of Maharashtra
Maharashtra covers an area of 307,713 $upright("km")^2$ in western and central India ($15.75^degree upright("N")$--$22.00^degree upright("N")$, $72.75^degree upright("E")$--$80.75^degree upright("E")$). The state exhibits three physiographic provinces:
1. *The Konkan Coastal Lowlands:* A narrow strip bounded by the Arabian Sea and the Western Ghats, receiving intense orographic precipitation ($>2,800" mm"$ annually).
2. *The Western Ghats (Sahyadri):* A continuous escarpment rising to 1,200--1,600 m, inducing extreme leeward precipitation dissipation.
3. *The Deccan Plateau:* Comprising the arid Rain-Shadow belt (Solapur, Ahmednagar), the Marathwada semi-arid transition zone, and the eastern Vidarbha plains.

#figure(
  image("figures/fig_annual_rainfall.png", width: 100%),
  caption: [Spatial distribution of climatological mean annual rainfall across Maharashtra (2001--2023), highlighting the Western Ghats orographic gradient.],
) <fig_rain>

#figure(
  image("figures/fig_monthly_climatology.png", width: 100%),
  caption: [Climatological monthly rainfall distribution across meteorological subdivisions, highlighting rainfall concentration in July and August.],
) <fig_month>

== B. IMD High-Resolution Gridded Dataset
This research utilizes the India Meteorological Department (IMD) $0.25^degree times 0.25^degree$ daily gridded rainfall product [6]. The dataset interpolates observations from over 6,500 surface rain-gauge stations across India using the Shepard local-weighting interpolation scheme:
- *Spatial Domain:* Bounding box of 28 latitudes $times$ 35 longitudes (980 total grid cells).
- *Masking:* Spatial masking against official Survey of India boundary vectors yields exactly *419 valid onshore land cells* inside Maharashtra (50 marine cells and 511 non-Maharashtra terrestrial cells excluded).
- *Temporal Span:* 23 consecutive years from January 1, 2001 to December 31, 2023 (8,400 consecutive calendar days per grid cell).
- *Data Volume:* $419 times 8,400 = 3,519,600$ terrestrial daily observations. NetCDF4 storage size is 14.35 MB.
- *Missing-Data Preservation:* Terrestrial observations maintain 0.0% missing values. Marine cells are encoded strictly as IEEE `NaN`. No artificial zero-filling or synthetic smoothing is applied.

= IV. Proposed Methodology

The MonsoonIQ methodology comprises five computational modules: local sustained onset detection, feature engineering, unsupervised clustering, sowing trigger sensitivity auditing, and the regime-aware advisory state machine.

== A. Local Sustained Onset Detection Algorithm
Let $R_(c,y)(t)$ denote daily rainfall (in mm) at grid cell $c$ on day-of-year $t in [1, 365]$ in year $y$. The algorithm initiates monitoring on June 1 ($t = 152$, non-leap year) following a pre-monsoon buffer starting May 15 ($t = 135$).

#figure(
  image("figures/fig_onset_detection_workflow.png", width: 95%),
  caption: [Flowchart of the two-stage Local Sustained Onset Detection Algorithm, separating sustained monsoonal progression from transient convective bursts.],
) <fig_onset_wf>

=== 1) Candidate Trigger Identification
A candidate onset date $t^* in [152, 212]$ (June 1 to July 31) is triggered on the first day satisfying a multi-day accumulation pulse:
$ sum_(k=0)^(W-1) R_(c,y)(t - k) gt.eq Theta_("pulse") quad upright("and") quad R_(c,y)(t) gt.eq R_("wet") $
where $W = 5" days"$, $Theta_("pulse") = 25.0" mm"$, and $R_("wet") = 2.5" mm"$ (IMD rainy day threshold).

=== 2) False Onset Filtering
To reject transient pre-monsoon convective thunderstorms, candidate $t^*$ is evaluated over a subsequent verification window $V = 15" days"$:
$ L_("dry")(t^*) = max_(t^* < tau lt.eq t^* + V) { sum_(i=0)^(d-1) bb(I)(R_(c,y)(tau + i) < R_("wet")) } $
where $bb(I)(dot)$ is the indicator function. The candidate is classified as a _false onset_ and rejected if:
$ L_("dry")(t^*) gt.eq L_("crit") quad (L_("crit") = 10" days") $
If rejected, the search advances to $t^* + 1$. If $L_("dry")(t^*) < L_("crit")$, $t^*$ is confirmed as the _Local Sustained Onset Date_ $D_(c,y)$. If no date satisfies the criteria by July 31 ($t=212$), the season is recorded as a non-detection event ($D_(c,y) = upright("NaN")$).

== B. Agro-Climatic Feature Engineering
To capture multidimensional onset dynamics, each grid cell $c$ is mapped to a 9-dimensional feature vector $bold(x)_c in bb(R)^9$ computed across the 23-year historical record:
1. *Median Onset DOY ($tilde(D)_c$):* Median confirmed onset day of year.
2. *Mean Onset DOY ($macron(D)_c$):* Arithmetic mean onset day of year.
3. *Onset Std. Dev. ($sigma_(D,c)$):* Interannual temporal variability:
$ sigma_(D,c) = sqrt(1 / (N_y - 1) sum_(y=1)^(N_y) (D_(c,y) - macron(D)_c)^2) $
4. *Interquartile Range ($upright("IQR")_c$):* Spread between 75th and 25th percentiles: $Q_3(D_c) - Q_1(D_c)$.
5. *Early Onset Frequency ($f_("early",c}$):* Fraction of years with $D_(c,y) lt.eq 156$ (June 5).
6. *Delayed Onset Frequency ($f_("delayed",c}$):* Fraction of years with $D_(c,y) gt.eq 176$ (June 25).
7. *Candidate Rejection Frequency ($f_("reject",c}$):* Mean annual rate of false onset candidate rejections:
$ f_("reject",c) = 1 / N_y sum_(y=1)^(N_y) N_("rejected",c,y) $
8. *Mean Max Early Dry Spell ($macron(L)_("dry",c}$):* Climatological mean length of the maximum consecutive dry spell in June.
9. *Onset Detection Frequency ($f_("det",c}$):* Proportion of years with a confirmed onset event: $f_("det",c) = 1 / N_y sum_(y=1)^(N_y) bb(I)(D_(c,y) != upright("NaN"))$.

== C. Unsupervised Clustering and Validation Metrics
Feature matrix $bold(X) in bb(R)^(419 times 9)$ is standardized using $z$-score normalization: $bold(Z) = (bold(X) - bold(mu)) / bold(sigma)$.

=== 1) K-Means Clustering
$K$-Means partitions the 419 cells into $K$ disjoint clusters $cal(C) = {C_1, dots, C_K}$ by minimizing within-cluster sum of squares (WCSS):
$ J = sum_(k=1)^K sum_(bold(z)_i in C_k) ||bold(z)_i - bold(m)_k||^2 $
where $bold(m)_k = 1 / (|C_k|) sum_(bold(z)_i in C_k) bold(z)_i$. We execute $K$-Means with $K=4$, $n_("init") = 50$, and maximum iterations $= 300$.

=== 2) Validation Metrics
Cluster quality is quantitatively assessed using:
- *Silhouette Coefficient ($S$):* For cell $i$, $s(i) = (b(i) - a(i)) / (max(a(i), b(i)))$, where $a(i)$ is mean intra-cluster distance and $b(i)$ is minimum mean inter-cluster distance [16].
- *Davies-Bouldin Index ($D B$):* Average similarity ratio between each cluster and its most similar counterpart [17]:
$ D B = 1 / K sum_(i=1)^K max_(j != i) { (s_i + s_j) / d(bold(m)_i, bold(m)_j) } $
- *Caliński-Harabasz Index ($C H$):* Ratio of between-cluster dispersion to within-cluster dispersion [18].
- *Adjusted Rand Index (ARI):* Compares cluster partition stability against alternative clustering algorithms (Agglomerative Hierarchical, Ward linkage) and bootstrap subsampling [21].

== D. Sowing Advisory Decision Engine & Accumulation Semantics
The advisory engine operates as a deterministic finite-state machine evaluating daily rainfall vectors $bold(R)_(c,y)$ up to date $t_("as_of")$.

=== 1) Active Wetting-Cycle Reset Rule
In semi-arid Vertisols, high pre-monsoon potential evapotranspiration ($upright("ET")_0 > 5" mm/day"$) rapidly desiccates topsoil moisture [10]. When an intervening dry break $Delta t_("dry") gt.eq 10$ consecutive days occurs between early rain and recent showers, moisture from earlier rain is treated as fully evaporated. The effective cumulative rainfall counter $R_("eff")$ resets:
$ R_("eff")(t) = cases(
  0.0" mm", & "if " L_("consec_dry")(t) gt.eq 10,
  sum_(tau = t_("reset"))^t R_(c,y)(tau), & "otherwise"
) $
where $t_("reset")$ marks the resumption of rainfall following the break.

=== 2) Advisory State Logic
The engine evaluates four distinct states:
1. *INSUFFICIENT DATA (Gray):* Triggered if data completeness is $<80%$ or if missing observations occur within the 5-day verification window.
2. *CAUTION (Yellow):* Sowing criteria pending: cumulative rainfall is below threshold ($<75" mm"$ for rain-shadow; $<50" mm"$ for maritime), or secondary persistence showers are awaiting verification.
3. *HIGH RISK (Red):* Unfavorable conditions: active post-trigger dry break $gt.eq 7" days"$, or evaluation date is past July 15 with severe rainfall deficit.
4. *RAINFALL CRITERIA MET (Green):* Regime threshold ($gt.eq 75" mm"$ or $gt.eq 50" mm"$) satisfied in the active wetting cycle, verified by $gt.eq 2$ wet days within 5 days, without an ongoing dry break.

#figure(
  image("figures/fig_advisory_state_machine.png", width: 100%),
  caption: [Advisory Engine State Machine integrating active wetting-cycle resets and 4-state risk management.],
) <fig_adv_state>

= V. Experimental Setup

Experiments were executed in Python 3.12 using `numpy` (1.26), `scipy` (1.13), `xarray` (2024.03), `scikit-learn` (1.4), and `geopandas` (0.14). 
- *Reproducibility:* Random seeds in all estimators ($K$-Means, bootstrap resamplers) were fixed at `random_state=42`.
- *Test Suite:* The framework is protected by an extensive automated test suite comprising 182 unit and integration tests executed via `pytest`.

= VI. Results and Discussion

== A. Local Onset Climatology and Spatial Variability
Across the 23-year historical record, the Local Sustained Onset Algorithm successfully identified 9,606 onset dates across 9,637 cell-seasons (99.68% detection efficiency). Only 31 cell-years exhibited non-detection, confined to extreme drought seasons (e.g., 2015 and 2018 in Solapur).

As illustrated in Fig. 6, median onset dates advance from June 1--June 5 (DOY 152--156) in southern Konkan to June 20--June 25 (DOY 171--176) in northern Marathwada and Khandesh. However, onset variability ($sigma$) displays non-uniform spatial structuring (Fig. 7). In the coastal Maritime zone, $sigma$ is minimal ($plus.minus 8.4" days"$), reflecting dependable monsoonal arrival. Conversely, in the rain-shadow and interior semi-arid belts, onset variability surges to $plus.minus 14.2$ and $plus.minus 16.2" days"$, introducing substantial agricultural uncertainty.

#figure(
  image("figures/fig_median_onset.png", width: 100%),
  caption: [Spatial distribution of median local monsoon onset day of year (2001--2023), depicting southwest-to-northeast monsoonal progression.],
) <fig_med_onset>

#figure(
  image("figures/fig_onset_variability.png", width: 100%),
  caption: [Spatial map of onset standard deviation ($sigma$, in days), highlighting high interannual volatility in the rain-shadow and transition zones.],
) <fig_onset_var>

#figure(
  image("figures/fig_regime_map.png", width: 100%),
  caption: [The Four Discovered Agro-Climatic Monsoon Onset Regimes across Maharashtra identified via $K$-Means ($K=4$).],
) <fig_regime>

== B. Regime Characterization ($K$-Means $K=4$)
The $K$-Means clustering algorithm partitions Maharashtra's 419 cells into four coherent agro-climatic regimes (Fig. 8 and Table 1).

#table(
  columns: (1.5fr, 0.8fr, 0.8fr, 1fr, 1fr, 1.2fr),
  stroke: (x, y) => if y == 0 { (bottom: 1pt + black) } else if y == 5 { (top: 1pt + black) } else { none },
  align: (left, center, center, center, center, center),
  [ *Regime Name* ], [ *Cells* ], [ *Share* ], [ *Median Onset* ], [ *Onset $sigma$* ], [ *Post-50mm Break* ],
  [ *0: Core Interior* ], [ 215 ], [ 51.3% ], [ Jun 12 (163) ], [ $plus.minus 10.7$ d ], [ 12.5% ],
  [ *1: Rain-Shadow* ], [ 42 ], [ 10.0% ], [ Jun 11 (162) ], [ $plus.minus 14.2$ d ], [ *39.1%* ],
  [ *2: Early Maritime* ], [ 65 ], [ 15.5% ], [ Jun 07 (158) ], [ $plus.minus 8.4$ d ], [ 7.0% ],
  [ *3: Transition* ], [ 97 ], [ 23.2% ], [ Jun 17 (168) ], [ $plus.minus 16.2$ d ], [ 25.0% ],
  [ *Maharashtra* ], [ *419* ], [ *100%* ], [ *Jun 11 (162)* ], [ *$plus.minus 12.4$ d* ], [ *16.9%* ],
)

=== 1) Regime 0: Core Interior Synchronized (51.31%)
Dominating Vidarbha and eastern Marathwada (215 cells), this regime represents the agrarian heartland of Maharashtra's soybean and cotton production. It exhibits moderate onset timing (median June 12) with low variance ($sigma = plus.minus 10.7" d"$) and robust June rainfall ($168.3" mm"$). Post-trigger 10-day dry break probability is low ($12.52%$), confirming high sowing reliability.

=== 2) Regime 1: Rain-Shadow High-Volatility (10.02%)
Spanning 42 grid cells in eastern Pune, Ahmednagar, and Solapur, this regime represents the critical risk zone. Despite low June rainfall ($106.9" mm"$), it exhibits high coefficient of variation ($66.8%$) and extreme post-trigger dry spell vulnerability (39.13%).

=== 3) Regime 2: Early Maritime & Western Ghats (15.51%)
Comprising 65 coastal and Ghat cells, this regime receives massive orographic rainfall ($486.3" mm"$ in June). Onset is earliest (June 7) and most stable ($sigma = plus.minus 8.4" d"$). Break risk is minimal ($7.04%$), but drainage and waterlogging represent primary agronomic hazards.

=== 4) Regime 3: Interior Semi-Arid Transition (23.15%)
Covering 97 cells across western Marathwada and Khandesh, this regime suffers the latest median onset (June 17) and highest temporal variability ($sigma = plus.minus 16.2" d"$), with $19.41%$ of cell-years experiencing sowing delays past July 1.

#figure(
  image("figures/fig_clustering_metrics.png", width: 100%),
  caption: [Clustering validation diagnostics: (a) K-Means Elbow inertia curve, and (b) Silhouette coefficient across cluster counts $K in [2, 8]$.],
) <fig_metrics>

== C. Cluster Validation and Stability Analysis
As shown in Fig. 9, $K=3$ achieves a higher silhouette score ($0.3484$) than $K=4$ ($0.2987$). However, cross-tabulation reveals that $K=3$ merges the 42 rain-shadow cells directly into the Semi-Arid Transition cluster. Selecting $K=4$ isolates this high-risk zone, providing vital domain-specific utility. 

Validation against Agglomerative Hierarchical clustering demonstrates 87.83% exact point-by-point agreement (368/419 cells) with an Adjusted Rand Index of $0.6803$. The 42 volatile cells in $K$-Means are assigned strictly to Volatile (30 cells) and Transition (12 cells) in Hierarchical clustering, validating cluster boundary stability. Spatial contiguity exceeds 75.3%, and Moran's $I$ across all features exceeds $0.50$ ($p < 0.001$), confirming that clusters reflect continuous geographical domains rather than statistical artifacts.

== D. Investigation of the Rain-Shadow Sowing Paradox
A conventional 50 mm cumulative sowing trigger produces a profound paradox (Fig. 10 and Fig. 11). 

In the Rain-Shadow regime, the median calendar date for achieving 50 mm cumulative rain is *DOY 165 (June 14)*---which is *4 days earlier* than the Core Interior (DOY 169, June 18) and *7 days earlier* than the Semi-Arid Transition (DOY 172, June 21). 

#figure(
  image("figures/fig_sowing_sensitivity.png", width: 100%),
  caption: [Sensitivity analysis of cumulative sowing trigger thresholds (25, 50, 75, 100 mm) across the four discovered regimes.],
) <fig_sens>

#figure(
  image("figures/fig_rain_shadow_anomaly.png", width: 100%),
  caption: [Empirical audit of the Rain-Shadow Anomaly: early 50 mm trigger satisfaction vs. severe post-trigger dry-break probability.],
) <fig_anomaly>

#figure(
  image("figures/fig_delayed_sowing.png", width: 100%),
  caption: [Frequency of sowing opportunity delay past July 1 and failure to reach threshold by July 15 across regimes.],
) <fig_delay>

Our empirical audit reveals that intense pre-monsoon convective heating in early June generates localized thunderstorms (single-day events exceeding 50 mm). Farmers sowing immediately upon reaching 50 mm suffer catastrophic consequences:
- *39.13% of 50 mm trigger events in the Rain-Shadow are followed by an immediate $gt.eq 10$-day severe dry break* (and 65.59% encounter a $gt.eq 7$-day break).
- Topsoil moisture in cracking Vertisols evaporates within 4 days under pre-monsoon temperatures ($>38^degree upright("C")$, $upright("ET")_0 > 5" mm/day"$), inducing total seed desiccation.
- Increasing the threshold to *75 mm* coupled with a *two-stage persistence rule* ($gt.eq 2$ rainy days within 5 days) successfully filters 82% of false convective bursts, ensuring root-zone saturation.
- Furthermore, 20.60% of cell-years in the Rain-Shadow fail to achieve 75 mm by July 15 (Fig. 12), requiring automated contingency advisory switching.

= VII. System Architecture and Research Dashboard

MonsoonIQ is integrated into an interactive web dashboard engineered with Streamlit, Plotly, Folium, and GeoPandas. The presentation layer follows a clean, modern meteorological design language featuring elevated white cards, responsive metrics, and a place-first grid-cell selector:
$ upright("{district} · {cell_id} · {latitude}")^degree upright("N, {longitude}")^degree upright("E") $
with clean fallback for missing metadata. Users can simulate historical replays across any year (2001--2023), inspect daily rainfall bar charts, review year-by-year onset timelines, evaluate regime boxplots, and simulate the real-time advisory engine with date sliders.

= VIII. Limitations

To maintain scientific honesty, several limitations must be noted:
1. *Spatial Resolution Limits:* IMD $0.25^degree times 0.25^degree$ gridded data ($approx 27.5" km"$) represents smoothed areal averages, not farm-specific microclimate observations.
2. *Soil Moisture Proxy:* Gridded rainfall accumulation is an empirical proxy for topsoil wetting, not direct sensor-measured volumetric water content.
3. *Heuristic Wetting Reset:* The 10-day evaporative reset rule is an empirical heuristic, not a full 1D Richards equation soil-water balance model.
4. *Climatological Nature:* Historical break probabilities reflect 23-year climatology, not live numerical weather prediction (NWP) forecasts.

= IX. Conclusion and Future Scope

MonsoonIQ establishes that broad, regional monsoon declarations are inadequate for rainfed agricultural decision-making in topographically diverse regions like Maharashtra. By coupling objective local sustained onset detection with unsupervised machine learning ($K$-Means $K=4$), this research discovered four distinct agro-climatic regimes and resolved the dangerous Rain-Shadow Sowing Paradox. The audited regime-aware advisory engine enforces audited wetting thresholds, active wetting-cycle resets, and transparent risk communications, eliminating misleading ``safe to sow'' claims.

Future research will focus on integrating real-time IMD GFS/NCUM weather forecasts, embedding physical FAO-56 daily soil-water balance equations parameterized with digital soil texture maps, and partnering with local Krishi Vigyan Kendras (KVKs) and state agricultural universities (MPKV, PDKV, VNMKV) for on-farm field validation across Kharif seasons.

= References

#set text(size: 8.5pt)
#set par(first-line-indent: 0pt, hanging-indent: 1.5em)

[1] M. V. K. Sivakumar, H. P. Das, and O. Brunini, "Impacts of present and future climate variability and change on agriculture and forestry in the arid and semi-arid tropics," _Climatic Change_, vol. 70, no. 1, pp. 31--72, 2005.

[2] S. Gadgil, "The Indian monsoon and its variability," _Annual Review of Earth and Planetary Sciences_, vol. 31, no. 1, pp. 429--467, 2003.

[3] S. Gadgil and P. R. S. Rao, "Farming strategies for a variable climate," _Current Science_, vol. 78, no. 10, pp. 1203--1215, 2000.

[4] V. U. M. Rao, B. B. Rao, I. Khandgonda, A. V. M. S. Rao, and P. V. Kumar, "Rainfall variability and dry spells in rain-shadow districts of Maharashtra," _Journal of Agrometeorology_, vol. 15, no. 2, pp. 124--129, 2013.

[5] R. Ananthakrishnan and M. K. Soman, "The onset of the southwest monsoon over Kerala: 1901--1980," _Journal of Climatology_, vol. 8, no. 3, pp. 283--296, 1988.

[6] D. S. Pai, L. Sridhar, M. Rajeevan, M. Kshirsagar, and V. S. Prasad, "Development of a new high spatial resolution (0.25x0.25) long period (1901--2010) daily gridded rainfall data set over India and its comparison with existing data sets," _Mausam_, vol. 65, no. 1, pp. 1--18, 2014.

[7] J. Hansen, C. Vaughan, D. Kagabo, et al., "Climate services can support African farmers: Climate services for agricultural development," _Climate Services_, vol. 14, pp. 36--44, 2019.

[8] S. P. Wani, P. Pathak, L. S. Jangawad, H. Eswaran, and P. Singh, _Improved management of Vertisols in the semiarid tropics for increased productivity and soil carbon sequestration_, ICRISAT Research Bulletin, Patancheru, India, 2003.

[9] ICAR-CRIDA, _District Agriculture Contingency Plans for Maharashtra: Drought and Dry Spell Management_, Central Research Institute for Dryland Agriculture, Hyderabad, India, 2020.

[10] R. G. Allen, L. S. Pereira, D. Raes, and M. Smith, _Crop evapotranspiration - Guidelines for computing crop water requirements - FAO Irrigation and drainage paper 56_, FAO, Rome, Italy, 1998.

[11] MPKV, _Package of Practices for Kharif Crops: Soil Moisture Conservation and Contingency Planning for Scarcity Zone_, Mahatma Phule Krishi Vidyapeeth, Rahuri, Ahmednagar, Maharashtra, India, 2022.

[12] M. K. Soman and K. K. Kumar, "Space-time evolution of meteorological features associated with the onset of Indian summer monsoon," _Monthly Weather Review_, vol. 121, no. 4, pp. 1177--1194, 1993.

[13] P. V. Joseph, J. K. Eischeid, and R. J. Pyle, "Interannual variability of the onset of the summer monsoon over India and its prediction," _Journal of Climate_, vol. 7, no. 1, pp. 81--105, 1994.

[14] M. Rajeevan, J. Bhate, J. D. Kale, and B. Lal, "High resolution daily gridded rainfall data for the Indian region: Analysis of break and active monsoons," _Current Science_, vol. 91, no. 3, pp. 296--306, 2006.

[15] J. MacQueen, "Some methods for classification and analysis of multivariate observations," in _Proc. 5th Berkeley Symp. Math. Statist. Prob._, vol. 1, pp. 281--297, 1967.

[16] P. J. Rousseeuw, "Silhouettes: A graphical aid to the interpretation and validation of cluster analysis," _J. Comput. Appl. Math._, vol. 20, pp. 53--65, 1987.

[17] D. L. Davies and D. W. Bouldin, "A cluster separation measure," _IEEE Trans. Pattern Anal. Mach. Intell._, vol. PAMI-1, no. 2, pp. 224--227, 1979.

[18] T. Caliński and J. Harabasz, "A dendrite method for cluster analysis," _Commun. Stat. Theory Methods_, vol. 3, no. 1, pp. 1--27, 1974.

[19] P. A. P. Moran, "Notes on continuous stochastic phenomena," _Biometrika_, vol. 37, no. 1/2, pp. 17--23, 1950.

[20] R. C. Stone and H. Meinke, "Operational seasonal forecasting for agriculture," _Phil. Trans. R. Soc. B_, vol. 360, no. 1463, pp. 2109--2124, 2005.

[21] L. Hubert and P. Arabie, "Comparing partitions," _Journal of Classification_, vol. 2, no. 1, pp. 193--218, 1985.
