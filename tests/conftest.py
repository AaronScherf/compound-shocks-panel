import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
RAW_FILES = {
    "conflict_events": ["acled_fixture.csv"],
    "displacement": ["prmn_fixture.csv"],
    "prices": ["wfp_prices_fixture.csv"],
    "admin_boundaries": ["codab_fixture.geojson"],
}


def make_instance(root: Path, name: str, boundaries: str = "codab_fixture.geojson") -> Path:
    instance = root / "instances" / name
    raw = instance / "data" / "raw"
    shutil.copy(FIXTURES / "instance_somalia" / "config.yaml", _ensure(instance) / "config.yaml")
    for role, files in RAW_FILES.items():
        for file in files if role != "admin_boundaries" else [boundaries]:
            shutil.copy(FIXTURES / file, _ensure(raw / role) / file)
    for tif in (FIXTURES / "chirps").glob("*.tif"):
        shutil.copy(tif, _ensure(raw / "rainfall") / tif.name)
    return instance


def _ensure(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def root(tmp_path):
    make_instance(tmp_path, "somalia")
    return tmp_path
