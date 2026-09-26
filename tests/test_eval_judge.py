import sys

import pytest

import eval_judge
from eval_judge import agreement_stats, build_report, compute_metrics, keep_applicable, load_labels
from rules import applicable_pairs, load_checklist


def test_counts_agreement_misses_false_alarms_and_unknowns():
    labels = {"a.md": {"x": True, "y": False, "z": True, "w": False}}
    predictions = {"a.md": {"x": True, "y": True, "z": False, "w": None}}
    overall, per_item = compute_metrics(labels, predictions)
    assert overall == {"total": 4, "agreed": 1, "misses": 1, "false_alarms": 1, "unknown": 1}
    assert per_item["y"]["misses"] == 1


def test_missing_page_counts_as_unknown():
    overall, _ = compute_metrics({"a.md": {"x": True}}, {})
    assert overall["unknown"] == 1


def test_report_lists_disagreements_and_new_stats():
    labels = {"a.md": {"x": False}}
    verdicts = {"a.md": {"x": {"passed": True, "reason": "Looks fine."}}}
    report = build_report("test-model", labels, verdicts, {"labeler": "Jared Chapman", "date": "2026-09-26"})
    assert "0%" in report
    assert "label says fail" in report
    assert "Always-pass baseline" in report
    assert "Cohen's κ" in report
    assert "Jared Chapman" in report


def test_kappa_and_baseline():
    labels = {"a.md": {"w": True, "x": True, "y": True, "z": False}}
    predictions = {"a.md": {"w": True, "x": True, "y": False, "z": False}}
    baseline, kappa = agreement_stats(labels, predictions)
    assert baseline == 0.75
    assert kappa == pytest.approx(0.5)


def test_always_pass_judge_gets_zero_kappa():
    labels = {"a.md": {"w": True, "x": True, "y": True, "z": False}}
    predictions = {"a.md": {"w": True, "x": True, "y": True, "z": True}}
    assert agreement_stats(labels, predictions)[1] == pytest.approx(0.0)


def test_unknown_counts_as_the_wrong_answer():
    labels = {"a.md": {"x": True, "y": False}}
    predictions = {"a.md": {"x": None, "y": False}}
    assert agreement_stats(labels, predictions)[1] == pytest.approx(0.0)


def test_no_labels_gives_no_stats():
    assert agreement_stats({}, {}) == (None, None)


def test_keep_applicable_drops_pairs_that_no_longer_apply():
    labels = {"a.md": {"x": True, "y": False}, "b.md": {"x": True}}
    assert keep_applicable(labels, [("a.md", "x")]) == {"a.md": {"x": True}}


def test_missing_labels_file(tmp_path):
    assert load_labels(tmp_path / "nope.json") == (None, None)


def test_labels_file_covers_only_applicable_pairs():
    meta, labels = load_labels()
    if labels is None:
        pytest.skip("No labels yet: run scripts/label.py")
    pairs = set(applicable_pairs(load_checklist()))
    labeled = {(page, item) for page, items in labels.items() for item in items}
    assert labeled <= pairs
    assert meta["labeler"]
    assert meta["rules_hash"].startswith("sha256:")


def _real_applicable_pair():
    """A real (page, item id) pair, so fake labels survive keep_applicable() in main()."""
    pairs = applicable_pairs(load_checklist())
    assert pairs, "expected at least one applicable (page, rule) pair in the repo fixtures"
    return pairs[0]


def test_main_exits_on_stale_labels(monkeypatch):
    page, item = _real_applicable_pair()
    monkeypatch.setattr(
        eval_judge, "load_labels",
        lambda: ({"labeler": "Jared Chapman", "date": "2026-09-26", "rules_hash": "sha256:stale"}, {page: {item: True}}),
    )
    monkeypatch.setattr(eval_judge, "rules_hash", lambda: "sha256:current")
    judge_calls = []
    monkeypatch.setattr(eval_judge, "judge_page", lambda *a, **k: judge_calls.append((a, k)) or {})
    monkeypatch.setattr(eval_judge, "publish", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", ["eval_judge.py"])

    with pytest.raises(SystemExit) as excinfo:
        eval_judge.main()

    assert excinfo.value.code == 1
    assert judge_calls == []


def test_main_allow_stale_proceeds(monkeypatch):
    page, item = _real_applicable_pair()
    monkeypatch.setattr(
        eval_judge, "load_labels",
        lambda: ({"labeler": "Jared Chapman", "date": "2026-09-26", "rules_hash": "sha256:stale"}, {page: {item: True}}),
    )
    monkeypatch.setattr(eval_judge, "rules_hash", lambda: "sha256:current")
    judge_calls = []

    def fake_judge_page(body, rules, model=None):
        judge_calls.append(model)
        return {item: {"passed": True, "reason": "faked"}}

    monkeypatch.setattr(eval_judge, "judge_page", fake_judge_page)
    published = []
    monkeypatch.setattr(eval_judge, "publish", lambda markdown: published.append(markdown))
    monkeypatch.setattr(sys, "argv", ["eval_judge.py", "--allow-stale"])

    eval_judge.main()  # must not raise

    assert judge_calls  # judge_page was called at least once
    assert published
