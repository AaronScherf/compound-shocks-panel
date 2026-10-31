"""Step graph for one instance. Steps pass data through files in data/derived so unchanged work is skipped."""

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
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

from compound_shocks.adapters import acled, boundaries, chirps, prmn, wfp_prices  # noqa: F401  (register adapters)
from compound_shocks.adapters.base import get_adapter
from compound_shocks.crosswalk import apply_crosswalk
from compound_shocks.panel import aggregate_conflict, fuse_panel, publishable_aggregates
from compound_shocks.schema import PANEL_COLUMNS, check_frame
from compound_shocks.spatial import assign_admin2

BASELINE_INSTANCE = "somalia"
TEXT_COLUMNS = ("admin2_id", "month", "date", "admin2", "origin_admin2", "dest_admin2", "market", "commodity",
                "unit", "currency", "reason", "event_id")


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


def _csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype={column: str for column in TEXT_COLUMNS})


def _log(log: Path, step: str) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as stream:
        stream.write(f"{step}\n")


def _report(path: Path, warnings: list[str], stats: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"warnings": warnings, "stats": stats}, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _read(role: str, provider: str, files: list[Path], target: Path, report: Path, boundaries_file: Path, log: Path) -> None:
    instance = {"boundaries": gpd.read_file(boundaries_file)} if role == "rainfall" else {}
    frame = get_adapter(role, provider).read(files, instance)
    fatal = check_frame(frame, role)
    if fatal:
        raise ValueError("; ".join(str(problem) for problem in fatal))
    if role == "admin_boundaries":
        frame.to_file(target, driver="GeoJSON")
    else:
        frame.to_csv(target, index=False)
    _report(report, [str(problem) for problem in frame.attrs.get("problems", [])], {f"rows_{role}": len(frame)})
    _log(log, f"read:{role}")


def _spatial(events_file: Path, boundaries_file: Path, target: Path, log: Path) -> None:
    assigned = assign_admin2(_csv(events_file), gpd.read_file(boundaries_file))
    assigned.to_csv(target, index=False)
    _log(log, "spatial")


def _aggregate(assigned_file: Path, target: Path, report: Path, log: Path) -> None:
    conflict = aggregate_conflict(_csv(assigned_file))
    conflict.to_csv(target, index=False)
    _report(report, [], {"unassigned_events": conflict.attrs["unassigned"]})
    _log(log, "aggregate")


def _fuse(derived: Path, months: list[str], target: Path, report: Path, log: Path) -> None:
    districts = gpd.read_file(derived / "admin_boundaries.geojson")
    names = dict(zip(districts["name"].astype(str), districts["admin2_id"].astype(str), strict=True))
    prices, price_problems = apply_crosswalk(_csv(derived / "prices.csv"), "admin2", names, "prices")
    moves, origin_problems = apply_crosswalk(_csv(derived / "displacement.csv"), "origin_admin2", names, "displacement")
    moves, dest_problems = apply_crosswalk(moves, "dest_admin2", names, "displacement")
    panel = fuse_panel(_csv(derived / "conflict_monthly.csv"), _csv(derived / "rainfall.csv"), prices, moves,
                       sorted(districts["admin2_id"].astype(str)), months)
    panel.to_csv(target, index=False)
    _report(report, [str(p) for p in price_problems + origin_problems + dest_problems], {"panel_rows": len(panel)})
    _log(log, "fuse")


def _outputs(instance_dir: Path, config_file: Path, root: Path, log: Path) -> None:
    derived, outputs = instance_dir / "data" / "derived", instance_dir / "outputs"
    panel = pd.read_csv(derived / "panel.csv", dtype={"admin2_id": str, "month": str})
    outputs.mkdir(parents=True, exist_ok=True)
    publishable_aggregates(panel).to_csv(outputs / "publishable_aggregates.csv", index=False)
    config, _ = load_yaml(config_file)
    raw_dir = instance_dir / "data" / "raw"
    manifest = build_manifest(config, collect_role_files(raw_dir, config["sources"]), raw_dir, code_version(root),
                              resolved_packages())
    manifest["panel_columns"] = {
        kind: sorted(name for name, k in PANEL_COLUMNS.items() if k == kind) for kind in ("core", "extension")
    }
    write_manifest(manifest, outputs / "manifest.json")
    warnings, stats = [], {}
    for part in sorted((derived / "reports").glob("*.json")):
        loaded = json.loads(part.read_text(encoding="utf-8"))
        warnings += [f"{part.stem}: {warning}" for warning in loaded["warnings"]]
        stats.update(loaded["stats"])
    _report(outputs / "run_report.json", warnings, stats)
    _log(log, "outputs")


def months_between(start: str, end: str) -> list[str]:
    return [period.strftime("%Y-%m") for period in pd.period_range(start, end, freq="M")]


def tasks(instance_dir: Path, config: dict, role_files: dict[str, list[Path]], root: Path) -> list[dict]:
    """doit task dicts: read:<role> per role, then spatial, aggregate, fuse, outputs."""
    derived = instance_dir / "data" / "derived"
    log, config_file = derived / "ran.log", instance_dir / "config.yaml"
    reports = derived / "reports"
    boundaries_file = derived / "admin_boundaries.geojson"
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
            "actions": [(_read, [role, config["sources"][role]["provider"], files, target, report, boundaries_file, log])],
        })
    events, assigned, conflict = derived / "conflict_events.csv", derived / "events_assigned.csv", derived / "conflict_monthly.csv"
    steps.append({
        "name": "spatial",
        "file_dep": [str(events), str(boundaries_file)],
        "targets": [str(assigned)],
        "actions": [(_spatial, [events, boundaries_file, assigned, log])],
    })
    steps.append({
        "name": "aggregate",
        "file_dep": [str(assigned)],
        "targets": [str(conflict), str(reports / "aggregate.json")],
        "actions": [(_aggregate, [assigned, conflict, reports / "aggregate.json", log])],
    })
    inputs = [conflict, boundaries_file] + [derived / f"{role}.csv" for role in ("prices", "displacement", "rainfall")]
    panel = derived / "panel.csv"
    steps.append({
        "name": "fuse",
        "file_dep": [str(path) for path in inputs] + [str(config_file)],
        "targets": [str(panel), str(reports / "fuse.json")],
        "actions": [(_fuse, [derived, months, panel, reports / "fuse.json", log])],
    })
    outputs = instance_dir / "outputs"
    raw_inputs = [str(path) for files in role_files.values() for path in files]
    steps.append({
        "name": "outputs",
        "file_dep": [str(panel), str(reports / "fuse.json"), str(config_file)] + raw_inputs,
        "targets": [str(outputs / name) for name in ("publishable_aggregates.csv", "manifest.json", "run_report.json")],
        "actions": [(_outputs, [instance_dir, config_file, root, log])],
    })
    return steps
