# Style Guide, Content Types, and Measured Reviewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `STYLE_GUIDE.md` the single source of truth for the Tally docs, enforce content types with a rule-based check, scope the Claude reviewer to each page's type, add a blind labeling tool, report honest accuracy stats, and publish the docs as an MkDocs site.

**Architecture:** `scripts/build_rules.py` parses tagged rules out of `STYLE_GUIDE.md` and generates `checklist.yaml` (Claude rules) and `content_types.yaml` (structure rules). `scripts/check_structure.py` enforces structure rules per page type, and the page type comes from each page's YAML frontmatter. The Claude reviewer, the eval, and the labeling tool all use `scripts/rules.py` to decide which rules apply to which page. MkDocs publishes `docs/` plus the style guide through a small hook.

**Tech Stack:** Python 3.9+ (local venv is 3.9.6, CI uses 3.12), PyYAML, Anthropic SDK, pytest, MkDocs 1.6, Vale (CI only), GitHub Actions.

**Spec:** `design/specs/2026-09-25-style-guide-content-types-design.md`

## Global Constraints

- Python 3.9 compatible: no `match`, no `X | Y` type unions, no `list[str]`-style annotations at runtime. Match the existing style: plain functions, short docstrings, and comments that explain *why* for a newcomer.
- The only new dependency is `mkdocs>=1.6,<2`.
- Content types are exactly: `tutorial`, `how-to`, `reference`, `troubleshooting`, `landing`. `landing` is only for `docs/index.md` and is exempt from all rules except `type_declared` and `single_h1`.
- The five Claude rule ids and their wording stay unchanged: `intro_audience`, `prereqs_first`, `one_action_per_step`, `no_undefined_jargon`, `outcome_stated`.
- How-to step limit: 7.
- The UI action verb is "select". Never write "tap" or "click" in `docs/` (the gesture "press and hold" is allowed).
- All content is about the fictional Tally app. No AbbVie material.
- **Never run `git push`.** Nothing leaves this machine without Jared's explicit go-ahead.
- Every commit message ends with a blank line and then `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Tests never need an API key. Claude is faked.
- Run tests with `venv/bin/pytest` from the repo root (`~/coding_stuff/docs-quality-demo`).

## File Structure

| File | Responsibility |
|---|---|
| `scripts/common.py` (modify) | Paths, `CONTENT_TYPES`, frontmatter parsing (`split_frontmatter`, `read_page`) |
| `scripts/check_structure.py` (new) | Rule-based structure checks per content type; `STRUCTURE_CHECKS` registry |
| `scripts/build_rules.py` (new) | Parse `STYLE_GUIDE.md` tags → generate `checklist.yaml` + `content_types.yaml`; `--check` for CI |
| `scripts/rules.py` (new) | Load checklist, `rules_for_type`, `applicable_pairs`, `rules_hash` |
| `scripts/judge.py` (modify) | Import `load_checklist` from `rules.py`; adjust the system prompt |
| `scripts/review_pages.py` (modify) | Scope the review by page type; landing pages and "review unavailable" in the report |
| `scripts/eval_judge.py` (modify) | New labels format, applicable pairs only, baseline + Cohen's κ, stale-labels guard |
| `scripts/label.py` (new) | Blind, resumable labeling CLI |
| `scripts/site_hooks.py` (new) | MkDocs hook: publish the style guide, render "Checked by" labels |
| `STYLE_GUIDE.md` (new) | The guide, with tagged rules |
| `templates/*.md` (new) | One skeleton page per content type |
| `checklist.yaml`, `content_types.yaml` | Generated. Never edit by hand |
| `docs/*.md` (modify) | Frontmatter `type:`, "select", intros, section fixes |
| `mkdocs.yml`, `docs/stylesheets/extra.css` (new) | Site config and label styling |
| `styles/DemoDocs/{Latin,Click,LinkText}.yml` (new) | Vale rules |
| `.github/workflows/docs-pr.yml` (modify), `deploy-site.yml` (new) | CI |
| `eval/labels.json` → `eval/labels.previous.json` | Old labels retired |
| `README.md` (modify) | Enforcement table, accuracy columns, demo PR 4, provenance |

---

### Task 1: Page frontmatter and content types on every page

**Files:**
- Modify: `scripts/common.py`
- Modify: all 15 files in `docs/`
- Create: `tests/test_common.py`, `tests/test_docs_pages.py`

**Interfaces:**
- Produces (in `common.py`):
  - `CONTENT_TYPES = ("tutorial", "how-to", "reference", "troubleshooting", "landing")`
  - `CHECKLIST_PATH = REPO_ROOT / "checklist.yaml"`, `CONTENT_TYPES_PATH = REPO_ROOT / "content_types.yaml"`, `GUIDE_PATH = REPO_ROOT / "STYLE_GUIDE.md"`
  - `split_frontmatter(text) -> (meta: dict, body: str, offset: int)`. `offset` is the number of file lines before the body, so body line `n` is file line `n + offset`.
  - `read_page(path) -> (meta, body, offset)`

- [ ] **Step 1: Write the failing tests**

`tests/test_common.py`:
```python
from common import split_frontmatter


def test_reads_type_and_body():
    meta, body, offset = split_frontmatter("---\ntype: how-to\n---\n# Title\n")
    assert meta == {"type": "how-to"}
    assert body == "# Title\n"
    assert offset == 3


def test_page_without_frontmatter():
    assert split_frontmatter("# Title\n") == ({}, "# Title\n", 0)


def test_broken_yaml_gives_empty_meta():
    meta, body, _ = split_frontmatter("---\ntype: [oops\n---\n# T\n")
    assert meta == {}
    assert body == "# T\n"


def test_unclosed_frontmatter_is_treated_as_body():
    text = "---\ntype: how-to\n# T\n"
    assert split_frontmatter(text) == ({}, text, 0)
```

`tests/test_docs_pages.py`:
```python
import re

from common import CONTENT_TYPES, DOCS_DIR, read_page

# Every page not listed here is a how-to
EXPECTED_TYPES = {
    "index.md": "landing",
    "getting-started.md": "tutorial",
    "keyboard-shortcuts.md": "reference",
    "faq.md": "reference",
    "troubleshooting-sync.md": "troubleshooting",
}


def test_every_page_declares_the_expected_type():
    pages = sorted(DOCS_DIR.glob("*.md"))
    assert len(pages) == 15
    for path in pages:
        meta, _, _ = read_page(path)
        assert meta.get("type") == EXPECTED_TYPES.get(path.name, "how-to"), path.name
        assert meta["type"] in CONTENT_TYPES


def test_docs_say_select_not_tap_or_click():
    word = re.compile(r"\b(tap|taps|tapping|click|clicks|clicking)\b", re.IGNORECASE)
    for path in DOCS_DIR.glob("*.md"):
        assert not word.search(path.read_text(encoding="utf-8")), path.name
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `venv/bin/pytest tests/test_common.py tests/test_docs_pages.py -v`
Expected: FAIL with `ImportError: cannot import name 'split_frontmatter'`

- [ ] **Step 3: Add the frontmatter helpers to `scripts/common.py`**

Replace the whole file with:
```python
"""Small helpers shared by the scripts."""
import os
from pathlib import Path

import yaml

# The repo's top folder, no matter where the script is run from
REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
GUIDE_PATH = REPO_ROOT / "STYLE_GUIDE.md"
# Both generated from STYLE_GUIDE.md by scripts/build_rules.py
CHECKLIST_PATH = REPO_ROOT / "checklist.yaml"
CONTENT_TYPES_PATH = REPO_ROOT / "content_types.yaml"

# Every page declares one of these in its frontmatter, for example `type: how-to`
CONTENT_TYPES = ("tutorial", "how-to", "reference", "troubleshooting", "landing")


def publish(markdown):
    """Print a report, and also add it to the GitHub Actions job summary when running in CI."""
    print(markdown)
    # GitHub sets this variable to a file path; anything written there shows on the run's summary page
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(markdown + "\n")


def split_frontmatter(text):
    """Split a page into (frontmatter dict, body text, number of file lines before the body).

    Frontmatter is a YAML block between two `---` lines at the very top of the page.
    A page with no frontmatter, or with broken YAML, gets an empty dict, so the
    structure check can report "no type" instead of crashing.
    """
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                try:
                    meta = yaml.safe_load("\n".join(lines[1:index])) or {}
                except yaml.YAMLError:
                    meta = {}
                if not isinstance(meta, dict):
                    meta = {}
                return meta, "\n".join(lines[index + 1:]), index + 1
    return {}, text, 0


def read_page(path):
    """Read a docs page and split off its frontmatter. See split_frontmatter."""
    return split_frontmatter(Path(path).read_text(encoding="utf-8"))
```

- [ ] **Step 4: Replace "tap" with "select" and add frontmatter to every page**

Run from the repo root:
```bash
venv/bin/python - <<'EOF'
import re
from pathlib import Path

TYPES = {
    "index.md": "landing",
    "getting-started.md": "tutorial",
    "keyboard-shortcuts.md": "reference",
    "faq.md": "reference",
    "troubleshooting-sync.md": "troubleshooting",
}
for path in sorted(Path("docs").glob("*.md")):
    text = path.read_text(encoding="utf-8")
    text = text.replace("tap and hold", "press and hold")
    text = re.sub(r"\bTap\b", "Select", text)
    text = re.sub(r"\btap\b", "select", text)
    page_type = TYPES.get(path.name, "how-to")
    path.write_text(f"---\ntype: {page_type}\n---\n{text}", encoding="utf-8")
    print(path.name, page_type)
EOF
```
Expected: 15 lines printed, one per page.

- [ ] **Step 5: Rewrite the 7 pages whose structure changes**

These edits keep every planted problem (noted in parentheses) but make each page follow the new structure rules. Overwrite each file with exactly this content.

`docs/change-password.md` (adds an intro that doesn't say who the page is for, so the `intro_audience` failure stays):
```markdown
---
type: how-to
---
# Change your password

Your Tally password is separate from the password for your email account.

1. Open **Settings**.
2. Select **Account**.
3. Select **Change password**.
4. Enter your current password.
5. Enter a new password.
6. Select **Save changes**.

You're signed out on your other devices and need to sign in again with the new password.
```

`docs/dark-mode.md` (same planted `intro_audience` failure):
```markdown
---
type: how-to
---
# Turn on dark mode

Dark mode shows light text on a dark background.

1. Open **Settings**.
2. Select **Appearance**.
3. Turn on **Dark mode**.

The app switches to a dark color theme right away. To switch back, turn off **Dark mode**.
```

`docs/edit-a-habit.md` (keeps the `intro_audience` failure and the multi-action step 1):
```markdown
---
type: how-to
---
# Edit a habit

A habit's name and schedule can be changed at any time.

1. On the **Today** screen, press and hold the habit, then select **Edit** and change the name or schedule.
2. Select **Save changes**.

Your changes apply starting today. Past check-ins keep their original schedule.
```

`docs/getting-started.md` ("Before you begin" becomes "Before you start", and a "Next steps" section is added):
```markdown
---
type: tutorial
---
# Get started with Tally

This guide is for new Tally users. By the end, you'll have your first habit set up and checked off for today.

## Before you start

- Install Tally from the App Store or Google Play.
- Create a Tally account with your email address.

## Create your first habit

1. Open Tally.
2. Select **New habit**.
3. Enter a name for the habit, such as "Drink water."
4. Select **Save changes**.

## Check it off

1. On the **Today** screen, select the circle next to your habit.

The circle fills in, and your streak counter shows **1 day**. You're all set.

## Next steps

- [Set up daily reminders](reminders.md) so you don't forget to check in.
- [Protect a streak with a streak freeze](streak-freeze.md) before you take a day off.
```

`docs/delete-account.md` (the one real warning callout on the site; "our servers" becomes "its servers" to match the voice rule):
```markdown
---
type: how-to
---
# Delete your account

This page is for people who want to permanently delete their Tally account and all of its data.

## Before you start

!!! warning
    Deleting your account can't be undone. If you want to keep your history, [export your data](export-data.md) first.

## Steps

1. Open **Settings**.
2. Select **Delete account**.
3. Enter your password.
4. Select **Delete account** again to confirm.

Tally signs you out and sends a confirmation email. Tally removes your data from its servers within 30 days.
```

`docs/reminders.md` (the banned Note callout becomes a plain paragraph; "Please" and the late prerequisite stay planted):
```markdown
---
type: how-to
---
# Set up daily reminders

This page shows you how to get a notification each day so you don't forget to check in.

1. Open **Settings**.
2. Select **Daily reminders**.
3. Choose a time.
4. Select **Save changes**.

At the time you picked, Tally sends a notification listing the habits you haven't checked off yet.

Please make sure you've allowed Tally to send notifications in your phone's settings. Reminders don't work without that permission.
```

`docs/troubleshooting-sync.md` (headings now name symptoms; the Title Case title, "just", and the passive voice stay planted for Vale):
```markdown
---
type: troubleshooting
---
# Troubleshooting Sync Problems

Use this page if your habits look different on two devices after you turn on **Cloud sync**.

## Your habits are different on each device

1. On each device, open **Settings**.
2. Check the email address at the top of the screen.

If the addresses are different, sign out on one device and sign in with the account you want to keep. Your habits will be synced by the app within a minute.

## A change on one device doesn't show up on the other

1. Open **Settings**.
2. Select **Cloud sync**.
3. Select **Sync now**.

The **Last synced** time updates to the current time. If your habits still don't match, just restart the app on both devices.
```

- [ ] **Step 6: Run the whole suite**

Run: `venv/bin/pytest -q`
Expected: all tests pass (the 13 existing plus the 6 new ones). The existing `test_labels_match_docs_and_checklist` still passes because page names and rule ids haven't changed.

- [ ] **Step 7: Commit**

```bash
git add scripts/common.py docs tests/test_common.py tests/test_docs_pages.py
git commit -m "Declare a content type on every docs page

Adds frontmatter parsing, a type on all 15 pages, 'select' instead of
'tap', and structure fixes that keep every planted problem.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Structure check

**Files:**
- Create: `scripts/check_structure.py`
- Create: `tests/test_check_structure.py`

**Interfaces:**
- Consumes: `common.split_frontmatter`, `common.CONTENT_TYPES`, `common.CONTENT_TYPES_PATH`, `common.DOCS_DIR`, `common.REPO_ROOT`, `common.publish`
- Produces:
  - `STRUCTURE_CHECKS: dict` mapping each check id to the `set` of parameter names it accepts
  - `Violation = namedtuple("Violation", "page line rule_id message")`. `line` is a **file** line number.
  - `check_page(page, text, rules) -> list of Violation`. `rules` is a list of `{"id": str, "types": [str], "params": {str: str}}`.
  - `load_structure_rules(path=CONTENT_TYPES_PATH) -> list of rule dicts`
  - `slugify(text) -> str`

- [ ] **Step 1: Write the failing tests**

`tests/test_check_structure.py`:
```python
from check_structure import STRUCTURE_CHECKS, check_page, slugify

ALL = ["tutorial", "how-to", "reference", "troubleshooting", "landing"]
NOT_LANDING = ["tutorial", "how-to", "reference", "troubleshooting"]
RULES = [
    {"id": "type_declared", "types": ALL, "params": {}},
    {"id": "single_h1", "types": ALL, "params": {}},
    {"id": "intro_first", "types": NOT_LANDING, "params": {}},
    {"id": "numbered_steps", "types": ["tutorial", "how-to"], "params": {}},
    {"id": "max_steps", "types": ["how-to"], "params": {"max_steps": "7"}},
    {"id": "required_sections", "types": ["tutorial"], "params": {"sections": "before-you-start,next-steps"}},
    {"id": "no_numbered_lists", "types": ["reference"], "params": {}},
    {"id": "symptom_headings", "types": ["troubleshooting"], "params": {}},
    {"id": "warnings_only", "types": NOT_LANDING, "params": {}},
]
GOOD_HOW_TO = (
    "# Do a thing\n\nThis page is for people who want a thing.\n\n"
    "1. Open **Settings**.\n2. Select **Thing**.\n\nThe thing is done.\n"
)


def page(page_type, body):
    return f"---\ntype: {page_type}\n---\n{body}"


def ids(violations):
    return [v.rule_id for v in violations]


def test_registry_covers_every_rule_used_here():
    assert {rule["id"] for rule in RULES} == set(STRUCTURE_CHECKS)


def test_good_how_to_passes():
    assert check_page("docs/a.md", page("how-to", GOOD_HOW_TO), RULES) == []


def test_missing_type_reports_only_that():
    violations = check_page("docs/a.md", "# T\n\nIntro.\n", RULES)
    assert ids(violations) == ["type_declared"]
    assert violations[0].line == 1


def test_unknown_type():
    assert ids(check_page("docs/a.md", page("essay", GOOD_HOW_TO), RULES)) == ["type_declared"]


def test_eight_steps_points_at_the_eighth():
    body = "# T\n\nIntro.\n\n" + "".join(f"{n}. Step {n}.\n" for n in range(1, 9))
    violations = check_page("docs/a.md", page("how-to", body), RULES)
    assert ids(violations) == ["max_steps"]
    # 3 frontmatter lines + 4 lines before the list + 8th item = file line 15
    assert violations[0].line == 15


def test_steps_before_intro():
    assert ids(check_page("docs/a.md", page("how-to", "# T\n\n1. Open it.\n"), RULES)) == ["intro_first"]


def test_tutorial_needs_both_sections():
    violations = check_page("docs/a.md", page("tutorial", "# T\n\nIntro.\n\n1. Do it.\n"), RULES)
    assert ids(violations) == ["required_sections", "required_sections"]
    messages = " ".join(v.message for v in violations)
    assert "## Before you start" in messages and "## Next steps" in messages


def test_reference_rejects_numbered_steps():
    violations = check_page("docs/a.md", page("reference", "# T\n\nIntro.\n\n1. Do it.\n"), RULES)
    assert ids(violations) == ["no_numbered_lists"]


def test_troubleshooting_needs_symptom_headings():
    assert ids(check_page("docs/a.md", page("troubleshooting", "# T\n\nIntro.\n"), RULES)) == ["symptom_headings"]


def test_only_warning_callouts_allowed():
    body = GOOD_HOW_TO + "\n> **Note:** Extra.\n\n!!! warning\n    Careful.\n\n!!! tip\n    Hint.\n"
    assert ids(check_page("docs/a.md", page("how-to", body), RULES)) == ["warnings_only", "warnings_only"]


def test_two_titles():
    assert ids(check_page("docs/a.md", page("how-to", GOOD_HOW_TO + "\n# Another\n"), RULES)) == ["single_h1"]


def test_landing_page_is_exempt():
    assert check_page("docs/index.md", page("landing", "# Welcome\n\n- [A](a.md)\n"), RULES) == []


def test_code_blocks_are_ignored():
    body = GOOD_HOW_TO + "\n```\n# not a heading\n1. not a step\n```\n"
    assert check_page("docs/a.md", page("how-to", body), RULES) == []


def test_slugify():
    assert slugify("Before you start!") == "before-you-start"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `venv/bin/pytest tests/test_check_structure.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'check_structure'`

- [ ] **Step 3: Write `scripts/check_structure.py`**

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `venv/bin/pytest tests/test_check_structure.py -v`
Expected: 14 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/check_structure.py tests/test_check_structure.py
git commit -m "Add rule-based structure check for content types

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Build rules from the style guide

**Files:**
- Create: `scripts/build_rules.py`
- Create: `tests/test_build_rules.py`

**Interfaces:**
- Consumes: `check_structure.STRUCTURE_CHECKS`; `common.CONTENT_TYPES`, `common.GUIDE_PATH`, `common.CHECKLIST_PATH`, `common.CONTENT_TYPES_PATH`
- Produces:
  - `class RuleError(Exception)`
  - `parse_rules(markdown) -> list of {"id", "check", "types": [str], "params": {str: str}, "text": str}`
  - `build_outputs(rules) -> {Path: str}` with exactly two keys, `CHECKLIST_PATH` and `CONTENT_TYPES_PATH`
  - `main(argv=None) -> int` (0 = ok, 1 = error or stale)
  - Generated `checklist.yaml`: `{"items": [{"id", "rule", "types"}]}`
  - Generated `content_types.yaml`: `{"types": [...CONTENT_TYPES], "rules": [{"id", "types", "params"}]}`

- [ ] **Step 1: Write the failing tests**

`tests/test_build_rules.py`:
```python
import pytest
import yaml

import build_rules
from build_rules import RuleError, build_outputs, parse_rules

GUIDE = """# Style guide

<!-- rule id=prereqs_first check=claude types=how-to,tutorial -->
**Put prerequisites before the steps.** Anything the reader needs
goes first.

*Why:* wasted steps.

<!-- rule id=max_steps check=structure types=how-to max_steps=7 -->
**Keep how-tos to 7 steps or fewer.**

<!-- rule id=minimizers check=vale -->
**Don't write "simply".**
"""


def test_parses_a_claude_rule():
    assert parse_rules(GUIDE)[0] == {
        "id": "prereqs_first",
        "check": "claude",
        "types": ["how-to", "tutorial"],
        "params": {},
        "text": "Put prerequisites before the steps. Anything the reader needs goes first.",
    }


def test_types_default_to_every_type_but_landing():
    assert parse_rules(GUIDE)[2]["types"] == ["tutorial", "how-to", "reference", "troubleshooting"]


def test_structure_parameters_are_kept():
    assert parse_rules(GUIDE)[1]["params"] == {"max_steps": "7"}


def test_outputs_are_split_by_checker():
    outputs = build_outputs(parse_rules(GUIDE))
    checklist = yaml.safe_load(outputs[build_rules.CHECKLIST_PATH])
    structure = yaml.safe_load(outputs[build_rules.CONTENT_TYPES_PATH])
    assert [item["id"] for item in checklist["items"]] == ["prereqs_first"]
    assert checklist["items"][0]["types"] == ["how-to", "tutorial"]
    assert structure["rules"] == [{"id": "max_steps", "types": ["how-to"], "params": {"max_steps": "7"}}]
    assert outputs[build_rules.CHECKLIST_PATH].startswith("# Generated from STYLE_GUIDE.md")


@pytest.mark.parametrize("bad, message", [
    ("<!-- rule id=a check=claude -->\nText.\n<!-- rule id=a check=vale -->\nText.", "duplicate"),
    ("<!-- rule id=a check=robot -->\nText.", "check 'robot'"),
    ("<!-- rule id=a check=claude types=how-to,essay -->\nText.", "unknown type"),
    ("<!-- rule id=a check=claude -->\n", "no paragraph"),
    ("<!-- rule id=made_up check=structure -->\nText.", "no check named"),
    ("<!-- rule id=max_steps check=structure -->\nText.", "needs parameters"),
    ("<!-- rule id=a check=claude max_steps=3 -->\nText.", "only structure rules"),
    ("<!-- rule check=claude -->\nText.", "no id"),
    ("<!-- rule id=a check=claude oops -->\nText.", "key=value"),
])
def test_bad_tags_fail_loudly(bad, message):
    with pytest.raises(RuleError, match=message):
        parse_rules(bad)


def test_check_mode_detects_hand_edits(tmp_path, monkeypatch):
    guide = tmp_path / "STYLE_GUIDE.md"
    guide.write_text(GUIDE)
    monkeypatch.setattr(build_rules, "GUIDE_PATH", guide)
    monkeypatch.setattr(build_rules, "CHECKLIST_PATH", tmp_path / "checklist.yaml")
    monkeypatch.setattr(build_rules, "CONTENT_TYPES_PATH", tmp_path / "content_types.yaml")

    assert build_rules.main([]) == 0            # writes both files
    assert build_rules.main(["--check"]) == 0   # in sync
    (tmp_path / "checklist.yaml").write_text("items: []\n")
    assert build_rules.main(["--check"]) == 1   # hand edit caught


def test_bad_guide_returns_error(tmp_path, monkeypatch):
    guide = tmp_path / "STYLE_GUIDE.md"
    guide.write_text("<!-- rule id=a check=robot -->\nText.\n")
    monkeypatch.setattr(build_rules, "GUIDE_PATH", guide)
    assert build_rules.main(["--check"]) == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `venv/bin/pytest tests/test_build_rules.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'build_rules'`

- [ ] **Step 3: Write `scripts/build_rules.py`**

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `venv/bin/pytest tests/test_build_rules.py -v`
Expected: 15 passed (4 parsing tests, 9 parametrized bad-tag cases, 2 `main` tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/build_rules.py tests/test_build_rules.py
git commit -m "Generate reviewer checklist and structure rules from the style guide

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The style guide, templates, generated rules, and Vale rules

**Files:**
- Create: `STYLE_GUIDE.md`
- Create: `templates/how-to.md`, `templates/tutorial.md`, `templates/reference.md`, `templates/troubleshooting.md`
- Regenerate: `checklist.yaml`, create `content_types.yaml` (both via `build_rules.py`)
- Create: `styles/DemoDocs/Latin.yml`, `styles/DemoDocs/Click.yml`, `styles/DemoDocs/LinkText.yml`
- Create: `tests/test_style_guide.py`

**Interfaces:**
- Consumes: `build_rules.parse_rules`, `build_rules.build_outputs`, `check_structure.check_page`, `check_structure.load_structure_rules`, `common.GUIDE_PATH`
- Produces: `checklist.yaml` items that now carry `types`; `content_types.yaml`

- [ ] **Step 1: Write the failing tests**

`tests/test_style_guide.py`:
```python
import yaml

from build_rules import build_outputs, parse_rules
from check_structure import check_page, load_structure_rules
from common import CHECKLIST_PATH, DOCS_DIR, GUIDE_PATH, REPO_ROOT

# If you reword a Claude rule on purpose, update this and relabel with scripts/label.py
CLAUDE_RULES = {
    "intro_audience": "The first paragraph says who the page is for or what the reader will accomplish.",
    "prereqs_first": "Anything the reader needs before starting (an account, a permission, a setting "
                     "turned on) is stated before the steps, not during or after them.",
    "one_action_per_step": "Each numbered step asks the reader to do exactly one thing.",
    "no_undefined_jargon": "Technical terms and acronyms a non-technical user wouldn't know are explained or avoided.",
    "outcome_stated": "After the steps, the page tells the reader what happens or how to tell that it worked.",
}


def test_generated_files_match_the_guide():
    outputs = build_outputs(parse_rules(GUIDE_PATH.read_text(encoding="utf-8")))
    for path, text in outputs.items():
        assert path.read_text(encoding="utf-8") == text, f"{path.name} is stale: run python scripts/build_rules.py"


def test_claude_rule_wording_unchanged():
    items = yaml.safe_load(CHECKLIST_PATH.read_text(encoding="utf-8"))["items"]
    assert {item["id"]: item["rule"] for item in items} == CLAUDE_RULES


def test_every_docs_page_passes_the_structure_check():
    rules = load_structure_rules()
    for path in sorted(DOCS_DIR.glob("*.md")):
        assert check_page(path.name, path.read_text(encoding="utf-8"), rules) == [], path.name


def test_every_template_passes_the_structure_check():
    rules = load_structure_rules()
    templates = sorted((REPO_ROOT / "templates").glob("*.md"))
    assert [p.stem for p in templates] == ["how-to", "reference", "troubleshooting", "tutorial"]
    for path in templates:
        assert check_page(path.name, path.read_text(encoding="utf-8"), rules) == [], path.name
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `venv/bin/pytest tests/test_style_guide.py -v`
Expected: FAIL with `FileNotFoundError` for `STYLE_GUIDE.md`

- [ ] **Step 3: Write `STYLE_GUIDE.md`**

Each tag sits on the line directly above its rule paragraph (no blank line between them). The site hook in Task 8 relies on that. The *Why:* lines are drafts for Jared to rewrite in his own words.

~~~markdown
# Tally docs style guide

This guide is for anyone on a Tally product team who writes or edits a help page. Follow it and your page will read like every other page on the site, and it will pass the automated checks on your pull request.

Each rule says what to do, why, and which check enforces it. A few pieces of guidance have no automated check. Reviewers catch those.

## Voice

<!-- rule id=address_reader check=vale -->
**Talk to the reader as "you," never as "we."** Write "You can export your history," not "We let you export your history" or "The user can export their history."

*Why:* the reader is the one doing the task. "We" puts the company in the sentence, and "the user" puts a stranger there.

Start every step with a verb: "Select **Save changes**," not "Now you'll want to select **Save changes**." Reviewers check this one by eye.

## Headings

<!-- rule id=single_h1 check=structure types=tutorial,how-to,reference,troubleshooting,landing -->
**Give each page exactly one title (`#` heading).**

*Why:* the title is what search results and the sidebar show. Two titles means the page is really two pages.

<!-- rule id=heading_case check=vale -->
**Write headings in sentence case, and start task headings with a verb.** Write "Turn on dark mode," not "Turn On Dark Mode" or "Dark mode settings."

*Why:* sentence case is faster to scan, and a verb tells the reader the page is about doing something.

## UI labels

<!-- rule id=ui_labels_bold check=drift -->
**Put button, menu, and setting names in bold, spelled exactly as they appear on screen.** Write "Select **Save changes**," with the same capitalization the app uses.

*Why:* the reader is matching your words to their screen. Exact text also lets the UI drift check find every page that mentions a label when the app renames it.

## Words to avoid

<!-- rule id=minimizers check=vale -->
**Don't write "just," "simply," or "easily."**

*Why:* if the reader is stuck, these words tell them the problem is them.

<!-- rule id=no_please check=vale -->
**Don't write "please" in instructions.**

*Why:* instructions are clearer without it, and it gives the reader nothing to act on.

<!-- rule id=no_latin check=vale -->
**Write "for example," "that is," and "and so on," not "e.g.," "i.e.," and "etc."**

*Why:* plain English is easier for readers whose first language isn't English, and easier to translate.

<!-- rule id=select_not_click check=vale -->
**Write "select," not "click" or "tap."**

*Why:* Tally runs on phones and on the web. "Select" is right on both, so one page works for everyone.

## Links

<!-- rule id=link_text check=vale -->
**Make link text say where the link goes.** Write "See [Turn on cloud sync](cloud-sync.md)," not "Select [here](cloud-sync.md)."

*Why:* screen readers can list a page's links on their own, and a list of "here, here, here" is useless. People who skim read the links first.

## Callouts

<!-- rule id=warnings_only check=structure -->
**Use a callout only to warn about data loss or an action that can't be undone, and make it a warning.** Everything else, including tips and notes, goes in the text.

*Why:* when every page has a few notes, readers learn to skip them, and then they skip the one warning that mattered.

Write a warning like this:

```markdown
!!! warning
    Deleting your account can't be undone.
```

The structure check makes sure every callout is a warning. Whether the warning is deserved is a reviewer's call.

## Content types

Every page declares its type at the top:

```yaml
---
type: how-to
---
```

<!-- rule id=type_declared check=structure types=tutorial,how-to,reference,troubleshooting,landing -->
**Declare one of these types in the page's frontmatter: `tutorial`, `how-to`, `reference`, `troubleshooting`, or `landing`.**

*Why:* the type decides which rules apply, so a page with no type can't be checked.

Only the home page uses `landing`, and it's exempt from the rules below.

| Type | Use it when the reader wants to... | Example | Template |
| --- | --- | --- | --- |
| Tutorial | learn Tally by doing one thing from start to finish | Get started with Tally | [tutorial.md](https://github.com/thejaredchapman/docs-quality-demo/blob/main/templates/tutorial.md) |
| How-to | finish one specific task | Turn on dark mode | [how-to.md](https://github.com/thejaredchapman/docs-quality-demo/blob/main/templates/how-to.md) |
| Reference | look something up | Keyboard shortcuts | [reference.md](https://github.com/thejaredchapman/docs-quality-demo/blob/main/templates/reference.md) |
| Troubleshooting | fix something that went wrong | Troubleshoot sync problems | [troubleshooting.md](https://github.com/thejaredchapman/docs-quality-demo/blob/main/templates/troubleshooting.md) |

If a page seems to need two types, it's two pages.

### Every page

<!-- rule id=intro_first check=structure -->
**Start with an intro paragraph between the title and anything else.**

*Why:* a page that opens with step 1 never tells the reader whether they're in the right place.

<!-- rule id=intro_audience check=claude -->
**The first paragraph says who the page is for or what the reader will accomplish.**

*Why:* readers decide in one sentence whether to keep reading. An intro that only describes the feature doesn't help them decide.

<!-- rule id=no_undefined_jargon check=claude -->
**Technical terms and acronyms a non-technical user wouldn't know are explained or avoided.**

*Why:* Tally's readers are building habits, not studying software. "OAuth" means nothing to most of them.

### Tutorials and how-tos

<!-- rule id=numbered_steps check=structure types=tutorial,how-to -->
**Write the task as numbered steps.**

*Why:* numbers let the reader keep their place when they look away to the app.

<!-- rule id=prereqs_first check=claude types=how-to,tutorial -->
**Anything the reader needs before starting (an account, a permission, a setting turned on) is stated before the steps, not during or after them.**

*Why:* a reader who finds out at step 4 that they needed an account has wasted three steps.

In a how-to, put prerequisites in the intro. In a tutorial, put them in a `## Before you start` section.

<!-- rule id=one_action_per_step check=claude types=how-to,tutorial,troubleshooting -->
**Each numbered step asks the reader to do exactly one thing.**

*Why:* a step with three actions is where readers lose their place and skip one.

<!-- rule id=outcome_stated check=claude types=how-to,tutorial -->
**After the steps, the page tells the reader what happens or how to tell that it worked.**

*Why:* without it, the reader can't tell success from a silent failure.

### How-tos

<!-- rule id=max_steps check=structure types=how-to max_steps=7 -->
**Keep a how-to to 7 steps or fewer.**

*Why:* past 7 steps it's usually two tasks. Split it, or give the setup its own page.

### Tutorials

<!-- rule id=required_sections check=structure types=tutorial sections=before-you-start,next-steps -->
**Include a `## Before you start` section and a `## Next steps` section.**

*Why:* a tutorial is often a reader's first page. Tell them what to have ready, and where to go when they finish.

### Reference

<!-- rule id=no_numbered_lists check=structure types=reference -->
**Don't put numbered steps on a reference page.**

*Why:* reference is for looking things up. If the reader has to do something, that's a how-to, so link to it.

### Troubleshooting

<!-- rule id=symptom_headings check=structure types=troubleshooting -->
**Give each problem a `##` heading that describes what the reader sees.** Write "Your habits are different on each device," not "Force a sync."

*Why:* readers arrive with a symptom, not a fix. They scan for what's happening to them.

The structure check makes sure the headings exist. Whether they name symptoms is a reviewer's call.

## How these rules are checked

| Kind of rule | Example | Checked by | Blocks a pull request? |
| --- | --- | --- | --- |
| Word-level | no "simply," no "click" | Vale | No, it adds comments |
| Structure | type declared, 7 steps or fewer | Structure check | Yes |
| Judgment | the intro says who the page is for | Claude review | No, it gives advice |
| Product sync | a page mentions a renamed button | UI drift check | Yes |

Claude only reviews the judgment rules, and only the ones for the page's type. How often it agrees with a human reviewer is measured and published in the project README.

This guide is also the source for those checks. To change a rule, edit this file and run `python scripts/build_rules.py`. The pull request check fails if the generated files don't match the guide.
~~~

- [ ] **Step 4: Write the four templates**

`templates/how-to.md`:
```markdown
---
type: how-to
---
# Verb the thing

This page is for people who want to [goal]. Before you start, you need [prerequisite, or delete this sentence].

1. Open **[Screen name]**.
2. Select **[Button label]**.
3. [One action per step.]

[What the reader sees when it worked.]
```

`templates/tutorial.md`:
```markdown
---
type: tutorial
---
# Get started with [feature]

This guide is for [who]. By the end, you'll have [result].

## Before you start

- [What to install or set up first.]

## [First stage, starting with a verb]

1. [One action.]
2. [One action.]

[What the reader sees now.]

## Next steps

- [Link to the next page to read, with link text that names it.]
```

`templates/reference.md`:
```markdown
---
type: reference
---
# [Thing] reference

This page is for people who want to look up [what].

| [Item] | What it does |
| --- | --- |
| [Item] | [Description] |
```

`templates/troubleshooting.md`:
```markdown
---
type: troubleshooting
---
# Troubleshoot [feature]

Use this page if [the symptom, in the reader's words].

## [What the reader sees, such as "Your habits are different on each device"]

1. [One action.]
2. [One action.]

[How to tell it's fixed, and what to try if it isn't.]
```

- [ ] **Step 5: Generate the rule files**

Run: `venv/bin/python scripts/build_rules.py`
Expected output:
```
Wrote checklist.yaml
Wrote content_types.yaml
```
Then run `venv/bin/python scripts/check_structure.py`.
Expected: `All 15 pages have the structure their content type requires.` and exit code 0.

- [ ] **Step 6: Add the Vale rules**

`styles/DemoDocs/Latin.yml`:
```yaml
extends: substitution
message: "Use '%s' instead of '%s'."
level: warning
ignorecase: true
swap:
  'e\.g\.': for example
  'i\.e\.': that is
  'etc\.': and so on
```

`styles/DemoDocs/Click.yml`:
```yaml
extends: substitution
message: "Use '%s' instead of '%s'. It's right on phones and on the web."
level: warning
ignorecase: true
swap:
  click: select
  clicks: selects
  tap: select
  taps: selects
```

`styles/DemoDocs/LinkText.yml`:
```yaml
extends: existence
message: "Link text should say where the link goes, not '%s'."
level: warning
ignorecase: true
scope: raw
raw:
  - '\[(click here|here|this page|this link|link)\]\('
```

The voice rule (`address_reader`) uses `Microsoft.We` from the Microsoft package `.vale.ini` already loads, so it needs no new file. If Vale is installed locally (`brew install vale`), run `vale sync && vale docs`. Expected: warnings for "just" in `streak-freeze.md` and `troubleshooting-sync.md`, "Please" in `reminders.md`, and Title Case in `troubleshooting-sync.md` and `keyboard-shortcuts.md`. If Vale isn't installed, skip this; CI runs it.

- [ ] **Step 7: Run the whole suite**

Run: `venv/bin/pytest -q`
Expected: all pass. `test_real_checklist_loads` and `test_labels_match_docs_and_checklist` still pass: the checklist has the same 5 ids, now with `types`.

- [ ] **Step 8: Commit**

```bash
git add STYLE_GUIDE.md templates checklist.yaml content_types.yaml styles/DemoDocs tests/test_style_guide.py
git commit -m "Add the Tally style guide as the single source of rules

Style decisions by Jared Chapman. The checklist and structure rules are
now generated from the guide, with templates for each content type and
Vale rules for the banned words.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Scope the Claude review to each page's type

**Files:**
- Create: `scripts/rules.py`
- Modify: `scripts/judge.py` (lines 6-17 and 45-48)
- Modify: `scripts/review_pages.py`
- Create: `tests/test_rules.py`, `tests/test_review_pages.py`

**Interfaces:**
- Consumes: `common.read_page`, `common.CHECKLIST_PATH`, `common.CONTENT_TYPES_PATH`, `common.DOCS_DIR`
- Produces (in `rules.py`):
  - `load_checklist(path=CHECKLIST_PATH) -> [{"id", "rule", "types"}]`
  - `rules_for_type(checklist_items, page_type) -> [items]`
  - `applicable_pairs(checklist_items, docs_dir=DOCS_DIR) -> [(page_name, rule_id)]`, sorted by page name, then checklist order
  - `rules_hash(paths=(CHECKLIST_PATH, CONTENT_TYPES_PATH)) -> "sha256:<hex>"`
- Produces (in `review_pages.py`): `review(paths, checklist, model, judge=judge_page) -> {page_name: verdicts}`. A page with no applicable rules maps to `{}`.
- `judge.load_checklist` keeps working (re-exported from `rules`).

- [ ] **Step 1: Write the failing tests**

`tests/test_rules.py`:
```python
from rules import applicable_pairs, load_checklist, rules_for_type, rules_hash

ITEMS = [
    {"id": "intro_audience", "rule": "r", "types": ["how-to", "reference"]},
    {"id": "outcome_stated", "rule": "r", "types": ["how-to"]},
]


def test_reference_page_gets_only_its_rules():
    assert [item["id"] for item in rules_for_type(ITEMS, "reference")] == ["intro_audience"]


def test_landing_and_missing_type_get_no_rules():
    assert rules_for_type(ITEMS, "landing") == []
    assert rules_for_type(ITEMS, None) == []


def test_applicable_pairs(tmp_path):
    (tmp_path / "a.md").write_text("---\ntype: how-to\n---\n# A\n")
    (tmp_path / "b.md").write_text("---\ntype: reference\n---\n# B\n")
    (tmp_path / "c.md").write_text("---\ntype: landing\n---\n# C\n")
    assert applicable_pairs(ITEMS, docs_dir=tmp_path) == [
        ("a.md", "intro_audience"),
        ("a.md", "outcome_stated"),
        ("b.md", "intro_audience"),
    ]


def test_real_docs_have_62_pairs():
    assert len(applicable_pairs(load_checklist())) == 62


def test_hash_changes_when_rules_change(tmp_path):
    rules_file = tmp_path / "checklist.yaml"
    rules_file.write_text("items: []\n")
    before = rules_hash([rules_file])
    rules_file.write_text("items: [x]\n")
    assert before.startswith("sha256:")
    assert rules_hash([rules_file]) != before
```

`tests/test_review_pages.py`:
```python
from review_pages import build_report, review
from rules import load_checklist


def test_landing_page_has_no_rules():
    assert "No review rules apply" in build_report({"index.md": {}})


def test_api_error_says_review_unavailable():
    verdicts = {
        "x": {"passed": None, "reason": "API error: boom"},
        "y": {"passed": None, "reason": "API error: boom"},
    }
    report = build_report({"a.md": verdicts})
    assert "review unavailable" in report
    assert "API error: boom" in report


def test_lists_only_problems():
    report = build_report({"a.md": {
        "x": {"passed": True, "reason": "ok"},
        "y": {"passed": False, "reason": "No outcome."},
    }})
    assert "1/2 checks passed" in report
    assert "**y**" in report and "**x**" not in report


def test_reference_page_is_sent_only_its_two_rules(tmp_path):
    page = tmp_path / "ref.md"
    page.write_text("---\ntype: reference\n---\n# Shortcuts\n\nThis page is for people who use a keyboard.\n")
    landing = tmp_path / "index.md"
    landing.write_text("---\ntype: landing\n---\n# Welcome\n")
    sent = {}

    def fake_judge(text, rules, model):
        sent["text"] = text
        sent["rules"] = [r["id"] for r in rules]
        return {r["id"]: {"passed": True, "reason": "ok"} for r in rules}

    result = review([page, landing], load_checklist(), "test-model", judge=fake_judge)
    assert sent["rules"] == ["intro_audience", "no_undefined_jargon"]
    assert "type: reference" not in sent["text"]  # frontmatter isn't sent to Claude
    assert result["index.md"] == {}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `venv/bin/pytest tests/test_rules.py tests/test_review_pages.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rules'`

- [ ] **Step 3: Write `scripts/rules.py`**

```python
"""Load the reviewer checklist and work out which rules apply to which pages.

Each checklist item lists the content types it applies to, and each page
declares its type in frontmatter. The reviewer, the eval, and the labeling
tool all use these helpers, so they always agree on what gets graded.
"""
import hashlib

import yaml

from common import CHECKLIST_PATH, CONTENT_TYPES_PATH, DOCS_DIR, read_page


def load_checklist(path=CHECKLIST_PATH):
    """Return the checklist as a list of {"id", "rule", "types"} dicts."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)["items"]


def rules_for_type(checklist_items, page_type):
    """The checklist items that apply to a page of this type."""
    return [item for item in checklist_items if page_type in item["types"]]


def applicable_pairs(checklist_items, docs_dir=DOCS_DIR):
    """Every (page name, rule id) the reviewer grades, sorted by page, then checklist order."""
    pairs = []
    for path in sorted(docs_dir.glob("*.md")):
        meta, _, _ = read_page(path)
        for item in rules_for_type(checklist_items, meta.get("type")):
            pairs.append((path.name, item["id"]))
    return pairs


def rules_hash(paths=(CHECKLIST_PATH, CONTENT_TYPES_PATH)):
    """A fingerprint of the current rules.

    It's saved with the labels, so the eval can tell when the rules have
    changed since labeling and the labels no longer mean the same thing.
    """
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()
```

- [ ] **Step 4: Update `scripts/judge.py`**

Replace lines 6-17 (the imports, `DEFAULT_MODEL`, `CHECKLIST_PATH`, and `SYSTEM_PROMPT`) with:
```python
import anthropic

# Re-exported so existing callers can keep doing `from judge import load_checklist`
from rules import load_checklist  # noqa: F401

DEFAULT_MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """You are a strict technical-writing reviewer.
Grade the page against each checklist item, and nothing else.
If the page has nothing a rule is about (for example, a rule about prerequisites on a page that needs none), mark it passed.
Report every checklist item exactly once, using its id."""
```
Then delete the old `load_checklist` function (lines 45-48). `format_checklist` and `judge_page` stay as they are.

- [ ] **Step 5: Update `scripts/review_pages.py`**

Replace the whole file with:
```python
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
```

- [ ] **Step 6: Run the whole suite**

Run: `venv/bin/pytest -q`
Expected: all pass, including the existing `tests/test_judge.py` (it imports `load_checklist` from `judge`, which is still re-exported).

- [ ] **Step 7: Commit**

```bash
git add scripts/rules.py scripts/judge.py scripts/review_pages.py tests/test_rules.py tests/test_review_pages.py
git commit -m "Scope the Claude review to the rules for each page's type

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Honest accuracy report

**Files:**
- Modify: `scripts/eval_judge.py`
- Move: `eval/labels.json` → `eval/labels.previous.json`
- Modify: `tests/test_eval_judge.py`

**Interfaces:**
- Consumes: `rules.applicable_pairs`, `rules.load_checklist`, `rules.rules_for_type`, `rules.rules_hash`, `common.read_page`
- Produces:
  - `LABELS_PATH = REPO_ROOT / "eval" / "labels.json"`
  - `load_labels(path=LABELS_PATH) -> (meta, labels)`, or `(None, None)` if the file doesn't exist. The file format is `{"meta": {"labeler", "date", "rules_hash"}, "labels": {page: {rule_id: bool}}}`.
  - `keep_applicable(labels, pairs) -> labels` (drops pairs that don't apply and pages left empty)
  - `agreement_stats(labels, predictions) -> (always_pass_baseline: float or None, kappa: float or None)`
  - `compute_metrics(labels, predictions)` is unchanged
  - `build_report(model, labels, verdicts, meta=None) -> str`

- [ ] **Step 1: Retire the old labels**

Run: `git mv eval/labels.json eval/labels.previous.json`

The old labels predate content types and their origin isn't documented, so nothing reads them. They're kept only for comparison.

- [ ] **Step 2: Write the failing tests**

Replace `tests/test_eval_judge.py` with:
```python
import pytest

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
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `venv/bin/pytest tests/test_eval_judge.py -v`
Expected: FAIL with `ImportError: cannot import name 'agreement_stats'`

- [ ] **Step 4: Rewrite `scripts/eval_judge.py`**

```python
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
```

- [ ] **Step 5: Run the whole suite**

Run: `venv/bin/pytest -q`
Expected: all pass. `test_labels_file_covers_only_applicable_pairs` shows as **skipped** until Jared labels.

- [ ] **Step 6: Commit**

```bash
git add scripts/eval_judge.py tests/test_eval_judge.py eval
git commit -m "Report baseline and Cohen's kappa; grade only applicable pairs

Retires the old labels to eval/labels.previous.json. New labels come
from scripts/label.py and carry the labeler, date, and a rules hash.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Blind labeling tool

**Files:**
- Create: `scripts/label.py`
- Create: `tests/test_label.py`

**Interfaces:**
- Consumes: `rules.applicable_pairs`, `rules.load_checklist`, `rules.rules_hash`, `common.read_page`, `common.DOCS_DIR`; writes the same format `eval_judge.load_labels` reads
- Produces:
  - `pending(pairs, labels) -> [(page, rule_id)]`
  - `label_loop(pairs, labels, show, ask, save, seed=None) -> labels`, where `show(page, rule_id, done, total)`, `ask() -> str`, and `save(labels)`
  - `main() -> int`

- [ ] **Step 1: Write the failing tests**

`tests/test_label.py`:
```python
import json

from label import label_loop, pending

PAIRS = [("a.md", "x"), ("a.md", "y"), ("b.md", "x")]


def run(answers, labels=None, seed=0):
    answers = iter(answers)
    shown, saves = [], []
    result = label_loop(
        PAIRS,
        {} if labels is None else labels,
        show=lambda page, rule_id, done, total: shown.append((page, rule_id)),
        ask=lambda: next(answers),
        save=lambda current: saves.append(json.dumps(current, sort_keys=True)),
        seed=seed,
    )
    return result, shown, saves


def count(labels):
    return sum(len(items) for items in labels.values())


def test_labels_every_pair_and_saves_after_each_answer():
    result, shown, saves = run(["y", "n", "y"])
    assert sorted(shown) == sorted(PAIRS)
    assert count(result) == 3
    assert len(saves) == 3


def test_quit_keeps_what_was_answered():
    result, _, saves = run(["y", "q"])
    assert count(result) == 1
    assert len(saves) == 1


def test_skip_leaves_the_pair_unlabeled():
    result, _, _ = run(["s", "y", "y"])
    assert len(pending(PAIRS, result)) == 1


def test_resume_only_asks_about_what_is_left():
    result, shown, _ = run(["n"], labels={"a.md": {"x": True, "y": True}})
    assert shown == [("b.md", "x")]
    assert result["b.md"]["x"] is False


def test_invalid_answer_asks_again():
    result, shown, _ = run(["maybe", "y", "y", "y"])
    assert len(shown) == 3
    assert count(result) == 3


def test_order_is_shuffled_but_repeatable():
    _, first, _ = run(["y", "y", "y"], seed=1)
    _, second, _ = run(["y", "y", "y"], seed=1)
    assert first == second
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `venv/bin/pytest tests/test_label.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'label'`

- [ ] **Step 3: Write `scripts/label.py`**

```python
"""Label docs pages by hand, one rule at a time, without seeing any other answers.

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


def pending(pairs, labels):
    """The pairs that don't have a label yet."""
    return [(page, rule_id) for page, rule_id in pairs if rule_id not in labels.get(page, {})]


def label_loop(pairs, labels, show, ask, save, seed=None):
    """Ask about every unlabeled pair in a random order, and return the labels.

    show(page, rule_id, done, total) displays one question.
    ask() returns "y", "n", "s" (skip) or "q" (quit); anything else is asked again.
    save(labels) is called after every answer, so quitting or crashing loses nothing.
    """
    todo = pending(pairs, labels)
    # Random order, so pages aren't labeled in a pattern that could bias the answers
    random.Random(seed).shuffle(todo)
    total = len(pairs)
    for page, rule_id in todo:
        show(page, rule_id, total - len(pending(pairs, labels)), total)
        answer = ask()
        while answer not in ("y", "n", "s", "q"):
            answer = ask()
        if answer == "q":
            break
        if answer == "s":
            continue
        labels.setdefault(page, {})[rule_id] = ANSWERS[answer]
        save(labels)
    return labels


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

    def show(page, rule_id, done, total):
        _, body, _ = read_page(DOCS_DIR / page)
        print("\n" + "=" * 72)
        print(f"[{done + 1}/{total}]  {page}\n")
        print(body.strip())
        print("\n" + "-" * 72)
        print(f"Rule: {rule_text[rule_id]}")

    def ask():
        return input("Does the page follow this rule? [y]es / [n]o / [s]kip / [q]uit: ").strip().lower()[:1]

    label_loop(pairs, labels, show, ask, save)
    done = len(pairs) - len(pending(pairs, labels))
    where = f" Saved in {LABELS_PATH.relative_to(REPO_ROOT)}." if LABELS_PATH.exists() else " Nothing saved yet."
    print(f"\n{done}/{len(pairs)} labeled.{where}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `venv/bin/pytest tests/test_label.py -v`
Expected: 6 passed

- [ ] **Step 5: Smoke-test the CLI without saving anything**

Run: `printf 'q\n' | venv/bin/python scripts/label.py --labeler test`
Expected: one page and one rule print, then `0/62 labeled. Nothing saved yet.` Because nothing was answered, `save` never ran, so `eval/labels.json` still doesn't exist. Confirm with `ls eval/` (only `labels.previous.json`).

- [ ] **Step 6: Commit**

```bash
git add scripts/label.py tests/test_label.py
git commit -m "Add a blind, resumable labeling tool

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: MkDocs site

**Files:**
- Modify: `requirements.txt`, `.gitignore`
- Create: `mkdocs.yml`, `scripts/site_hooks.py`, `docs/stylesheets/extra.css`, `.github/workflows/deploy-site.yml`
- Create: `tests/test_site.py`

**Interfaces:**
- Consumes: `common.read_page`, `common.DOCS_DIR`, `common.REPO_ROOT` (tests only; the hook itself imports nothing from `scripts/`)
- Produces (in `site_hooks.py`): `render_rule_tags(markdown) -> str`, plus the MkDocs hooks `on_files(files, config)` and `on_page_markdown(markdown, page, config, files)`

- [ ] **Step 1: Install MkDocs**

Add this line to `requirements.txt`:
```
mkdocs>=1.6,<2
```
Add this line to `.gitignore`:
```
site/
```
Run: `venv/bin/pip install -r requirements.txt`
Expected: `Successfully installed ... mkdocs-1.6.x ...`

- [ ] **Step 2: Write the failing tests**

`tests/test_site.py`:
```python
import yaml

from common import DOCS_DIR, REPO_ROOT, read_page
from site_hooks import render_rule_tags

GROUP_TYPES = {
    "Home": "landing",
    "Get started": "tutorial",
    "How-to guides": "how-to",
    "Reference": "reference",
    "Troubleshooting": "troubleshooting",
}


def nav_entries():
    config = yaml.safe_load((REPO_ROOT / "mkdocs.yml").read_text(encoding="utf-8"))
    entries = []
    for entry in config["nav"]:
        (group, value), = entry.items()
        for page in value if isinstance(value, list) else [value]:
            entries.append((group, page))
    return entries


def test_every_page_is_in_the_nav_group_for_its_type():
    placed = [(group, page) for group, page in nav_entries() if group in GROUP_TYPES]
    assert sorted(page for _, page in placed) == sorted(p.name for p in DOCS_DIR.glob("*.md"))
    for group, page in placed:
        meta, _, _ = read_page(DOCS_DIR / page)
        assert meta["type"] == GROUP_TYPES[group], page


def test_style_guide_is_in_the_nav():
    assert ("Style guide", "style-guide.md") in nav_entries()


def test_rule_tags_become_checked_by_labels():
    rendered = render_rule_tags("<!-- rule id=prereqs_first check=claude types=how-to -->\n**Rule.**")
    assert rendered == '<span class="rule-check">Checked by: Claude review</span>\n**Rule.**'


def test_other_comments_are_left_alone():
    assert render_rule_tags("<!-- just a comment -->") == "<!-- just a comment -->"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `venv/bin/pytest tests/test_site.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'site_hooks'`

- [ ] **Step 4: Write `scripts/site_hooks.py`**

```python
"""MkDocs hooks: publish STYLE_GUIDE.md on the site, and show how each rule is checked.

The style guide lives at the repo root (it's the source for the CI checks), so
it isn't inside docs/. This hook adds it to the site as style-guide.md, and
turns each hidden rule tag into a visible "Checked by: ..." label.
"""
import re
from pathlib import Path

from mkdocs.structure.files import File

# Not imported from common.py: MkDocs loads this file by path, so scripts/ may not be importable
GUIDE_PATH = Path(__file__).resolve().parent.parent / "STYLE_GUIDE.md"
TAG = re.compile(r"<!--\s*rule\s+(.*?)\s*-->")
CHECK_NAMES = {
    "vale": "Vale",
    "structure": "Structure check",
    "claude": "Claude review",
    "drift": "UI drift check",
}


def render_rule_tags(markdown):
    """Replace each rule tag with a small label naming the check that enforces it."""
    def replace(match):
        fields = dict(token.split("=", 1) for token in match.group(1).split() if "=" in token)
        check = fields.get("check", "")
        return f'<span class="rule-check">Checked by: {CHECK_NAMES.get(check, check)}</span>'
    return TAG.sub(replace, markdown)


def on_files(files, config):
    files.append(File.generated(config, "style-guide.md", abs_src_path=str(GUIDE_PATH)))
    return files


def on_page_markdown(markdown, page, config, files):
    if page.file.src_uri == "style-guide.md":
        return render_rule_tags(markdown)
    return markdown
```

- [ ] **Step 5: Write `mkdocs.yml` and the stylesheet**

`mkdocs.yml`:
```yaml
site_name: Tally Help
site_description: Help pages for Tally, a made-up habit tracker, built to demo automated docs quality checks.
repo_url: https://github.com/thejaredchapman/docs-quality-demo
docs_dir: docs

hooks:
  - scripts/site_hooks.py

extra_css:
  - stylesheets/extra.css

markdown_extensions:
  - admonition
  - tables

# Grouped by content type, so the site's structure matches the style guide
nav:
  - Home: index.md
  - Get started:
      - getting-started.md
  - How-to guides:
      - create-a-habit.md
      - edit-a-habit.md
      - reminders.md
      - streak-freeze.md
      - dark-mode.md
      - cloud-sync.md
      - share-progress.md
      - export-data.md
      - change-password.md
      - delete-account.md
  - Reference:
      - keyboard-shortcuts.md
      - faq.md
  - Troubleshooting:
      - troubleshooting-sync.md
  - Style guide: style-guide.md
```

`docs/stylesheets/extra.css`:
```css
/* The "Checked by: ..." label above each rule in the style guide */
.rule-check {
  display: block;
  width: fit-content;
  margin-bottom: 0.25em;
  padding: 0.1em 0.6em;
  border-radius: 4px;
  background: #eef2f7;
  color: #34495e;
  font-size: 0.75em;
  font-weight: 600;
}
```

- [ ] **Step 6: Run the tests and build the site**

Run: `venv/bin/pytest tests/test_site.py -v`
Expected: 4 passed

Run: `venv/bin/mkdocs build --strict`
Expected: ends with `INFO - Documentation built in ...` and no warnings. If strict mode reports a broken link, fix the link in the page it names and rerun.

Run: `venv/bin/mkdocs serve`, open http://127.0.0.1:8000, and check two things: the sidebar shows the five groups plus "Style guide", and the style guide shows a "Checked by" label above each rule. Stop the server with Ctrl+C.

- [ ] **Step 7: Write the deploy workflow**

`.github/workflows/deploy-site.yml`:
```yaml
name: Deploy docs site

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write     # lets the job publish to GitHub Pages
  id-token: write  # required by actions/deploy-pages

concurrency:
  group: pages
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -r requirements.txt
      - run: mkdocs build --strict
      - uses: actions/upload-pages-artifact@v3
        with:
          path: site

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

Run: `venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-site.yml'))" && echo ok`
Expected: `ok`

- [ ] **Step 8: Commit**

```bash
git add requirements.txt .gitignore mkdocs.yml scripts/site_hooks.py docs/stylesheets tests/test_site.py .github/workflows/deploy-site.yml
git commit -m "Publish the docs and style guide as an MkDocs site

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Wire the new checks into PR CI and update the README

**Files:**
- Modify: `.github/workflows/docs-pr.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: `scripts/build_rules.py --check` (exit 1 when stale), `scripts/check_structure.py` (exit 1 on violations)

- [ ] **Step 1: Add the structure job to `.github/workflows/docs-pr.yml`**

Insert this job between the `vale` job and the `claude-review` job (after line 19):
```yaml
  structure:
    name: Style guide sync + page structure
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -r requirements.txt
      - name: Checklist and structure rules match the style guide
        run: python scripts/build_rules.py --check
      - name: Every page has the structure its type requires
        run: python scripts/check_structure.py
```

Run: `venv/bin/python -c "import yaml; print(list(yaml.safe_load(open('.github/workflows/docs-pr.yml'))['jobs']))"`
Expected: `['vale', 'structure', 'claude-review', 'ui-drift']`

- [ ] **Step 2: Check the numbers the README quotes**

Run: `grep -rn -E '(Save changes|Cloud sync)' docs | wc -l`
Expected: `11`. If it prints another number, use that number in demo PR 2 below.

Run: `venv/bin/python -c "import sys; sys.path.insert(0,'scripts'); from rules import applicable_pairs, load_checklist; print(len(applicable_pairs(load_checklist())))"`
Expected: `62`

- [ ] **Step 3: Replace `README.md`**

The `__` cells in the accuracy table are filled in by Jared after he labels and runs the eval. They are intentional.

~~~markdown
# Docs quality checks: a GitHub Action demo

A small help site for **Tally**, a made-up habit-tracker app, with a style guide and the automated checks that enforce it on every pull request.

- **Style guide:** [`STYLE_GUIDE.md`](STYLE_GUIDE.md), also published on the [docs site](https://thejaredchapman.github.io/docs-quality-demo/style-guide/)
- **Docs site:** https://thejaredchapman.github.io/docs-quality-demo/

The style guide is the single source of truth. The Claude reviewer's checklist and the structure rules are generated from it, and CI fails if they drift apart.

## Who checks what

| Kind of rule | Example | Checked by | Blocks the PR? |
|---|---|---|---|
| Guide sync | the checklist was edited by hand | `build_rules.py --check` | **Yes** |
| Structure | page declares a type, how-to has 7 steps or fewer, tutorial has "Next steps" | `check_structure.py`, rule-based | **Yes** |
| Word-level | "simply," "click," "e.g.," "click here" links | [Vale](https://vale.sh), rule-based | No (annotations) |
| Judgment | the intro says who the page is for, one action per step | Claude, graded against the rules for the page's type | No (advisory) |
| Product sync | docs still mention a button the code just renamed | `ui_drift.py`, diff of [`app/ui_strings.json`](app/ui_strings.json) | **Yes** |

Rules handle everything rules can do. Claude only handles the judgment calls, and its accuracy is **measured**, not assumed.

## Content types

Every page declares `type:` in its frontmatter: `tutorial`, `how-to`, `reference`, `troubleshooting`, or `landing` (the home page only). The type decides which structure rules and which Claude rules apply. Templates for each type are in [`templates/`](templates/).

## How accurate is the Claude reviewer?

[`eval/labels.json`](eval/labels.json) holds hand labels: for each page, and each Claude rule that applies to its type, does the page follow the rule? That's 62 judgments on 14 pages. The labels were made blind with [`scripts/label.py`](scripts/label.py), which never shows Claude's answers.

| Model | Agreement | Always-pass baseline | Cohen's κ | Misses | False alarms |
|---|---|---|---|---|---|
| `claude-haiku-4-5-20251001` | __% | __% | __ | __ | __ |
| `claude-sonnet-5` | __% | __% | __ | __ | __ |

Most pages follow most rules, so a "reviewer" that always says pass would already match the **always-pass baseline**. Cohen's κ measures agreement beyond that: 0 means no better than chance, and 1 means perfect. "Unknown" answers count as wrong, so neither number is inflated. n = 62 is small, so treat the numbers as directional.

## Repo layout

```
STYLE_GUIDE.md                    # the guide; the source for checklist.yaml and content_types.yaml
templates/                        # one skeleton page per content type
docs/                             # 15 sample pages, some with planted problems
checklist.yaml                    # generated: rules Claude grades
content_types.yaml                # generated: structure rules per type
app/ui_strings.json               # stand-in for product code: UI labels
eval/labels.json                  # hand labels (made with scripts/label.py)
styles/DemoDocs/                  # custom Vale rules
mkdocs.yml                        # site config; nav grouped by content type
scripts/build_rules.py            # STYLE_GUIDE.md -> generated rule files (--check in CI)
scripts/check_structure.py        # rule-based structure checks
scripts/judge.py                  # Claude grader (Anthropic SDK, forced tool use for structured output)
scripts/review_pages.py           # grades the pages changed in a PR
scripts/label.py                  # blind labeling CLI
scripts/eval_judge.py             # compares the grader to the labels: agreement, baseline, kappa
scripts/ui_drift.py               # flags docs that mention changed UI text
scripts/site_hooks.py             # publishes the style guide on the site
.github/workflows/docs-pr.yml     # every PR: sync, structure, Vale, Claude review, drift
.github/workflows/judge-eval.yml  # run by hand: measures judge accuracy
.github/workflows/deploy-site.yml # every push to main: builds and deploys the site
```

## Setup

1. Push this repo to GitHub.
2. Add a repository secret named `ANTHROPIC_API_KEY` (**Settings → Secrets and variables → Actions**).
3. Turn on the site: **Settings → Pages → Source: GitHub Actions**.
4. Open a PR from a branch in this repo. PRs from forks don't get secrets, so the Claude review would fail there.

## Run locally

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pytest                                   # no API key needed: Claude is faked in tests

python scripts/build_rules.py            # after editing STYLE_GUIDE.md
python scripts/check_structure.py
python scripts/label.py                  # make the hand labels (about 30 minutes)
mkdocs serve                             # preview the site at http://127.0.0.1:8000

export ANTHROPIC_API_KEY=...
python scripts/review_pages.py docs/dark-mode.md
python scripts/eval_judge.py --model claude-haiku-4-5-20251001 --model claude-sonnet-5
python scripts/ui_drift.py --base-ref main
vale docs                                # needs Vale installed: brew install vale && vale sync
```

## Demo PRs

1. **Style problems.** Edit `docs/streak-freeze.md` and `docs/edit-a-habit.md`. Vale flags "just," and Claude flags the missing outcome and the multi-action step.
2. **UI rename.** In `app/ui_strings.json`, change `"Save changes"` → `"Save"` and `"Cloud sync"` → `"Sync"`. The drift check fails and lists the 11 lines that need updating.
3. **Clean PR.** A small fix to `docs/delete-account.md`. Everything passes.
4. **Structure problems.** Add `docs/pause-a-habit.md` with `type: how-to`, 8 numbered steps, and a `> **Note:**` callout. The structure check fails with two annotations: `max_steps` on step 8 and `warnings_only` on the note.

## Limitations and next steps

- The drift check uses exact matching, so docs that paraphrase a label ("the save button") aren't caught. Next step: fuzzy matching, or asking Claude to confirm likely matches.
- The labels are one person's judgment. A second labeler would show how much people agree with each other, which is the ceiling for any reviewer.
- The structure check can tell that a troubleshooting page has headings, but not that they name symptoms. The guide leaves that to human review.
- Real products keep UI strings in localization files (`.json`, `.strings`, `.po`). `ui_drift.py` would need a small loader for each format.

## Credits

Style guide decisions and eval labels by Jared Chapman; drafting and code written with Claude Code. Tally is fictional.
~~~

- [ ] **Step 4: Run everything once more**

Run: `venv/bin/pytest -q && venv/bin/python scripts/build_rules.py --check && venv/bin/python scripts/check_structure.py > /dev/null && venv/bin/mkdocs build --strict -q && echo ALL GREEN`
Expected: pytest passes with 1 skipped (the labels test), then `ALL GREEN`

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/docs-pr.yml README.md
git commit -m "Run sync and structure checks on every PR; document the new setup

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## After the plan: Jared's manual steps (not agent tasks)

1. Read `STYLE_GUIDE.md` and rewrite any *Why:* line you wouldn't say in an interview. Then run `python scripts/build_rules.py` and commit. Changing only *Why:* lines leaves the generated files unchanged.
2. `python scripts/label.py` (about 30 minutes), then commit `eval/labels.json`.
3. `export ANTHROPIC_API_KEY=...` and `python scripts/eval_judge.py --model claude-haiku-4-5-20251001 --model claude-sonnet-5`. Then paste the numbers into the README table and commit.
4. Tell Claude to push: create the public repo `thejaredchapman/docs-quality-demo`, push, add the secret, and turn on Pages.
