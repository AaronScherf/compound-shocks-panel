"""PRMN origin-destination flows; missing reports remain missing."""

from pathlib import Path

import pandas as pd
from reprokit.problems import Problem

from compound_shocks.adapters.base import register
from compound_shocks.adapters.mapping import apply_mapping, load_mapping
from compound_shocks.schema import ROLE_COLUMNS

MAPPING = Path(__file__).parent / "mappings" / "prmn.yaml"
REASONS = {"drought": "drought", "conflict": "conflict", "flood": "flood", "other": "other"}


class PrmnAdapter:
    role = "displacement"
    provider = "UNHCR/NRC PRMN"

    def find(self, raw_dir: Path) -> list[Path]:
        return sorted(Path(raw_dir).glob("*.csv"))

    def read(self, paths: list[Path], instance: dict) -> pd.DataFrame:
        frames = []
        for path in paths:
            renamed, problems = apply_mapping(pd.read_csv(path, encoding="utf-8-sig"), load_mapping(MAPPING))
            if problems:
                raise ValueError(f"{path.name}: " + "; ".join(map(str, problems)))
            frames.append(renamed[ROLE_COLUMNS[self.role]])
        result = pd.concat(frames, ignore_index=True)
        result["month"] = pd.to_datetime(result["month"]).dt.strftime("%Y-%m")
        result["individuals"] = pd.to_numeric(result["individuals"], errors="coerce")
        raw_reasons = result["reason"].astype("string").str.strip().str.casefold()
        unknown = sorted(result.loc[~raw_reasons.isin(REASONS), "reason"].dropna().astype(str).unique())
        result["reason"] = raw_reasons.map(REASONS).fillna("other").astype(str)
        result.attrs["problems"] = [Problem("displacement", value, "unknown reason mapped to other") for value in unknown]
        return result


register(PrmnAdapter())
