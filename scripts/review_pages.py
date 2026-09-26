"""Review docs pages with Claude and publish a pass/fail report.

Usage:
    python scripts/review_pages.py docs/dark-mode.md docs/faq.md
    python scripts/review_pages.py --all
"""
import argparse
from pathlib import Path

from common import DOCS_DIR, publish
from judge import DEFAULT_MODEL, judge_page, load_checklist

ICONS = {True: "✅", False: "❌", None: "❔"}


def build_report(page_verdicts):
    """page_verdicts: {page_name: {item_id: {"passed": ..., "reason": ...}}} -> markdown text."""
    lines = ["## Claude style review", ""]
    if not page_verdicts:
        lines.append("No docs pages changed in this PR.")
        return "\n".join(lines)

    for page, verdicts in page_verdicts.items():
        passed_count = sum(1 for v in verdicts.values() if v["passed"] is True)
        lines.append(f"### `{page}`: {passed_count}/{len(verdicts)} checks passed")
        # Only list the items that need attention, to keep the report short
        problems = {item_id: v for item_id, v in verdicts.items() if v["passed"] is not True}
        if not problems:
            lines.append("All checks passed.")
        for item_id, v in problems.items():
            lines.append(f"- {ICONS[v['passed']]} **{item_id}**: {v['reason']}")
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pages", nargs="*", help="Markdown files to review")
    parser.add_argument("--all", action="store_true", help="Review every page in docs/")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    paths = sorted(DOCS_DIR.glob("*.md")) if args.all else [Path(p) for p in args.pages]
    checklist = load_checklist()

    page_verdicts = {}
    for path in paths:
        page_verdicts[path.name] = judge_page(path.read_text(encoding="utf-8"), checklist, model=args.model)

    publish(build_report(page_verdicts))
    # Advisory only: this check reports problems but never blocks the PR


if __name__ == "__main__":
    main()
