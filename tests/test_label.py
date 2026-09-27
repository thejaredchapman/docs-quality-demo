import json

from label import INTRO, label_loop, pending, progress_summary, read_answer, VALID_ANSWERS

PAIRS = [("a.md", "x"), ("a.md", "y"), ("b.md", "x")]


def run(answers, labels=None, seed=0):
    answers = iter(answers)
    shown, saves = [], []
    result = label_loop(
        PAIRS,
        {} if labels is None else labels,
        show=lambda page, rule_id, done, total, rule_number, rule_count: shown.append((page, rule_id)),
        ask=lambda: next(answers),
        save=lambda current: saves.append(json.dumps(current, sort_keys=True)),
        seed=seed,
    )
    return result, shown, saves


def count(labels):
    return sum(len(items) for items in labels.values())


def test_labels_every_pair_and_saves_after_each_answer():
    result, shown, saves = run(["y", "n", "y"])
    assert sorted(shown) == sorted(PAIRS)
    assert count(result) == 3
    assert len(saves) == 3


def test_quit_keeps_what_was_answered():
    result, _, saves = run(["y", "q"])
    assert count(result) == 1
    assert len(saves) == 1


def test_skip_leaves_the_pair_unlabeled():
    result, _, _ = run(["s", "y", "y"])
    assert len(pending(PAIRS, result)) == 1


def test_resume_only_asks_about_what_is_left():
    result, shown, _ = run(["n"], labels={"a.md": {"x": True, "y": True}})
    assert shown == [("b.md", "x")]
    assert result["b.md"]["x"] is False


def test_invalid_answer_asks_again():
    result, shown, _ = run(["maybe", "y", "y", "y"])
    assert len(shown) == 3
    assert count(result) == 3


def test_order_is_shuffled_but_repeatable():
    _, first, _ = run(["y", "y", "y"], seed=1)
    _, second, _ = run(["y", "y", "y"], seed=1)
    assert first == second


def test_read_answer_returns_q_on_eof():
    def mock_input(prompt):
        raise EOFError()
    assert read_answer(prompt_fn=mock_input) == "q"


def test_read_answer_extracts_first_lowercase_char():
    def mock_input(prompt):
        return "  Yes "
    assert read_answer(prompt_fn=mock_input) == "y"


def test_each_page_is_shown_once_with_all_its_rules_in_a_row():
    _, shown, _ = run(["y", "y", "y"], seed=3)
    pages = [page for page, _ in shown]
    # No page comes back after another page has been shown
    assert pages in (["a.md", "a.md", "b.md"], ["b.md", "a.md", "a.md"])


def test_show_numbers_the_rules_within_a_page():
    calls = []
    label_loop(
        PAIRS, {},
        show=lambda page, rule_id, done, total, rule_number, rule_count: calls.append((page, rule_number, rule_count)),
        ask=lambda: "y", save=lambda current: None, seed=0,
    )
    assert [(n, c) for page, n, c in calls if page == "a.md"] == [(1, 2), (2, 2)]
    assert [(n, c) for page, n, c in calls if page == "b.md"] == [(1, 1)]


def test_resume_counts_only_the_rules_left_on_a_page():
    calls = []
    label_loop(
        PAIRS, {"a.md": {"x": True}},
        show=lambda page, rule_id, done, total, rule_number, rule_count: calls.append((page, rule_id, rule_number, rule_count)),
        ask=lambda: "y", save=lambda current: None, seed=0,
    )
    assert ("a.md", "y", 1, 1) in calls


def test_prompt_says_what_yes_means():
    seen = []
    read_answer(prompt_fn=lambda prompt: seen.append(prompt) or "y")
    assert "follows" in seen[0] and "breaks" in seen[0]
    assert VALID_ANSWERS == ("y", "n", "s", "q")


def test_intro_explains_that_questions_do_not_repeat():
    assert "different rule" in INTRO
    assert "y = it follows the rule" in INTRO and "n = it breaks the rule" in INTRO


def test_progress_summary_states_the_question_count():
    assert progress_summary(PAIRS, {}) == "There are 3 questions in total, across 2 pages."
    assert progress_summary(PAIRS, {"a.md": {"x": True}}) == (
        "There are 3 questions in total, across 2 pages. You've answered 1, so 2 are left."
    )
