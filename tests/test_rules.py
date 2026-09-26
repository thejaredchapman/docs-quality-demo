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
