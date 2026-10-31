"""Explicit provider-name to COD-AB ID translation with full mismatch reporting."""

import pandas as pd
from reprokit.problems import Problem


def apply_crosswalk(df: pd.DataFrame, column: str, crosswalk: dict[str, str], role: str) -> tuple[pd.DataFrame, list[Problem]]:
    if column not in df:
        raise ValueError(f"{role}: missing source column {column}")
    result = df.copy()
    missing = sorted(set(result[column].dropna().astype(str)) - set(crosswalk))
    result[column] = result[column].map(crosswalk).astype("string")
    problems = [Problem(f"crosswalk:{role}", name, f"unmatched {column} name") for name in missing]
    return result, problems
