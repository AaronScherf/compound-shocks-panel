from pathlib import Path

import pytest

from compound_shocks.cli import main

ROLES = ["prices", "rainfall"]


@pytest.fixture
def root(tmp_path):
    for role in ROLES:
        raw = tmp_path / "instances/demo/data/raw" / role
        raw.mkdir(parents=True)
        (raw / "a.csv").write_text(f"{role},1\n")
    return tmp_path


def reproduce(root):
    return main(["reproduce", "--instance", "demo", "--root", str(root)])


def ran(root):
    log = root / "instances/demo/data/derived/ran.log"
    return log.read_text().split() if log.exists() else []


def test_reproduce_runs_skeleton_on_fixture_instance(root):
    assert reproduce(root) == 0
    assert (root / "instances/demo/data/derived/panel.csv").exists()


def test_second_run_does_no_work(root):
    reproduce(root)
    first = ran(root)
    assert first and reproduce(root) == 0
    assert ran(root) == first


def test_changed_input_reruns_only_dependents(root):
    reproduce(root)
    before = len(ran(root))
    (root / "instances/demo/data/raw/prices/a.csv").write_text("prices,2\n")
    assert reproduce(root) == 0
    new = ran(root)[before:]
    assert "read:prices" in new and "aggregate" in new and "fuse" in new
    assert "read:rainfall" not in new


def test_runs_with_no_make_installed(root, monkeypatch):
    monkeypatch.setenv("PATH", "")
    assert reproduce(root) == 0


def test_missing_instance_is_a_plain_error(root, capsys):
    assert main(["reproduce", "--instance", "nowhere", "--root", str(root)]) == 1
    assert "nowhere" in capsys.readouterr().out


def test_instance_with_no_raw_files_names_the_role(root, capsys):
    (root / "instances/demo/data/raw/prices/a.csv").unlink()
    assert reproduce(root) == 1
    assert "prices" in capsys.readouterr().out
