"""IOM DTM Sudan: stocks of displaced people present in a locality, by state of origin. Not flows."""

from pathlib import Path

import pandas as pd

from compound_shocks.adapters.base import register
from compound_shocks.adapters.mapping import apply_mapping, load_mapping
from compound_shocks.schema import STOCK_COLUMNS

MAPPING = Path(__file__).parent / "mappings" / "iom_dtm.yaml"
# DTM publishes overlapping series whose levels disagree for the same locality and month (the Monthly and original
# series run at about 2.4 to 3 times the Overview in the overlap), so mixing them would put series switches into the
# stock and its change. Only this one series is used; other operations are dropped, not filled in.
PRIMARY_OPERATION = "Armed Clashes in Sudan (Overview)"
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
        other = int((locality["operation"] != PRIMARY_OPERATION).sum())
        locality = locality[locality["operation"] == PRIMARY_OPERATION].copy()
        locality["month"] = locality["date"].dt.strftime("%Y-%m")
        locality["stock"] = pd.to_numeric(locality["stock"], errors="coerce")
        for column in ("dest_admin2", "origin_admin1"):
            locality[column] = locality[column].astype("string").str.strip()
        locality["origin_admin1"] = locality["origin_admin1"].fillna("Not available")
        before = len(locality)
        # Several reports per month: keep the last day and add up the reason rows.
        locality = locality[locality["date"] == locality.groupby(KEY)["date"].transform("max")]
        result = locality.groupby(KEY, as_index=False)["stock"].sum(min_count=1)[STOCK_COLUMNS]
        result.attrs["schema"] = "displacement_stock"
        result.attrs["decisions"] = [
            (f"IOM DTM: displacement is a stock (people present), not a flow; {outside} locality rows outside the study "
            f"period excluded; {other} rows from operations other than {PRIMARY_OPERATION!r} excluded; "
            f"{before - len(locality)} of {before} rows superseded by a later report in the same month; "
            "reason rows summed")
        ]
        return result


register(IomDtmAdapter())
