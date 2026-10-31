# Compound Shocks Panel

This project builds a district-by-month panel combining conflict events (ACLED), rainfall (CHIRPS), food
prices (WFP) and displacement (PRMN) over official district boundaries, starting with Somalia (2021-01 to
2023-08). The aim is to find out what these open sources can and cannot support before any modeling. This
phase is data work only: ingestion, spatial joins, a panel, exploratory plots and an audit memo. It makes no
causal claims. The same steps run for another country by adding an instance folder (Sudan is the planned
portability test).

## Quick start

```
uv lock            # first time only: creates uv.lock; commit it
uv sync --locked
uv run reprokit validate
```

To reproduce the results, follow `protocol.md` and the run steps for your deliverables in `project.yaml`.

## Data

Every data source has a descriptor in `data/descriptors/` saying what it is, how it was queried, its terms of
use, and what to look for if you need the same kind of data for another place. Raw data is never stored in this
repository. For sources that need an account, register with the provider, put your credentials in `.env`
(copy `.env.example`), and run the fetch step.

## Panel columns

Core columns exist for every country and are the only ones used in cross-country comparison: `events`,
`fatalities`, `precip_mm`, `coverage_frac`, `price_sorghum`, `price_wheat`.

Extension columns depend on what a country's sources provide: `displaced_individuals`, `price_goat`,
`wage_labor`, `tot_goat_sorghum`, `tot_wage_sorghum`.

## AI and compute

- This project is designed to run on an ordinary laptop with no GPU. See `compute.yaml` for the assumed limits.
- No step needs a paid AI subscription, an API key for an AI service, or heavy compute. The pipeline is
  ordinary Python (pandas, geopandas, rasterio) and runs on a laptop. Run time on the full Somalia
  rasters is still to be measured (see the Task 14 verification note).
- AI coding assistants helped write the code, but nothing in `reproduce` calls one. Raw ACLED rows must never
  be sent to an external AI service (see `agents.yaml`).
- The only account needed is a free ACLED registration, used with `ACLED_EMAIL` and `ACLED_PASSWORD`
  environment variables.

## Using this for another country or question

See "Adapting this project" in `AGENTS.md`. The same steps work for a person or an AI agent.

## License and citation

Code: MIT (see `LICENSE`). Data and outputs: see each descriptor. Cite using `CITATION.cff`.
