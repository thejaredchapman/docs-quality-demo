"""Flag docs pages that still mention UI text that this change renamed or removed.

Compares app/ui_strings.json on the base branch with the current version,
then searches the docs for every old string that changed.

Usage:
    python scripts/ui_drift.py --base-ref origin/main
"""
import argparse
import json
import re
import subprocess
import sys

from common import DOCS_DIR, REPO_ROOT, publish

STRINGS_PATH = "app/ui_strings.json"


def load_strings_at_ref(ref, path=STRINGS_PATH):
    """Read the strings file as it was on another branch or commit."""
    # `git show main:app/ui_strings.json` prints the file as it is on main
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        capture_output=True, text=True, check=True, cwd=REPO_ROOT,
    )
    return json.loads(result.stdout)


def find_changed_strings(old_strings, new_strings):
    """Return [(key, old_text, new_text)] for strings that changed or were removed.

    new_text is None when the string was removed. New keys are ignored,
    since the docs can't mention text that didn't exist before.
    """
    changed = []
    for key, old_text in old_strings.items():
        new_text = new_strings.get(key)  # None if the key was deleted
        if new_text != old_text:
            changed.append((key, old_text, new_text))
    return changed


def find_mentions(text, docs_dir=DOCS_DIR):
    """Return [(page_path, line_number, line)] for every line that mentions `text`.

    Matching is exact and case-sensitive, and only matches whole phrases,
    so "Settings" doesn't match "settings" or "Settingsmenu".
    """
    # (?<!\w) and (?!\w) mean "no letter or digit right before/after the phrase"
    pattern = re.compile(rf"(?<!\w){re.escape(text)}(?!\w)")
    mentions = []
    for page in sorted(docs_dir.rglob("*.md")):
        lines = page.read_text(encoding="utf-8").splitlines()
        for line_number, line in enumerate(lines, start=1):
            if pattern.search(line):
                relative_path = page.relative_to(docs_dir.parent).as_posix()
                mentions.append((relative_path, line_number, line.strip()))
    return mentions


def build_report(flags):
    """flags: [(page, line_number, old_text, new_text)] -> markdown text."""
    lines = ["## UI text drift", ""]
    if not flags:
        lines.append("No docs pages mention UI text that this change altered.")
        return "\n".join(lines)
    lines += [
        f"{len(flags)} line(s) mention UI text that this change renamed or removed:",
        "",
        "| Page | Line | Old text | New text |",
        "| --- | --- | --- | --- |",
    ]
    for page, line_number, old_text, new_text in flags:
        new_display = f"`{new_text}`" if new_text is not None else "_(removed)_"
        lines.append(f"| `{page}` | {line_number} | `{old_text}` | {new_display} |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", default="origin/main", help="Branch or commit to compare against")
    args = parser.parse_args()

    try:
        old_strings = load_strings_at_ref(args.base_ref)
    except subprocess.CalledProcessError:
        publish(f"## UI text drift\n\n`{STRINGS_PATH}` doesn't exist on `{args.base_ref}`, so there's nothing to compare.")
        return
    with open(REPO_ROOT / STRINGS_PATH, encoding="utf-8") as f:
        new_strings = json.load(f)

    flags = []
    for _key, old_text, new_text in find_changed_strings(old_strings, new_strings):
        for page, line_number, _line in find_mentions(old_text):
            flags.append((page, line_number, old_text, new_text))
            # This special line format makes GitHub show a warning on that line of the PR
            change = f'"{new_text}"' if new_text is not None else "nothing (removed)"
            print(f'::warning file={page},line={line_number}::Mentions "{old_text}", which this change renames to {change}.')

    publish(build_report(flags))
    # Fail the check when docs are out of date, so the PR shows a red X
    sys.exit(1 if flags else 0)


if __name__ == "__main__":
    main()
