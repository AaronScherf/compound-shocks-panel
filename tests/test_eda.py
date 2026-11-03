import numpy as np
import pandas as pd
import pytest

from compound_shocks.eda import (
    CONFLICT_COLUMNS,
    SOURCE_GROUPS,
    data_profile,
    district_summary,
)
from compound_shocks.schema import PANEL_COLUMNS

NAN = np.nan


def make_panel():
    rows = []
    for district in ("D1", "D2", "D3"):
        for month in ("2021-01", "2021-02", "2021-03"):
            rows.append({"admin2_id": district, "month": month, "events": 0, "fatalities": 0, "precip_mm": 5.0,
                         "coverage_frac": 1.0, "price_sorghum": NAN, "price_wheat": NAN,
                         "displaced_individuals": NAN})
    panel = pd.DataFrame(rows)
    panel.loc[(panel.admin2_id == "D1") & (panel.month == "2021-02"), ["events", "fatalities"]] = [4, 9]
    panel.loc[(panel.admin2_id == "D1") & (panel.month == "2021-02"), "price_sorghum"] = 10.0
    panel.loc[(panel.admin2_id == "D2") & (panel.month == "2021-03"), "price_sorghum"] = 12.0
    panel.loc[(panel.admin2_id == "D2") & (panel.month == "2021-01"), "displaced_individuals"] = 0.0
    return panel


def test_profile_counts_zeros_and_nans_separately():
    profile = data_profile(make_panel())["columns"]
    assert profile["events"]["zero"] == 8 and profile["events"]["null"] == 0
    assert profile["price_sorghum"]["non_null"] == 2 and profile["price_sorghum"]["null"] == 7
    assert profile["price_sorghum"]["zero"] == 0
    assert profile["displaced_individuals"]["zero"] == 1 and profile["displaced_individuals"]["non_null"] == 1


def test_profile_reports_district_coverage_per_source():
    profile = data_profile(make_panel())
    assert profile["columns"]["price_sorghum"]["districts_with_value"] == 2
    assert profile["groups"]["prices"]["districts_with_value"] == 2
    assert profile["groups"]["displacement"]["districts_with_value"] == 1
    assert profile["groups"]["rainfall"]["districts_with_value"] == 3
    assert profile["districts"] == 3 and profile["months"] == 3 and profile["rows"] == 9


def test_profile_reports_month_range_of_observed_values():
    column = data_profile(make_panel())["columns"]["price_sorghum"]
    assert (column["min_month"], column["max_month"]) == ("2021-02", "2021-03")
    assert data_profile(make_panel())["columns"]["price_wheat"]["min_month"] is None


def test_every_non_key_panel_column_belongs_to_one_source_group():
    grouped = [column for columns in SOURCE_GROUPS.values() for column in columns]
    assert set(make_panel().columns) - {"admin2_id", "month"} <= set(grouped)
    assert len(grouped) == len(set(grouped))
    assert set(grouped) - {"displaced_stock", "displaced_stock_change"} <= set(PANEL_COLUMNS)


def test_profile_rejects_a_panel_missing_key_columns():
    with pytest.raises(ValueError, match="admin2_id"):
        data_profile(make_panel().drop(columns=["admin2_id"]))


def test_district_summary_sums_conflict_columns_and_gives_coverage_share_otherwise():
    panel = make_panel()
    events = district_summary(panel, "events")
    assert events["D1"] == 4 and events["D2"] == 0 and CONFLICT_COLUMNS >= {"events", "fatalities"}
    price = district_summary(panel, "price_sorghum")
    assert price["D1"] == pytest.approx(1 / 3) and price["D3"] == 0


def test_missingness_vs_conflict_separates_districts_and_months():
    from compound_shocks.eda import missingness_vs_conflict

    panel = pd.DataFrame({
        "admin2_id": ["A"] * 4 + ["B"] * 2,
        "month": ["2021-01", "2021-02", "2022-01", "2022-02", "2021-01", "2021-02"],
        "events": [5, 0, 0, 3, 9, 9], "fatalities": [1, 0, 0, 0, 4, 4],
        "price_sorghum": [10.0, np.nan, 12.0, np.nan, np.nan, np.nan],
    })
    result = missingness_vs_conflict(panel)
    assert result["districts_ever"] == {"with_value": 1, "without_value": 1}
    assert result["district_cut"]["never_has_value"]["mean_events"] == 9
    assert result["month_cut"]["with_value"]["mean_events"] == 2.5 and result["month_cut"]["without_value"]["mean_events"] == 1.5
    assert [y["year"] for y in result["by_year"]] == ["2021", "2022"]
    assert result["by_year"][0]["share_observed"] == 0.5
    with pytest.raises(ValueError, match="unknown panel column"):
        missingness_vs_conflict(panel, "nope")


def test_conflict_rate_per_100k_is_reported_when_population_is_present():
    from compound_shocks.eda import missingness_vs_conflict

    panel = pd.DataFrame({
        "admin2_id": ["A", "A", "B", "B"], "month": ["2021-01", "2021-02"] * 2, "events": [10, 10, 1, 1],
        "fatalities": 0, "population": [100_000, 100_000, 1_000, 1_000], "price_sorghum": [1.0, 1.0, NAN, NAN],
    })
    cut = missingness_vs_conflict(panel)["district_cut"]
    assert cut["ever_has_value"]["events_per_100k"] == 10 and cut["never_has_value"]["events_per_100k"] == 100
    assert missingness_vs_conflict(panel.drop(columns="population"))["district_cut"]["ever_has_value"]["events_per_100k"] is None
