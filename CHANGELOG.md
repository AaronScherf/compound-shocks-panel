# Changelog

## Unreleased (0.1.0, Phase A data pipeline; not yet tagged)

- Somalia panel: 74 districts x 58 months (2021-01 to 2025-10). Displacement (PRMN flow) present to 2023-08 only.
- Sudan panel: 189 localities x 58 months (2021-01 to 2025-10). Displacement is the IOM DTM Overview stock only;
  harmonization record approved 2026-11-02.
- Core and extension column marking; PRMN flow and DTM stock kept as separate, non-comparable columns.
- Fetchers for WFP, PRMN, DTM, COD-AB, COD-PS and CHIRPS; ACLED by manual export or API (credentials from environment variables).
- Exploratory figures and an audit memo per instance; only ACLED district-month totals are marked publishable.
- README replication guide, `CITATION.cff`, security and licensing review.
