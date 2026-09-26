"""Measure how often the Claude judge agrees with the hand labels in eval/labels.json.

Usage:
    python scripts/eval_judge.py
    python scripts/eval_judge.py --model claude-haiku-4-5-20251001 --model claude-sonnet-5
"""
import argparse
import json

from common import DOCS_DIR, REPO_ROOT, publish
from judge import DEFAULT_MODEL, judge_page, load_checklist

LABELS_PATH = REPO_ROOT / "eval" / "labels.json"


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


def percent(part, whole):
    return f"{100 * part / whole:.0f}%" if whole else "n/a"


def build_report(model, labels, verdicts):
    """verdicts: {page: {item_id: {"passed": ..., "reason": ...}}} from the judge."""
    predictions = {page: {i: v["passed"] for i, v in items.items()} for page, items in verdicts.items()}
    overall, per_item = compute_metrics(labels, predictions)

    lines = [
        f"## Judge accuracy: `{model}`",
        "",
        f"**Agreement with hand labels: {percent(overall['agreed'], overall['total'])}** "
        f"({overall['agreed']}/{overall['total']} judgments, {len(labels)} pages)",
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="append", help="Model to evaluate (repeat to compare models)")
    args = parser.parse_args()
    models = args.model or [DEFAULT_MODEL]

    with open(LABELS_PATH, encoding="utf-8") as f:
        labels = json.load(f)
    checklist = load_checklist()

    for model in models:
        verdicts = {}
        for page in labels:
            page_text = (DOCS_DIR / page).read_text(encoding="utf-8")
            verdicts[page] = judge_page(page_text, checklist, model=model)
        publish(build_report(model, labels, verdicts))


if __name__ == "__main__":
    main()
