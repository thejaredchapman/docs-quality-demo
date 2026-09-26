# Docs quality checks: a GitHub Action demo

Three automated checks that run on every pull request to a small sample docs site for **Tally**, a made-up habit-tracker app:

| Check | What it catches | How | Blocks the PR? |
|---|---|---|---|
| **Style lint** | Mechanical style problems: filler words, "please", heading case, Microsoft style rules | [Vale](https://vale.sh), rule-based | No (annotations) |
| **Style review** | Judgment calls a linter can't make: missing intro, prerequisites after the steps, jargon, no stated outcome | Claude, graded against [`checklist.yaml`](checklist.yaml) | No (advisory) |
| **UI text drift** | Docs that still mention a button label or setting that the code change just renamed or removed | Diff of [`app/ui_strings.json`](app/ui_strings.json), then an exact search of the docs | **Yes** |

The rule-based checks handle everything rules can do. Claude only handles the judgment calls, and its accuracy is **measured**, not assumed.

## How accurate is the Claude reviewer?

[`eval/labels.json`](eval/labels.json) holds hand labels: for each of the 15 pages and each of the 5 checklist items, does the page pass? That's 75 judgments, 13 of them failures planted on purpose. The **Judge accuracy** workflow runs Claude on every page and compares it with the labels.

| Model | Agreement with hand labels | Misses | False alarms |
|---|---|---|---|
| `claude-haiku-4-5-20251001` | __% | __ | __ |
| `claude-sonnet-5` | __% | __ | __ |

n = 75 judgments on 15 pages. That's a small sample, so treat the numbers as directional. "Unknown" answers count as disagreements, so the score is never inflated.

## Repo layout

```
.github/workflows/docs-pr.yml     # runs on every PR: Vale + Claude review + drift check
.github/workflows/judge-eval.yml  # run by hand: measures judge accuracy
docs/                             # 15 sample pages, some with planted problems
app/ui_strings.json               # stand-in for product code: UI labels
checklist.yaml                    # the style checklist Claude grades against
eval/labels.json                  # hand labels (true = page follows the rule)
styles/DemoDocs/                  # custom Vale rules
scripts/judge.py                  # Claude grader (Anthropic SDK, forced tool use for structured output)
scripts/review_pages.py           # grades the pages changed in a PR
scripts/eval_judge.py             # compares the grader to the hand labels
scripts/ui_drift.py               # flags docs that mention changed UI text
```

## Setup

1. Push this repo to GitHub.
2. Add a repository secret named `ANTHROPIC_API_KEY` (**Settings → Secrets and variables → Actions**).
3. Open a PR from a branch in this repo. PRs from forks don't get secrets, so the Claude review would fail there.

## Run locally

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pytest                                   # no API key needed: Claude is faked in tests

export ANTHROPIC_API_KEY=...
python scripts/review_pages.py docs/dark-mode.md
python scripts/eval_judge.py --model claude-haiku-4-5-20251001 --model claude-sonnet-5
python scripts/ui_drift.py --base-ref main
vale docs                                # needs Vale installed: brew install vale && vale sync
```

## Demo PRs

1. **Style problems.** Edit `docs/streak-freeze.md` and `docs/edit-a-habit.md`. Vale flags "just," and Claude flags the missing intro, the multi-action step and the missing outcome.
2. **UI rename.** In `app/ui_strings.json`, change `"Save changes"` → `"Save"` and `"Cloud sync"` → `"Sync"`. The drift check fails and lists the 11 lines that need updating.
3. **Clean PR.** A small fix to `docs/delete-account.md`. Everything passes.

## Limitations and next steps

- The drift check uses exact matching, so docs that paraphrase a label ("the save button") aren't caught. Next step: fuzzy matching, or asking Claude to confirm likely matches.
- The labels are one person's judgment. A second labeler would show how much people agree with each other, which is the ceiling for any judge.
- Real products keep UI strings in localization files (`.json`, `.strings`, `.po`). `ui_drift.py` would need a small loader for each format.
