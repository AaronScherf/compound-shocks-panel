from pathlib import Path

import pytest

from compound_shocks.adapters.wfp_prices import WfpPricesAdapter
from compound_shocks.schema import check_frame

FIXTURE = Path(__file__).parent / "fixtures" / "wfp_prices_fixture.csv"


def test_prices_mixed_units_are_flagged():
    frame = WfpPricesAdapter().read([FIXTURE], {})
    assert len(frame) == 3
    assert len(frame.attrs["problems"]) == 2  # unit and currency changes
    assert "unit" in str(frame.attrs["problems"][0])
    assert "currency" in str(frame.attrs["problems"][1])


def test_missing_source_column_names_it(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("date,market\n2021-01-01,A\n", encoding="utf-8")
    with pytest.raises(ValueError, match="admin2"):
        WfpPricesAdapter().read([path], {})


def test_mixed_price_types_are_reported_not_silently_averaged(tmp_path):
    path = tmp_path / "prices.csv"
    path.write_text(
        "date,market,admin2,commodity,unit,currency,price,pricetype\n"
        "2021-01-15,M,Alpha,Sorghum,KG,SOS,10,Retail\n"
        "2021-01-15,M,Alpha,Sorghum,KG,SOS,8,Wholesale\n",
        encoding="utf-8",
    )
    problems = WfpPricesAdapter().read([path], {}).attrs["problems"]
    assert any("pricetype" in str(p) and "Retail" in str(p) and "Wholesale" in str(p) for p in problems)


def test_single_price_type_adds_no_problem(tmp_path):
    path = tmp_path / "prices.csv"
    path.write_text(
        "date,market,admin2,commodity,unit,currency,price,pricetype\n2021-01-15,M,Alpha,Sorghum,KG,SOS,10,Retail\n",
        encoding="utf-8",
    )
    assert WfpPricesAdapter().read([path], {}).attrs["problems"] == []


def test_wfp_output_passes_check_frame():
    assert check_frame(WfpPricesAdapter().read([FIXTURE], {}), "prices") == []


def _history(tmp_path):
    path = tmp_path / "prices.csv"
    path.write_text(
        "date,market,admin2,commodity,unit,currency,price\n"
        "2015-01-15,M,Alpha,Sorghum,KG,SOS,10\n"
        "2015-02-15,M,Alpha,Sorghum,KG,SLS,11\n"
        "2021-01-15,M,Alpha,Sorghum,KG,SLS,12\n"
        "2021-02-15,M,Alpha,Sorghum,KG,SLS,13\n"
        "2024-01-15,M,Alpha,Sorghum,KG,SLS,14\n",
        encoding="utf-8",
    )
    return path


PERIOD = {"start": "2021-01-01", "end": "2023-08-31"}


def test_rows_outside_the_study_period_are_dropped_before_checks(tmp_path):
    frame = WfpPricesAdapter().read([_history(tmp_path)], {"period": PERIOD})
    assert frame["date"].tolist() == ["2021-01-15", "2021-02-15"]
    assert not any("currency" in str(problem) for problem in frame.attrs["problems"])
    assert any("dropped 3" in decision for decision in frame.attrs["decisions"])


def test_without_a_period_every_row_is_kept_and_history_is_checked(tmp_path):
    frame = WfpPricesAdapter().read([_history(tmp_path)], {})
    assert len(frame) == 5 and any("currency" in str(problem) for problem in frame.attrs["problems"])
    assert frame.attrs["decisions"] == []
