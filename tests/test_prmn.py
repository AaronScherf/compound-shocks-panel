from pathlib import Path

import pandas as pd
import pytest

from compound_shocks.adapters.prmn import PrmnAdapter
from compound_shocks.schema import check_frame

FIXTURE = Path(__file__).parent / "fixtures" / "prmn_fixture.xlsx"


def read():
    return PrmnAdapter().read([FIXTURE], {})


def test_find_returns_xlsx_files_only(tmp_path):
    (tmp_path / "a.xlsx").write_text("x")
    (tmp_path / "stale_summary.csv").write_text("x")
    assert [p.name for p in PrmnAdapter().find(tmp_path)] == ["a.xlsx"]


def test_prmn_weekly_rows_are_summed_into_district_month():
    frame = read()
    january = frame[frame["month"] == "2021-01"]
    assert len(january) == 1 and january["individuals"].iloc[0] == 25
    assert not frame.duplicated(["month", "origin_admin2", "dest_admin2", "reason"]).any()


def test_prmn_month_end_is_parsed_day_first():
    assert read()["month"].tolist() == ["2021-01", "2021-02", "2021-03", "2021-04"]


def test_prmn_unreported_month_is_nan_not_zero():
    frame = read()
    assert pd.isna(frame.loc[frame["month"] == "2021-02", "individuals"].iloc[0])
    assert "2021-05" not in frame["month"].tolist()


def test_prmn_departure_and_arrival_columns_map_to_origin_and_destination():
    row = read().iloc[0]
    assert (row["origin_admin2"], row["dest_admin2"]) == ("Alpha", "Bravo")


def test_prmn_reason_categories_mapped_and_unknown_reported():
    frame = read()
    assert frame["reason"].tolist() == ["drought", "conflict", "flood", "other"]
    assert len(frame.attrs["problems"]) == 1
    assert "Unclear" in str(frame.attrs["problems"][0])


def test_prmn_output_passes_check_frame():
    assert check_frame(read(), "displacement") == []


def test_prmn_missing_source_column_names_it(tmp_path):
    import openpyxl

    book = openpyxl.Workbook()
    book.active.append(["Month End", "Reason"])
    path = tmp_path / "bad.xlsx"
    book.save(path)
    with pytest.raises(ValueError, match="Number of Individuals"):
        PrmnAdapter().read([path], {})
