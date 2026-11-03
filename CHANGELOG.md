# Changelog

## 0.1.2 (2026-11-03)

- Audit memo wording: the "points to carry" list no longer says displacement is a PRMN flow (wrong for Sudan, which is a DTM stock), and the panel line says "Admin 2 units" instead of "districts" for Sudan's localities. No data or hash changes.

## 0.1.1 (2026-11-03)

- Somalia population reading confirmed against the HDX file description (2014 UNFPA total, 2005 UNDP figure; modelled planning estimates).
- Licence corrected: the Somalia COD-PS population file is "restricted for use only in HRP and Humanitarian Operations", not CC BY-IGO; the README licence table now says so. No data or output changes; panel and aggregate hashes are unchanged.
- Clean-room checks recorded for Somalia and Sudan (hashes matched in a fresh clone); run times corrected to about 15 and 20 minutes.

## 0.1.0 (2026-11-02, Phase A data pipeline)

- Somalia panel: 74 districts x 58 months (2021-01 to 2025-10). Displacement (PRMN flow) present to 2023-08 only.
- Sudan panel: 189 localities x 58 months (2021-01 to 2025-10). Displacement is the IOM DTM Overview stock only;
  harmonization record approved 2026-11-02.
- Core and extension column marking; PRMN flow and DTM stock kept as separate, non-comparable columns.
- Fetchers for WFP, PRMN, DTM, COD-AB, COD-PS and CHIRPS; ACLED by manual export or API (credentials from environment variables).
- Exploratory figures and an audit memo per instance; only ACLED district-month totals are marked publishable.
- README replication guide, `CITATION.cff`, security and licensing review.
