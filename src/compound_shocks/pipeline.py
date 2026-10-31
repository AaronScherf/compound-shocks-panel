"""Step graph for one instance: read each role, aggregate, fuse. Steps declare inputs and outputs so unchanged work is skipped."""

from pathlib import Path


def _log(log: Path, step: str) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as stream:
        stream.write(f"{step}\n")


def _read(role: str, files: list[Path], target: Path, log: Path) -> None:
    lines = [line for path in files for line in path.read_text(encoding="utf-8").splitlines()]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _log(log, f"read:{role}")


def _concat(step: str, sources: list[Path], target: Path, log: Path) -> None:
    text = "".join(source.read_text(encoding="utf-8") for source in sources)
    target.write_text(text, encoding="utf-8")
    _log(log, step)


def tasks(instance_dir: Path, role_files: dict[str, list[Path]]) -> list[dict]:
    """doit task dicts: read:<role> for each role, then aggregate, then fuse."""
    derived = instance_dir / "data" / "derived"
    log = derived / "ran.log"
    read_targets = {role: derived / f"{role}.csv" for role in role_files}
    aggregate_target = derived / "aggregate.csv"
    panel_target = derived / "panel.csv"
    steps = [
        {
            "name": f"read:{role}",
            "file_dep": [str(path) for path in files],
            "targets": [str(read_targets[role])],
            "actions": [(_read, [role, files, read_targets[role], log])],
        }
        for role, files in role_files.items()
    ]
    steps.append(
        {
            "name": "aggregate",
            "file_dep": [str(target) for target in read_targets.values()],
            "targets": [str(aggregate_target)],
            "actions": [(_concat, ["aggregate", list(read_targets.values()), aggregate_target, log])],
        }
    )
    steps.append(
        {
            "name": "fuse",
            "file_dep": [str(aggregate_target)],
            "targets": [str(panel_target)],
            "actions": [(_concat, ["fuse", [aggregate_target], panel_target, log])],
        }
    )
    return steps
