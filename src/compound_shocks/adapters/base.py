"""Adapter protocol and registry: one adapter per (role, provider)."""

from pathlib import Path
from typing import Protocol

import pandas as pd

from compound_shocks.schema import ROLE_COLUMNS

_REGISTRY: dict[tuple[str, str], "Adapter"] = {}


class Adapter(Protocol):
    role: str
    provider: str

    def find(self, raw_dir: Path) -> list[Path]: ...

    def read(self, paths: list[Path], instance: dict) -> pd.DataFrame: ...


def _norm(provider: str) -> str:
    return provider.strip().casefold()


def register(adapter: Adapter) -> None:
    if adapter.role not in ROLE_COLUMNS:
        raise ValueError(f"role {adapter.role!r} has no canonical schema; roles: {', '.join(sorted(ROLE_COLUMNS))}")
    key = (adapter.role, _norm(adapter.provider))
    if key in _REGISTRY:
        raise ValueError(f"adapter already registered for {adapter.role} / {adapter.provider}")
    _REGISTRY[key] = adapter


def get_adapter(role: str, provider: str) -> Adapter:
    try:
        return _REGISTRY[(role, _norm(provider))]
    except KeyError:
        known = sorted(a.provider for (r, _), a in _REGISTRY.items() if r == role)
        listing = ", ".join(known) if known else "no adapters registered"
        raise KeyError(f"no adapter for role {role!r}, provider {provider!r}; registered: {listing}") from None
