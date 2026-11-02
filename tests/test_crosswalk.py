import pandas as pd

from compound_shocks.crosswalk import apply_crosswalk


def test_crosswalk_reports_every_unmatched_name():
    source = pd.DataFrame({"admin2": ["Alpha", "Missing B", "Missing C", "Missing B"]})
    result, problems = apply_crosswalk(source, "admin2", {"Alpha": "A"}, "prices")
    assert result["admin2"].tolist()[0] == "A"
    assert pd.isna(result["admin2"].iloc[1])
    assert len(problems) == 2
    assert all(name in " ".join(map(str, problems)) for name in ("Missing B", "Missing C"))


def test_adapters_output_passes_check_frame():
    from pathlib import Path

    from compound_shocks.adapters.prmn import PrmnAdapter
    from compound_shocks.adapters.wfp_prices import WfpPricesAdapter
    from compound_shocks.schema import check_frame

    fixtures = Path(__file__).parent / "fixtures"
    assert check_frame(WfpPricesAdapter().read([fixtures / "wfp_prices_fixture.csv"], {}), "prices") == []
    assert check_frame(PrmnAdapter().read([fixtures / "prmn_fixture.xlsx"], {}), "displacement") == []
