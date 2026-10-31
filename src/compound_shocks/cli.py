import argparse
from pathlib import Path

from doit.cmd_base import ModuleTaskLoader
from doit.doit_cmd import DoitMain
from reprokit.manifest import collect_role_files
from reprokit.problems import Problem

from .pipeline import tasks


def _role_files(instance_dir: Path) -> dict[str, list[Path]]:
    raw = instance_dir / "data" / "raw"
    roles = [path.name for path in sorted(raw.iterdir()) if path.is_dir()]
    return collect_role_files(raw, roles)


def _reproduce(instance: str, root: Path) -> int:
    instance_dir = root / "instances" / instance
    if not instance_dir.is_dir():
        print(Problem(str(instance_dir), "", f"instance {instance!r} not found"))
        return 1
    try:
        role_files = _role_files(instance_dir)
    except FileNotFoundError as exc:
        print(Problem(str(instance_dir), "data/raw", str(exc)))
        return 1
    derived = instance_dir / "data" / "derived"
    derived.mkdir(parents=True, exist_ok=True)

    def task_steps():
        yield from tasks(instance_dir, role_files)

    namespace = {
        "task_steps": task_steps,
        "DOIT_CONFIG": {"dep_file": str(derived / ".doit-db.json"), "backend": "json", "verbosity": 0},
    }
    return DoitMain(ModuleTaskLoader(namespace)).run(["run"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="compound-shocks")
    subcommands = parser.add_subparsers(dest="command", required=True)
    reproduce = subcommands.add_parser("reproduce", help="rebuild every output for one instance, skipping unchanged steps")
    reproduce.add_argument("--instance", required=True)
    reproduce.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    return _reproduce(args.instance, args.root)
