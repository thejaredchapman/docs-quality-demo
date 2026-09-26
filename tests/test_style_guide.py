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
