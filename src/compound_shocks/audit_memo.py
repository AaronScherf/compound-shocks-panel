"""Data audit memo: what the sources provide, how complete the panel is, and what to keep in mind. Descriptive only."""

import html
import json
import re
from pathlib import Path

import geopandas as gpd
import pandas as pd
import yaml

from compound_shocks.eda import SOURCE_GROUPS, data_profile, missingness_vs_conflict
from compound_shocks.figures import (
    make_district_audit_map,
    missingness_matrix,
    plot_commodity_series,
    plot_conflict_rainfall_trends,
)

FIGURES = {
    "missingness.png": "Which district-months have a value, by panel column",
    "prices.png": "Raw market-level prices by commodity, in nominal local currency",
    "conflict_rainfall.png": "Monthly national totals of events and fatalities, with mean precipitation",
    "map_events.png": "Total events per district over the period",
    "map_price_sorghum.png": "Share of months with a sorghum price, per district",
}
NOT_RECORDED = "not recorded"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _descriptors(instance_dir: Path) -> dict[str, dict]:
    folder = instance_dir / "data" / "descriptors"
    loaded = (yaml.safe_load(path.read_text(encoding="utf-8")) for path in sorted(folder.glob("*.yaml")))
    return {descriptor["role"]: descriptor for descriptor in loaded}


def _sidecar_date(raw_dir: Path, role: str) -> str:
    dates = sorted(_json(path).get("accessed", "") for path in (raw_dir / role).glob("*.fetch.json"))
    return dates[-1] if dates and dates[-1] else NOT_RECORDED


def _accessed(descriptors: dict, raw_dir: Path, role: str) -> str:
    return descriptors.get(role, {}).get("accessed") or _sidecar_date(raw_dir, role)


def _table(header: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def _provenance(manifest: dict, config: dict, descriptors: dict, raw_dir: Path, vintage: str | None) -> str:
    rows = []
    for role, files in sorted(manifest["inputs"].items()):
        data_files = [f for f in files if not f["path"].endswith(".fetch.json")]
        digest = f"{data_files[0]['sha256'][:16]}" + (f" (+{len(data_files) - 1} more)" if len(data_files) > 1 else "")
        provider = descriptors.get(role, {}).get("provider") or config["sources"][role]["provider"]
        rows.append([role, provider, _accessed(descriptors, raw_dir, role), len(data_files), digest])
    text = _table(["Role", "Provider", "Accessed", "Files", "sha256 (first 16)"], rows)
    if vintage:
        text += f"\n\nBoundary vintage: {vintage}."
    return text + f"\n\nCode version `{manifest['code_version'][:7]}`; every file hash is in `manifest.json`."


def _names(boundaries: gpd.GeoDataFrame | None, ids: list[str]) -> str:
    if boundaries is None:
        return ", ".join(ids)
    lookup = dict(zip(boundaries["admin2_id"].astype(str), boundaries["name"]))
    return ", ".join(f"{lookup.get(i, i)} ({i})" for i in ids)


def _coverage(panel: pd.DataFrame, run_report: dict, boundaries: gpd.GeoDataFrame | None) -> str:
    profile = data_profile(panel)
    stats, rows = run_report["stats"], profile["rows"]
    by_district = panel.groupby("admin2_id")
    no_price = sorted(by_district["price_sorghum"].apply(lambda s: s.isna().all()).loc[lambda s: s].index.astype(str))
    price_share = profile["groups"]["prices"]["non_null"] / rows
    displacement_columns = [c for c in SOURCE_GROUPS["displacement"] if c in panel.columns]
    moves = panel[displacement_columns].notna().any(axis=1).groupby(panel["month"]).any()
    silent_months = sorted(moves.loc[~moves].index)
    lines = [
        f"- The panel has {rows} rows: {profile['districts']} districts by {profile['months']} months.",
        (f"- {price_share:.0%} of district-months have a sorghum or wheat price; "
        f"{len(no_price)} of {profile['districts']} districts have none in the whole period."),
        (f"- {profile['groups']['displacement']['non_null'] / rows:.0%} of district-months have a displacement value. "
        f"Months with no displacement report anywhere: {', '.join(silent_months) if silent_months else 'none'}."),
        (f"- {profile['columns']['events']['zero']} district-months have zero events "
        f"({profile['columns']['events']['zero'] / rows:.0%}). Zero means none were recorded, not that none occurred."),
        f"- ACLED events that fall outside every district: {stats.get('unassigned_events', NOT_RECORDED)}.",
        (f"- Mean rainfall coverage is {panel['coverage_frac'].mean():.1%} of district area; the lowest district-month is "
        f"{panel['coverage_frac'].min():.1%}."),
    ]
    if no_price:
        lines.append(f"\nDistricts with no price observation: {_names(boundaries, no_price)}.")
    return "\n".join(lines)


def _missingness_vs_conflict(panel: pd.DataFrame) -> str:
    result = missingness_vs_conflict(panel, "price_sorghum")
    cut = result["district_cut"]
    header = ["Group", "District-months", "Mean events", "Events per 100,000 residents", "Share with any event",
              "Mean fatalities"]

    def row(label: str, stats: dict) -> list:
        return [label, stats["district_months"], stats["mean_events"], stats["events_per_100k"],
                stats["share_with_events"], stats["mean_fatalities"]]

    districts = _table(header, [row("Districts that ever have a sorghum price", cut["ever_has_value"]),
                                row("Districts that never do", cut["never_has_value"])])
    months = _table(header, [row("Months with a price (market districts only)", result["month_cut"]["with_value"]),
                             row("Months without (market districts only)", result["month_cut"]["without_value"])])
    years = _table(
        ["Year", "Share of months with a price", "Mean events with price", "Mean events without"],
        [[y["year"], y["share_observed"], y["with_value"]["mean_events"], y["without_value"]["mean_events"]]
         for y in result["by_year"]],
    )
    return "\n\n".join([
        (f"{result['districts_ever']['with_value']} districts ever have a sorghum price and "
        f"{result['districts_ever']['without_value']} never do. The tables compare conflict counts across those groups. "
        "They are descriptive: no test is run, and differences may reflect where markets are placed."),
        "Between districts:", districts, "Within districts that have a market, by month:", months, "By year:", years,
    ])


def _market_districts(panel: pd.DataFrame, boundaries: gpd.GeoDataFrame) -> str:
    """Why a district with a market can still have few prices: months with a price, and who lives there."""
    if "population" not in panel:
        return ""
    by_district = panel.groupby("admin2_id").agg(
        population=("population", "first"), priced=("price_sorghum", "count"), months=("month", "nunique"),
        events=("events", "sum"),
    )
    names = dict(zip(boundaries["admin2_id"].astype(str), boundaries["name"]))
    total = by_district["population"].sum()
    market = by_district[by_district["priced"] > 0].copy()
    market["share"] = market["priced"] / market["months"]
    steady = int((market["share"] >= 0.75).sum())
    lines = [
        (f"{len(market)} of {len(by_district)} districts have a sorghum price in at least one month; {steady} have one in "
        f"at least 75% of months. Those {len(market)} districts hold {market['population'].sum() / total:.0%} of the "
        f"population in the panel, so district counts understate population coverage "
        f"(districts with any price: {len(market) / len(by_district):.0%}; population in them: "
        f"{market['population'].sum() / total:.0%})."),
        "",
    ]
    market = market.sort_values("population", ascending=False)
    rows = [[names.get(i, i), int(r.population) if pd.notna(r.population) else "n/a", f"{int(r.priced)} of {int(r.months)}",
             f"{r.share:.0%}", int(r.events)] for i, r in market.iterrows()]
    return "\n".join(lines) + "\n" + _table(["District", "Population", "Months with a price", "Share", "Events in period"], rows)


def _acled_answers(descriptors: dict, raw_dir: Path) -> str:
    acled = descriptors.get("conflict_events", {})
    accessed = _accessed(descriptors, raw_dir, "conflict_events")
    return "\n".join([
        "Source: ACLED (acleddata.com), accessed " + accessed + ". Figures and tables here are aggregates only; "
        "no event rows are included.",
        "",
        f"1. Date accessed: {accessed}.",
        f"2. Filters applied: {acled.get('applied_filters', NOT_RECORDED)}",
        f"3. Manipulation: {acled.get('manipulation', NOT_RECORDED)}",
    ])


def _observations(run_report: dict) -> str:
    decisions = [f"- {text}" for text in run_report["decisions"]]
    warnings = [f"- {text}" for text in run_report["warnings"]] or ["- none"]
    caveats = [
        "- Prices are nominal and in local currency, so levels are not comparable across districts or over time.",
        "- A missing displacement row is a missing value: PRMN lists reported flows only.",
        "- ACLED counts reflect reporting as well as events; low counts may mean little reporting.",
        "- Coverage differs by source, so any later analysis should state its sample and handling of missing values.",
    ]
    return "\n".join([
        "Processing decisions applied in this run:", "", *decisions, "", "Warnings from this run:", "", *warnings, "",
        "Points to carry into the literature review and research design:", "", *caveats,
    ])


def _figures(outputs: Path) -> str:
    lines = []
    for name, caption in FIGURES.items():
        if (outputs / "figures" / name).exists():
            lines += [f"![{caption}](figures/{name})", "", f"*{caption}.*", ""]
    return "\n".join(lines)


def make_figures(instance_dir: Path, panel: pd.DataFrame, accessed: str) -> None:
    derived, figures = instance_dir / "data" / "derived", instance_dir / "outputs" / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    missingness_matrix(panel, figures / "missingness.png")
    plot_commodity_series(pd.read_csv(derived / "prices.csv", dtype={"admin2": str}), figures / "prices.png")
    plot_conflict_rainfall_trends(panel, figures / "conflict_rainfall.png", accessed)
    boundaries = gpd.read_file(derived / "admin_boundaries.geojson")
    make_district_audit_map(panel, boundaries, "events", figures / "map_events.png", accessed)
    make_district_audit_map(panel, boundaries, "price_sorghum", figures / "map_price_sorghum.png", accessed)


def to_html(markdown: str, title: str) -> str:
    """Convert the memo's small markdown subset (headings, tables, lists, images, paragraphs) to a standalone page."""
    body, block = [], []

    def inline(text: str) -> str:
        text = html.escape(text)
        text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        return re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)

    def flush() -> None:
        if not block:
            return
        first = block[0]
        if first.startswith("|"):
            rows = [[c.strip() for c in line.strip("|").split("|")] for line in block if not set(line) <= set("|- ")]
            cells = "".join(
                "<tr>" + "".join(f"<{'th' if i == 0 else 'td'}>{inline(c)}</{'th' if i == 0 else 'td'}>" for c in row) + "</tr>"
                for i, row in enumerate(rows)
            )
            body.append(f"<table>{cells}</table>")
        elif first.startswith("- "):
            body.append("<ul>" + "".join(f"<li>{inline(line[2:])}</li>" for line in block) + "</ul>")
        elif first.startswith("!["):
            match = re.match(r"!\[(.*)\]\((.*)\)", first)
            body.append(f'<img src="{html.escape(match[2])}" alt="{html.escape(match[1])}" style="max-width:100%">')
        elif first.startswith("#"):
            level = len(first) - len(first.lstrip("#"))
            body.append(f"<h{level}>{inline(first.lstrip('# '))}</h{level}>")
        else:
            body.append(f"<p>{inline(' '.join(block))}</p>")
        block.clear()

    for line in markdown.splitlines():
        kind = line[:1]
        if not line.strip():
            flush()
        elif block and (kind in "#!" or (block[0][:1] in "#!") or (line.startswith("- ") != block[0].startswith("- "))
                        or (kind == "|") != (block[0][:1] == "|")):
            flush()
            block.append(line)
        else:
            block.append(line)
    flush()
    return (f"<!doctype html><html lang=\"en\"><meta charset=\"utf-8\"><title>{html.escape(title)}</title>"
            "<style>body{font-family:sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem}"
            "table{border-collapse:collapse}td,th{border:1px solid #bbb;padding:.2rem .5rem;text-align:left}</style>"
            + "".join(body) + "</html>\n")


def build_audit_memo(instance_dir: Path) -> Path:
    """Write outputs/audit_memo.md (and .html) with figures from a finished run; return the markdown path."""
    derived, outputs = instance_dir / "data" / "derived", instance_dir / "outputs"
    raw_dir = instance_dir / "data" / "raw"
    manifest, run_report = _json(outputs / "manifest.json"), _json(outputs / "run_report.json")
    panel = pd.read_csv(derived / "panel.csv", dtype={"admin2_id": str, "month": str})
    descriptors = _descriptors(instance_dir)
    accessed = _accessed(descriptors, raw_dir, "conflict_events")
    make_figures(instance_dir, panel, accessed)
    boundaries = gpd.read_file(derived / "admin_boundaries.geojson")
    config = yaml.safe_load((instance_dir / "config.yaml").read_text(encoding="utf-8"))
    period = config["period"]
    sections = [
        f"# Data audit memo: {instance_dir.name}",
        (f"Study period {period['start']} to {period['end']}. This memo describes what the data contain and where they "
        "are incomplete. It makes no causal or hypothesis claim."),
        "## Dataset provenance",
        _provenance(manifest, config, descriptors, raw_dir, run_report["stats"].get("boundary_vintage")),
        "## Coverage and missingness",
        _coverage(panel, run_report, boundaries),
        "## Price gaps and conflict",
        _missingness_vs_conflict(panel),
        _market_districts(panel, boundaries),
        "## Figures",
        _figures(outputs),
        "## ACLED: access, filters and manipulation",
        _acled_answers(descriptors, raw_dir),
        "## Observations and caveats",
        _observations(run_report),
    ]
    memo = outputs / "audit_memo.md"
    text = "\n\n".join(sections) + "\n"
    memo.write_text(text, encoding="utf-8", newline="\n")
    memo.with_suffix(".html").write_text(to_html(text, f"Data audit memo: {instance_dir.name}"), encoding="utf-8", newline="\n")
    return memo
