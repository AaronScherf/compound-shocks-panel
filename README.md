# Compound Shocks Panel

## What this is

This project builds a **district-by-month table** (a "panel") that puts four kinds of open data side by side for
one country: armed conflict (ACLED), rainfall (CHIRPS), food prices (WFP) and displacement (PRMN for Somalia,
IOM DTM for Sudan), all matched to official district boundaries (OCHA COD-AB). The aim is to find out what these
open sources can and cannot support before anyone models anything.

This is **data work only** (version 0.1.2, "Phase A"): downloading, matching places and dates, building the
panel, exploratory plots and an audit memo that says where the data are thin. It makes **no causal claims** and
runs no regressions.

| Country | Units | Period | Notes |
| --- | --- | --- | --- |
| Somalia | 74 districts (Mogadishu's 17 districts merged into Banadir) | 2021-01 to 2025-10 (58 months) | Displacement (PRMN) is **missing, not zero**, after its last report (2023-08). Measured run facts: [run summary](instances/somalia/outputs/RUN_SUMMARY.md) after `reproduce`. |
| Sudan | 189 localities | 2021-01 to 2025-10 (58 months) | Displacement (DTM) is missing before its first report (2023-08). Shows that the method carries to a second country. Measured run facts: [run summary](instances/sudan/outputs/RUN_SUMMARY.md) after `reproduce`. |

Units and period come from each instance's `config.yaml`. Run time, memory and file checksums are measured: they appear in the generated run summaries, and the authors' first clean-room measurements (including run time) are in [Somalia](docs/verification/somalia-2026-11-02.md) and [Sudan](docs/verification/sudan-2026-11-02.md). Real-data runs take tens of minutes.


Everything is ordinary Python and runs on a laptop. **No paid AI subscription, AI API key or special hardware is
needed**; nothing in the pipeline calls an AI service.

## Quick start

You need [Python 3.11+](https://www.python.org/downloads/) and [uv](https://docs.astral.sh/uv/)
(`pip install uv` works). Then, in a terminal:

```
git clone https://github.com/AaronScherf/compound-shocks-panel.git
cd compound-shocks-panel
uv sync --locked                 # installs the exact package versions
uv run reprokit quick-check      # runs the pipeline on made-up data, without downloads
uv run pytest                    # uses made-up test data, no network
uv run reprokit validate .       # checks the project's records are complete
```

The quick check reports **PASS** when the synthetic panel is made and checked; it proves the basic software setup works, not that the real data or research results are correct. **FAIL** names what stopped and how to retry. Its script is `quick_check.py`. These commands need no real data or accounts. To rebuild the real Somalia panel:

```
uv run python -m compound_shocks fetch --instance somalia --dry-run   # lists the public downloads
uv run python -m compound_shocks fetch --instance somalia             # WFP, PRMN, COD-AB, COD-PS, CHIRPS (about 150 MB)
# ACLED: see "Getting the data" below; put the export in instances/somalia/data/raw/conflict_events/
uv run python -m compound_shocks reproduce --instance somalia
```

Sudan is memory-heavy in the rainfall step (an earlier run was killed for low memory, so close other programs). If a data file is missing, `reproduce` stops and names the folder it expected. Outputs go to
`instances/<country>/outputs/` and `instances/<country>/data/derived/` (both git-ignored):

- `data/derived/panel.csv`: the district-by-month panel.
- `outputs/publishable_aggregates.csv`: event and fatality **totals** per district-month, the only file meant for sharing.
- `outputs/audit_memo.md` and `.html`: what the data contain and where they are incomplete.
- `outputs/manifest.json` (inputs, settings, hashes, package versions) and `run_report.json` (every processing decision, with counts).
- `outputs/RUN_SUMMARY.md`: the measured study window, final row count, file checksums, time, and memory for that run.

Read the [Somalia run summary](instances/somalia/outputs/RUN_SUMMARY.md) or [Sudan run summary](instances/sudan/outputs/RUN_SUMMARY.md) after running `reproduce`. These pages are generated locally and are not stored in Git. If the quick check fails, read its message, run `uv sync --locked` if it asks you to restore packages, and try `uv run reprokit quick-check` again.

A second run with unchanged inputs and code does no work. To check you got the same result as the authors,
compare the `sha256` of your `panel.csv` and `publishable_aggregates.csv` with those in
`docs/verification/somalia-2026-11-02.md` and `docs/verification/sudan-2026-11-02.md`. Downloads come from live
sites, so if a provider has revised a file since 2026-11-02 the hashes will differ; the `.fetch.json` files record
each download's hash so you can see which input changed.

## Getting the data

Raw data are never stored in this repository. `fetch` downloads everything public. Only ACLED needs an account.
Every source is free.

| Source | What it gives | How to get it |
| --- | --- | --- |
| **ACLED** (conflict events) | Event dates, places, types, fatalities | Register at <https://acleddata.com> with an institutional email (Research tier; the generic-email tier has no event-level data). Log in, use the data export tool for your country and dates, and save the CSV into `instances/<country>/data/raw/conflict_events/`. Alternatively set the environment variables `ACLED_EMAIL` and `ACLED_PASSWORD` and use the API fetch (not yet tested against the live API). Never write credentials into a file in this repository. |
| **CHIRPS** (rainfall) | Monthly rainfall grid for Africa | `fetch` downloads it from the Climate Hazards Center. No account. |
| **WFP food prices** | Market prices by month | `fetch`, from the Humanitarian Data Exchange (HDX). No account. |
| **OCHA COD-AB** (boundaries) | Official district polygons | `fetch`, from HDX. No account. |
| **OCHA COD-PS** (population) | District population | `fetch`, from HDX. No account. |
| **PRMN** (Somalia displacement) | People arriving, by origin district | `fetch`, from HDX. No account. |
| **IOM DTM** (Sudan displacement) | People displaced and present, by locality | `fetch`, from HDX. No account. |

## Running another country (Sudan walkthrough)

An "instance" is a folder holding one country's settings. Sudan was added by copying Somalia's and changing what
differs. To do the same for a new country:

1. **Copy an instance.** `instances/sudan/` has the pieces: `config.yaml` (country code, period, boundary file),
   `crosswalks/` (spelling fixes that match names across sources, for example WFP market names to official
   localities), `data/descriptors/` (one file per source: where it came from, terms of use, how to find the
   equivalent elsewhere) and `harmonization/`.
2. **Find each source for your country.** Each descriptor has a `find_in_other_geography` line saying what to look
   for (for example, boundaries are the HDX dataset `cod-ab-<iso3>`). Put downloads in
   `instances/<country>/data/raw/<role>/`.
3. **Adapters** read each provider's file layout into the project's standard columns. They live in
   `src/compound_shocks/adapters/`. If your source already has an adapter (WFP, CHIRPS, COD-AB, COD-PS, ACLED),
   change nothing. If not, write one. Sudan needed `adapters/iom_dtm.py`, because IOM DTM reports a **stock**
   (people displaced and present at each assessment round) where Somalia's PRMN reports **flows**.
4. **Write a harmonization record when a source differs in meaning.** Sudan's is
   `instances/sudan/harmonization/displacement.yaml`. It says what PRMN and DTM each measure and what was decided:
   keep the stock in its own columns, and use only the DTM "Overview" operation because the other operations
   disagree with it by 2.4 to 3 times. The owner approves it before a run.
5. **Check and run.** `uv run reprokit validate .`, then `fetch --instance <name>`, then `reproduce --instance <name>`.
   Compare your `run_report.json` and manifest with the original run.

## Core and extension columns

Columns are marked so nobody compares what cannot be compared.

- **Core columns** exist for every country and are the **only** ones to use in cross-country comparison:
  `events`, `fatalities`, `precip_mm`, `coverage_frac`, `price_sorghum`, `price_wheat`.
- **Extension columns** depend on what a country's sources provide and are never compared across countries:
  - `population`: one fixed estimate per district repeated every month, not a time series (Somalia's is read as the
    2014 UNFPA estimate, confirmed against the HDX file description; these are modelled planning estimates, not census figures),
  - Somalia: `displaced_individuals`, a PRMN **flow** (people arriving, summed by origin district; missing after 2023-08),
  - Sudan: `displaced_stock` and `displaced_stock_change`, a DTM **stock** and its month-to-month change (a proxy
    that mixes arrivals with departures and re-counts; missing where there is no report, none before 2023-08),
  - Somalia: `price_goat`, `wage_labor`, `tot_goat_sorghum`, `tot_wage_sorghum`.

**The two displacement measures are deliberately separate columns and are not comparable.** One counts people
moving in a period, the other counts people present at a point in time. They must not share a column, be pooled,
or feed a cross-country statistic. Missing means "no report", never zero.

Prices are sparse in both countries. Read each instance's audit memo for the observed coverage before using them.

## Data licences and terms

| Source | Terms | What this repo does |
| --- | --- | --- |
| ACLED | [ACLED EULA (8 July 2025)](https://acleddata.com/terms-of-use/) and Attribution Policy | Raw event rows are never committed or shared. Only district-month totals (`events`, `fatalities`; no coordinates, dates, IDs or notes) are produced for sharing, with citation. |
| OCHA COD-AB (boundaries) | CC BY-IGO as listed on HDX | Downloaded at run time, not redistributed here. |
| OCHA COD-PS (population) | Somalia: HDX licence "Other", **restricted for use only in HRP and Humanitarian Operations**; modelled indicative estimates, not for legal, political, electoral, boundary or entitlement uses. Sudan: confirm on the dataset page. | Same. Check that your own use is permitted before you rely on it. |
| WFP food prices | CC BY-IGO as listed on HDX | Same. |
| IOM DTM | CC BY 4.0 / IOM data protection principles as listed on HDX | Same. |
| UNHCR/NRC PRMN | CC BY as listed on HDX | Same. |
| CHIRPS | Public data from the UCSB Climate Hazards Center; cite Funk et al. (2015), *Scientific Data* 2:150066 | Same. |

Each source's terms and access date are in `instances/<country>/data/descriptors/`. They were taken from the
providers' listings; re-check them on the provider's page before reusing any data.

### ACLED: what you may and may not share

- **Do not** publish, post or send anyone ACLED event-level rows, even a subset. Your export stays in `data/raw/`,
  which git ignores.
- **You may** share aggregated counts (the `publishable_aggregates.csv` totals) and figures built from them, with
  ACLED's attribution: the source, what data and dates, and how it was changed ("aggregated from event-level data
  into monthly counts by district by the author").
- **Capture-date caveat.** ACLED revises past events, and the Research tier withholds roughly the latest 12 months.
  An export taken later can differ from ours, so your totals may not match. Our exports were captured on
  2026-10-31 (Somalia) and 2026-11-02 (Sudan); the capture date is in each conflict-events descriptor. Always cite
  the capture date.
- Raw ACLED rows must never be sent to an external AI service (see `agents.yaml`).
- This reading of the terms has not been confirmed with ACLED. Low-count cells (one event in one district-month)
  are an open question, so only totals are published until ACLED answers.

## Records

Every processing decision is in `protocol.md` (decision log) and lives in `instances/<country>/config.yaml` or
`crosswalks/`, never hidden in code. `docs/verification/` holds counts and hashes for each run. `AGENTS.md` has the
adaptation steps for a person or an AI agent. See `CHANGELOG.md` for versions.

## How to cite

Cite the software with `CITATION.cff` (GitHub's "Cite this repository" button reads it):

> Scherf, A. (2026). *Compound Shocks Panel* (version 0.1.2) [Computer software]. https://github.com/AaronScherf/compound-shocks-panel

Also cite each data source as its provider requires, ACLED's Attribution Policy in particular.

## Licence

Code: MIT (see `LICENSE`). Data and outputs: see the licence table above and each descriptor.
