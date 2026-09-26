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
