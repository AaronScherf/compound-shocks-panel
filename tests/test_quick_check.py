"""The quick check uses only synthetic inputs and explains both outcomes."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "quick_check.py"
spec = importlib.util.spec_from_file_location("quick_check", SCRIPT)
quick_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quick_check)


def test_quick_check_runs_fixture_pipeline_and_reports_pass(capsys):
    assert quick_check.main() == 0
    output = capsys.readouterr().out
    assert "Quick check: PASS." in output
    assert "This does not test the real data." in output


def test_quick_check_explains_pipeline_failure(monkeypatch, capsys):
    monkeypatch.setattr(quick_check, "panel_main", lambda _args: 1)
    assert quick_check.main() == 1
    output = capsys.readouterr().out
    assert "Quick check: FAIL." in output
    assert 'The step "reproduce" stopped' in output
    assert "Then type `uv run reprokit quick-check` again." in output
