from pathlib import Path

import pandas as pd

from compound_shocks.adapters.boundaries import CodAbAdapter
from compound_shocks.spatial import assign_admin2

BOUNDARIES = CodAbAdapter().read([Path(__file__).parent / "fixtures" / "codab_fixture.geojson"], {})


def test_point_on_shared_boundary_is_assigned_to_lowest_id():
    result = assign_admin2(pd.DataFrame({"lat": [0.5], "lon": [1.0]}), BOUNDARIES)
    assert result["admin2_id"].tolist() == ["A"]


def test_point_outside_all_polygons_is_unassigned_and_counted():
    result = assign_admin2(pd.DataFrame({"lat": [9.0], "lon": [9.0]}), BOUNDARIES)
    assert pd.isna(result.loc[0, "admin2_id"])
    assert result.attrs["unassigned"] == 1


def test_row_count_preserved():
    points = pd.DataFrame({"lat": [0.5, 0.5, 9.0], "lon": [0.5, 1.0, 9.0]})
    result = assign_admin2(points, BOUNDARIES)
    assert len(result) == len(points)
    assert result["admin2_id"].tolist()[:2] == ["B", "A"]
    assert result.attrs["unassigned"] == 1
