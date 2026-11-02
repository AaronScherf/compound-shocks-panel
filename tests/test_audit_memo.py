import re
from pathlib import Path

import pytest
import yaml
from conftest import FIXTURES

from compound_shocks import audit_memo
from compound_shocks.audit_memo import to_html
from compound_shocks.cli import main

FORBIDDEN = ("effect of", "causes", "impact of", "significant")


def descriptor(role, **extra):
    base = {"role": role, "provider": f"{role}-provider", "accessed": "2026-10-31"}
    return {**base, **extra}


@pytest.fixture
def memo_root(root):
    folder = root / "instances/somalia/data/descriptors"
    folder.mkdir(parents=True)
    acled = descriptor("conflict_events", applied_filters="Somalia 2021 to 2023", manipulation="district-month totals")
    (folder / "conflict_events.yaml").write_text(yaml.safe_dump(acled), encoding="utf-8")
    assert main(["reproduce", "--instance", "somalia", "--root", str(root)]) == 0
    return root


def memo_text(root) -> str:
    return (root / "instances/somalia/outputs/audit_memo.md").read_text(encoding="utf-8")


def test_memo_contains_provenance_hashes_and_access_dates(memo_root):
    text = memo_text(memo_root)
    manifest = (memo_root / "instances/somalia/outputs/manifest.json").read_text(encoding="utf-8")
    hashes = re.findall(r'"sha256": "([0-9a-f]{64})"', manifest)
    assert sum(h[:16] in text for h in hashes) >= 4  # one per role with data files
    assert "2026-10-31" in text and "Boundary vintage" in text


def test_memo_reports_districts_with_no_price_observations(memo_root):
    text = memo_text(memo_root)
    assert "Districts with no price observation: " in text and "B" in text.split("Districts with no price observation: ")[1]
    assert re.search(r"\d+% of district-months have a sorghum or wheat price", text)


def test_memo_contains_acled_citation_block_and_three_answers(memo_root):
    text = memo_text(memo_root)
    assert "Source: ACLED (acleddata.com), accessed 2026-10-31" in text
    assert "1. Date accessed: 2026-10-31" in text
    assert "2. Filters applied: Somalia 2021 to 2023" in text
    assert "3. Manipulation: district-month totals" in text


def test_memo_includes_figures_and_an_html_copy(memo_root):
    outputs = memo_root / "instances/somalia/outputs"
    for name in audit_memo.FIGURES:
        assert (outputs / "figures" / name).stat().st_size > 0
        assert f"figures/{name}" in memo_text(memo_root)
    page = (outputs / "audit_memo.html").read_text(encoding="utf-8")
    assert page.startswith("<!doctype html>") and "<table>" in page and "<img " in page


def test_memo_makes_no_causal_claims(memo_root):
    for text in (memo_text(memo_root), Path(audit_memo.__file__).read_text(encoding="utf-8")):
        assert not any(word in text.lower() for word in FORBIDDEN)


def test_memo_without_descriptors_says_not_recorded(root):
    assert main(["reproduce", "--instance", "somalia", "--root", str(root)]) == 0
    assert "1. Date accessed: not recorded" in memo_text(root)


def test_audit_step_is_part_of_reproduce(root):
    main(["reproduce", "--instance", "somalia", "--root", str(root)])
    log = (root / "instances/somalia/data/derived/ran.log").read_text().split()
    assert log[-1] == "audit"
    assert main(["reproduce", "--instance", "somalia", "--root", str(root)]) == 0
    assert (root / "instances/somalia/data/derived/ran.log").read_text().split() == log


def test_html_escapes_text_and_renders_lists_and_tables():
    page = to_html("# T\n\n- <b>one</b>\n- two\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n", "t")
    assert "<h1>T</h1>" in page and "<li>&lt;b&gt;one&lt;/b&gt;</li>" in page
    assert "<th>a</th>" in page and "<td>2</td>" in page and "---" not in page


def test_project_charter_lists_the_audit_memo_deliverable():
    charter = yaml.safe_load((Path(FIXTURES).parents[1] / "project.yaml").read_text(encoding="utf-8"))
    memo = next(d for d in charter["deliverables"] if d["id"] == "data-audit-memo")
    assert memo["format"] == "markdown" and "reproduce" in memo["build"]
