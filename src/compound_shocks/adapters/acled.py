"""ACLED event export -> canonical conflict_events. Reads only files the user downloaded; never fetches."""

from pathlib import Path

import pandas as pd

from compound_shocks.adapters.base import register
from compound_shocks.adapters.mapping import apply_mapping, load_mapping
from compound_shocks.schema import ROLE_COLUMNS

MAPPING = Path(__file__).parent / "mappings" / "acled.yaml"
# Columns kept as-is: already carry their canonical names in the ACLED export.
PASSTHROUGH = ["event_type", "sub_event_type", "actor1", "fatalities", "geo_precision"]


class AcledAdapter:
    role = "conflict_events"
    provider = "ACLED"

    def find(self, raw_dir: Path) -> list[Path]:
        return sorted(Path(raw_dir).glob("*.csv"))

    def read(self, paths: list[Path], instance: dict) -> pd.DataFrame:
        frames = [self._read_one(path) for path in paths]
        return pd.concat(frames, ignore_index=True)

    def _read_one(self, path: Path) -> pd.DataFrame:
        raw = pd.read_csv(path, encoding="utf-8-sig", dtype={"event_id_cnty": str})
        if "lat_long" in raw.columns and "latitude" not in raw.columns:
            pair = raw["lat_long"].str.split(r"[,\s]+", n=1, expand=True)
            raw["latitude"], raw["longitude"] = pair[0].astype(float), pair[1].astype(float)
        renamed, problems = apply_mapping(raw, load_mapping(MAPPING))
        if problems:
            raise ValueError(f"{path.name}: " + "; ".join(str(p) for p in problems))
        renamed["date"] = pd.to_datetime(renamed["date"]).dt.strftime("%Y-%m-%d")
        renamed["fatalities"] = renamed["fatalities"].fillna(0).astype(int)
        renamed["geo_precision"] = renamed["geo_precision"].astype(int)
        return renamed[ROLE_COLUMNS[self.role]]


register(AcledAdapter())
