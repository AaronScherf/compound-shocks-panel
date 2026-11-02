"""Spatial assignment and district aggregation helpers."""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.windows import Window, from_bounds
from shapely import transform
from shapely.geometry import box

# CHIRPS marks sea and out-of-coverage cells -9999 but its GeoTIFFs carry no nodata tag.
CHIRPS_FILL_VALUE = -9999


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


def zonal_monthly(rasters: dict[str, Path], boundaries: gpd.GeoDataFrame) -> pd.DataFrame:
    """Area-weighted mean and valid-area share for each district and month."""
    rows = []
    for month, path in sorted(rasters.items()):
        with rasterio.open(path) as src:
            polygons = boundaries.to_crs(src.crs)
            equal_area = Transformer.from_crs(src.crs, "EPSG:6933", always_xy=True).transform
            for district in polygons.itertuples():
                shape = district.geometry
                district_area = transform(shape, equal_area, interleaved=False).area
                valid_area = weighted_sum = 0.0
                left, bottom, right, top = shape.bounds
                raw_window = from_bounds(left, bottom, right, top, src.transform)
                col0 = max(0, int(np.floor(raw_window.col_off)))
                row0 = max(0, int(np.floor(raw_window.row_off)))
                col1 = min(src.width, int(np.ceil(raw_window.col_off + raw_window.width)))
                row1 = min(src.height, int(np.ceil(raw_window.row_off + raw_window.height)))
                if col1 > col0 and row1 > row0:
                    window = Window(col0, row0, col1 - col0, row1 - row0)
                    values = np.ma.masked_equal(src.read(1, window=window, masked=True), CHIRPS_FILL_VALUE)
                    for local_row, local_col in np.ndindex(values.shape):
                        value = values[local_row, local_col]
                        if np.ma.is_masked(value) or not np.isfinite(value):
                            continue
                        col, row = col0 + local_col, row0 + local_row
                        x0, y0 = src.transform @ (col, row)
                        x1, y1 = src.transform @ (col + 1, row + 1)
                        overlap = shape.intersection(box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
                        if not overlap.is_empty:
                            area = transform(overlap, equal_area, interleaved=False).area
                            valid_area += area
                            weighted_sum += float(value) * area
                rows.append({"admin2_id": str(district.admin2_id), "month": month,
                             "precip_mm": weighted_sum / valid_area if valid_area else np.nan,
                             "coverage_frac": min(1.0, valid_area / district_area) if district_area else 0.0})
    return pd.DataFrame(rows, columns=["admin2_id", "month", "precip_mm", "coverage_frac"])
