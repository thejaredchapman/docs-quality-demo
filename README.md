# Docs quality checks: a GitHub Action demo

A small help site for **Tally**, a made-up habit-tracker app, with a style guide and the automated checks that enforce it on every pull request.

- **Style guide:** [`STYLE_GUIDE.md`](STYLE_GUIDE.md), also published on the [docs site](https://thejaredchapman.github.io/docs-quality-demo/style-guide/)
- **Docs site:** https://thejaredchapman.github.io/docs-quality-demo/

The style guide is the single source of truth. The Claude reviewer's checklist and the structure rules are generated from it, and CI fails if they drift apart.

## Who checks what

| Kind of rule | Example | Checked by | Blocks the PR? |
|---|---|---|---|
| Guide sync | the checklist was edited by hand | `build_rules.py --check` | **Yes** |
| Structure | page declares a type, how-to has 7 steps or fewer, tutorial has "Next steps" | `check_structure.py`, rule-based | **Yes** |
| Word-level | "simply," "click," "e.g.," "click here" links | [Vale](https://vale.sh), rule-based | No (annotations) |
| Judgment | the intro says who the page is for, one action per step | Claude, graded against the rules for the page's type | No (advisory) |
| Product sync | docs still mention a button the code just renamed | `ui_drift.py`, diff of [`app/ui_strings.json`](app/ui_strings.json) | **Yes** |

Rules handle everything rules can do. Claude only handles the judgment calls, and its accuracy is **measured**, not assumed.

## Content types

Every page declares `type:` in its frontmatter: `tutorial`, `how-to`, `reference`, `troubleshooting`, or `landing` (the home page only). The type decides which structure rules and which Claude rules apply. Templates for each type are in [`templates/`](templates/).

## How accurate is the Claude reviewer?

[`eval/labels.json`](eval/labels.json) holds hand labels: for each page, and each Claude rule that applies to its type, does the page follow the rule? That's 62 judgments on 14 pages. The labels were made blind with [`scripts/label.py`](scripts/label.py), which never shows Claude's answers.

| Model | Agreement | Always-pass baseline | Cohen's κ | Misses | False alarms |
|---|---|---|---|---|---|
| `claude-haiku-4-5-20251001` | __% | __% | __ | __ | __ |
| `claude-sonnet-5` | __% | __% | __ | __ | __ |

Most pages follow most rules, so a "reviewer" that always says pass would already match the **always-pass baseline**. Cohen's κ measures agreement beyond that: 0 means no better than chance, and 1 means perfect. "Unknown" answers count as wrong, so neither number is inflated. n = 62 is small, so treat the numbers as directional.

## Repo layout

```
STYLE_GUIDE.md                    # the guide; the source for checklist.yaml and content_types.yaml
templates/                        # one skeleton page per content type
docs/                             # 15 sample pages, some with planted problems
checklist.yaml                    # generated: rules Claude grades
content_types.yaml                # generated: structure rules per type
app/ui_strings.json               # stand-in for product code: UI labels
eval/labels.json                  # hand labels (made with scripts/label.py)
styles/DemoDocs/                  # custom Vale rules
mkdocs.yml                        # site config; nav grouped by content type
scripts/build_rules.py            # STYLE_GUIDE.md -> generated rule files (--check in CI)
scripts/check_structure.py        # rule-based structure checks
scripts/judge.py                  # Claude grader (Anthropic SDK, forced tool use for structured output)
scripts/review_pages.py           # grades the pages changed in a PR
scripts/label.py                  # blind labeling CLI
scripts/eval_judge.py             # compares the grader to the labels: agreement, baseline, kappa
scripts/ui_drift.py               # flags docs that mention changed UI text
scripts/site_hooks.py             # publishes the style guide on the site
.github/workflows/docs-pr.yml     # every PR: sync, structure, Vale, Claude review, drift
.github/workflows/judge-eval.yml  # run by hand: measures judge accuracy
.github/workflows/deploy-site.yml # every push to main: builds and deploys the site
```

## Setup

1. Push this repo to GitHub.
2. Add a repository secret named `ANTHROPIC_API_KEY` (**Settings → Secrets and variables → Actions**).
3. Turn on the site: **Settings → Pages → Source: GitHub Actions**.
4. Open a PR from a branch in this repo. PRs from forks don't get secrets, so the Claude review would fail there.

## Run locally

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pytest                                   # no API key needed: Claude is faked in tests

python scripts/build_rules.py            # after editing STYLE_GUIDE.md
python scripts/check_structure.py
python scripts/label.py                  # make the hand labels (about 30 minutes)
mkdocs serve                             # preview the site at http://127.0.0.1:8000

export ANTHROPIC_API_KEY=...
python scripts/review_pages.py docs/dark-mode.md
python scripts/eval_judge.py --model claude-haiku-4-5-20251001 --model claude-sonnet-5
python scripts/ui_drift.py --base-ref main
vale docs                                # needs Vale installed: brew install vale && vale sync
```

## Demo PRs

1. **Style problems.** Edit `docs/streak-freeze.md` and `docs/edit-a-habit.md`. Vale flags "just," and Claude flags the missing outcome and the multi-action step.
2. **UI rename.** In `app/ui_strings.json`, change `"Save changes"` → `"Save"` and `"Cloud sync"` → `"Sync"`. The drift check fails and lists the 11 lines that need updating.
3. **Clean PR.** A small fix to `docs/delete-account.md`. Everything passes.
4. **Structure problems.** Add `docs/pause-a-habit.md` with `type: how-to`, 8 numbered steps, and a `> **Note:**` callout. The structure check fails with two annotations: `max_steps` on step 8 and `warnings_only` on the note.

## Limitations and next steps

- The drift check uses exact matching, so docs that paraphrase a label ("the save button") aren't caught. Next step: fuzzy matching, or asking Claude to confirm likely matches.
- The labels are one person's judgment. A second labeler would show how much people agree with each other, which is the ceiling for any reviewer.
- The structure check can tell that a troubleshooting page has headings, but not that they name symptoms. The guide leaves that to human review.
- Real products keep UI strings in localization files (`.json`, `.strings`, `.po`). `ui_drift.py` would need a small loader for each format.

## Credits

Style guide decisions and eval labels by Jared Chapman; drafting and code written with Claude Code. Tally is fictional.
