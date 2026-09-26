import json

from common import DOCS_DIR, REPO_ROOT
from eval_judge import build_report, compute_metrics
from judge import load_checklist


def test_counts_agreement_misses_false_alarms_and_unknowns():
    labels = {"a.md": {"x": True, "y": False, "z": True, "w": False}}
    predictions = {"a.md": {"x": True, "y": True, "z": False, "w": None}}
    overall, per_item = compute_metrics(labels, predictions)
    assert overall == {"total": 4, "agreed": 1, "misses": 1, "false_alarms": 1, "unknown": 1}
    assert per_item["y"]["misses"] == 1


def test_missing_page_counts_as_unknown():
    overall, _ = compute_metrics({"a.md": {"x": True}}, {})
    assert overall["unknown"] == 1


def test_report_lists_disagreements():
    labels = {"a.md": {"x": False}}
    verdicts = {"a.md": {"x": {"passed": True, "reason": "Looks fine."}}}
    report = build_report("test-model", labels, verdicts)
    assert "0%" in report
    assert "label says fail" in report


def test_labels_match_docs_and_checklist():
    """Every labeled page exists, and every page is labeled for every checklist item."""
    labels = json.loads((REPO_ROOT / "eval" / "labels.json").read_text())
    item_ids = {item["id"] for item in load_checklist()}
    assert set(labels) == {p.name for p in DOCS_DIR.glob("*.md")}
    for page_labels in labels.values():
        assert set(page_labels) == item_ids
