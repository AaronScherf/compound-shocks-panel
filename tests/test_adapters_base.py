from pathlib import Path

import pandas as pd
import pytest

from compound_shocks.adapters import base
from compound_shocks.adapters.mapping import apply_mapping, load_mapping
from compound_shocks.schema import PANEL_COLUMNS

ROOT = Path(__file__).parent.parent


class FakeAdapter:
    def __init__(self, role, provider):
        self.role = role
        self.provider = provider

    def find(self, raw_dir):
        return []

    def read(self, paths, instance):
        return pd.DataFrame()


@pytest.fixture(autouse=True)
def empty_registry(monkeypatch):
    monkeypatch.setattr(base, "_REGISTRY", {})


def test_get_adapter_ignores_case_and_whitespace():
    adapter = FakeAdapter("prices", "WFP")
    base.register(adapter)
    assert base.get_adapter("prices", "  wfp ") is adapter


def test_get_adapter_unknown_provider_lists_registered():
    base.register(FakeAdapter("prices", "WFP"))
    with pytest.raises(KeyError, match="WFP"):
        base.get_adapter("prices", "Other")


def test_get_adapter_unknown_role_with_nothing_registered_says_so():
    with pytest.raises(KeyError, match="no adapters registered"):
        base.get_adapter("prices", "WFP")


def test_register_rejects_a_role_with_no_canonical_schema():
    with pytest.raises(ValueError, match="nonsense"):
        base.register(FakeAdapter("nonsense", "X"))


def test_register_rejects_a_second_adapter_for_the_same_role_and_provider():
    base.register(FakeAdapter("prices", "WFP"))
    with pytest.raises(ValueError, match="already registered"):
        base.register(FakeAdapter("prices", "wfp"))


def test_load_mapping_reads_yaml(tmp_path):
    path = tmp_path / "m.yaml"
    path.write_text("event_id_cnty: event_id\nevent_date: date\n")
    assert load_mapping(path) == {"event_id_cnty": "event_id", "event_date": "date"}


def test_load_mapping_on_bad_file_raises_valueerror_naming_file(tmp_path):
    path = tmp_path / "m.yaml"
    path.write_text("a: [oops\n")
    with pytest.raises(ValueError, match="m.yaml"):
        load_mapping(path)


def test_apply_mapping_renames_and_reports_missing_source_column():
    frame = pd.DataFrame({"latitude": [1.0], "other": [2]})
    renamed, problems = apply_mapping(frame, {"latitude": "lat", "longitude": "lon"})
    assert list(renamed.columns) == ["lat", "other"]
    assert len(problems) == 1 and "longitude" in str(problems[0])


def test_apply_mapping_leaves_unmapped_columns_untouched():
    renamed, problems = apply_mapping(pd.DataFrame({"x": [1]}), {})
    assert list(renamed.columns) == ["x"] and problems == []


def test_every_panel_column_is_documented_in_the_readme():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for column in PANEL_COLUMNS:
        assert f"`{column}`" in readme, column
