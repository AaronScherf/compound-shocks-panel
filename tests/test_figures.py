import subprocess
import sys

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
import pytest
from shapely.geometry import box
from test_eda import make_panel

from compound_shocks.figures import (
    acled_caption,
    conflict_rainfall_figure,
    district_audit_map_figure,
    make_district_audit_map,
    missingness_figure,
    missingness_matrix,
    plot_commodity_series,
    plot_conflict_rainfall_trends,
    price_series_figure,
)

ACCESSED = "2026-10-31"
CAPTION = "Source: ACLED (acleddata.com), accessed 2026-10-31"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")


def prices():
    return pd.DataFrame({
        "date": ["2021-01-15", "2021-02-15", "2021-01-15", "2021-02-15", "2021-01-15"],
        "market": ["A", "A", "B", "B", "A"],
        "admin2": ["D1", "D1", "D2", "D2", "D1"],
        "commodity": ["Sorghum"] * 4 + ["Wheat"],
        "unit": ["KG"] * 5, "currency": ["SOS"] * 5,
        "price": [10.0, 30.0, 11.0, 12.0, 7.0],
    })


def boundaries():
    return gpd.GeoDataFrame({"admin2_id": ["D1", "D2", "D3"], "name": ["a", "b", "c"],
                             "geometry": [box(0, 0, 1, 1), box(1, 0, 2, 1), box(2, 0, 3, 1)]}, crs="EPSG:4326")


def texts(fig):
    return [t.get_text() for t in fig.texts] + [t.get_text() for ax in fig.axes for t in ax.texts]


def test_acled_caption_text():
    assert acled_caption(ACCESSED) == CAPTION


def test_missingness_matrix_writes_png_with_one_panel_per_column(tmp_path):
    panel = make_panel()
    value_columns = [c for c in panel.columns if c not in ("admin2_id", "month")]
    assert len(missingness_figure(panel).axes) == len(value_columns)
    out = tmp_path / "missing.png"
    missingness_matrix(panel, out)
    assert out.read_bytes().startswith(PNG_MAGIC) and not plt.get_fignums()


def test_missingness_marks_missing_cells_distinctly():
    fig = missingness_figure(make_panel())
    price_ax = fig.axes[[ax.get_title() for ax in fig.axes].index("price_sorghum")]
    grid = price_ax.images[0].get_array()
    assert grid.shape == (3, 3) and int(grid.sum()) == 2  # two observed district-months of nine


def test_price_series_uses_raw_prices_not_an_index():
    fig = price_series_figure(prices())
    plotted = sorted(float(y) for ax in fig.axes for line in ax.lines for y in line.get_ydata())
    assert plotted == sorted(prices()["price"].tolist())


def test_price_series_has_one_panel_per_commodity_and_one_line_per_market():
    fig = price_series_figure(prices())
    assert [ax.get_title() for ax in fig.axes] == ["Sorghum", "Wheat"]
    assert [len(ax.lines) for ax in fig.axes] == [2, 1]


def test_price_figure_has_no_acled_caption(tmp_path):
    assert not any("ACLED" in text for text in texts(price_series_figure(prices())))
    plot_commodity_series(prices(), tmp_path / "prices.png")
    assert (tmp_path / "prices.png").read_bytes().startswith(PNG_MAGIC)


def test_conflict_figures_have_acled_caption(tmp_path):
    assert CAPTION in texts(conflict_rainfall_figure(make_panel(), ACCESSED))
    assert CAPTION in texts(district_audit_map_figure(make_panel(), boundaries(), "events", ACCESSED))
    plot_conflict_rainfall_trends(make_panel(), tmp_path / "trend.png", ACCESSED)
    make_district_audit_map(make_panel(), boundaries(), "fatalities", tmp_path / "map.png", ACCESSED)
    assert (tmp_path / "trend.png").exists() and (tmp_path / "map.png").exists()


def test_trend_figure_plots_national_totals_and_mean_rainfall():
    fig = conflict_rainfall_figure(make_panel(), ACCESSED)
    ydata = [list(line.get_ydata()) for ax in fig.axes for line in ax.lines]
    assert [0, 4, 0] in ydata and [0, 9, 0] in ydata and [5.0, 5.0, 5.0] in ydata


def test_non_conflict_map_has_no_acled_caption():
    assert not any("ACLED" in t for t in texts(district_audit_map_figure(make_panel(), boundaries(), "price_sorghum", ACCESSED)))


def test_map_rejects_unknown_column():
    with pytest.raises(ValueError, match="nonsense"):
        district_audit_map_figure(make_panel(), boundaries(), "nonsense", ACCESSED)


def test_no_modeling_imports():
    code = ("import sys, compound_shocks.eda, compound_shocks.figures; "
            "bad = {'statsmodels', 'sklearn'} & set(sys.modules); assert not bad, bad")
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0
