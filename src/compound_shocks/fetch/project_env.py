"""Temporary copy of reprokit.env.load_project_env until its next release."""

import os
from pathlib import Path


def load_project_env(root: Path | str) -> None:
    """Set missing environment variables from root/.env."""
    path = Path(root) / ".env"
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or not (key[0].isalpha() or key[0] == "_") or not all(
            char.isalnum() or char == "_" for char in key
        ):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)
