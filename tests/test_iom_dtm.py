import pandas as pd
import pytest
from conftest import make_instance

from compound_shocks.adapters.base import get_adapter
from compound_shocks.cli import main
from compound_shocks.panel import stock_change
from compound_shocks.schema import check_frame

COLUMNS = ["operation", "adminLevel", "admin2Name", "idpOriginAdmin1Pcode", "numPresentIdpInd", "reportingDate",
           "displacementReason"]
OVERVIEW, MONTHLY = "Armed Clashes in Sudan (Overview)", "Armed Clashes in Sudan (Monthly)"
PERIOD = {"start": "2021-01-01", "end": "2021-03-31"}


def write_dtm(path, rows):
    pd.DataFrame(rows, columns=COLUMNS).to_csv(path, index=False)
    return path


def read(tmp_path, rows, period=PERIOD):
    return get_adapter("displacement", "IOM DTM").read([write_dtm(tmp_path / "dtm.csv", rows)], {"period": period})


def test_iom_dtm_output_passes_check_frame(tmp_path):
    result = read(tmp_path, [[OVERVIEW, "2", "Alpha", "SD01", "100", "2021-01-31T00:00:00", "Conflict"]])
    assert check_frame(result, result.attrs["schema"]) == []
    assert list(result.columns) == ["month", "dest_admin2", "origin_admin1", "stock"]


def test_latest_report_in_the_month_wins_and_reasons_are_added(tmp_path):
    result = read(tmp_path, [
        [OVERVIEW, "2", "Alpha", "SD01", "100", "2021-01-10T00:00:00", "Conflict"],
        [OVERVIEW, "2", "Alpha", "SD01", "70", "2021-01-31T00:00:00", "Conflict"],
        [OVERVIEW, "2", "Alpha", "SD01", "5", "2021-01-31T00:00:00", "Natural disaster"],
    ])
    assert result["stock"].tolist() == [75]


def test_preferred_series_wins_on_the_same_day(tmp_path):
    result = read(tmp_path, [
        [MONTHLY, "2", "Alpha", "SD01", "999", "2021-01-31T00:00:00", "Conflict"],
        [OVERVIEW, "2", "Alpha", "SD01", "100", "2021-01-31T00:00:00", "Conflict"],
    ])
    assert result["stock"].tolist() == [100]


def test_only_locality_rows_inside_the_period_are_kept(tmp_path):
    result = read(tmp_path, [
        [OVERVIEW, "1", "", "SD01", "500", "2021-01-31T00:00:00", "Conflict"],
        [OVERVIEW, "2", "Alpha", "SD01", "100", "2020-12-31T00:00:00", "Conflict"],
        [OVERVIEW, "2", "Alpha", "SD01", "40", "2021-02-28T00:00:00", "Conflict"],
    ])
    assert result[["month", "stock"]].values.tolist() == [["2021-02", 40]]
    assert "1 locality rows outside the study period" in result.attrs["decisions"][0]


def test_missing_origin_is_kept_as_not_available(tmp_path):
    result = read(tmp_path, [[OVERVIEW, "2", "Alpha", None, "8", "2021-01-31T00:00:00", "Conflict"]])
    assert result["origin_admin1"].tolist() == ["Not available"]


def test_stock_change_nan_when_month_missing():
    stock = pd.DataFrame({
        "dest_admin2": ["Alpha"] * 3, "month": ["2021-01", "2021-02", "2021-04"], "stock": [100.0, 130.0, 200.0],
    })
    result = stock_change(stock)
    assert result["stock_change"].isna().tolist() == [True, False, True]
    assert result.loc[1, "stock_change"] == 30


def test_stock_change_adds_origins_before_differencing():
    stock = pd.DataFrame({
        "dest_admin2": ["Alpha"] * 4, "month": ["2021-01", "2021-01", "2021-02", "2021-02"],
        "origin_admin1": ["SD01", "SD02"] * 2, "stock": [10.0, 5.0, 12.0, 8.0],
    })
    assert stock_change(stock).loc[1, "stock_change"] == 5


def sudan_instance(root, with_record):
    instance = make_instance(root, "sudan")
    config = instance / "config.yaml"
    config.write_text(config.read_text(encoding="utf-8").replace("UNHCR/NRC PRMN", "IOM DTM"), encoding="utf-8")
    for old in (instance / "data/raw/displacement").glob("*"):
        old.unlink()
    write_dtm(instance / "data/raw/displacement/dtm.csv", [
        [OVERVIEW, "2", "Alpha", "SD01", "100", "2021-01-31T00:00:00", "Conflict"],
        [OVERVIEW, "2", "Alpha", "SD01", "130", "2021-02-28T00:00:00", "Conflict"],
        [OVERVIEW, "2", "Bravo", "SD02", "50", "2021-03-31T00:00:00", "Conflict"],
    ])
    if with_record:
        record = instance / "harmonization" / "displacement.yaml"
        record.parent.mkdir()
        record.write_text(
            "schema_version: 0.1.0\nrole: displacement\nfrom_source: UNHCR/NRC PRMN\nto_source: IOM DTM\n"
            "differences: stock instead of flow\ndecision: use stock and its monthly change\nrationale: test\n"
            "affected_outputs: [panel]\napproved_by: tester\ndate: '2026-11-02'\n",
            encoding="utf-8",
        )
    return instance


def test_sudan_reproduce_blocked_without_displacement_record(root, capsys):
    sudan_instance(root, with_record=False)
    assert main(["reproduce", "--instance", "sudan", "--root", str(root)]) == 1
    assert "displacement" in capsys.readouterr().out
    assert not (root / "instances/sudan/data/derived").exists()


@pytest.fixture
def sudan_root(root):
    sudan_instance(root, with_record=True)
    assert main(["reproduce", "--instance", "sudan", "--root", str(root)]) == 0
    return root


def test_sudan_reproduce_with_record_produces_panel_and_manifest(sudan_root):
    base = sudan_root / "instances/sudan"
    panel = pd.read_csv(base / "data/derived/panel.csv", dtype={"admin2_id": str, "month": str})
    assert "displaced_stock" in panel and "displaced_individuals" not in panel
    values = panel.set_index(["admin2_id", "month"])
    assert values.loc[("A", "2021-02"), "displaced_stock"] == 130 and values.loc[("A", "2021-02"), "displaced_stock_change"] == 30
    assert pd.isna(values.loc[("A", "2021-03"), "displaced_stock"]) and pd.isna(values.loc[("B", "2021-03"), "displaced_stock_change"])
    assert (base / "outputs/manifest.json").exists() and (base / "outputs/audit_memo.md").exists()
