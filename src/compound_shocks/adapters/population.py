"""OCHA COD-PS district population totals (UNFPA-led planning estimates). One fixed figure per district."""

from pathlib import Path

import pandas as pd

from compound_shocks.adapters.base import register
from compound_shocks.schema import ROLE_COLUMNS

# Column names differ by country file; matched case-insensitively. T_TL is the total population.
CODE_COLUMNS = ("admin2pcode", "adm2_pcode")
TOTAL_COLUMN = "t_tl"


class CodPsAdapter:
    role = "population"
    provider = "OCHA COD-PS"

    def find(self, raw_dir: Path) -> list[Path]:
        return sorted(Path(raw_dir).glob("*.csv"))

    def read(self, paths: list[Path], instance: dict) -> pd.DataFrame:
        frames = []
        for path in paths:
            raw = pd.read_csv(path, dtype={}, encoding="utf-8-sig")
            raw.columns = [str(column).strip().casefold() for column in raw.columns]
            code = next((column for column in CODE_COLUMNS if column in raw.columns), None)
            if code is None or TOTAL_COLUMN not in raw.columns:
                raise ValueError(f"{path.name}: needs a district code column ({' or '.join(CODE_COLUMNS)}) and {TOTAL_COLUMN}")
            frame = raw[[code, TOTAL_COLUMN]].rename(columns={code: "admin2_id", TOTAL_COLUMN: "population"})
            frame["admin2_id"] = frame["admin2_id"].astype("string").str.strip().astype(str)
            frame["population"] = pd.to_numeric(frame["population"], errors="coerce")
            frames.append(frame)
        return pd.concat(frames, ignore_index=True)[ROLE_COLUMNS[self.role]]


register(CodPsAdapter())
