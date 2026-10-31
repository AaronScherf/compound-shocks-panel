"""Seeded generator for synthetic test fixtures. Nothing here is real data. Run: python tests/fixtures/make_fixtures.py"""

import csv
import json
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


def write_boundaries(path: Path, *, fallback: bool = False) -> None:
    """Three synthetic unit squares, with a shared edge and one separate cell."""
    features = []
    for code, name, x in [("B", "Bravo", 0), ("A", "Alpha", 1), ("C", "Charlie", 3)]:
        props = {"shapeID": code, "shapeName": name} if fallback else {"ADM2_PCODE": code, "ADM2_EN": name}
        features.append({"type": "Feature", "properties": props, "geometry": {
            "type": "Polygon", "coordinates": [[[x, 0], [x + 1, 0], [x + 1, 1], [x, 1], [x, 0]]],
        }})
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")


def write_chirps(directory: Path) -> None:
    """Two 1-by-4 monthly grids; -9999 is a missing cell."""
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    directory.mkdir(exist_ok=True)
    for month, values in {"2021-01": [10, 20, -9999, -9999], "2021-02": [0, 40, 30, -9999]}.items():
        with rasterio.open(directory / f"chirps_{month}.tif", "w", driver="GTiff", width=4, height=1,
                           count=1, dtype="float32", crs="EPSG:4326", transform=from_origin(0, 1, 1, 1),
                           nodata=-9999) as dst:
            dst.write(np.array([values], dtype="float32"), 1)


if __name__ == "__main__":
    write_acled(HERE / "acled_fixture.csv")
    write_boundaries(HERE / "codab_fixture.geojson")
    write_boundaries(HERE / "geoboundaries_fixture.geojson", fallback=True)
    write_chirps(HERE / "chirps")
