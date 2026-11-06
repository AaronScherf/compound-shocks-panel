"""Measure doit steps and write reprokit's per-run metrics beside the outputs."""

import json
import os
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import psutil
from reprokit.manifest import hash_file
from reprokit.run_summary import carry_forward_skipped_steps, write_run_summary


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def measure(action, args: list, name: str, recorded: dict, run_date: str) -> None:
    """Sample this process's RSS while one synchronous pipeline action runs."""
    process = psutil.Process()
    peak = process.memory_info().rss
    done = threading.Event()

    def sample() -> None:
        nonlocal peak
        while not done.wait(0.01):
            peak = max(peak, process.memory_info().rss)

    watcher = threading.Thread(target=sample, daemon=True)
    started = time.perf_counter()
    watcher.start()
    try:
        action(*args)
    finally:
        done.set()
        watcher.join()
        peak = max(peak, process.memory_info().rss)
        recorded[name] = {
            "name": name,
            "elapsed_seconds": time.perf_counter() - started,
            "peak_rss_mb": peak / (1024 * 1024),
            "rss_basis": "process",
            "measurement_run_date_utc": run_date,
            "skipped": False,
        }


def previous_metrics(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def finish_run(instance_dir: Path, step_names: list[str], recorded: dict, previous: dict | None, run_date: str) -> None:
    outputs = instance_dir / "outputs"
    ignored = {".gitkeep", "manifest.json", "run_report.json", "run_metrics.json", "RUN_SUMMARY.md"}
    made = [path for path in sorted(outputs.rglob("*")) if path.is_file() and path.name not in ignored]
    current = {
        "schema_version": "0.1.0",
        "run_date_utc": run_date,
        "steps": [recorded.get(name, {"name": name, "skipped": True}) for name in step_names],
        "outputs": [{"path": path.relative_to(outputs).as_posix(), "sha256": hash_file(path)} for path in made],
    }
    complete = carry_forward_skipped_steps(current, previous)
    metrics_path = outputs / "run_metrics.json"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=outputs, delete=False, newline="\n") as stream:
        temporary = Path(stream.name)
        json.dump(complete, stream, indent=2)
        stream.write("\n")
    try:
        os.replace(temporary, metrics_path)
    finally:
        temporary.unlink(missing_ok=True)
    write_run_summary(outputs / "manifest.json", outputs / "run_report.json", metrics_path,
                      instance_dir / "config.yaml", outputs / "RUN_SUMMARY.md")
