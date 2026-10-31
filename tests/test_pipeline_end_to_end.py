import json
import shutil

import pandas as pd
from conftest import make_instance

from compound_shocks.cli import main

REPORT_PANEL = ["admin2_id", "month", "events", "fatalities", "precip_mm", "coverage_frac", "price_sorghum",
                "price_wheat", "displaced_individuals"]


def reproduce(root, instance="somalia"):
    return main(["reproduce", "--instance", instance, "--root", str(root)])


def paths(root, instance="somalia"):
    base = root / "instances" / instance
    return base / "data" / "derived", base / "outputs"


def ran(root):
    log = root / "instances/somalia/data/derived/ran.log"
    return log.read_text().split() if log.exists() else []


def swap_boundary_provider(root, name="swapped"):
    instance = make_instance(root, name, boundaries="geoboundaries_fixture.geojson")
    (instance / "data/raw/admin_boundaries/codab_fixture.geojson").unlink(missing_ok=True)
    config = instance / "config.yaml"
    config.write_text(config.read_text().replace("OCHA COD-AB", "geoBoundaries"), encoding="utf-8")
    return instance


def test_end_to_end_on_fixture_instance(root):
    assert reproduce(root) == 0
    derived, outputs = paths(root)
    panel = pd.read_csv(derived / "panel.csv", dtype={"admin2_id": str, "month": str})
    assert list(panel.columns) == REPORT_PANEL
    assert len(panel) == 3 * 3 and not panel.duplicated(["admin2_id", "month"]).any()
    published = pd.read_csv(outputs / "publishable_aggregates.csv")
    assert list(published.columns) == ["admin2_id", "month", "events", "fatalities"]
    assert (outputs / "manifest.json").exists()


def test_fixture_values_reach_the_panel(root):
    reproduce(root)
    derived, _ = paths(root)
    panel = pd.read_csv(derived / "panel.csv", dtype={"admin2_id": str, "month": str}).set_index(["admin2_id", "month"])
    assert panel.loc[("A", "2021-01"), "price_sorghum"] == 10
    assert panel.loc[("A", "2021-01"), "displaced_individuals"] == 20
    assert pd.isna(panel.loc[("B", "2021-01"), "price_sorghum"])
    assert panel.loc[("A", "2021-01"), "precip_mm"] == 20 and pd.isna(panel.loc[("A", "2021-03"), "precip_mm"])


def test_provider_swap_without_record_stops_before_processing(root, capsys):
    swap_boundary_provider(root)
    assert reproduce(root, "swapped") == 1
    assert "admin_boundaries" in capsys.readouterr().out
    assert not (root / "instances/swapped/data/derived").exists()


def test_provider_swap_with_record_proceeds(root):
    instance = swap_boundary_provider(root)
    record = instance / "harmonization" / "admin_boundaries.yaml"
    record.parent.mkdir()
    record.write_text(
        "schema_version: 0.1.0\nrole: admin_boundaries\nfrom_source: OCHA COD-AB\nto_source: geoBoundaries\n"
        "differences: fallback boundaries\ndecision: use fallback\nrationale: test\naffected_outputs: [panel]\n"
        "approved_by: tester\ndate: '2026-10-31'\n",
        encoding="utf-8",
    )
    assert reproduce(root, "swapped") == 0
    assert (root / "instances/swapped/data/derived/panel.csv").exists()


def test_manifest_lists_core_and_extension_columns(root):
    reproduce(root)
    manifest = json.loads((paths(root)[1] / "manifest.json").read_text(encoding="utf-8"))
    assert "events" in manifest["panel_columns"]["core"] and "displaced_individuals" in manifest["panel_columns"]["extension"]
    assert set(manifest["inputs"]) == {"conflict_events", "displacement", "prices", "rainfall", "admin_boundaries"}


def test_rerun_is_idempotent(root):
    reproduce(root)
    derived, outputs = paths(root)
    panel_before = (derived / "panel.csv").read_bytes()
    manifest_before = json.loads((outputs / "manifest.json").read_text(encoding="utf-8"))
    shutil.rmtree(derived)
    shutil.rmtree(outputs)
    assert reproduce(root) == 0
    manifest_after = json.loads((outputs / "manifest.json").read_text(encoding="utf-8"))
    assert (derived / "panel.csv").read_bytes() == panel_before
    manifest_before.pop("created_utc"), manifest_after.pop("created_utc")
    assert manifest_after == manifest_before


def test_second_run_does_no_work(root):
    reproduce(root)
    first = ran(root)
    assert first and reproduce(root) == 0
    assert ran(root) == first


def test_changed_input_reruns_only_dependents(root):
    reproduce(root)
    before = len(ran(root))
    price_file = root / "instances/somalia/data/raw/prices/wfp_prices_fixture.csv"
    price_file.write_text(price_file.read_text() + "2021-01-20,Market A,Alpha,Sorghum,kg,SOS,12\n")
    assert reproduce(root) == 0
    new = ran(root)[before:]
    assert "read:prices" in new and "fuse" in new
    assert "read:rainfall" not in new and "read:conflict_events" not in new


def test_adapter_problems_and_unassigned_reach_the_run_report(root):
    reproduce(root)
    report = json.loads((paths(root)[1] / "run_report.json").read_text(encoding="utf-8"))
    assert any("mixed unit" in warning for warning in report["warnings"])
    assert any("unknown reason" in warning for warning in report["warnings"])
    assert report["stats"]["unassigned_events"] == 0


def test_missing_role_stops_with_exit_1(root, capsys):
    shutil.rmtree(root / "instances/somalia/data/raw/prices")
    assert reproduce(root) == 1
    assert "prices" in capsys.readouterr().out


def test_unknown_instance_stops_with_exit_1(root):
    assert reproduce(root, "nowhere") == 1
