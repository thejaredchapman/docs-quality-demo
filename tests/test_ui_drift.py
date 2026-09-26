from ui_drift import build_report, find_changed_strings, find_mentions


def test_finds_changed_and_removed_strings_but_ignores_new_ones():
    old = {"save": "Save changes", "sync": "Cloud sync", "same": "Settings"}
    new = {"save": "Save", "same": "Settings", "brand_new": "Streaks"}
    assert find_changed_strings(old, new) == [
        ("save", "Save changes", "Save"),
        ("sync", "Cloud sync", None),
    ]


def test_mentions_are_exact_case_and_whole_phrase(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(
        "Open **Settings**.\n"      # match
        "Change your settings.\n"   # different case: no match
        "Open Settingsmenu.\n"      # part of a longer word: no match
        "Settings, then more.\n"    # match
    )
    mentions = find_mentions("Settings", docs_dir=docs)
    assert [(page, line) for page, line, _ in mentions] == [("docs/page.md", 1), ("docs/page.md", 4)]


def test_report_shows_removed_strings():
    report = build_report([("docs/a.md", 3, "Cloud sync", None)])
    assert "_(removed)_" in report


def test_report_when_nothing_found():
    assert "No docs pages mention" in build_report([])
