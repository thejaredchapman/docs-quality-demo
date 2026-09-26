import json

from label import label_loop, pending

PAIRS = [("a.md", "x"), ("a.md", "y"), ("b.md", "x")]


def run(answers, labels=None, seed=0):
    answers = iter(answers)
    shown, saves = [], []
    result = label_loop(
        PAIRS,
        {} if labels is None else labels,
        show=lambda page, rule_id, done, total: shown.append((page, rule_id)),
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
