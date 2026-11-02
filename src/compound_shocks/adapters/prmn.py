"""PRMN displacement flows (HDX XLSX, sheet OutputsArrivals); missing reports remain missing."""

from pathlib import Path

import pandas as pd
from reprokit.problems import Problem

from compound_shocks.adapters.base import register
from compound_shocks.adapters.mapping import apply_mapping, load_mapping
from compound_shocks.schema import ROLE_COLUMNS

MAPPING = Path(__file__).parent / "mappings" / "prmn.yaml"
REASONS = {"drought related": "drought", "conflict/insecurity": "conflict", "flood": "flood", "other": "other"}
KEY = ["month", "origin_admin2", "dest_admin2", "reason"]


class PrmnAdapter:
    role = "displacement"
    provider = "UNHCR/NRC PRMN"

    def find(self, raw_dir: Path) -> list[Path]:
        return sorted(Path(raw_dir).glob("*.xlsx"))

    def read(self, paths: list[Path], instance: dict) -> pd.DataFrame:
        frames = []
        for path in paths:
            renamed, problems = apply_mapping(pd.read_excel(path, sheet_name=0), load_mapping(MAPPING))
            if problems:
                raise ValueError(f"{path.name}: " + "; ".join(map(str, problems)))
            frames.append(renamed[["month", "origin_admin2", "dest_admin2", "individuals", "reason"]])
        result = pd.concat(frames, ignore_index=True)
        result["month"] = pd.to_datetime(result["month"], format="%d/%m/%Y").dt.strftime("%Y-%m")
        for column in ("origin_admin2", "dest_admin2"):
            result[column] = result[column].astype("string").str.strip()
        result["individuals"] = pd.to_numeric(result["individuals"], errors="coerce")
        raw_reasons = result["reason"].astype("string").str.strip().str.casefold()
        unknown = sorted(result.loc[~raw_reasons.isin(REASONS), "reason"].dropna().astype(str).unique())
        result["reason"] = raw_reasons.map(REASONS).fillna("other").astype(str)
        # Source rows are weekly and split by priority need; one row per district-month-reason is canonical.
        result = result.groupby(KEY, as_index=False, dropna=False)["individuals"].sum(min_count=1)
        result = result[ROLE_COLUMNS[self.role]]
        result.attrs["problems"] = [Problem("displacement", value, "unknown reason mapped to other") for value in unknown]
        return result


register(PrmnAdapter())
