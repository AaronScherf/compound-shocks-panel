import argparse
from pathlib import Path

from doit.cmd_base import ModuleTaskLoader
from doit.doit_cmd import DoitMain
from reprokit.loader import load_yaml
from reprokit.problems import Problem

from .adapters.base import get_adapter
from .fetch import FetchError, chirps_url, fetch_chirps, hdx
from .pipeline import check_instance_gate, months_between, tasks


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


# role -> (provider, what is fetched). The dataset IDs pinned in compound_shocks.fetch are Somalia's.
PINNED = {
    "prices": ("WFP", f"HDX {hdx.WFP_DATASET} / {hdx.WFP_RESOURCE}"),
    "displacement": ("UNHCR/NRC PRMN", f"HDX {hdx.PRMN_DATASET} / {hdx.PRMN_RESOURCE}"),
    "admin_boundaries": ("OCHA COD-AB", f"HDX {hdx.CODAB_DATASET} / {hdx.CODAB_RESOURCE} (Admin 2 layer)"),
}
CHIRPS_PROVIDER = "UCSB CHC CHIRPS"


def _fetch(instance: str, root: Path, dry_run: bool) -> int:
    instance_dir = root / "instances" / instance
    if not (instance_dir / "config.yaml").exists():
        print(Problem(str(instance_dir), "", f"instance {instance!r} not found"))
        return 1
    config, _ = load_yaml(instance_dir / "config.yaml")
    raw = instance_dir / "data" / "raw"
    months = months_between(config["period"]["start"], config["period"]["end"])
    fetchers = {"prices": hdx.fetch_wfp_prices, "displacement": hdx.fetch_prmn, "admin_boundaries": hdx.fetch_codab}
    downloads = []  # (description, action); decided for every role before anything is downloaded
    for role, source in config["sources"].items():
        provider = source["provider"]
        if role == "conflict_events":
            print(f"{role}: {provider} is a manual export (or fetch_acled with ACLED_EMAIL and ACLED_PASSWORD); skipped")
        elif role == "rainfall" and provider == CHIRPS_PROVIDER:
            downloads.append((f"{role}: CHIRPS v2.0, {len(months)} monthly files, e.g. {chirps_url(months[0])}",
                              lambda role=role: fetch_chirps(months, raw / role)))
        elif role in PINNED and provider == PINNED[role][0]:
            downloads.append((f"{role}: {PINNED[role][1]}", lambda role=role: fetchers[role](raw / role)))
        else:
            print(Problem(str(instance_dir), role, f"no pinned fetcher for provider {provider!r}; download it by hand"))
            return 1
    for description, action in downloads:
        print(description)
        if not dry_run:
            action()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="compound-shocks")
    subcommands = parser.add_subparsers(dest="command", required=True)
    fetch = subcommands.add_parser("fetch", help="download the public sources for one instance into data/raw")
    fetch.add_argument("--instance", required=True)
    fetch.add_argument("--root", type=Path, default=Path("."))
    fetch.add_argument("--dry-run", action="store_true", help="list what would be downloaded and download nothing")
    reproduce = subcommands.add_parser("reproduce", help="rebuild every output for one instance, skipping unchanged steps")
    reproduce.add_argument("--instance", required=True)
    reproduce.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    if args.command == "fetch":
        try:
            return _fetch(args.instance, args.root, args.dry_run)
        except FetchError as exc:
            print(Problem(str(args.root), "fetch", str(exc)))
            return 1
    return _reproduce(args.instance, args.root)
