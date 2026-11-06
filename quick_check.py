"""Run the real pipeline on committed synthetic inputs in a temporary instance."""

import json
import shutil
import tempfile
import time
from pathlib import Path

from reprokit.manifest import hash_file
from reprokit.smoke import verify_smoke_result

from compound_shocks.cli import main as panel_main

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "tests" / "fixtures"
RAW_FILES = {
    "conflict_events": "acled_fixture.csv",
    "displacement": "prmn_fixture.xlsx",
    "prices": "wfp_prices_fixture.csv",
    "admin_boundaries": "codab_fixture.geojson",
    "population": "population_fixture.csv",
}


def _copy_fixture_instance(root: Path) -> Path:
    instance = root / "instances" / "somalia"
    instance.mkdir(parents=True)
    shutil.copyfile(FIXTURES / "instance_somalia" / "config.yaml", instance / "config.yaml")
    for role, filename in RAW_FILES.items():
        folder = instance / "data" / "raw" / role
        folder.mkdir(parents=True)
        shutil.copyfile(FIXTURES / filename, folder / filename)
    rainfall = instance / "data" / "raw" / "rainfall"
    rainfall.mkdir(parents=True)
    for path in (FIXTURES / "chirps").glob("*.tif"):
        shutil.copyfile(path, rainfall / path.name)
    return instance


def main() -> int:
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="compound-shocks-check-") as folder:
        root = Path(folder)
        instance = _copy_fixture_instance(root)
        record = root / "quick_check_result.json"
        try:
            status = panel_main(["reproduce", "--instance", "somalia", "--root", str(root)])
            elapsed = time.perf_counter() - started
            final = instance / "data" / "derived" / "panel.csv"
            summary = instance / "outputs" / "RUN_SUMMARY.md"
            success = status == 0 and final.is_file() and summary.is_file() and elapsed < 60
            result = {
                "offline": True,
                "success": success,
                "elapsed_seconds": elapsed,
                "required_outputs": [{"path": "instances/somalia/data/derived/panel.csv", "sha256": hash_file(final)}] if success else [],
            }
            if not success:
                result.update(failed_step="reproduce", failure_reason="the synthetic panel or run summary was not made within 60 seconds")
        except Exception as exc:  # noqa: BLE001 - turn any pipeline failure into a readable FAIL
            result = {"offline": True, "success": False, "elapsed_seconds": time.perf_counter() - started,
                      "required_outputs": [], "failed_step": "reproduce", "failure_reason": str(exc)}
        record.write_text(json.dumps(result), encoding="utf-8")
        checked = verify_smoke_result(record, root)
        print(checked.text)
        return int(not checked.passed)


if __name__ == "__main__":
    raise SystemExit(main())
