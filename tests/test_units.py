import geopandas as gpd
import pytest
from shapely.geometry import box

from compound_shocks.schema import check_frame
from compound_shocks.units import merge_units


def frame():
    return gpd.GeoDataFrame(
        {"admin2_id": ["A", "B", "C"], "name": ["a", "b", "c"], "geometry": [box(0, 0, 1, 1), box(1, 0, 2, 1), box(3, 0, 4, 1)]},
        crs="EPSG:4326",
    )


MERGE = [{"id": "AB", "name": "Alpha-Bravo", "members": ["A", "B"]}]


def test_merge_dissolves_members_into_one_unit():
    merged, _ = merge_units(frame(), MERGE)
    assert sorted(merged["admin2_id"]) == ["AB", "C"]
    unit = merged[merged["admin2_id"] == "AB"].iloc[0]
    assert unit["name"] == "Alpha-Bravo" and unit.geometry.area == pytest.approx(2.0)
    assert unit.geometry.geom_type == "Polygon"


def test_merge_leaves_other_rows_untouched():
    merged, _ = merge_units(frame(), MERGE)
    other = merged[merged["admin2_id"] == "C"].iloc[0]
    assert other["name"] == "c" and other.geometry.equals(box(3, 0, 4, 1))


def test_merge_records_what_it_did():
    _, decisions = merge_units(frame(), MERGE)
    assert decisions == ["merged 2 districts (A, B) into AB (Alpha-Bravo)"]


def test_merge_result_passes_check_frame_and_keeps_vintage():
    source = frame()
    source.attrs["vintage"] = "v03"
    merged, _ = merge_units(source, MERGE)
    assert check_frame(merged, "admin_boundaries") == [] and merged.attrs["vintage"] == "v03"


def test_no_merges_returns_the_input_unchanged():
    merged, decisions = merge_units(frame(), [])
    assert merged["admin2_id"].tolist() == ["A", "B", "C"] and decisions == []


def test_unknown_member_raises_naming_it():
    with pytest.raises(ValueError, match="Z"):
        merge_units(frame(), [{"id": "AZ", "name": "x", "members": ["A", "Z"]}])


def test_member_in_two_merges_raises():
    merges = MERGE + [{"id": "BC", "name": "Bravo-Charlie", "members": ["B", "C"]}]
    with pytest.raises(ValueError, match="B"):
        merge_units(frame(), merges)


def test_merged_id_colliding_with_an_unmerged_district_raises():
    with pytest.raises(ValueError, match="C"):
        merge_units(frame(), [{"id": "C", "name": "x", "members": ["A", "B"]}])


def test_merge_entry_missing_a_key_raises_naming_it():
    with pytest.raises(ValueError, match="members"):
        merge_units(frame(), [{"id": "AB", "name": "x"}])
