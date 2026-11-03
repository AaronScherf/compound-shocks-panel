# Compound Shocks Panel: research protocol

**Status:** Data intake and pipeline build. No analysis or causal design is approved. Layer 1 only (prices, rainfall, conflict, displacement, boundaries); descriptive, no causal claims.

## Questions to resolve before building the panel

- Define the outcome: origin outflows, destination inflows, or another measure; specify how missing reports and zero reports differ.
- Verify the unit, period, administrative boundary vintage, and crosswalk before any spatial join. Preserve source coordinates and source administrative labels in derived metadata.
- Specify which ACLED event types and geographic precision levels count as exposure, how dates are assigned to months, and how reporting bias is assessed.
- Verify whether price observations represent the same commodity, unit, currency, market, and collection method over time.
- Define the climate anomaly baseline and raster aggregation rule. Record coverage and missing grid cells for each district-month.
- Treat transfer presence and placement as potentially endogenous. Do not present descriptive patterns as treatment effects.
- Predefine missingness checks, source disagreements, sensitivity analyses, and disclosure limits before interpreting results.

## Decision log

Record each substantive decision with date, author, evidence, alternatives considered, and affected outputs. Keep rejected or revised specifications visible rather than silently replacing them. Add preregistration or a dated analysis plan if confirmatory claims are pursued.

| Date | Decision | Evidence | Affects |
| --- | --- | --- | --- |
| 2026-10-31 | Pilot is Layer 1 only; cross-country comparison uses the common core | Owner decision; Sudan source check | Panel columns, Sudan instance |
| 2026-10-31 | Somalia window 2021-01 to 2023-08; CHIRPS v2.0; boundaries from OCHA COD-AB with geoBoundaries as fallback | HDX PRMN dataset ends 2023-08; owner decision | Somalia config, descriptors |
| 2026-10-31 | Committed ACLED aggregates are district-month totals only until ACLED answers the low-count question | ACLED terms findings (Gemini reading, unconfirmed) | Publishable aggregates |
| 2026-10-31 | Scope realigned to Phase A: data ingestion, adapters, panel, exploratory analysis, audit memo and Sudan portability (data pipeline only). Modeling, price-basket decompositions, cross-country tests and the paper are Phase B, started only after a review gate (data audit, literature gap analysis, owner approval) | Owner decision after the pilot grew into a full research implementation; Gemini scope note | Plan tasks 11, 12, 15; project.yaml deliverables; `statsmodels` removed |
| 2026-10-31 | Panel conventions: `price_*` is the mean over markets and matching commodities; `displaced_individuals` counts people leaving a district (origin); unmatched district names are reported, not fatal | Task 9 and 10 implementation; owner may revise | Panel columns, run report |
| 2026-11-02 | **Banadir is one analysis unit.** The 17 Mogadishu districts and the "Unspecified" remainder polygon in COD-AB v03 are dissolved into `SO22` "Banadir" | PRMN and WFP report Mogadishu only as "Banadir"; it is 20% of PRMN arrivals and 4.8% of departures in the window. Owner decision (option a) | `instances/somalia/config.yaml` `parameters.merge_districts`; 74 units instead of 91 |
| 2026-11-02 | Provider spellings Baidoa, Kismayo, Lasqoray are renamed to COD-AB's Baydhaba, Kismaayo, Laasqoray. **Badhan and Dhahar (Sanaag; 0.1% to 0.2% of displacement) are absent from COD-AB v03 and stay unassigned**, reported in the run report, as does one PRMN row with district "0" | Name comparison of the real PRMN and WFP files against COD-AB, 2026-11-02 | `instances/somalia/crosswalks/district_names.yaml` |
| 2026-11-02 | 204 WFP price rows in the window have blank admin1 and admin2; all belong to the Wadajir market (Mogadishu) and are assigned to Banadir | WFP file inspection | `instances/somalia/crosswalks/wfp_market_districts.yaml` |
| 2026-11-02 | The ACLED export repeats each event once per actor row (101,144 rows, 52,925 events; every repeated event appears twice with identical date, location, type and fatalities). The pipeline keeps one row per event, so events and fatalities are counted once; it stops if repeated rows disagree on event details. `actor1` is then arbitrary and unused | Counts on the real export, 2026-11-02 | ACLED adapter; panel `events`, `fatalities` |
| 2026-11-02 | ACLED events are placed in districts by coordinates only, never by country or ACLED's own admin names. 261 export rows are labelled country "Indian Ocean" (maritime); they fall outside every district and are counted as unassigned | Review Focus items 3 and 4 | run report `unassigned_events` |
| 2026-11-02 | PRMN displacement comes from the HDX XLSX (sheet `OutputsArrivals`), not the HDX CSV, which is a 3 KB per-district total as at 2022-11-30. Weekly rows are summed to one row per month, origin, destination and reason; reasons map to drought, conflict, flood, other | HDX resource listing and file inspection | PRMN adapter and mapping |
| 2026-11-02 | CHIRPS GeoTIFFs carry no nodata tag but mark sea cells -9999; those cells are treated as missing, so they lower `coverage_frac` and never enter `precip_mm` | 41% of cells in Somalia's bounding box are -9999; bug found on the real files | `compound_shocks.spatial.CHIRPS_FILL_VALUE` |
| 2026-11-02 | Only the study period 2021-01 to 2023-08 is processed for ACLED events and WFP prices (including the unit, currency and price-type checks), so reports describe the window rather than 30 years of history | Run report noise from earlier years | `compound_shocks.pipeline`; run report decisions |
| 2026-11-02 | **Prices are nominal, in local currency** (Somali shilling in most districts, Somaliland shilling in others; no district mixes them in the window), so they are not comparable across districts. WFP's `usdprice` is not used yet. Whether to convert is deferred to the review gate | Currency counts in the real WFP file | `price_sorghum`, `price_wheat`; audit memo caveat |
| 2026-11-02 | **A missing displacement row is NaN, not zero**: PRMN lists only reported flows, so a district-month with no row may mean no displacement or no report, and the data cannot tell which | Source structure | `displaced_individuals`; audit memo caveat |
| 2026-11-02 | **Food-aid prices are not market prices.** Commodities whose name contains "food aid" (for example "Sorghum (food aid)" in WFP Sudan) are excluded from `price_sorghum` and `price_wheat`. Somalia outputs are unchanged by this rule | WFP Sudan commodity list, 2026-11-02; Somalia panel hashes identical before and after | `compound_shocks.panel._monthly_price` |
| 2026-11-02 | Sudan study period is 2021-01 to 2024-12 (my call, owner to confirm): two years before the April 2023 war and 21 months after | Pre-war DTM and price coverage differ from post-war | `instances/sudan/config.yaml` |
| 2026-11-02 | Sudan displacement is a **stock** from IOM DTM, kept as `displaced_stock` and `displaced_stock_change`, never mixed with the Somalia flow column. Per locality, origin state and month the last report is used, with series precedence Overview, Monthly, original | HDX `sdn-iom-dtm-from-api` inspected 2026-11-02: overlapping series report different numbers for the same locality and day | `instances/sudan/harmonization/displacement.yaml`; IOM DTM adapter |
| 2026-11-02 | WFP Sudan district names are mapped to COD-AB localities by placing each market's coordinates inside the locality polygon (14 aliases). IOM DTM P-codes and names match COD-AB v03 exactly. The state codes in the Gemini portability note (SD01 Northern and so on) are wrong; COD-AB v03 uses SD01 Khartoum and so on | Spatial join of 18 WFP markets; join of DTM P-codes to COD-AB | `instances/sudan/crosswalks/district_names.yaml` |
| 2026-11-02 | **Population is a fixed OCHA COD-PS district total**, repeated in every month of the panel as context, not a time series. Somalia uses the humanitarian planning file `som_pplp_adm2_v2.csv` (total `T_TL`; the planning-year label is not in the file and still needs confirming on the HDX page); Sudan uses `sdn_admpop_adm2_2024.csv`. Merged districts sum their members (Mogadishu is already one row, SO2201, so Banadir needs no splitting). Abyei (SD19001) has no row and stays NaN | The audit memo needs a denominator: 37 of 74 Somali districts have a price but hold 68% of the population | `population` role, `adapters/population.py`, `units.merge_populations`, memo market-district table |

Every decision above that changes data is also applied by code and recorded in each run: `outputs/run_report.json` lists
the decisions applied with counts, and `outputs/manifest.json` records the config, the crosswalk files (hashed), the
code fingerprint and the pinned packages. Edit the YAML files named here, not the code, to change a decision.

## Verification states

Mark results explicitly as **proposed**, **source-verified**, **fixture-tested**, **run on acquired data**, or **independently reproduced**. A checksum alone establishes byte identity, not validity of the source, join, measurement, or inference.
