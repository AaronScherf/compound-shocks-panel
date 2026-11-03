"""Step graph for one instance. Steps pass data through files in data/derived so unchanged work is skipped."""

import hashlib
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
from doit.tools import config_changed
from reprokit.harmonization import check_gate
from reprokit.loader import load_yaml
from reprokit.manifest import (
    build_manifest,
    code_version,
    collect_role_files,
    resolved_packages,
    write_manifest,
)
from reprokit.problems import Problem
from reprokit.validate import validate_document

from compound_shocks.adapters import (  # noqa: F401  (register adapters)
    acled,
    boundaries,
    chirps,
    iom_dtm,
    population,
    prmn,
    wfp_prices,
)
from compound_shocks.adapters.base import get_adapter
from compound_shocks.audit_memo import build_audit_memo
from compound_shocks.crosswalk import (
    apply_crosswalk,
    build_name_index,
    fill_missing_by_market,
    load_name_map,
)
from compound_shocks.panel import aggregate_conflict, fuse_panel, publishable_aggregates
from compound_shocks.schema import PANEL_COLUMNS, check_frame
from compound_shocks.spatial import assign_admin2
from compound_shocks.units import merge_populations, merge_units

BASELINE_INSTANCE = "somalia"
TEXT_COLUMNS = ("admin2_id", "month", "date", "admin2", "origin_admin2", "dest_admin2", "market", "commodity",
                "unit", "currency", "reason", "event_id", "origin_admin1")


def check_instance_gate(root: Path, instance_dir: Path) -> list[Problem]:
    """Provider changes against the Somalia baseline need a harmonization record in the instance."""
    baseline = root / "instances" / BASELINE_INSTANCE / "config.yaml"
    current = instance_dir / "config.yaml"
    problems = []
    for path in (baseline, current):
        problems += validate_document(path, "config")
    if problems:
        return problems
    base_doc, _ = load_yaml(baseline)
    current_doc, _ = load_yaml(current)
    return check_gate(base_doc["sources"], current_doc["sources"], instance_dir / "harmonization")


def _text_hash(path: Path) -> str:
    """sha256 of a text file with line endings normalised, so Windows and Linux checkouts hash alike."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _code_fingerprint() -> str:
    """Hash of every source and mapping file in the package: a code change invalidates every step."""
    package = Path(__file__).parent
    digest = hashlib.sha256()
    for path in sorted(p for p in package.rglob("*") if p.suffix in {".py", ".yaml"} and "__pycache__" not in p.parts):
        digest.update(path.relative_to(package).as_posix().encode())
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def _csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype={column: str for column in TEXT_COLUMNS})


def _log(log: Path, step: str) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as stream:
        stream.write(f"{step}\n")


def _report(path: Path, warnings: list[str], stats: dict, decisions: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"decisions": decisions or [], "stats": stats, "warnings": warnings}
    path.write_text(json.dumps(body, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _read(
    role: str,
    provider: str,
    files: list[Path],
    target: Path,
    report: Path,
    boundaries_file: Path,
    merges: list[dict],
    period: dict,
    log: Path,
) -> None:
    instance = {"period": period}
    if role == "rainfall":
        instance["boundaries"] = gpd.read_file(boundaries_file)
    frame = get_adapter(role, provider).read(files, instance)
    decisions, stats = list(frame.attrs.get("decisions", [])), {f"rows_{role}": len(frame)}
    if role == "admin_boundaries":
        frame, merged = merge_units(frame, merges)
        decisions += merged
        stats["boundary_vintage"] = frame.attrs.get("vintage")
    if role == "population":
        frame, merged = merge_populations(frame, merges)
        decisions += merged
    fatal = check_frame(frame, frame.attrs.get("schema", role))
    if fatal:
        raise ValueError("; ".join(str(problem) for problem in fatal))
    if role == "admin_boundaries":
        frame.to_file(target, driver="GeoJSON")
    else:
        frame.to_csv(target, index=False, lineterminator="\n")
    _report(report, [str(problem) for problem in frame.attrs.get("problems", [])], stats, decisions)
    _log(log, f"read:{role}")


def _spatial(events_file: Path, boundaries_file: Path, period: dict, target: Path, report: Path, log: Path) -> None:
    events = _csv(events_file)
    dates = pd.to_datetime(events["date"])
    inside = (dates >= pd.Timestamp(period["start"])) & (dates <= pd.Timestamp(period["end"]))
    outside = int((~inside).sum())
    assigned = assign_admin2(events[inside].reset_index(drop=True), gpd.read_file(boundaries_file))
    assigned.to_csv(target, index=False, lineterminator="\n")
    decisions = (
        [f"ACLED: {outside} events outside the study period {period['start']} to {period['end']} excluded"] if outside else []
    )
    _report(report, [], {"events_in_period": int(inside.sum()), "events_outside_period": outside}, decisions)
    _log(log, "spatial")


def _aggregate(assigned_file: Path, target: Path, report: Path, log: Path) -> None:
    conflict = aggregate_conflict(_csv(assigned_file))
    conflict.to_csv(target, index=False, lineterminator="\n")
    _report(report, [], {"unassigned_events": conflict.attrs["unassigned"]})
    _log(log, "aggregate")


def _fuse(derived: Path, crosswalks: Path, months: list[str], target: Path, report: Path, log: Path) -> None:
    districts = gpd.read_file(derived / "admin_boundaries.geojson")
    aliases = load_name_map(crosswalks / "district_names.yaml")
    market_districts = load_name_map(crosswalks / "wfp_market_districts.yaml")
    names, alias_problems = build_name_index(districts, aliases)
    prices, filled = fill_missing_by_market(_csv(derived / "prices.csv"), market_districts)
    moves = _csv(derived / "displacement.csv")
    stock = "stock" in moves.columns
    place_columns = ["dest_admin2"] if stock else ["origin_admin2", "dest_admin2"]
    renamed = sum(int(frame[column].isin(list(aliases)).sum()) for frame, column in
                  [(prices, "admin2"), *[(moves, c) for c in place_columns]])
    decisions = []
    if aliases:
        decisions.append(f"crosswalks/district_names.yaml: {renamed} provider district names renamed through {len(aliases)} aliases")
    if filled:
        decisions.append(f"crosswalks/wfp_market_districts.yaml: district filled from the market for {filled} price rows")
    prices, price_problems = apply_crosswalk(prices, "admin2", names, "prices")
    origin_problems = []
    if not stock:
        moves, origin_problems = apply_crosswalk(moves, "origin_admin2", names, "displacement")
    moves, dest_problems = apply_crosswalk(moves, "dest_admin2", names, "displacement")
    panel = fuse_panel(_csv(derived / "conflict_monthly.csv"), _csv(derived / "rainfall.csv"), prices, moves,
                       sorted(districts["admin2_id"].astype(str)), months, _csv(derived / "population.csv"))
    panel.to_csv(target, index=False, lineterminator="\n")
    problems = alias_problems + price_problems + origin_problems + dest_problems
    _report(report, [str(p) for p in problems], {"panel_rows": len(panel)}, decisions)
    _log(log, "fuse")


def _outputs(instance_dir: Path, config_file: Path, root: Path, log: Path) -> None:
    derived, outputs = instance_dir / "data" / "derived", instance_dir / "outputs"
    panel = pd.read_csv(derived / "panel.csv", dtype={"admin2_id": str, "month": str})
    outputs.mkdir(parents=True, exist_ok=True)
    publishable_aggregates(panel).to_csv(outputs / "publishable_aggregates.csv", index=False, lineterminator="\n")
    config, _ = load_yaml(config_file)
    raw_dir = instance_dir / "data" / "raw"
    manifest = build_manifest(config, collect_role_files(raw_dir, config["sources"]), raw_dir, code_version(root),
                              resolved_packages())
    manifest["panel_columns"] = {
        kind: sorted(name for name, k in PANEL_COLUMNS.items() if k == kind) for kind in ("core", "extension")
    }
    instance_files = [config_file, *sorted((instance_dir / "crosswalks").glob("*.yaml"))]
    manifest["code_fingerprint"] = _code_fingerprint()
    manifest["instance_files"] = {path.relative_to(instance_dir).as_posix(): _text_hash(path) for path in instance_files}
    write_manifest(manifest, outputs / "manifest.json")
    warnings, stats, decisions = [], {}, []
    for part in sorted((derived / "reports").glob("*.json")):
        loaded = json.loads(part.read_text(encoding="utf-8"))
        warnings += [f"{part.stem}: {warning}" for warning in loaded["warnings"]]
        decisions += loaded["decisions"]
        stats.update(loaded["stats"])
    _report(outputs / "run_report.json", warnings, stats, decisions)
    _log(log, "outputs")


def _audit(instance_dir: Path, log: Path) -> None:
    build_audit_memo(instance_dir)
    _log(log, "audit")


def months_between(start: str, end: str) -> list[str]:
    return [period.strftime("%Y-%m") for period in pd.period_range(start, end, freq="M")]


def tasks(instance_dir: Path, config: dict, role_files: dict[str, list[Path]], root: Path) -> list[dict]:
    """doit task dicts: read:<role> per role, then spatial, aggregate, fuse, outputs."""
    derived = instance_dir / "data" / "derived"
    log, config_file = derived / "ran.log", instance_dir / "config.yaml"
    reports = derived / "reports"
    boundaries_file = derived / "admin_boundaries.geojson"
    merges = config["parameters"].get("merge_districts", [])
    crosswalk_files = [str(path) for path in sorted((instance_dir / "crosswalks").glob("*.yaml"))]
    months = months_between(config["period"]["start"], config["period"]["end"])
    steps = []
    for role, files in role_files.items():
        target = boundaries_file if role == "admin_boundaries" else derived / f"{role}.csv"
        report = reports / f"read_{role}.json"
        extra = [str(boundaries_file)] if role == "rainfall" else []
        steps.append({
            "name": f"read:{role}",
            "file_dep": [str(path) for path in files] + extra + [str(config_file)],
            "targets": [str(target), str(report)],
            "actions": [(_read, [role, config["sources"][role]["provider"], files, target, report, boundaries_file, merges, config["period"], log])],
        })
    events, assigned, conflict = derived / "conflict_events.csv", derived / "events_assigned.csv", derived / "conflict_monthly.csv"
    steps.append({
        "name": "spatial",
        "file_dep": [str(events), str(boundaries_file), str(config_file)],
        "targets": [str(assigned), str(reports / "spatial.json")],
        "actions": [(_spatial, [events, boundaries_file, config["period"], assigned, reports / "spatial.json", log])],
    })
    steps.append({
        "name": "aggregate",
        "file_dep": [str(assigned)],
        "targets": [str(conflict), str(reports / "aggregate.json")],
        "actions": [(_aggregate, [assigned, conflict, reports / "aggregate.json", log])],
    })
    inputs = [conflict, boundaries_file] + [derived / f"{role}.csv" for role in ("prices", "displacement", "rainfall", "population")]
    panel = derived / "panel.csv"
    steps.append({
        "name": "fuse",
        "file_dep": [str(path) for path in inputs] + [str(config_file)] + crosswalk_files,
        "targets": [str(panel), str(reports / "fuse.json")],
        "actions": [(_fuse, [derived, instance_dir / "crosswalks", months, panel, reports / "fuse.json", log])],
    })
    outputs = instance_dir / "outputs"
    raw_inputs = [str(path) for files in role_files.values() for path in files]
    steps.append({
        "name": "outputs",
        "file_dep": [str(panel), str(reports / "fuse.json"), str(config_file)] + crosswalk_files + raw_inputs,
        "targets": [str(outputs / name) for name in ("publishable_aggregates.csv", "manifest.json", "run_report.json")],
        "actions": [(_outputs, [instance_dir, config_file, root, log])],
    })
    descriptors = [str(path) for path in sorted((instance_dir / "data" / "descriptors").glob("*.yaml"))]
    steps.append({
        "name": "audit",
        "file_dep": [str(panel), str(derived / "prices.csv"), str(boundaries_file)] + descriptors
        + [str(outputs / name) for name in ("manifest.json", "run_report.json")],
        "targets": [str(outputs / "audit_memo.md"), str(outputs / "audit_memo.html")],
        "actions": [(_audit, [instance_dir, log])],
    })
    fingerprint = _code_fingerprint()
    for step in steps:
        step["uptodate"] = [config_changed(fingerprint)]
    return steps
