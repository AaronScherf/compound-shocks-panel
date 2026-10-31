"""Seeded generator for synthetic test fixtures. Nothing here is real data. Run: python tests/fixtures/make_fixtures.py"""

import csv
import random
from pathlib import Path

HERE = Path(__file__).parent

ACLED_COLUMNS = [
    "event_id_cnty", "event_date", "year", "time_precision", "disorder_type", "event_type", "sub_event_type",
    "actor1", "assoc_actor_1", "inter1", "interaction", "civilian_targeting", "iso", "region", "country",
    "admin1", "admin2", "admin3", "location", "latitude", "longitude", "geo_precision", "source",
    "source_scale", "notes", "fatalities", "tags", "timestamp",
]


def acled_rows(n: int = 12, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        row = dict.fromkeys(ACLED_COLUMNS, "")
        row.update(
            event_id_cnty=f"SYN{i:04d}", event_date=f"2021-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            year=2021, event_type=rng.choice(["Battles", "Riots", "Violence against civilians"]),
            sub_event_type="Synthetic", actor1="Synthetic actor", country="Synthland",
            latitude=round(rng.uniform(0, 1), 4), longitude=round(rng.uniform(0, 1), 4),
            geo_precision=rng.choice([1, 2, 3]), notes="synthetic", fatalities=rng.randint(0, 5),
        )
        rows.append(row)
    return rows


def write_acled(path: Path) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ACLED_COLUMNS)
        writer.writeheader()
        writer.writerows(acled_rows())


if __name__ == "__main__":
    write_acled(HERE / "acled_fixture.csv")
