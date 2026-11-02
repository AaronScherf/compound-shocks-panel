"""Descriptive summaries of the district-month panel. Counts and coverage only: no modeling."""

import pandas as pd

KEYS = ("admin2_id", "month")
SOURCE_GROUPS: dict[str, list[str]] = {
    "conflict": ["events", "fatalities"],
    "rainfall": ["precip_mm", "coverage_frac"],
    "prices": ["price_sorghum", "price_wheat"],
    "displacement": ["displaced_individuals"],
}
CONFLICT_COLUMNS = frozenset(SOURCE_GROUPS["conflict"])


def _require_keys(panel: pd.DataFrame) -> None:
    missing = [key for key in KEYS if key not in panel.columns]
    if missing:
        raise ValueError(f"panel is missing key column(s): {', '.join(missing)}")


def _coverage(panel: pd.DataFrame, observed: pd.Series) -> dict:
    months = panel.loc[observed, "month"]
    return {
        "non_null": int(observed.sum()),
        "null": int((~observed).sum()),
        "min_month": months.min() if len(months) else None,
        "max_month": months.max() if len(months) else None,
        "districts_with_value": int(panel.loc[observed, "admin2_id"].nunique()),
    }


def data_profile(panel: pd.DataFrame) -> dict:
    """Per column and per source group: non-null, null and zero counts, observed month range, district coverage.

    Zeros and nulls are counted apart: a conflict zero means no events were recorded, a null price means no price.
    """
    _require_keys(panel)
    columns = {}
    for column in (c for c in panel.columns if c not in KEYS):
        columns[column] = {**_coverage(panel, panel[column].notna()), "zero": int((panel[column] == 0).sum())}
    groups = {}
    for group, members in SOURCE_GROUPS.items():
        present = [column for column in members if column in panel.columns]
        if present:
            groups[group] = _coverage(panel, panel[present].notna().any(axis=1))
    return {
        "rows": len(panel),
        "districts": int(panel["admin2_id"].nunique()),
        "months": int(panel["month"].nunique()),
        "columns": columns,
        "groups": groups,
    }


def district_summary(panel: pd.DataFrame, column: str) -> pd.Series:
    """One value per district: the total for conflict columns, otherwise the share of months with a value."""
    _require_keys(panel)
    if column not in panel.columns or column in KEYS:
        raise ValueError(f"unknown panel column {column!r}")
    by_district = panel.groupby("admin2_id")[column]
    return by_district.sum() if column in CONFLICT_COLUMNS else by_district.apply(lambda s: s.notna().mean())
