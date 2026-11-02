"""Exploratory figures. Each builder returns a Figure so it can be inspected; each public function saves a PNG.

Figures use matplotlib Figure objects directly (no pyplot), so no global state or display backend is involved.
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd
from matplotlib.dates import AutoDateLocator, ConciseDateFormatter
from matplotlib.figure import Figure

from compound_shocks.eda import CONFLICT_COLUMNS, KEYS, district_summary


def acled_caption(accessed: str) -> str:
    return f"Source: ACLED (acleddata.com), accessed {accessed}"


def _save(fig: Figure, out: Path) -> None:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120, bbox_inches="tight")


def _month_dates(months: pd.Series) -> pd.DatetimeIndex:
    return pd.to_datetime(months.astype(str) + "-01")


def _date_axis(ax) -> None:
    locator = AutoDateLocator()
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(ConciseDateFormatter(locator))


def _reserve_caption_space(fig: Figure) -> None:
    fig.get_layout_engine().set(rect=(0, 0.04, 1, 0.96))


def missingness_figure(panel: pd.DataFrame) -> Figure:
    columns = [c for c in panel.columns if c not in KEYS]
    fig = Figure(figsize=(2.6 * len(columns), 5), layout="constrained")
    axes = fig.subplots(1, len(columns), squeeze=False)[0]
    for ax, column in zip(axes, columns, strict=True):
        grid = panel.assign(_seen=panel[column].notna().astype(int)).pivot_table(
            index="admin2_id", columns="month", values="_seen", aggfunc="max", fill_value=0
        )
        ax.imshow(grid.to_numpy(), aspect="auto", cmap="Greys", vmin=0, vmax=1, interpolation="nearest")
        ax.set_title(column, fontsize=9)
        ax.set_xticks(range(len(grid.columns)), grid.columns, rotation=90, fontsize=6)
        ax.set_yticks(range(len(grid.index)), grid.index if len(grid.index) <= 40 else [], fontsize=6)
    fig.suptitle("Observed (dark) vs missing (light), districts by month")
    return fig


def missingness_matrix(panel: pd.DataFrame, out: Path) -> None:
    _save(missingness_figure(panel), out)


def price_series_figure(prices: pd.DataFrame) -> Figure:
    """Raw market-level prices exactly as reported: no index, no basket weights, no unit conversion."""
    commodities = sorted(prices["commodity"].dropna().unique())
    fig = Figure(figsize=(9, 3 * len(commodities)), layout="constrained")
    axes = fig.subplots(len(commodities), 1, squeeze=False, sharex=True)[:, 0]
    for ax, commodity in zip(axes, commodities, strict=True):
        subset = prices[prices["commodity"] == commodity]
        for market, series in subset.groupby("market"):
            series = series.assign(date=pd.to_datetime(series["date"])).sort_values("date")
            ax.plot(series["date"], series["price"], marker="o", markersize=3, linewidth=1, label=str(market))
        ax.set_title(commodity, fontsize=10)
        pairs = subset[["currency", "unit"]].drop_duplicates().itertuples(index=False)
        ax.set_ylabel(f"price as reported ({', '.join(sorted(f'{c}/{u}' for c, u in pairs))})", fontsize=8)
        if subset["market"].nunique() <= 12:
            ax.legend(fontsize=7, ncols=2)
        _date_axis(ax)
    return fig


def plot_commodity_series(prices: pd.DataFrame, out: Path) -> None:
    _save(price_series_figure(prices), out)


def conflict_rainfall_figure(panel: pd.DataFrame, accessed: str) -> Figure:
    monthly = panel.groupby("month").agg(
        events=("events", "sum"), fatalities=("fatalities", "sum"), precip_mm=("precip_mm", "mean")
    )
    dates = _month_dates(monthly.index.to_series())
    fig = Figure(figsize=(9, 6), layout="constrained")
    top, bottom = fig.subplots(2, 1, sharex=True)
    top.plot(dates, monthly["events"], label="events", marker="o", markersize=3)
    top.plot(dates, monthly["fatalities"], label="fatalities", marker="o", markersize=3)
    top.set_ylabel("national monthly total")
    top.legend()
    bottom.plot(dates, monthly["precip_mm"], color="tab:green", marker="o", markersize=3)
    bottom.set_ylabel("mean district rainfall (mm)")
    _date_axis(bottom)
    _reserve_caption_space(fig)
    fig.text(0.01, 0.005, acled_caption(accessed), fontsize=8, ha="left", va="bottom")
    return fig


def plot_conflict_rainfall_trends(panel: pd.DataFrame, out: Path, accessed: str) -> None:
    _save(conflict_rainfall_figure(panel, accessed), out)


def district_audit_map_figure(panel: pd.DataFrame, boundaries: gpd.GeoDataFrame, column: str, accessed: str) -> Figure:
    summary = district_summary(panel, column).rename("value")
    merged = boundaries.merge(summary, left_on="admin2_id", right_index=True, how="left")
    fig = Figure(figsize=(7, 7), layout="constrained")
    ax = fig.subplots()
    merged.plot(
        column="value", ax=ax, legend=True, cmap="viridis", edgecolor="white", linewidth=0.3,
        missing_kwds={"color": "lightgrey", "hatch": "//"},
    )
    kind = "total over the period" if column in CONFLICT_COLUMNS else "share of months with a value"
    ax.set_title(f"{column}: {kind}", fontsize=10)
    ax.set_axis_off()
    if column in CONFLICT_COLUMNS:
        _reserve_caption_space(fig)
        fig.text(0.01, 0.005, acled_caption(accessed), fontsize=8, ha="left", va="bottom")
    return fig


def make_district_audit_map(
    panel: pd.DataFrame, boundaries: gpd.GeoDataFrame, column: str, out: Path, accessed: str
) -> None:
    _save(district_audit_map_figure(panel, boundaries, column, accessed), out)
