"""Column-rename mappings kept in YAML so a new provider needs a file, not code."""

from pathlib import Path

import pandas as pd
from reprokit.loader import load_yaml
from reprokit.problems import Problem


def load_mapping(path: Path) -> dict[str, str]:
    doc, problems = load_yaml(path)
    if problems:
        raise ValueError("; ".join(str(p) for p in problems))
    return {str(k): str(v) for k, v in doc.items()}


def apply_mapping(df: pd.DataFrame, mapping: dict[str, str]) -> tuple[pd.DataFrame, list[Problem]]:
    problems = [Problem("mapping", src, "source column not found in data") for src in mapping if src not in df.columns]
    present = {src: dst for src, dst in mapping.items() if src in df.columns}
    return df.rename(columns=present), problems
