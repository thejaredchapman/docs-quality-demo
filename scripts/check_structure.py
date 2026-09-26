"""Check that every docs page has the structure its content type requires.

The rules come from content_types.yaml, which scripts/build_rules.py generates
from STYLE_GUIDE.md. These checks are plain rules, with no AI involved, so they
are free, instant, and can block a pull request.

Usage:
    python scripts/check_structure.py                  # every page in docs/
    python scripts/check_structure.py docs/faq.md
"""
import argparse
import re
import sys
from collections import namedtuple
from pathlib import Path

import yaml

from common import CONTENT_TYPES, CONTENT_TYPES_PATH, DOCS_DIR, REPO_ROOT, publish, split_frontmatter

# Every check this script knows how to run, and the parameters each one takes.
# build_rules.py uses this to reject a style-guide rule this script can't run.
STRUCTURE_CHECKS = {
    "type_declared": set(),
    "single_h1": set(),
    "intro_first": set(),
    "numbered_steps": set(),
    "max_steps": {"max_steps"},
    "required_sections": {"sections"},
    "no_numbered_lists": set(),
    "symptom_headings": set(),
    "warnings_only": set(),
}

# `line` is the line number in the file, so GitHub can annotate the right line
Violation = namedtuple("Violation", "page line rule_id message")

HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
NUMBERED_ITEM = re.compile(r"^\d+\.\s")
LIST_ITEM = re.compile(r"^(\d+\.|[-*+])\s")
# A callout is an MkDocs admonition (!!! note) or a bold label in a quote (> **Note:**)
CALLOUT = re.compile(r"^(?:!!!\s+(\w+)|>\s*\*\*(\w+):?\*\*)")


def slugify(text):
    """'Before you start' -> 'before-you-start'"""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def body_lines(body):
    """Return [(body_line_number, line)] for lines outside fenced code blocks."""
    result = []
    in_code = False
    for number, line in enumerate(body.split("\n"), start=1):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            result.append((number, line))
    return result


def load_structure_rules(path=CONTENT_TYPES_PATH):
    """Return the structure rules as a list of {"id", "types", "params"} dicts."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)["rules"]


def check_page(page, text, rules):
    """Return a list of Violations for one page. `page` is the path shown in messages."""
    meta, body, offset = split_frontmatter(text)
    page_type = meta.get("type")

    # Without a known type we can't tell which rules apply, so stop here
    if page_type not in CONTENT_TYPES:
        allowed = ", ".join(CONTENT_TYPES)
        return [Violation(page, 1, "type_declared", f"Add frontmatter `type:` set to one of: {allowed}.")]

    lines = body_lines(body)
    headings = []  # (body_line, level, text)
    for number, line in lines:
        match = HEADING.match(line)
        if match:
            headings.append((number, len(match.group(1)), match.group(2)))
    titles = [number for number, level, _ in headings if level == 1]
    title_line = titles[0] if titles else 1
    steps = [number for number, line in lines if NUMBERED_ITEM.match(line)]

    violations = []

    def flag(body_line, rule_id, message):
        violations.append(Violation(page, body_line + offset, rule_id, message))

    for rule in rules:
        if page_type not in rule["types"]:
            continue
        rule_id = rule["id"]
        params = rule.get("params") or {}

        if rule_id == "single_h1" and len(titles) != 1:
            where = titles[1] if len(titles) > 1 else 1
            flag(where, rule_id, f"Use exactly one `#` title; this page has {len(titles)}.")

        elif rule_id == "intro_first":
            first = next(((n, line) for n, line in lines if n > title_line and line.strip()), None)
            not_a_paragraph = first is None or HEADING.match(first[1]) or LIST_ITEM.match(first[1]) \
                or first[1].lstrip().startswith(("|", "!!!", ">"))
            if not_a_paragraph:
                where = first[0] if first else title_line
                flag(where, rule_id, "Start with an intro paragraph between the title and anything else.")

        elif rule_id == "numbered_steps" and not steps:
            flag(title_line, rule_id, "Write the task as numbered steps.")

        elif rule_id == "max_steps":
            limit = int(params["max_steps"])
            if len(steps) > limit:
                flag(steps[limit], rule_id,
                     f"This page has {len(steps)} steps; the limit is {limit}. Split the task into two pages.")

        elif rule_id == "required_sections":
            present = {slugify(text) for _, level, text in headings if level == 2}
            for slug in params["sections"].split(","):
                if slug not in present:
                    title = slug.replace("-", " ").capitalize()
                    flag(title_line, rule_id, f"Add a `## {title}` section.")

        elif rule_id == "no_numbered_lists" and steps:
            flag(steps[0], rule_id, "Reference pages don't have numbered steps. Move the task to a how-to and link to it.")

        elif rule_id == "symptom_headings" and not any(level == 2 for _, level, _ in headings):
            flag(title_line, rule_id, "Add a `##` heading for each symptom the reader might see.")

        elif rule_id == "warnings_only":
            for number, line in lines:
                match = CALLOUT.match(line)
                kind = match and (match.group(1) or match.group(2))
                if kind and kind.lower() != "warning":
                    flag(number, rule_id, f"Only warnings are allowed as callouts. Move this '{kind}' into the text.")

    return violations


def build_report(violations, page_count):
    lines = ["## Page structure", ""]
    if not violations:
        lines.append(f"All {page_count} pages have the structure their content type requires.")
        return "\n".join(lines)
    lines += [
        f"{len(violations)} problem(s):",
        "",
        "| Page | Line | Rule | Fix |",
        "| --- | --- | --- | --- |",
    ]
    for v in violations:
        lines.append(f"| `{v.page}` | {v.line} | {v.rule_id} | {v.message} |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pages", nargs="*", help="Markdown files to check (default: every page in docs/)")
    args = parser.parse_args()

    paths = [Path(p) for p in args.pages] or sorted(DOCS_DIR.glob("*.md"))
    rules = load_structure_rules()

    violations = []
    for path in paths:
        label = path.resolve().relative_to(REPO_ROOT).as_posix()
        found = check_page(label, path.read_text(encoding="utf-8"), rules)
        for v in found:
            # This special line format makes GitHub show an error on that line of the PR
            print(f"::error file={v.page},line={v.line}::[{v.rule_id}] {v.message}")
        violations += found

    publish(build_report(violations, len(paths)))
    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()
