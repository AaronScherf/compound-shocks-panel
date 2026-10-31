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


def test_wfp_output_passes_check_frame():
    assert check_frame(WfpPricesAdapter().read([FIXTURE], {}), "prices") == []
