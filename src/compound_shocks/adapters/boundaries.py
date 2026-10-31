"""Read Admin 2 polygons from the configured boundary provider."""

from pathlib import Path

import geopandas as gpd
import pandas as pd

from compound_shocks.adapters.base import register
from compound_shocks.adapters.mapping import apply_mapping, load_mapping
from compound_shocks.schema import ROLE_COLUMNS

MAPPINGS = Path(__file__).parent / "mappings"


class _BoundaryAdapter:
    role = "admin_boundaries"
    provider = ""
    mapping_file = ""

    def find(self, raw_dir: Path) -> list[Path]:
        return sorted(Path(raw_dir).glob("*.geojson"))

    def read(self, paths: list[Path], instance: dict) -> gpd.GeoDataFrame:
        frames = []
        for path in paths:
            raw = gpd.read_file(path)
            renamed, problems = apply_mapping(raw, load_mapping(MAPPINGS / self.mapping_file))
            if problems:
                raise ValueError(f"{path.name}: " + "; ".join(str(p) for p in problems))
            frames.append(renamed[ROLE_COLUMNS[self.role]])
        result = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), geometry="geometry", crs=frames[0].crs)
        result["admin2_id"] = result["admin2_id"].astype(str)
        result.attrs["vintage"] = instance.get("boundary_vintage")
        return result


class CodAbAdapter(_BoundaryAdapter):
    provider = "OCHA COD-AB"
    mapping_file = "codab.yaml"


class GeoBoundariesAdapter(_BoundaryAdapter):
    provider = "geoBoundaries"
    mapping_file = "geoboundaries.yaml"


register(CodAbAdapter())
register(GeoBoundariesAdapter())
