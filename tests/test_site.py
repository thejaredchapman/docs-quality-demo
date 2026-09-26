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
