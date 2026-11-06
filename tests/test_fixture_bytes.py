"""Keep committed fixture bytes identical across Git checkouts."""

import hashlib
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
EXPECTED_SHA256 = {
    "acled_fixture.csv": "845ce4ab3c3ecc3b89bedc3bc2a605bcea3b0dda3cebdcd75d063d9fa1bbf298",
    "wfp_prices_fixture.csv": "eb9edfcfc5eac84e2baff7accbe9ed4ca712db7be7ce1bea0fdb227357663bca",
    "population_fixture.csv": "1d05355d068334665b3850e449a369ccae5a044dc9fd01ca34e9bdd9c92bfefc",
    "codab_fixture.geojson": "a6a1f1820d0594514f343934a43e6b9332f8be48aa43b8016ba4551175550a20",
    "geoboundaries_fixture.geojson": "6f87622ee86b0d59215ffb35009c17ed3d99eed7eb9d3e7a2df5075f8aeed534",
}


def test_all_csv_and_geojson_fixtures_have_recorded_hashes():
    actual = {path.name for pattern in ("*.csv", "*.geojson") for path in FIXTURES.glob(pattern)}
    assert actual == EXPECTED_SHA256.keys(), "Update fixture SHA-256 pins when fixtures are added or removed"


@pytest.mark.parametrize("name, expected", EXPECTED_SHA256.items())
def test_committed_fixture_bytes_match_sha256(name: str, expected: str):
    actual = hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest()
    assert actual == expected, (
        f"{name}: fixture SHA-256 mismatch (possible CRLF checkout); "
        f"expected {expected}, got {actual}"
    )
