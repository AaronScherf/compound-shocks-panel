import pandas as pd

from compound_shocks.crosswalk import apply_crosswalk


def test_crosswalk_reports_every_unmatched_name():
    source = pd.DataFrame({"admin2": ["Alpha", "Missing B", "Missing C", "Missing B"]})
    result, problems = apply_crosswalk(source, "admin2", {"Alpha": "A"}, "prices")
    assert result["admin2"].tolist()[0] == "A"
    assert pd.isna(result["admin2"].iloc[1])
    assert len(problems) == 2
    assert all(name in " ".join(map(str, problems)) for name in ("Missing B", "Missing C"))


def test_adapters_output_passes_check_frame():
    from pathlib import Path

    from compound_shocks.adapters.prmn import PrmnAdapter
    from compound_shocks.adapters.wfp_prices import WfpPricesAdapter
    from compound_shocks.schema import check_frame

    fixtures = Path(__file__).parent / "fixtures"
    assert check_frame(WfpPricesAdapter().read([fixtures / "wfp_prices_fixture.csv"], {}), "prices") == []
    assert check_frame(PrmnAdapter().read([fixtures / "prmn_fixture.xlsx"], {}), "displacement") == []


def test_load_name_map_reads_yaml_and_a_missing_file_is_empty(tmp_path):
    from compound_shocks.crosswalk import load_name_map

    path = tmp_path / "names.yaml"
    path.write_text("Baidoa: Baydhaba\n", encoding="utf-8")
    assert load_name_map(path) == {"Baidoa": "Baydhaba"}
    assert load_name_map(tmp_path / "absent.yaml") == {}


def test_name_index_maps_unit_names_and_aliases_to_ids():
    import geopandas as gpd
    from shapely.geometry import box

    from compound_shocks.crosswalk import build_name_index

    units = gpd.GeoDataFrame({"admin2_id": ["S1", "S2"], "name": ["Baydhaba", "Kismaayo"],
                              "geometry": [box(0, 0, 1, 1), box(1, 0, 2, 1)]})
    index, problems = build_name_index(units, {"Baidoa": "Baydhaba", "Nowhere": "Missing Town"})
    assert index["Baydhaba"] == "S1" and index["Baidoa"] == "S1" and "Nowhere" not in index
    assert len(problems) == 1 and "Missing Town" in str(problems[0])


def test_fill_missing_by_market_fills_only_blank_districts_and_counts_them():
    from compound_shocks.crosswalk import fill_missing_by_market

    frame = pd.DataFrame({"market": ["Wadajir", "Wadajir", "Other"], "admin2": [None, "Hodan", None]})
    filled, count = fill_missing_by_market(frame, {"Wadajir": "Banadir"})
    assert filled["admin2"].tolist()[0] == "Banadir" and filled["admin2"].tolist()[1] == "Hodan"
    assert pd.isna(filled["admin2"].iloc[2]) and count == 1
