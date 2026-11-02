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
