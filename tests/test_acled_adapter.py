import csv
from pathlib import Path

import pytest

from compound_shocks.adapters.acled import AcledAdapter
from compound_shocks.adapters.mapping import load_mapping
from compound_shocks.schema import check_frame

FIXTURE = Path(__file__).parent / "fixtures" / "acled_fixture.csv"
REAL_DIR = Path(__file__).parent.parent / "instances" / "somalia" / "data" / "raw" / "conflict_events"


def test_reads_fixture_with_bom():
    assert FIXTURE.read_bytes().startswith(b"\xef\xbb\xbf")
    frame = AcledAdapter().read([FIXTURE], {})
    assert len(frame) == 12 and frame["event_id"].iloc[0] == "SYN0000"


def test_lat_long_single_column_variant_is_split(tmp_path):
    with FIXTURE.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["lat_long"] = f"{row.pop('latitude')},{row.pop('longitude')}"
    path = tmp_path / "combined.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    frame = AcledAdapter().read([path], {})
    original = AcledAdapter().read([FIXTURE], {})
    assert frame[["lat", "lon"]].equals(original[["lat", "lon"]])


def test_output_passes_check_frame():
    assert check_frame(AcledAdapter().read([FIXTURE], {}), "conflict_events") == []


def test_dates_are_iso_strings_and_fatalities_int():
    frame = AcledAdapter().read([FIXTURE], {})
    assert frame["date"].str.fullmatch(r"\d{4}-\d{2}-\d{2}").all()
    assert frame["fatalities"].dtype.kind == "i"


def test_find_ignores_non_csv_and_gitkeep(tmp_path):
    (tmp_path / ".gitkeep").write_text("")
    (tmp_path / "notes.txt").write_text("x")
    (tmp_path / "a.csv").write_text("x")
    assert [p.name for p in AcledAdapter().find(tmp_path)] == ["a.csv"]


def test_missing_source_column_raises_naming_it(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("event_id_cnty,event_date\nA,2021-01-01\n", encoding="utf-8")
    with pytest.raises(ValueError, match="latitude"):
        AcledAdapter().read([path], {})


@pytest.mark.real_data
def test_real_export_header_maps():
    exports = sorted(REAL_DIR.glob("*.csv"))
    if not exports:
        pytest.skip("no real ACLED export present")
    with exports[0].open(encoding="utf-8-sig", newline="") as handle:
        header = next(csv.reader(handle))  # header only: no event rows are read
    mapping = load_mapping(Path(__file__).parent.parent / "src/compound_shocks/adapters/mappings/acled.yaml")
    assert set(mapping) <= set(header)
