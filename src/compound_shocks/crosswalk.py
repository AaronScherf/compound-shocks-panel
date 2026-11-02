"""Explicit provider-name to COD-AB ID translation with full mismatch reporting."""

from pathlib import Path

import geopandas as gpd
import pandas as pd
from reprokit.problems import Problem

from compound_shocks.adapters.mapping import load_mapping


def apply_crosswalk(df: pd.DataFrame, column: str, crosswalk: dict[str, str], role: str) -> tuple[pd.DataFrame, list[Problem]]:
    if column not in df:
        raise ValueError(f"{role}: missing source column {column}")
    result = df.copy()
    missing = sorted(set(result[column].dropna().astype(str)) - set(crosswalk))
    result[column] = result[column].map(crosswalk).astype("string")
    problems = [Problem(f"crosswalk:{role}", name, f"unmatched {column} name") for name in missing]
    return result, problems


def load_name_map(path: Path) -> dict[str, str]:
    """A one-level YAML mapping kept in the instance (crosswalks/*.yaml); a missing file means no entries."""
    return load_mapping(path) if Path(path).exists() else {}


def build_name_index(boundaries: gpd.GeoDataFrame, aliases: dict[str, str]) -> tuple[dict[str, str], list[Problem]]:
    """District name to admin2_id, plus each alias pointing at the id of the district name it stands for."""
    index = dict(zip(boundaries["name"].astype(str), boundaries["admin2_id"].astype(str), strict=True))
    problems = []
    for alias, target in aliases.items():
        if alias in index:
            problems.append(Problem("crosswalks/district_names.yaml", alias, "alias shadows an existing district name"))
        elif target not in index:
            problems.append(Problem("crosswalks/district_names.yaml", alias, f"alias target {target!r} is not a district name"))
        else:
            index[alias] = index[target]
    return index, problems


def fill_missing_by_market(
    df: pd.DataFrame, market_districts: dict[str, str], column: str = "admin2", market_column: str = "market"
) -> tuple[pd.DataFrame, int]:
    """Give rows with no district the district their market is known to be in; return the new frame and the count."""
    result = df.copy()
    fillable = result[column].isna() & result[market_column].isin(list(market_districts))
    result.loc[fillable, column] = result.loc[fillable, market_column].map(market_districts)
    return result, int(fillable.sum())
