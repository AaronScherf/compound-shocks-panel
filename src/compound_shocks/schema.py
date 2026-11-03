"""Canonical tables every adapter must produce, and the panel columns built from them."""

from typing import Literal

import pandas as pd
from reprokit.problems import Problem

# column -> kind: text, int, number (int or float), geometry
_SPEC: dict[str, dict[str, str]] = {
    "conflict_events": {
        "event_id": "text", "date": "text", "lat": "number", "lon": "number", "event_type": "text",
        "sub_event_type": "text", "actor1": "text", "fatalities": "int", "geo_precision": "int",
    },
    "displacement": {
        "month": "text", "origin_admin2": "text", "dest_admin2": "text", "individuals": "number", "reason": "text",
    },
    "prices": {
        "date": "text", "market": "text", "admin2": "text", "commodity": "text", "unit": "text",
        "currency": "text", "price": "number",
    },
    "rainfall": {"admin2_id": "text", "month": "text", "precip_mm": "number", "coverage_frac": "number"},
    "admin_boundaries": {"admin2_id": "text", "name": "text", "geometry": "geometry"},
    "population": {"admin2_id": "text", "population": "number"},
}

# A provider that reports stocks (people present) instead of flows (people moving) fills this table; the config
# role is still "displacement". Adapters name it in df.attrs["schema"].
STOCK_SPEC: dict[str, str] = {"month": "text", "dest_admin2": "text", "origin_admin1": "text", "stock": "number"}
_SCHEMAS = {**_SPEC, "displacement_stock": STOCK_SPEC}

KEYS: dict[str, list[str]] = {
    "conflict_events": ["event_id"],
    "displacement": ["month", "origin_admin2", "dest_admin2", "reason"],
    "prices": ["date", "market", "commodity", "unit"],
    "rainfall": ["admin2_id", "month"],
    "admin_boundaries": ["admin2_id"],
    "displacement_stock": ["month", "dest_admin2", "origin_admin1"],
    "population": ["admin2_id"],
}

ROLE_COLUMNS: dict[str, list[str]] = {role: list(cols) for role, cols in _SPEC.items()}
STOCK_COLUMNS: list[str] = list(STOCK_SPEC)

PANEL_COLUMNS: dict[str, Literal["core", "extension"]] = {
    "events": "core",
    "fatalities": "core",
    "precip_mm": "core",
    "coverage_frac": "core",
    "price_sorghum": "core",
    "price_wheat": "core",
    "displaced_individuals": "extension",
    "population": "extension",
    "displaced_stock": "extension",
    "displaced_stock_change": "extension",
    "price_goat": "extension",
    "wage_labor": "extension",
    "tot_goat_sorghum": "extension",
    "tot_wage_sorghum": "extension",
}


def _kind_ok(series: pd.Series, kind: str) -> bool:
    if kind == "text":
        return series.dtype == object or pd.api.types.is_string_dtype(series)
    if kind == "int":
        return pd.api.types.is_integer_dtype(series)
    if kind == "number":
        return pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)
    return series.dtype == "geometry"


def check_frame(df: pd.DataFrame, role: str) -> list[Problem]:
    if role not in _SCHEMAS:
        raise KeyError(f"unknown role {role!r}; roles: {', '.join(sorted(_SCHEMAS))}")
    spec = _SCHEMAS[role]
    where = f"table:{role}"
    problems = [Problem(where, col, "missing column") for col in spec if col not in df.columns]
    problems += [Problem(where, col, "unexpected column") for col in df.columns if col not in spec]
    problems += [
        Problem(where, col, f"expected {kind}, got dtype {df[col].dtype}")
        for col, kind in spec.items()
        if col in df.columns and not _kind_ok(df[col], kind)
    ]
    keys = KEYS[role]
    if all(k in df.columns for k in keys) and df.duplicated(subset=keys).any():
        n = int(df.duplicated(subset=keys).sum())
        problems.append(Problem(where, ", ".join(keys), f"{n} duplicate key row(s)"))
    return problems
