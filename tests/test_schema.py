import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Polygon

from compound_shocks.schema import PANEL_COLUMNS, ROLE_COLUMNS, check_frame

SQUARE = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])

VALID = {
    "conflict_events": pd.DataFrame(
        {"event_id": ["a1", "a2"], "date": ["2021-01-05", "2021-01-09"], "lat": [2.0, 3.1], "lon": [45.3, 44.9],
         "event_type": ["Battles", "Riots"], "sub_event_type": ["Armed clash", "Violent demonstration"],
         "actor1": ["x", "y"], "fatalities": [0, 3], "geo_precision": [1, 2]}
    ),
    "displacement": pd.DataFrame(
        {"month": ["2021-01", "2021-01"], "origin_admin2": ["SO0101", "SO0102"], "dest_admin2": ["SO0201", "SO0201"],
         "individuals": [10.0, float("nan")], "reason": ["drought", "conflict"]}
    ),
    "prices": pd.DataFrame(
        {"date": ["2021-01-15"], "market": ["Baidoa"], "admin2": ["SO0101"], "commodity": ["Sorghum (red)"],
         "unit": ["KG"], "currency": ["SOS"], "price": [10500.0]}
    ),
    "rainfall": pd.DataFrame({"admin2_id": ["SO0101"], "month": ["2021-01"], "precip_mm": [12.5], "coverage_frac": [1.0]}),
    "admin_boundaries": gpd.GeoDataFrame({"admin2_id": ["SO0101"], "name": ["Baidoa"], "geometry": [SQUARE]}),
}


@pytest.mark.parametrize("role", sorted(ROLE_COLUMNS))
def test_valid_frame_passes_for_every_role(role):
    assert check_frame(VALID[role], role) == []


def test_every_role_has_a_valid_example():
    assert sorted(VALID) == sorted(ROLE_COLUMNS)


def test_check_frame_names_missing_column():
    problems = check_frame(VALID["prices"].drop(columns=["unit"]), "prices")
    assert len(problems) == 1 and "unit" in str(problems[0])


def test_check_frame_flags_extra_column():
    problems = check_frame(VALID["prices"].assign(notes="x"), "prices")
    assert len(problems) == 1 and "notes" in str(problems[0])


def test_check_frame_flags_wrong_dtype():
    problems = check_frame(VALID["conflict_events"].assign(fatalities=["0", "3"]), "conflict_events")
    assert len(problems) == 1 and "fatalities" in str(problems[0])


def test_check_frame_flags_duplicate_keys():
    frame = pd.concat([VALID["conflict_events"], VALID["conflict_events"].iloc[[0]]], ignore_index=True)
    problems = check_frame(frame, "conflict_events")
    assert len(problems) == 1 and "duplicate" in str(problems[0]) and "event_id" in str(problems[0])


def test_same_price_in_two_units_is_not_a_duplicate_key():
    frame = pd.concat([VALID["prices"], VALID["prices"].assign(unit="L")], ignore_index=True)
    assert check_frame(frame, "prices") == []


def test_unknown_role_raises_keyerror_listing_roles():
    with pytest.raises(KeyError, match="conflict_events"):
        check_frame(pd.DataFrame(), "nonsense")


def test_every_panel_column_is_core_or_extension():
    assert set(PANEL_COLUMNS.values()) == {"core", "extension"}
