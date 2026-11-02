from pathlib import Path

from compound_shocks.adapters.boundaries import CodAbAdapter, GeoBoundariesAdapter
from compound_shocks.schema import check_frame

FIXTURES = Path(__file__).parent / "fixtures"


def test_vintage_recorded_from_the_file_version_and_valid_on():
    frame = CodAbAdapter().read([FIXTURES / "codab_fixture.geojson"], {})
    assert frame.attrs["vintage"] == "v03, valid on 2025-01-08"
    assert check_frame(frame, "admin_boundaries") == []


def test_vintage_falls_back_to_the_instance_setting_when_the_file_has_none():
    frame = GeoBoundariesAdapter().read([FIXTURES / "geoboundaries_fixture.geojson"], {"boundary_vintage": "2024"})
    assert frame.attrs["vintage"] == "2024"


def test_geoboundaries_output_matches_canonical_columns():
    frame = GeoBoundariesAdapter().read([FIXTURES / "geoboundaries_fixture.geojson"], {"boundary_vintage": "2024"})
    assert list(frame.columns) == ["admin2_id", "name", "geometry"]
    assert frame["admin2_id"].tolist() == ["B", "A", "C"]
    assert check_frame(frame, "admin_boundaries") == []
