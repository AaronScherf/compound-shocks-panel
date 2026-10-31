from pathlib import Path

import pandas as pd

from compound_shocks.adapters.prmn import PrmnAdapter
from compound_shocks.schema import check_frame

FIXTURE = Path(__file__).parent / "fixtures" / "prmn_fixture.csv"


def test_prmn_unreported_month_is_nan_not_zero():
    frame = PrmnAdapter().read([FIXTURE], {})
    assert pd.isna(frame.loc[frame["month"] == "2021-02", "individuals"].iloc[0])
    assert "2021-05" not in frame["month"].tolist()


def test_prmn_reason_categories_mapped_and_unknown_reported():
    frame = PrmnAdapter().read([FIXTURE], {})
    assert frame["reason"].tolist() == ["drought", "conflict", "flood", "other"]
    assert len(frame.attrs["problems"]) == 1
    assert "Unclear" in str(frame.attrs["problems"][0])


def test_prmn_output_passes_check_frame():
    assert check_frame(PrmnAdapter().read([FIXTURE], {}), "displacement") == []
