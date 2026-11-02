from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import box

from compound_shocks.adapters.boundaries import CodAbAdapter
from compound_shocks.adapters.chirps import ChirpsAdapter
from compound_shocks.schema import check_frame
from compound_shocks.spatial import zonal_monthly

FIXTURES = Path(__file__).parent / "fixtures"
RASTERS = {month: FIXTURES / "chirps" / f"chirps_{month}.tif" for month in ("2021-01", "2021-02")}


def _boundary(left, right):
    return gpd.GeoDataFrame({"admin2_id": ["X"], "geometry": [box(left, 0, right, 1)]}, crs="EPSG:4326")


def test_area_weighted_mean_on_known_grid():
    result = zonal_monthly({"2021-01": RASTERS["2021-01"]}, _boundary(0.5, 1.5))
    assert result.loc[0, "precip_mm"] == pytest.approx(15)
    assert result.loc[0, "coverage_frac"] == pytest.approx(1)


def test_nodata_cells_lower_coverage_frac_not_precip():
    result = zonal_monthly({"2021-01": RASTERS["2021-01"]}, _boundary(1.5, 2.5))
    assert result.loc[0, "precip_mm"] == pytest.approx(20)
    assert result.loc[0, "coverage_frac"] == pytest.approx(0.5)


def test_district_with_no_valid_cells_has_nan_precip_and_zero_coverage():
    result = zonal_monthly({"2021-01": RASTERS["2021-01"]}, _boundary(3, 4))
    assert result.loc[0, "coverage_frac"] == 0
    assert result.loc[0, "precip_mm"] != result.loc[0, "precip_mm"]


def test_month_taken_from_mapping_keys():
    boundaries = CodAbAdapter().read([FIXTURES / "codab_fixture.geojson"], {})
    result = zonal_monthly({"2099-12": RASTERS["2021-01"]}, boundaries)
    assert set(result["month"]) == {"2099-12"}
    assert check_frame(result, "rainfall") == []
    adapter = ChirpsAdapter()
    assert adapter.provider == "UCSB CHC CHIRPS"
    assert check_frame(adapter.read(adapter.find(FIXTURES / "chirps"), {"boundaries": boundaries}), "rainfall") == []


def _untagged_raster(path, values):
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    with rasterio.open(path, "w", driver="GTiff", width=len(values), height=1, count=1, dtype="float32",
                       crs="EPSG:4326", transform=from_origin(0, 1, 1, 1)) as dst:  # no nodata tag, like real CHIRPS
        dst.write(np.array([values], dtype="float32"), 1)


def test_untagged_minus_9999_cells_are_nodata_not_rainfall(tmp_path):
    raster = tmp_path / "chirps-v2.0.2021.01.tif"
    _untagged_raster(raster, [10, 20, -9999, -9999])
    result = zonal_monthly({"2021-01": raster}, _boundary(1.5, 2.5))
    assert result.loc[0, "precip_mm"] == pytest.approx(20)
    assert result.loc[0, "coverage_frac"] == pytest.approx(0.5)


def test_district_wholly_over_untagged_sea_cells_has_nan_precip_and_zero_coverage(tmp_path):
    raster = tmp_path / "chirps-v2.0.2021.01.tif"
    _untagged_raster(raster, [10, 20, -9999, -9999])
    result = zonal_monthly({"2021-01": raster}, _boundary(2.5, 3.5))
    assert result.loc[0, "coverage_frac"] == 0 and result.loc[0, "precip_mm"] != result.loc[0, "precip_mm"]
