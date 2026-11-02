"""IOM DTM Sudan: stocks of displaced people present in a locality, by state of origin. Not flows."""

from pathlib import Path

import pandas as pd

from compound_shocks.adapters.base import register
from compound_shocks.adapters.mapping import apply_mapping, load_mapping
from compound_shocks.schema import STOCK_COLUMNS

MAPPING = Path(__file__).parent / "mappings" / "iom_dtm.yaml"
# DTM publishes overlapping series. Where two report the same locality on the same day, the first listed wins.
OPERATION_PRECEDENCE = [
    "Armed Clashes in Sudan (Overview)",
    "Armed Clashes in Sudan (Monthly)",
    "Armed Clashes in Sudan",
    "Darfur conflict",
]
KEY = ["month", "dest_admin2", "origin_admin1"]


class IomDtmAdapter:
    role = "displacement"
    provider = "IOM DTM"

    def find(self, raw_dir: Path) -> list[Path]:
        return sorted(Path(raw_dir).glob("*.csv"))

    def read(self, paths: list[Path], instance: dict) -> pd.DataFrame:
        frames = []
        for path in paths:
            renamed, problems = apply_mapping(pd.read_csv(path, dtype=str, encoding="utf-8-sig"), load_mapping(MAPPING))
            if problems:
                raise ValueError(f"{path.name}: " + "; ".join(map(str, problems)))
            frames.append(renamed[["date", "dest_admin2", "origin_admin1", "stock", "operation", "admin_level"]])
        raw = pd.concat(frames, ignore_index=True)
        locality = raw[raw["admin_level"] == "2"].copy()
        locality["date"] = pd.to_datetime(locality["date"])
        period, outside = instance.get("period"), 0
        if period:
            inside = (locality["date"] >= pd.Timestamp(period["start"])) & (locality["date"] <= pd.Timestamp(period["end"]))
            outside, locality = int((~inside).sum()), locality[inside]
        locality["month"] = locality["date"].dt.strftime("%Y-%m")
        locality["stock"] = pd.to_numeric(locality["stock"], errors="coerce")
        locality["rank"] = locality["operation"].map({name: i for i, name in enumerate(OPERATION_PRECEDENCE)}).fillna(
            len(OPERATION_PRECEDENCE)
        )
        for column in ("dest_admin2", "origin_admin1"):
            locality[column] = locality[column].astype("string").str.strip()
        locality["origin_admin1"] = locality["origin_admin1"].fillna("Not available")
        before = len(locality)
        # Several reports per month: keep the last day, then the preferred series, and add up the reason rows.
        locality = locality[locality["date"] == locality.groupby(KEY)["date"].transform("max")]
        locality = locality[locality["rank"] == locality.groupby(KEY)["rank"].transform("min")]
        result = locality.groupby(KEY, as_index=False)["stock"].sum(min_count=1)[STOCK_COLUMNS]
        result.attrs["schema"] = "displacement_stock"
        result.attrs["decisions"] = [
            (f"IOM DTM: displacement is a stock (people present), not a flow; {outside} locality rows outside the study "
            f"period excluded; {before - len(locality)} of {before} rows superseded by a later report in the same month "
            "or by a preferred DTM series; reason rows summed")
        ]
        return result


register(IomDtmAdapter())
