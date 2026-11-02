"""Plain-HTTP download helpers. Every download leaves a sidecar record (url, access date, sha256)."""

import hashlib
import json
from datetime import date
from pathlib import Path

import requests

TIMEOUT_SECONDS = 120


class FetchError(RuntimeError):
    pass


class ProviderRevisedData(FetchError):
    pass


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def get(url: str, source: str, **kwargs) -> requests.Response:
    response = requests.get(url, timeout=TIMEOUT_SECONDS, **kwargs)
    if response.status_code != 200:
        raise FetchError(
            f"{source}: {url} returned HTTP {response.status_code}; the provider may have moved or revised the file"
        )
    return response


def save(data: bytes, url: str, out_dir: Path, name: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    path.write_bytes(data)
    record = {"url": url, "accessed": date.today().isoformat(), "sha256": sha256_of(data)}
    path.with_name(path.name + ".fetch.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return path


def fetch_file(
    url: str,
    out_dir: Path,
    expected_sha256: str | None = None,
    refresh: bool = False,
    source: str = "download",
    name: str | None = None,
) -> Path:
    data = get(url, source).content
    digest = sha256_of(data)
    if expected_sha256 and digest != expected_sha256 and not refresh:
        raise ProviderRevisedData(
            f"{source}: {url} now has sha256 {digest}, expected {expected_sha256} (accessed {date.today().isoformat()}); "
            "the provider revised the data. Re-run with refresh=True to accept it and record a new descriptor hash."
        )
    return save(data, url, Path(out_dir), name or url.rsplit("/", 1)[-1])
