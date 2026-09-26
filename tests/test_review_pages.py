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
