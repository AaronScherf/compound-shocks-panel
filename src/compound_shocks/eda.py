"""Descriptive summaries of the district-month panel. Counts and coverage only: no modeling."""

import pandas as pd

KEYS = ("admin2_id", "month")
SOURCE_GROUPS: dict[str, list[str]] = {
    "conflict": ["events", "fatalities"],
    "rainfall": ["precip_mm", "coverage_frac"],
    "prices": ["price_sorghum", "price_wheat"],
    "displacement": ["displaced_individuals", "displaced_stock", "displaced_stock_change"],
    "context": ["population"],
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


def _conflict_means(frame: pd.DataFrame) -> dict:
    rate = None
    if "population" in frame and (frame["population"] > 0).any():
        sized = frame[frame["population"] > 0]
        rate = round(float((sized["events"] / sized["population"] * 100_000).mean()), 2)
    return {
        "events_per_100k": rate,
        "district_months": len(frame),
        "mean_events": round(float(frame["events"].mean()), 2) if len(frame) else None,
        "share_with_events": round(float((frame["events"] > 0).mean()), 3) if len(frame) else None,
        "mean_fatalities": round(float(frame["fatalities"].mean()), 2) if len(frame) else None,
    }


def missingness_vs_conflict(panel: pd.DataFrame, column: str = "price_sorghum") -> dict:
    """How conflict counts differ between observed and missing values of one column. Descriptive, no test.

    Three cuts: districts that ever have a value against those that never do; district-months with and without a
    value inside the districts that ever have one; and the second cut by calendar year.
    """
    _require_keys(panel)
    if column not in panel.columns or column in KEYS:
        raise ValueError(f"unknown panel column {column!r}")
    observed = panel[column].notna()
    ever = observed.groupby(panel["admin2_id"]).transform("any")
    covered = panel[ever]
    covered_observed = observed[ever]
    by_year = []
    for year, group in covered.groupby(covered["month"].str[:4]):
        has = covered_observed.loc[group.index]
        by_year.append({
            "year": year, "share_observed": round(float(has.mean()), 3),
            "with_value": _conflict_means(group[has]), "without_value": _conflict_means(group[~has]),
        })
    return {
        "column": column,
        "districts_ever": {"with_value": int(ever.groupby(panel["admin2_id"]).first().sum()),
                           "without_value": int((~ever.groupby(panel["admin2_id"]).first()).sum())},
        "district_cut": {"ever_has_value": _conflict_means(covered), "never_has_value": _conflict_means(panel[~ever])},
        "month_cut": {"with_value": _conflict_means(covered[covered_observed]),
                      "without_value": _conflict_means(covered[~covered_observed])},
        "by_year": by_year,
    }
