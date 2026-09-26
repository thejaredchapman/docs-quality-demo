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


def test_zero_titles_reports_single_h1_at_first_body_line():
    # Note: this page also trips `intro_first` (see check_structure.py's title_line
    # fallback to 1 when there's no heading, which makes the intro check skip body
    # line 1 entirely) -- that's the checker's actual behavior, reported here rather
    # than papered over, per the fix-wave instructions not to change checker code.
    body = "This page is for people who want a thing.\n\n1. Open **Settings**.\n2. Select **Thing**.\n\nThe thing is done.\n"
    violations = check_page("docs/a.md", page("how-to", body), RULES)
    single_h1 = [v for v in violations if v.rule_id == "single_h1"]
    assert len(single_h1) == 1
    # 3 frontmatter lines + line 1 of the body (no title) = file line 4
    assert single_h1[0].line == 4


def test_two_titles():
    assert ids(check_page("docs/a.md", page("how-to", GOOD_HOW_TO + "\n# Another\n"), RULES)) == ["single_h1"]


def test_landing_page_is_exempt():
    assert check_page("docs/index.md", page("landing", "# Welcome\n\n- [A](a.md)\n"), RULES) == []


def test_code_blocks_are_ignored():
    body = GOOD_HOW_TO + "\n```\n# not a heading\n1. not a step\n```\n"
    assert check_page("docs/a.md", page("how-to", body), RULES) == []


def test_slugify():
    assert slugify("Before you start!") == "before-you-start"
