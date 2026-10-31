"""Spatial assignment and district aggregation helpers."""

import geopandas as gpd
import pandas as pd


def assign_admin2(points: pd.DataFrame, boundaries: gpd.GeoDataFrame) -> pd.DataFrame:
    """Assign WGS84 lon/lat points; shared edges resolve to the lowest ID."""
    indexed = points.reset_index(drop=True).copy()
    indexed["_row"] = range(len(indexed))
    locations = gpd.GeoDataFrame(indexed[["_row"]], geometry=gpd.points_from_xy(indexed["lon"], indexed["lat"]), crs="EPSG:4326")
    polygons = boundaries[["admin2_id", "geometry"]].to_crs(locations.crs)
    matches = gpd.sjoin(locations, polygons, how="left", predicate="intersects")
    matches = matches.sort_values(["_row", "admin2_id"], na_position="last").drop_duplicates("_row")
    result = points.copy()
    result["admin2_id"] = pd.array(matches.sort_values("_row")["admin2_id"].to_numpy(), dtype="string")
    result.attrs["unassigned"] = int(result["admin2_id"].isna().sum())
    return result
