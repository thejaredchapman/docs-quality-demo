import pytest

from review_sheet import SheetError, build_sheet, parse_sheet

PAIRS = [("a.md", "x"), ("a.md", "y"), ("b.md", "x")]
RULE_TEXT = {"x": "Rule X.", "y": "Rule Y."}
BODIES = {"a.md": "# A\n\nPage A.\n", "b.md": "# B\n\nPage B.\n"}


def sheet(labels=None):
    return build_sheet(PAIRS, labels or {}, RULE_TEXT, BODIES.get, "sha256:abc")


def test_each_page_appears_once_with_its_rules():
    text = sheet()
    assert text.count("## a.md") == 1 and text.count("## b.md") == 1
    assert "Page A." in text and "Page B." in text
    assert text.count("- [x] **x**: Rule X.") == 2


def test_unlabeled_pairs_start_checked_and_existing_labels_are_kept():
    text = sheet({"a.md": {"y": False}})
    assert "- [ ] **y**: Rule Y." in text
    assert text.count("- [x]") == 2


def test_round_trip_reads_checked_as_follows_and_unchecked_as_breaks():
    text = sheet().replace("- [x] **y**: Rule Y.", "- [ ] **y**: Rule Y.")
    labels, rules_hash = parse_sheet(text, PAIRS)
    assert labels == {"a.md": {"x": True, "y": False}, "b.md": {"x": True}}
    assert rules_hash == "sha256:abc"


def test_missing_question_is_an_error():
    text = sheet().replace("- [x] **y**: Rule Y.\n", "")
    with pytest.raises(SheetError, match="a.md / y"):
        parse_sheet(text, PAIRS)


def test_unknown_question_is_an_error():
    text = sheet() + "- [x] **z**: Rule Z.\n"
    with pytest.raises(SheetError, match="z"):
        parse_sheet(text, PAIRS)


def test_checkbox_lines_inside_a_page_body_are_ignored():
    bodies = {"a.md": "# A\n\n- [ ] **x**: not a real answer\n", "b.md": "# B\n"}
    text = build_sheet(PAIRS, {}, RULE_TEXT, bodies.get, "sha256:abc")
    labels, _ = parse_sheet(text, PAIRS)
    assert labels["a.md"]["x"] is True
