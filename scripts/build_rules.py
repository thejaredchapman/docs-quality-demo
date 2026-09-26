"""Build the reviewer checklist and the structure rules from STYLE_GUIDE.md.

The style guide is the single source of truth. Each rule in it has a tag
comment on the line above it, like:

    <!-- rule id=prereqs_first check=claude types=how-to,tutorial -->
    **Put prerequisites before the steps.** ...

The `claude` rules become checklist.yaml, and the `structure` rules become
content_types.yaml. The `vale` and `drift` rules are enforced elsewhere, so
this script only validates their tags.

Usage:
    python scripts/build_rules.py          # rewrite the generated files
    python scripts/build_rules.py --check  # fail if they're out of date (used in CI)
"""
import argparse
import re
import sys

import yaml

from check_structure import STRUCTURE_CHECKS
from common import CHECKLIST_PATH, CONTENT_TYPES, CONTENT_TYPES_PATH, GUIDE_PATH

VALID_CHECKS = ("vale", "structure", "claude", "drift")
# A rule with no `types=` applies to every type except the landing page
DEFAULT_TYPES = [t for t in CONTENT_TYPES if t != "landing"]
TAG = re.compile(r"^<!--\s*rule\s+(.*?)\s*-->$")
HEADER = "# Generated from STYLE_GUIDE.md by scripts/build_rules.py. Do not edit by hand.\n"


class RuleError(Exception):
    """The style guide has a rule tag this script can't use."""


def parse_tag(fields_text, line_number):
    """'id=a check=claude' -> {"id": "a", "check": "claude"}"""
    fields = {}
    for token in fields_text.split():
        if "=" not in token:
            raise RuleError(f"Line {line_number}: expected key=value in the rule tag, got '{token}'.")
        key, value = token.split("=", 1)
        fields[key] = value
    return fields


def rule_text(lines, start):
    """Return the first paragraph at or after `start` as one line, with ** removed."""
    index = start
    while index < len(lines) and not lines[index].strip():
        index += 1
    paragraph = []
    while index < len(lines) and lines[index].strip() and not TAG.match(lines[index].strip()):
        paragraph.append(lines[index].strip())
        index += 1
    return " ".join(paragraph).replace("**", "")


def parse_rules(markdown):
    """Return every tagged rule in the guide, in order. Raises RuleError on a bad tag."""
    lines = markdown.split("\n")
    rules = []
    seen = set()
    for index, line in enumerate(lines):
        match = TAG.match(line.strip())
        if not match:
            continue
        number = index + 1
        fields = parse_tag(match.group(1), number)
        rule_id = fields.pop("id", None)
        check = fields.pop("check", None)

        if not rule_id:
            raise RuleError(f"Line {number}: the rule tag has no id.")
        if rule_id in seen:
            raise RuleError(f"Line {number}: duplicate rule id '{rule_id}'.")
        seen.add(rule_id)
        if check not in VALID_CHECKS:
            raise RuleError(
                f"Line {number}: rule '{rule_id}' has check '{check}'; use one of {', '.join(VALID_CHECKS)}."
            )

        types = fields.pop("types").split(",") if "types" in fields else list(DEFAULT_TYPES)
        unknown = [t for t in types if t not in CONTENT_TYPES]
        if unknown:
            raise RuleError(f"Line {number}: rule '{rule_id}' has an unknown type: {', '.join(unknown)}.")

        text = rule_text(lines, index + 1)
        if not text:
            raise RuleError(f"Line {number}: rule '{rule_id}' has no paragraph after its tag.")

        # Whatever is left in `fields` now is a parameter
        if check == "structure":
            if rule_id not in STRUCTURE_CHECKS:
                raise RuleError(f"Line {number}: check_structure.py has no check named '{rule_id}'.")
            expected = STRUCTURE_CHECKS[rule_id]
            if set(fields) != expected:
                raise RuleError(
                    f"Line {number}: structure rule '{rule_id}' needs parameters "
                    f"{sorted(expected)}, got {sorted(fields)}."
                )
        elif fields:
            raise RuleError(
                f"Line {number}: only structure rules take parameters; '{rule_id}' has {', '.join(sorted(fields))}."
            )

        rules.append({"id": rule_id, "check": check, "types": types, "params": fields, "text": text})
    return rules


def dump(data):
    return HEADER + yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000)


def build_outputs(rules):
    """Return {path: file text} for both generated files."""
    checklist = {"items": [
        {"id": r["id"], "rule": r["text"], "types": r["types"]}
        for r in rules if r["check"] == "claude"
    ]}
    structure = {"types": list(CONTENT_TYPES), "rules": [
        {"id": r["id"], "types": r["types"], "params": r["params"]}
        for r in rules if r["check"] == "structure"
    ]}
    return {CHECKLIST_PATH: dump(checklist), CONTENT_TYPES_PATH: dump(structure)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="Fail if the generated files are out of date")
    args = parser.parse_args(argv)

    try:
        rules = parse_rules(GUIDE_PATH.read_text(encoding="utf-8"))
    except RuleError as error:
        print(f"::error file=STYLE_GUIDE.md::{error}")
        return 1

    outputs = build_outputs(rules)
    if args.check:
        stale = [p.name for p, text in outputs.items() if not p.exists() or p.read_text(encoding="utf-8") != text]
        if stale:
            print(f"::error::{', '.join(stale)} don't match STYLE_GUIDE.md. "
                  "Run `python scripts/build_rules.py` and commit the result.")
            return 1
        print("The generated rule files match STYLE_GUIDE.md.")
        return 0

    for path, text in outputs.items():
        path.write_text(text, encoding="utf-8")
        print(f"Wrote {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
