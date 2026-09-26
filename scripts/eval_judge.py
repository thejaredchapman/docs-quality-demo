"""Measure how often the Claude judge agrees with the hand labels in eval/labels.json.

Only (page, rule) pairs that apply to the page's content type are graded.
Make the labels first with `python scripts/label.py`.

Usage:
    python scripts/eval_judge.py
    python scripts/eval_judge.py --model claude-haiku-4-5-20251001 --model claude-sonnet-5
"""
import argparse
import json
import sys

from common import DOCS_DIR, REPO_ROOT, publish, read_page
from judge import DEFAULT_MODEL, judge_page
from rules import applicable_pairs, load_checklist, rules_for_type, rules_hash

LABELS_PATH = REPO_ROOT / "eval" / "labels.json"


def load_labels(path=LABELS_PATH):
    """Return (meta, labels), or (None, None) if nobody has labeled yet.

    labels: {page: {item_id: True/False}}  (True = the page follows the rule)
    """
    if not path.exists():
        return None, None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["meta"], data["labels"]


def keep_applicable(labels, pairs):
    """Drop labeled pairs that no longer apply, for example after a page changed type."""
    allowed = set(pairs)
    kept = {}
    for page, items in labels.items():
        page_items = {item_id: v for item_id, v in items.items() if (page, item_id) in allowed}
        if page_items:
            kept[page] = page_items
    return kept


def new_counts():
    return {"total": 0, "agreed": 0, "misses": 0, "false_alarms": 0, "unknown": 0}


def compute_metrics(labels, predictions):
    """Compare the judge to the hand labels.

    labels:      {page: {item_id: True/False}}       (True = page follows the rule)
    predictions: {page: {item_id: True/False/None}}  (None = judge gave no answer)

    Returns (overall_counts, {item_id: counts}).
    - miss:        the page broke the rule, but the judge said it passed
    - false alarm: the page followed the rule, but the judge said it failed
    Unknown answers count against agreement, so the score is never inflated.
    """
    overall = new_counts()
    per_item = {}
    for page, item_labels in labels.items():
        for item_id, expected in item_labels.items():
            got = predictions.get(page, {}).get(item_id)
            item_counts = per_item.setdefault(item_id, new_counts())
            for counts in (overall, item_counts):
                counts["total"] += 1
                if got is None:
                    counts["unknown"] += 1
                elif got == expected:
                    counts["agreed"] += 1
                elif expected is False:
                    counts["misses"] += 1
                else:
                    counts["false_alarms"] += 1
    return overall, per_item


def agreement_stats(labels, predictions):
    """Return (always-pass baseline, Cohen's kappa). Either is None when it can't be computed.

    Most pages follow most rules, so a "judge" that always says pass already
    scores well on raw agreement. The baseline shows that score, and kappa
    measures agreement beyond what chance and that imbalance would give.
    Unknown answers are scored as the wrong answer, the same as in compute_metrics.
    """
    pairs = [
        (expected, predictions.get(page, {}).get(item_id))
        for page, items in labels.items()
        for item_id, expected in items.items()
    ]
    n = len(pairs)
    if n == 0:
        return None, None
    scored = [(expected, (not expected) if got is None else got) for expected, got in pairs]
    observed = sum(1 for expected, got in scored if expected == got) / n
    label_pass = sum(1 for expected, _ in scored if expected) / n
    judge_pass = sum(1 for _, got in scored if got) / n
    chance = label_pass * judge_pass + (1 - label_pass) * (1 - judge_pass)
    kappa = None if chance == 1 else (observed - chance) / (1 - chance)
    return label_pass, kappa


def percent(part, whole):
    return f"{100 * part / whole:.0f}%" if whole else "n/a"


def build_report(model, labels, verdicts, meta=None):
    """verdicts: {page: {item_id: {"passed": ..., "reason": ...}}} from the judge."""
    predictions = {page: {i: v["passed"] for i, v in items.items()} for page, items in verdicts.items()}
    overall, per_item = compute_metrics(labels, predictions)
    baseline, kappa = agreement_stats(labels, predictions)

    baseline_text = "n/a" if baseline is None else f"{100 * baseline:.0f}%"
    kappa_text = "n/a" if kappa is None else f"{kappa:.2f}"

    lines = [f"## Judge accuracy: `{model}`", ""]
    if meta:
        lines += [f"Labels by {meta.get('labeler', 'unknown')} on {meta.get('date', 'unknown date')}.", ""]
    lines += [
        f"**Agreement with hand labels: {percent(overall['agreed'], overall['total'])}** "
        f"({overall['agreed']}/{overall['total']} judgments, {len(labels)} pages)",
        "",
        f"Always-pass baseline: {baseline_text} · Cohen's κ: {kappa_text}",
        "",
        "| Checklist item | Agreement | Misses | False alarms | Unknown |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item_id, c in per_item.items():
        lines.append(
            f"| {item_id} | {percent(c['agreed'], c['total'])} | {c['misses']} "
            f"| {c['false_alarms']} | {c['unknown']} |"
        )

    # List every disagreement so you can read Claude's reasoning and decide who was right
    lines += ["", "### Disagreements", ""]
    disagreements = 0
    for page, item_labels in labels.items():
        for item_id, expected in item_labels.items():
            verdict = verdicts.get(page, {}).get(item_id, {"passed": None, "reason": "Not judged."})
            if verdict["passed"] != expected:
                disagreements += 1
                label = "pass" if expected else "fail"
                lines.append(f"- `{page}` / **{item_id}**: label says {label}. Judge: {verdict['reason']}")
    if disagreements == 0:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", action="append", help="Model to evaluate (repeat to compare models)")
    parser.add_argument("--allow-stale", action="store_true", help="Run even if the rules changed since labeling")
    args = parser.parse_args()
    models = args.model or [DEFAULT_MODEL]

    meta, labels = load_labels()
    if labels is None:
        print("No labels yet. Run `python scripts/label.py` first.")
        sys.exit(1)
    if meta.get("rules_hash") != rules_hash() and not args.allow_stale:
        print("::error::The rules changed since these labels were made. "
              "Relabel with `python scripts/label.py --restart`, or pass --allow-stale.")
        sys.exit(1)

    checklist = load_checklist()
    labels = keep_applicable(labels, applicable_pairs(checklist))

    for model in models:
        verdicts = {}
        for page in labels:
            page_meta, body, _ = read_page(DOCS_DIR / page)
            verdicts[page] = judge_page(body, rules_for_type(checklist, page_meta.get("type")), model=model)
        publish(build_report(model, labels, verdicts, meta))


if __name__ == "__main__":
    main()
