import argparse
from pathlib import Path

from doit.cmd_base import ModuleTaskLoader
from doit.doit_cmd import DoitMain
from reprokit.loader import load_yaml
from reprokit.problems import Problem

from .adapters.base import get_adapter
from .pipeline import check_instance_gate, tasks


def _role_files(instance_dir: Path, config: dict) -> dict[str, list[Path]]:
    raw = instance_dir / "data" / "raw"
    files = {}
    for role, source in config["sources"].items():
        found = get_adapter(role, source["provider"]).find(raw / role)
        if not found:
            raise FileNotFoundError(f"no files for role {role} in {raw / role}")
        files[role] = found
    return files


def _reproduce(instance: str, root: Path) -> int:
    instance_dir = root / "instances" / instance
    if not instance_dir.is_dir():
        print(Problem(str(instance_dir), "", f"instance {instance!r} not found"))
        return 1
    problems = check_instance_gate(root, instance_dir)
    if problems:
        for problem in problems:
            print(problem)
        return 1
    config, _ = load_yaml(instance_dir / "config.yaml")
    try:
        role_files = _role_files(instance_dir, config)
    except (FileNotFoundError, KeyError) as exc:
        print(Problem(str(instance_dir), "data/raw", str(exc)))
        return 1
    derived = instance_dir / "data" / "derived"
    derived.mkdir(parents=True, exist_ok=True)

    def task_steps():
        yield from tasks(instance_dir, config, role_files, root)

    namespace = {
        "task_steps": task_steps,
        "DOIT_CONFIG": {"dep_file": str(derived / ".doit-db.json"), "backend": "json", "verbosity": 0},
    }
    return int(bool(DoitMain(ModuleTaskLoader(namespace)).run(["run"])))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="compound-shocks")
    subcommands = parser.add_subparsers(dest="command", required=True)
    reproduce = subcommands.add_parser("reproduce", help="rebuild every output for one instance, skipping unchanged steps")
    reproduce.add_argument("--instance", required=True)
    reproduce.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    return _reproduce(args.instance, args.root)
