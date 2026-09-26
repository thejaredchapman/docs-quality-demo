"""Review docs pages with Claude and publish a pass/fail report.

Each page is graded only against the checklist rules for its content type.

Usage:
    python scripts/review_pages.py docs/dark-mode.md docs/faq.md
    python scripts/review_pages.py --all
"""
import argparse
from pathlib import Path

from common import DOCS_DIR, publish, read_page
from judge import DEFAULT_MODEL, judge_page
from rules import load_checklist, rules_for_type

ICONS = {True: "✅", False: "❌", None: "❔"}


def review(paths, checklist, model, judge=judge_page):
    """Return {page_name: verdicts}. A page with no applicable rules gets {} and no API call."""
    page_verdicts = {}
    for path in paths:
        meta, body, _ = read_page(path)
        rules = rules_for_type(checklist, meta.get("type"))
        # Send the body only: the frontmatter is for our tools, not for the reviewer
        page_verdicts[Path(path).name] = judge(body, rules, model=model) if rules else {}
    return page_verdicts


def build_report(page_verdicts):
    """page_verdicts: {page_name: {item_id: {"passed": ..., "reason": ...}}} -> markdown text."""
    lines = ["## Claude style review", ""]
    if not page_verdicts:
        lines.append("No docs pages changed in this PR.")
        return "\n".join(lines)

    for page, verdicts in page_verdicts.items():
        if not verdicts:
            lines += [f"### `{page}`", "No review rules apply to this page type.", ""]
            continue
        if all(v["passed"] is None for v in verdicts.values()):
            # Every answer is unknown, which means the API call itself failed
            reason = next(iter(verdicts.values()))["reason"]
            lines += [f"### `{page}`: review unavailable", reason, ""]
            continue
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
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pages", nargs="*", help="Markdown files to review")
    parser.add_argument("--all", action="store_true", help="Review every page in docs/")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    paths = sorted(DOCS_DIR.glob("*.md")) if args.all else [Path(p) for p in args.pages]
    publish(build_report(review(paths, load_checklist(), args.model)))
    # Advisory only: this check reports problems but never blocks the PR


if __name__ == "__main__":
    main()
