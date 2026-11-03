from pathlib import Path

import yaml
from reprokit.cli import main

ROOT = Path(__file__).parent.parent
ROLES = ["conflict_events", "displacement", "prices", "rainfall", "admin_boundaries", "population"]


def test_reprokit_validate_passes_on_repo(capsys):
    assert main(["validate", str(ROOT)]) == 0, capsys.readouterr().out


def test_somalia_and_sudan_instances_exist():
    assert (ROOT / "instances/somalia/config.yaml").exists()
    assert (ROOT / "instances/sudan").is_dir()


def test_somalia_config_names_all_five_roles_and_the_decided_window():
    config = yaml.safe_load((ROOT / "instances/somalia/config.yaml").read_text())
    assert sorted(config["sources"]) == sorted(ROLES)
    assert config["period"] == {"start": "2021-01-01", "end": "2023-08-31"}


def test_somalia_has_a_descriptor_for_every_role():
    folder = ROOT / "instances/somalia/data/descriptors"
    roles = {yaml.safe_load(path.read_text())["role"] for path in folder.glob("*.yaml")}
    assert roles == set(ROLES)


def test_acled_descriptor_records_provenance():
    descriptor = yaml.safe_load((ROOT / "instances/somalia/data/descriptors/conflict_events.yaml").read_text())
    assert descriptor["access_class"] == "account_required"
    assert descriptor["accessed"] == "2026-10-31"
    assert "1997-01-01" in descriptor["applied_filters"] and "2025-10-31" in descriptor["applied_filters"]


def test_raw_and_derived_instance_data_are_not_tracked():
    ignore = (ROOT / ".gitignore").read_text().splitlines()
    for pattern in ("/instances/*/data/raw/*", "/instances/*/data/derived/*", "/instances/*/outputs/*"):
        assert pattern in ignore
