"""Read Admin 2 polygons from the configured boundary provider."""

from pathlib import Path

import geopandas as gpd
import pandas as pd

from compound_shocks.adapters.base import register
from compound_shocks.adapters.mapping import apply_mapping, load_mapping
from compound_shocks.schema import ROLE_COLUMNS

MAPPINGS = Path(__file__).parent / "mappings"


def _vintage(raw: gpd.GeoDataFrame) -> str | None:
    """OCHA files carry version and valid_on on every feature; other providers have neither."""
    if {"version", "valid_on"} <= set(raw.columns) and len(raw):
        return f"{raw['version'].iloc[0]}, valid on {pd.Timestamp(raw['valid_on'].iloc[0]).date().isoformat()}"
    return None


class _BoundaryAdapter:
    role = "admin_boundaries"
    provider = ""
    mapping_file = ""

    def find(self, raw_dir: Path) -> list[Path]:
        return sorted(Path(raw_dir).glob("*.geojson"))

    def read(self, paths: list[Path], instance: dict) -> gpd.GeoDataFrame:
        frames, vintages = [], []
        for path in paths:
            raw = gpd.read_file(path)
            vintages.append(_vintage(raw))
            renamed, problems = apply_mapping(raw, load_mapping(MAPPINGS / self.mapping_file))
            if problems:
                raise ValueError(f"{path.name}: " + "; ".join(str(p) for p in problems))
            frames.append(renamed[ROLE_COLUMNS[self.role]])
        result = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), geometry="geometry", crs=frames[0].crs)
        result["admin2_id"] = result["admin2_id"].astype(str)
        result.attrs["vintage"] = next((v for v in vintages if v), instance.get("boundary_vintage"))
        return result


class CodAbAdapter(_BoundaryAdapter):
    provider = "OCHA COD-AB"
    mapping_file = "codab.yaml"


class GeoBoundariesAdapter(_BoundaryAdapter):
    provider = "geoBoundaries"
    mapping_file = "geoboundaries.yaml"


register(CodAbAdapter())
register(GeoBoundariesAdapter())
