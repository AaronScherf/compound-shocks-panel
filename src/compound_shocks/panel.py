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
    names = prices["commodity"].str.casefold()
    chosen = prices[names.str.contains(keyword, na=False) & ~names.str.contains("food aid", na=False)]
    chosen = chosen.assign(month=chosen["date"].map(month_of), admin2_id=chosen["admin2"].astype(str))
    return chosen.groupby(["admin2_id", "month"], as_index=False)["price"].mean().rename(columns={"price": name})


def stock_change(stock: pd.DataFrame) -> pd.DataFrame:
    """Total stock per locality and month (origins added up) and its change from the previous calendar month.

    The change is NaN when the previous month has no report, so a gap never turns into a jump. A change in a stock
    mixes new arrivals with departures, returns and re-counts; it is not a flow.
    """
    totals = stock.groupby(["dest_admin2", "month"], as_index=False)["stock"].sum(min_count=1)
    previous = totals.assign(month=(pd.PeriodIndex(totals["month"], freq="M") + 1).strftime("%Y-%m"))
    previous = previous.rename(columns={"stock": "previous_stock"})
    merged = totals.merge(previous, on=["dest_admin2", "month"], how="left")
    merged["stock_change"] = merged["stock"] - merged["previous_stock"]
    return merged[["dest_admin2", "month", "stock", "stock_change"]]


def fuse_panel(
    conflict: pd.DataFrame,
    rainfall: pd.DataFrame,
    prices: pd.DataFrame,
    displacement: pd.DataFrame,
    admin2_ids: list[str],
    months: list[str],
    population: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """One row per (admin2_id, month). No events means 0; missing prices, rain and displacement stay NaN.

    price_* is the mean over markets and matching commodities; displaced_individuals counts people
    leaving the district (origin_admin2). A stock table (columns month, dest_admin2, origin_admin1, stock) gives
    displaced_stock and displaced_stock_change instead: people present in the district, not people moving.
    """
    grid = pd.MultiIndex.from_product([admin2_ids, months], names=["admin2_id", "month"]).to_frame(index=False)
    panel = grid.merge(conflict, on=["admin2_id", "month"], how="left")
    panel[["events", "fatalities"]] = panel[["events", "fatalities"]].fillna(0).astype(int)
    panel = panel.merge(rainfall[["admin2_id", "month", "precip_mm", "coverage_frac"]], on=["admin2_id", "month"], how="left")
    for name, keyword in COMMODITY_COLUMNS.items():
        panel = panel.merge(_monthly_price(prices, keyword, name), on=["admin2_id", "month"], how="left")
    if "stock" in displacement.columns:
        moved = stock_change(displacement).rename(
            columns={"dest_admin2": "admin2_id", "stock": "displaced_stock", "stock_change": "displaced_stock_change"}
        )
    else:
        moved = (
            displacement.groupby(["origin_admin2", "month"], as_index=False)["individuals"]
            .sum(min_count=1)
            .rename(columns={"origin_admin2": "admin2_id", "individuals": "displaced_individuals"})
        )
    panel = panel.merge(moved, on=["admin2_id", "month"], how="left")
    if population is not None:  # one fixed figure per district, repeated in every month
        panel = panel.merge(population[["admin2_id", "population"]].astype({"admin2_id": str}), on="admin2_id", how="left")
    panel.attrs["column_kinds"] = dict(PANEL_COLUMNS)
    return panel


def publishable_aggregates(panel: pd.DataFrame) -> pd.DataFrame:
    return panel[PUBLISHABLE].copy()
