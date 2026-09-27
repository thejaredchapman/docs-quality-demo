"""Label every page in one sitting: write a review sheet, edit it, import it.

The sheet shows each page once, followed by its rules as checkboxes. Every
rule starts checked ("the page follows it"), except answers you already gave
as "breaks it". Read each page, uncheck any rule it breaks, save, and import.
Like label.py, the sheet never shows Claude's answers.

Usage:
    python scripts/review_sheet.py export    # writes eval/review-sheet.md
    python scripts/review_sheet.py import    # reads it back into eval/labels.json
"""
import argparse
import datetime
import json
import re
import sys

from common import DOCS_DIR, REPO_ROOT, read_page
from label import LABELS_PATH, git_user_name
from rules import applicable_pairs, load_checklist, rules_hash

SHEET_PATH = REPO_ROOT / "eval" / "review-sheet.md"
PAGE_HEADING = re.compile(r"^## (\S+\.md)$")
CHECKBOX = re.compile(r"^- \[([ xX])\] \*\*(\w+)\*\*")
HASH_LINE = re.compile(r"^<!-- rules_hash: (\S+) -->$")
# The page text sits inside this fence, so checkbox-looking lines in a page never count as answers
FENCE = "~~~~"

HEADER = """# Labeling review sheet

Read each page, then look at its rules. A checked box means the page follows
the rule. **Uncheck any rule the page breaks.** Every rule starts checked, so
the only edits you make are the problems you find.

When you're done, save and run `python scripts/review_sheet.py import`.
"""


class SheetError(Exception):
    """The review sheet is missing a question, or has one that doesn't exist."""


def build_sheet(pairs, labels, rule_text, read_body, current_hash):
    """Return the sheet as markdown. read_body(page) returns the page text without frontmatter."""
    lines = [HEADER, f"<!-- rules_hash: {current_hash} -->", ""]
    rules_by_page = {}
    for page, rule_id in pairs:
        rules_by_page.setdefault(page, []).append(rule_id)
    for page in sorted(rules_by_page):
        lines += [f"## {page}", "", FENCE, read_body(page).strip(), FENCE, ""]
        for rule_id in rules_by_page[page]:
            follows = labels.get(page, {}).get(rule_id, True)
            box = "x" if follows else " "
            lines.append(f"- [{box}] **{rule_id}**: {rule_text[rule_id]}")
        lines.append("")
    return "\n".join(lines)


def parse_sheet(text, pairs):
    """Return (labels, rules_hash) from an edited sheet. Raises SheetError if questions don't match."""
    labels = {}
    found = []
    sheet_hash = None
    page = None
    in_page_text = False
    for line in text.split("\n"):
        if line.strip() == FENCE:
            in_page_text = not in_page_text
            continue
        if in_page_text:
            continue
        hash_match = HASH_LINE.match(line.strip())
        if hash_match:
            sheet_hash = hash_match.group(1)
            continue
        heading = PAGE_HEADING.match(line.strip())
        if heading:
            page = heading.group(1)
            continue
        box = CHECKBOX.match(line.strip())
        if box and page:
            rule_id = box.group(2)
            found.append((page, rule_id))
            labels.setdefault(page, {})[rule_id] = box.group(1).lower() == "x"

    expected = set(pairs)
    missing = sorted(expected - set(found))
    extra = sorted(set(found) - expected)
    if missing:
        raise SheetError("The sheet is missing: " + ", ".join(f"{p} / {r}" for p, r in missing))
    if extra:
        raise SheetError("The sheet has questions that don't exist: " + ", ".join(f"{p} / {r}" for p, r in extra))
    return labels, sheet_hash


def load_existing_labels():
    if not LABELS_PATH.exists():
        return {}
    return json.loads(LABELS_PATH.read_text(encoding="utf-8"))["labels"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["export", "import"])
    parser.add_argument("--labeler", help="Your name (default: git config user.name)")
    args = parser.parse_args(argv)

    checklist = load_checklist()
    pairs = applicable_pairs(checklist)
    current_hash = rules_hash()

    if args.command == "export":
        rule_text = {item["id"]: item["rule"] for item in checklist}
        text = build_sheet(pairs, load_existing_labels(), rule_text,
                           lambda page: read_page(DOCS_DIR / page)[1], current_hash)
        SHEET_PATH.write_text(text, encoding="utf-8")
        print(f"Wrote {SHEET_PATH.relative_to(REPO_ROOT)}: {len(pairs)} questions. "
              "Uncheck the rules each page breaks, then run the import.")
        return 0

    try:
        labels, sheet_hash = parse_sheet(SHEET_PATH.read_text(encoding="utf-8"), pairs)
    except SheetError as error:
        print(f"Not imported. {error}")
        return 1
    if sheet_hash != current_hash:
        print("Not imported. The rules changed since this sheet was written. Run the export again.")
        return 1
    meta = {
        "labeler": args.labeler or git_user_name(),
        "date": datetime.date.today().isoformat(),
        "rules_hash": current_hash,
        # Recorded so anyone reading the numbers knows how the labels were made
        "method": "review sheet: every rule started as 'follows'; the labeler unchecked the ones a page breaks",
    }
    LABELS_PATH.write_text(json.dumps({"meta": meta, "labels": labels}, indent=2) + "\n", encoding="utf-8")
    breaks = sum(1 for items in labels.values() for follows in items.values() if not follows)
    print(f"Imported {len(pairs)} labels into {LABELS_PATH.relative_to(REPO_ROOT)}: "
          f"{len(pairs) - breaks} follow the rule, {breaks} break it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
