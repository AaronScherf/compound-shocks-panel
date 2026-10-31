import numpy as np
import pandas as pd
import pytest

from compound_shocks.panel import (
    aggregate_conflict,
    fuse_panel,
    month_of,
    publishable_aggregates,
)
from compound_shocks.schema import PANEL_COLUMNS

IDS = ["D1", "D2"]
MONTHS = ["2021-01", "2021-02"]


def events(rows):
    return pd.DataFrame(rows, columns=["admin2_id", "date", "fatalities"]).assign(
        event_id=lambda d: [f"e{i}" for i in range(len(d))], lat=0.5, lon=0.5, event_type="Battles",
        sub_event_type="x", actor1="secret actor", geo_precision=1,
    ).astype({"admin2_id": "string"})


EMPTY_RAIN = pd.DataFrame({"admin2_id": ["D1"], "month": ["2021-01"], "precip_mm": [5.0], "coverage_frac": [1.0]})
EMPTY_PRICES = pd.DataFrame(columns=["date", "market", "admin2", "commodity", "unit", "currency", "price"])
EMPTY_DISP = pd.DataFrame(columns=["month", "origin_admin2", "dest_admin2", "individuals", "reason"])


def build(conflict_rows, prices=EMPTY_PRICES, disp=EMPTY_DISP):
    conflict = aggregate_conflict(events(conflict_rows))
    return fuse_panel(conflict, EMPTY_RAIN, prices, disp, IDS, MONTHS)


@pytest.mark.parametrize("date,month", [("2021-01-31", "2021-01"), ("2021-02-28", "2021-02"), ("2021-12-31", "2021-12")])
def test_month_boundaries(date, month):
    assert month_of(date) == month


def test_aggregate_counts_events_and_sums_fatalities():
    out = aggregate_conflict(events([("D1", "2021-01-02", 2), ("D1", "2021-01-30", 3)]))
    assert out.to_dict("records") == [{"admin2_id": "D1", "month": "2021-01", "events": 2, "fatalities": 5}]


def test_district_month_without_events_is_zero():
    panel = build([("D1", "2021-01-02", 2)])
    row = panel[(panel.admin2_id == "D2") & (panel.month == "2021-02")].iloc[0]
    assert row["events"] == 0 and row["fatalities"] == 0


def test_missing_price_is_nan_not_zero():
    panel = build([])
    assert panel["price_sorghum"].isna().all() and panel["price_wheat"].isna().all()


def test_prices_average_markets_by_commodity_and_month():
    prices = pd.DataFrame({
        "date": ["2021-01-15", "2021-01-20", "2021-01-15"], "market": ["A", "B", "A"], "admin2": ["D1", "D1", "D1"],
        "commodity": ["Sorghum (red)", "Sorghum (white)", "Wheat flour"], "unit": ["KG"] * 3,
        "currency": ["SOS"] * 3, "price": [10.0, 20.0, 7.0],
    })
    panel = build([], prices=prices)
    row = panel[(panel.admin2_id == "D1") & (panel.month == "2021-01")].iloc[0]
    assert row["price_sorghum"] == 15.0 and row["price_wheat"] == 7.0


def test_missing_displacement_is_nan_and_reported_is_summed():
    disp = pd.DataFrame({"month": ["2021-01", "2021-01"], "origin_admin2": ["D1", "D1"], "dest_admin2": ["D2", "D2"],
                         "individuals": [4.0, 6.0], "reason": ["drought", "conflict"]})
    panel = build([], disp=disp)
    d1 = panel[(panel.admin2_id == "D1") & (panel.month == "2021-01")].iloc[0]
    assert d1["displaced_individuals"] == 10.0
    assert np.isnan(panel[(panel.admin2_id == "D2") & (panel.month == "2021-01")].iloc[0]["displaced_individuals"])


def test_panel_keys_unique_and_complete():
    panel = build([("D1", "2021-01-02", 2)])
    assert len(panel) == len(IDS) * len(MONTHS)
    assert not panel.duplicated(["admin2_id", "month"]).any()


def test_unassigned_events_are_not_in_panel_but_counted():
    ev = events([("D1", "2021-01-02", 2), (None, "2021-01-03", 4)])
    conflict = aggregate_conflict(ev)
    assert conflict.attrs["unassigned"] == 1
    panel = fuse_panel(conflict, EMPTY_RAIN, EMPTY_PRICES, EMPTY_DISP, IDS, MONTHS)
    assert panel["events"].sum() == 1 and panel["fatalities"].sum() == 2


def test_events_outside_requested_months_are_dropped():
    panel = build([("D1", "2020-12-31", 9)])
    assert panel["events"].sum() == 0


def test_column_kinds_copy_panel_columns():
    assert build([]).attrs["column_kinds"] == PANEL_COLUMNS


def test_publishable_aggregates_has_no_coordinates_ids_actors_or_event_types():
    out = publishable_aggregates(build([("D1", "2021-01-02", 2)]))
    assert list(out.columns) == ["admin2_id", "month", "events", "fatalities"]
