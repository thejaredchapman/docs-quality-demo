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
