"""CHIRPS v2.0 monthly Africa GeoTIFFs from UCSB CHC. No login. The older CHIRPS-2.0 path is gone (404)."""

import gzip
from pathlib import Path

from compound_shocks.fetch.core import get, save

BASE = "https://data.chc.ucsb.edu/products/CHIRPS/v2.0/africa_monthly/tifs"


def chirps_url(month: str) -> str:
    year, number = month.split("-")
    return f"{BASE}/chirps-v2.0.{year}.{number}.tif.gz"


def fetch_chirps(months: list[str], out_dir: Path) -> list[Path]:
    paths = []
    for month in months:
        url = chirps_url(month)
        data = gzip.decompress(get(url, "CHIRPS v2.0").content)
        paths.append(save(data, url, Path(out_dir), f"chirps-v2.0.{month.replace('-', '.')}.tif"))
    return paths
