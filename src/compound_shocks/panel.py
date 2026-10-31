"""Fuse canonical tables into the district-month panel. Event rows never leave this module."""

import pandas as pd

from compound_shocks.schema import PANEL_COLUMNS

COMMODITY_COLUMNS = {"price_sorghum": "sorghum", "price_wheat": "wheat"}
PUBLISHABLE = ["admin2_id", "month", "events", "fatalities"]


def month_of(date: str) -> str:
    return pd.Timestamp(date).strftime("%Y-%m")


def aggregate_conflict(events: pd.DataFrame) -> pd.DataFrame:
    """Count events and sum fatalities per district-month; events without a district are only counted."""
    unassigned = int(events["admin2_id"].isna().sum())
    assigned = events.dropna(subset=["admin2_id"]).assign(month=lambda d: d["date"].map(month_of))
    out = (
        assigned.groupby(["admin2_id", "month"], as_index=False)
        .agg(events=("event_id", "size"), fatalities=("fatalities", "sum"))
        .astype({"admin2_id": str})
    )
    out.attrs["unassigned"] = unassigned
    return out


def _monthly_price(prices: pd.DataFrame, keyword: str, name: str) -> pd.DataFrame:
    chosen = prices[prices["commodity"].str.casefold().str.contains(keyword, na=False)]
    chosen = chosen.assign(month=chosen["date"].map(month_of), admin2_id=chosen["admin2"].astype(str))
    return chosen.groupby(["admin2_id", "month"], as_index=False)["price"].mean().rename(columns={"price": name})


def fuse_panel(
    conflict: pd.DataFrame,
    rainfall: pd.DataFrame,
    prices: pd.DataFrame,
    displacement: pd.DataFrame,
    admin2_ids: list[str],
    months: list[str],
) -> pd.DataFrame:
    """One row per (admin2_id, month). No events means 0; missing prices, rain and displacement stay NaN.

    price_* is the mean over markets and matching commodities; displaced_individuals counts people
    leaving the district (origin_admin2).
    """
    grid = pd.MultiIndex.from_product([admin2_ids, months], names=["admin2_id", "month"]).to_frame(index=False)
    panel = grid.merge(conflict, on=["admin2_id", "month"], how="left")
    panel[["events", "fatalities"]] = panel[["events", "fatalities"]].fillna(0).astype(int)
    panel = panel.merge(rainfall[["admin2_id", "month", "precip_mm", "coverage_frac"]], on=["admin2_id", "month"], how="left")
    for name, keyword in COMMODITY_COLUMNS.items():
        panel = panel.merge(_monthly_price(prices, keyword, name), on=["admin2_id", "month"], how="left")
    moved = (
        displacement.groupby(["origin_admin2", "month"], as_index=False)["individuals"]
        .sum(min_count=1)
        .rename(columns={"origin_admin2": "admin2_id", "individuals": "displaced_individuals"})
    )
    panel = panel.merge(moved, on=["admin2_id", "month"], how="left")
    panel.attrs["column_kinds"] = dict(PANEL_COLUMNS)
    return panel


def publishable_aggregates(panel: pd.DataFrame) -> pd.DataFrame:
    return panel[PUBLISHABLE].copy()
