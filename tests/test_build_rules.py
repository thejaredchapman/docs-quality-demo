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
