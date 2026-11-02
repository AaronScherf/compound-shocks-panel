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
    assert panel.loc[("A", "2021-01"), "displaced_individuals"] == 25
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


def merged_instance(root, aliases=True):
    instance = make_instance(root, "merged")
    config = instance / "config.yaml"
    config.write_text(
        config.read_text(encoding="utf-8") + "  merge_districts:\n    - id: AB\n      name: Merged\n      members: [A, B]\n",
        encoding="utf-8",
    )
    if aliases:
        crosswalks = instance / "crosswalks"
        crosswalks.mkdir()
        (crosswalks / "district_names.yaml").write_text("Alpha: Merged\nBravo: Merged\n", encoding="utf-8")
    return instance


def test_merge_and_aliases_come_from_instance_files(root):
    merged_instance(root)
    assert reproduce(root, "merged") == 0
    derived, _ = paths(root, "merged")
    panel = pd.read_csv(derived / "panel.csv", dtype={"admin2_id": str, "month": str}).set_index(["admin2_id", "month"])
    assert sorted(panel.index.get_level_values("admin2_id").unique()) == ["AB", "C"]
    assert panel.loc[("AB", "2021-01"), "price_sorghum"] == 10 and panel.loc[("AB", "2021-01"), "displaced_individuals"] == 25


def test_run_report_and_manifest_record_every_processing_decision(root):
    merged_instance(root)
    reproduce(root, "merged")
    _, outputs = paths(root, "merged")
    report = json.loads((outputs / "run_report.json").read_text(encoding="utf-8"))
    assert "merged 2 districts (A, B) into AB (Merged)" in report["decisions"]
    assert any("district_names.yaml" in decision for decision in report["decisions"])
    assert report["stats"]["boundary_vintage"] == "v03, valid on 2025-01-08"
    manifest = json.loads((outputs / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["instance_files"]) == {"config.yaml", "crosswalks/district_names.yaml"}
    assert manifest["parameters"]["merge_districts"][0]["id"] == "AB"


def test_editing_a_crosswalk_reruns_the_fuse_step(root):
    instance = merged_instance(root)
    reproduce(root, "merged")
    log = instance / "data/derived/ran.log"
    before = len(log.read_text().split())
    (instance / "crosswalks/district_names.yaml").write_text("Alpha: Merged\nBravo: Merged\n# edited\n", encoding="utf-8")
    assert reproduce(root, "merged") == 0
    assert "fuse" in log.read_text().split()[before:]


def test_unmatched_names_are_reported_not_fatal(root):
    merged_instance(root, aliases=False)
    assert reproduce(root, "merged") == 0
    _, outputs = paths(root, "merged")
    report = json.loads((outputs / "run_report.json").read_text(encoding="utf-8"))
    assert any("Alpha" in warning and "unmatched" in warning for warning in report["warnings"])


def test_bad_merge_member_stops_with_exit_1(root, capsys):
    instance = merged_instance(root)
    config = instance / "config.yaml"
    config.write_text(config.read_text(encoding="utf-8").replace("[A, B]", "[A, ZZ]"), encoding="utf-8")
    assert reproduce(root, "merged") == 1
    assert not (instance / "outputs/manifest.json").exists()


def test_events_outside_the_study_period_are_excluded_and_reported(root):
    reproduce(root)
    _, outputs = paths(root)
    report = json.loads((outputs / "run_report.json").read_text(encoding="utf-8"))
    assert any("outside the study period 2021-01-01 to 2021-03-31" in decision for decision in report["decisions"])
    assert report["stats"]["events_in_period"] + report["stats"]["events_outside_period"] == report["stats"]["rows_conflict_events"]
    assert report["stats"]["events_outside_period"] > 0


def test_price_rows_outside_the_period_are_reported_as_a_decision(root):
    price_file = root / "instances/somalia/data/raw/prices/wfp_prices_fixture.csv"
    price_file.write_text(price_file.read_text() + "2015-01-15,Market A,Alpha,Sorghum,kg,SOS,9\n")
    reproduce(root)
    report = json.loads((paths(root)[1] / "run_report.json").read_text(encoding="utf-8"))
    assert any("WFP" in decision and "dropped 1" in decision for decision in report["decisions"])


def test_csv_outputs_use_lf_line_endings_on_every_platform(root):
    reproduce(root)
    derived, outputs = paths(root)
    for path in (derived / "panel.csv", derived / "conflict_events.csv", outputs / "publishable_aggregates.csv"):
        assert b"\r" not in path.read_bytes(), path.name


def test_a_code_change_reruns_every_step(root, monkeypatch):
    from compound_shocks import pipeline

    reproduce(root)
    log = root / "instances/somalia/data/derived/ran.log"
    before = len(log.read_text().split())
    monkeypatch.setattr(pipeline, "_code_fingerprint", lambda: "a-different-version-of-the-code")
    assert reproduce(root) == 0
    rerun = log.read_text().split()[before:]
    for step in ("read:conflict_events", "read:prices", "read:admin_boundaries", "spatial", "aggregate", "fuse", "outputs"):
        assert step in rerun, step


def test_manifest_records_the_code_fingerprint_and_it_is_stable(root):
    from compound_shocks import pipeline

    reproduce(root)
    manifest = json.loads((paths(root)[1] / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["code_fingerprint"] == pipeline._code_fingerprint()


def test_text_hash_ignores_line_endings(tmp_path):
    from compound_shocks.pipeline import _text_hash

    (tmp_path / "lf.yaml").write_bytes(b"a: 1\nb: 2\n")
    (tmp_path / "crlf.yaml").write_bytes(b"a: 1\r\nb: 2\r\n")
    assert _text_hash(tmp_path / "lf.yaml") == _text_hash(tmp_path / "crlf.yaml")
