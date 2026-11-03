import pandas as pd
import pytest

from compound_shocks.adapters.base import get_adapter
from compound_shocks.panel import fuse_panel
from compound_shocks.schema import check_frame
from compound_shocks.units import merge_populations


def read(tmp_path, text, name="pop.csv"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return get_adapter("population", "OCHA COD-PS").read([path], {})


def test_somalia_style_columns_pass_check_frame(tmp_path):
    result = read(tmp_path, "admin2Pcode,Admin2Name_en,T_TL,T_TL_2005\nSO1101,Borama,398609,215616\n")
    assert check_frame(result, "population") == [] and result["population"].tolist() == [398609]


def test_sudan_style_columns_are_found_case_insensitively(tmp_path):
    result = read(tmp_path, "Year,ADM2_PCODE,T_TL\n2024,SD01001,1500\n")
    assert result[["admin2_id", "population"]].values.tolist() == [["SD01001", 1500]]


def test_file_without_a_total_column_is_refused(tmp_path):
    with pytest.raises(ValueError, match="needs a district code column"):
        read(tmp_path, "admin2Pcode,other\nA,1\n")


def test_merged_districts_add_their_populations():
    population = pd.DataFrame({"admin2_id": ["A", "B", "C"], "population": [10.0, 5.0, 7.0]})
    result, notes = merge_populations(population, [{"id": "M", "name": "Merged", "members": ["A", "B", "Z"]}])
    assert dict(zip(result["admin2_id"], result["population"])) == {"C": 7.0, "M": 15.0}
    assert "2 of 3 members of M had a row" in notes[0]


def test_population_is_repeated_in_every_month_and_missing_district_stays_nan():
    conflict = pd.DataFrame({"admin2_id": ["A"], "month": ["2021-01"], "events": [1], "fatalities": [0]})
    rainfall = pd.DataFrame({"admin2_id": ["A", "B"] * 2, "month": ["2021-01"] * 2 + ["2021-02"] * 2,
                             "precip_mm": 1.0, "coverage_frac": 1.0})
    prices = pd.DataFrame({"date": pd.Series([], dtype=object), "admin2": pd.Series([], dtype=object),
                           "commodity": pd.Series([], dtype=object), "price": pd.Series([], dtype=float)})
    moves = pd.DataFrame({"origin_admin2": [], "month": [], "individuals": []})
    population = pd.DataFrame({"admin2_id": ["A"], "population": [100.0]})
    panel = fuse_panel(conflict, rainfall, prices, moves, ["A", "B"], ["2021-01", "2021-02"], population)
    assert panel.loc[panel["admin2_id"] == "A", "population"].tolist() == [100.0, 100.0]
    assert panel.loc[panel["admin2_id"] == "B", "population"].isna().all()
