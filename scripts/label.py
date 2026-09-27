"""Label docs pages by hand, one page at a time, without seeing any other answers.

Your labels are the answer key the Claude reviewer is measured against, so
this tool never shows Claude's verdicts or any earlier labels. It saves after
every answer; run it again to pick up where you left off.

Usage:
    python scripts/label.py
    python scripts/label.py --labeler "Jared Chapman"
    python scripts/label.py --restart      # start over after the rules changed
"""
import argparse
import datetime
import json
import random
import subprocess
import sys

from common import DOCS_DIR, REPO_ROOT, read_page
from rules import applicable_pairs, load_checklist, rules_hash

LABELS_PATH = REPO_ROOT / "eval" / "labels.json"
ANSWERS = {"y": True, "n": False}
VALID_ANSWERS = ("y", "n", "s", "q")
PROMPT = "Does the page follow this rule? [y] yes, it follows it / [n] no, it breaks it / [s] skip / [q] quit: "


def pending(pairs, labels):
    """The pairs that don't have a label yet."""
    return [(page, rule_id) for page, rule_id in pairs if rule_id not in labels.get(page, {})]


def order_by_page(todo, seed=None):
    """Group the pairs by page, in a random page order, with each page's rules shuffled.

    Each page is shown once, and all its rules are asked in a row, so the
    labeler reads a page once instead of meeting it again later in the list.
    """
    rng = random.Random(seed)
    rules_by_page = {}
    for page, rule_id in todo:
        rules_by_page.setdefault(page, []).append(rule_id)
    pages = sorted(rules_by_page)
    rng.shuffle(pages)
    ordered = []
    for page in pages:
        rule_ids = rules_by_page[page]
        rng.shuffle(rule_ids)
        ordered += [(page, rule_id) for rule_id in rule_ids]
    return ordered


def label_loop(pairs, labels, show, ask, save, seed=None):
    """Ask about every unlabeled pair, one page at a time, and return the labels.

    show(page, rule_id, done, total, rule_number, rule_count) displays one question;
    rule_number counts from 1 within the current page, so show() can print the
    page text only once.
    ask() returns "y", "n", "s" (skip) or "q" (quit); anything else is asked again.
    save(labels) is called after every answer, so quitting or crashing loses nothing.
    """
    todo = order_by_page(pending(pairs, labels), seed)
    rule_count = {}
    for page, _ in todo:
        rule_count[page] = rule_count.get(page, 0) + 1
    total = len(pairs)
    rule_number = {}
    for page, rule_id in todo:
        rule_number[page] = rule_number.get(page, 0) + 1
        show(page, rule_id, total - len(pending(pairs, labels)), total, rule_number[page], rule_count[page])
        answer = ask()
        while answer not in VALID_ANSWERS:
            answer = ask()
        if answer == "q":
            break
        if answer == "s":
            continue
        labels.setdefault(page, {})[rule_id] = ANSWERS[answer]
        save(labels)
    return labels


def read_answer(prompt_fn=input):
    """Read an answer from the user, catching EOFError (stdin closed).

    Returns the first lowercase character of the response, or "q" if stdin closes.
    """
    try:
        response = prompt_fn(PROMPT)
        return response.strip().lower()[:1]
    except EOFError:
        print()  # Print newline so summary starts on its own line
        return "q"


def git_user_name():
    result = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True, cwd=REPO_ROOT)
    return result.stdout.strip() or "unknown"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--labeler", help="Your name (default: git config user.name)")
    parser.add_argument("--restart", action="store_true", help="Discard labels made against older rules")
    args = parser.parse_args()

    checklist = load_checklist()
    rule_text = {item["id"]: item["rule"] for item in checklist}
    pairs = applicable_pairs(checklist)
    current_hash = rules_hash()

    labels = {}
    if LABELS_PATH.exists():
        data = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
        if data["meta"].get("rules_hash") == current_hash:
            labels = data["labels"]
        elif not args.restart:
            print("The rules changed since these labels were made. Run with --restart to start over.")
            return 1

    meta = {
        "labeler": args.labeler or git_user_name(),
        "date": datetime.date.today().isoformat(),
        "rules_hash": current_hash,
    }

    def save(current):
        LABELS_PATH.parent.mkdir(exist_ok=True)
        LABELS_PATH.write_text(json.dumps({"meta": meta, "labels": current}, indent=2) + "\n", encoding="utf-8")

    def show(page, rule_id, done, total, rule_number, rule_count):
        if rule_number == 1:
            _, body, _ = read_page(DOCS_DIR / page)
            print("\n" + "=" * 72)
            print(f"{page}\n")
            print(body.strip())
        print("\n" + "-" * 72)
        print(f"[{done + 1}/{total}]  {page}: rule {rule_number} of {rule_count} for this page")
        print(f"Rule: {rule_text[rule_id]}")

    def ask():
        answer = read_answer()
        while answer not in VALID_ANSWERS:
            print("Type y, n, s, or q, then press Enter.")
            answer = read_answer()
        return answer

    label_loop(pairs, labels, show, ask, save)
    done = len(pairs) - len(pending(pairs, labels))
    where = f" Saved in {LABELS_PATH.relative_to(REPO_ROOT)}." if LABELS_PATH.exists() else " Nothing saved yet."
    print(f"\n{done}/{len(pairs)} labeled.{where}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
