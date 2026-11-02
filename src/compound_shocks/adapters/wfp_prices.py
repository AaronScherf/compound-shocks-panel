"""WFP market prices to canonical rows; unit/currency conflicts stay visible."""

from pathlib import Path

import pandas as pd
from reprokit.problems import Problem

from compound_shocks.adapters.base import register
from compound_shocks.adapters.mapping import apply_mapping, load_mapping
from compound_shocks.schema import ROLE_COLUMNS

MAPPING = Path(__file__).parent / "mappings" / "wfp_prices.yaml"


class WfpPricesAdapter:
    role = "prices"
    provider = "WFP"

    def find(self, raw_dir: Path) -> list[Path]:
        return sorted(Path(raw_dir).glob("*.csv"))

    def read(self, paths: list[Path], instance: dict) -> pd.DataFrame:
        frames, mixed_types = [], []
        period, dropped = instance.get("period"), 0
        for path in paths:
            raw = pd.read_csv(path, encoding="utf-8-sig")
            if period:  # checks below should speak about the study period, not 30 years of history
                dates = pd.to_datetime(raw["date"])
                inside = (dates >= pd.Timestamp(period["start"])) & (dates <= pd.Timestamp(period["end"]))
                dropped += int((~inside).sum())
                raw = raw[inside]
            renamed, problems = apply_mapping(raw, load_mapping(MAPPING))
            if problems:
                raise ValueError(f"{path.name}: " + "; ".join(map(str, problems)))
            if "pricetype" in raw.columns:
                price_types = sorted(raw["pricetype"].dropna().astype(str).unique())
                if len(price_types) > 1:
                    mixed_types.append(Problem(path.name, "pricetype", f"mixed pricetype: {', '.join(price_types)}"))
            frame = renamed[ROLE_COLUMNS[self.role]].copy()
            frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
            frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
            frames.append(frame)
        result = pd.concat(frames, ignore_index=True)
        problems = list(mixed_types)
        for (market, commodity), group in result.groupby(["market", "commodity"], dropna=False):
            for field in ("unit", "currency"):
                values = sorted(group[field].dropna().astype(str).unique())
                if len(values) > 1:
                    problems.append(Problem("prices", f"{market}/{commodity}/{field}",
                                            f"mixed {field}: {', '.join(values)}"))
        result.attrs["problems"] = problems
        result.attrs["decisions"] = (
            [f"WFP: dropped {dropped} price rows outside the study period {period['start']} to {period['end']}"]
            if dropped
            else []
        )
        return result


register(WfpPricesAdapter())
