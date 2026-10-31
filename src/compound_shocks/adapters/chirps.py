"""Monthly CHIRPS GeoTIFFs to canonical district rainfall."""

import re
from pathlib import Path

import pandas as pd

from compound_shocks.adapters.base import register
from compound_shocks.spatial import zonal_monthly

MONTH = re.compile(r"(?<!\d)(\d{4})[.-](\d{2})(?!\d)")


class ChirpsAdapter:
    role = "rainfall"
    provider = "UCSB CHC CHIRPS"

    def find(self, raw_dir: Path) -> list[Path]:
        return sorted(Path(raw_dir).glob("*.tif"))

    def read(self, paths: list[Path], instance: dict) -> pd.DataFrame:
        rasters = {}
        for path in paths:
            match = MONTH.search(path.stem)
            if not match:
                raise ValueError(f"{path.name}: expected YYYY-MM or YYYY.MM in raster name")
            month = f"{match[1]}-{match[2]}"
            if month in rasters:
                raise ValueError(f"duplicate CHIRPS month {month}")
            rasters[month] = path
        return zonal_monthly(rasters, instance["boundaries"])


register(ChirpsAdapter())
