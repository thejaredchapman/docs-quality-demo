# Docs quality checks: a GitHub Action demo

Help docs written by many people drift. The style guide says one thing, the pages do another, and a button gets renamed in the app while five pages still mention the old name. Usually a reader finds it first.

This repo is a small, working version of the fix. It's a help site for **Tally**, a made-up habit-tracker app, with a style guide and a set of automated checks that run on every pull request. The style guide is the single source of truth: the checks are generated from it, so the rules people read and the rules CI enforces can't disagree.

- **Docs site:** https://thejaredchapman.github.io/docs-quality-demo/
- **Style guide:** [`STYLE_GUIDE.md`](STYLE_GUIDE.md), also on the [docs site](https://thejaredchapman.github.io/docs-quality-demo/style-guide/), where each rule shows which check enforces it

## What happens on a pull request

When someone opens a PR that touches the docs, 6 checks run:

| Check | What it catches | How | Blocks the PR? |
|---|---|---|---|
| Guide sync | Someone edited the generated rule files by hand, or changed the guide without regenerating them | `build_rules.py --check` | **Yes** |
| Page structure | A page with no content type, a how-to with more than 7 steps, a tutorial with no "Next steps" section | `check_structure.py`, rule-based | **Yes** |
| Unit tests | A change that breaks the checking scripts themselves | `pytest` on Python 3.9 | **Yes** |
| Wording | "simply," "click," "e.g.," link text that says "here" | [Vale](https://vale.sh), rule-based | No, it comments on the lines |
| Judgment | An intro that doesn't say who the page is for, a step that asks for two actions | Claude, graded only against the rules for that page's type | No, it's advice |
| UI drift | Docs that still mention a button or setting the app just renamed | `ui_drift.py`, diff of [`app/ui_strings.json`](app/ui_strings.json) | **Yes** |

Anything a rule can catch goes to a rule-based check, which is free and instant. Claude only gets the judgment calls, and how often it agrees with a human is **measured** (see [How accurate is the Claude reviewer?](#how-accurate-is-the-claude-reviewer)).

## Who can use this

Tally is fictional, but the setup works for any docs that live in a Git repo as Markdown. Here's where each part earns its keep.

### For businesses

- **Product teams shipping UI changes every week.** Point the UI drift check at your app's string file. When a PR renames "Save changes" to "Save," it fails and lists every help page that still says the old name, before customers see them.
- **Help centers written by many teams.** Give each kind of article a template and a content type. The structure check keeps a how-to from turning into a 15-step essay, and keeps troubleshooting pages organized by the symptom the customer sees.
- **Developer and API docs.** Encode your house style (voice, banned words, link text) as Vale rules, so reviewers stop leaving the same 5 comments on every PR.
- **Internal runbooks and onboarding guides.** The "prerequisites before the steps" and "one action per step" rules are the ones that matter most at 2 a.m. during an incident.
- **Regulated or audited teams.** Every docs change passes the same documented checks, and the PR history shows it. The style guide says which check enforces each rule, which is easy to hand an auditor.
- **Docs headed for translation.** Rules against "e.g.," "i.e.," and minimizers like "simply" keep the source English plain, which makes translation cheaper and more accurate.
- **Teams deciding whether to trust an AI reviewer.** The labeling tools and the accuracy report work for any AI grader. Label a sample by hand, measure agreement and κ against the always-pass baseline, then decide how much to rely on it.

### For individuals

- **Open-source maintainers.** Contributors get consistent feedback on their docs PRs automatically, so your review time goes to the content.
- **Writers and bloggers.** Turn your own writing habits into Vale rules (the words you overuse, the phrases you've banned) and check every post before you publish.
- **Indie developers and side projects.** Keep your app's help pages in sync with its UI on your own, with no docs team.
- **People learning to evaluate AI.** Label 62 small judgments, run the comparison, and read where the model disagreed with you. It's a hands-on way to learn what agreement, baselines, and Cohen's κ actually tell you.
- **Job seekers and students.** Fork it as a docs-as-code portfolio piece: write your own style guide, and show that the checks enforce it.

### Adapting it to your docs

1. Replace the pages in `docs/` with yours, and give each one a `type:`.
2. Rewrite `STYLE_GUIDE.md` with your rules, then run `python scripts/build_rules.py`.
3. Point the drift check at your UI strings: change `STRINGS_PATH` at the top of `scripts/ui_drift.py`. It expects a flat JSON file of `"key": "label"` pairs, like [`app/ui_strings.json`](app/ui_strings.json).
4. Update the `nav:` in `mkdocs.yml`.
5. Relabel with `scripts/label.py` or `scripts/review_sheet.py`, then run the comparison, so the accuracy numbers describe your docs and your rules.

## How to use it

### Set up locally (once)

```bash
git clone https://github.com/thejaredchapman/docs-quality-demo.git
cd docs-quality-demo
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pytest                      # no API key needed: Claude is faked in the tests
```

Optional: install Vale with `brew install vale`, then run `vale sync` once.

### Write or edit a page

1. Start from the template for the kind of page you're writing, in [`templates/`](templates/). Not sure which? See [Content types](#content-types).
2. Keep the `type:` line at the top. It decides which rules apply.
3. Check your page before you open a PR:

   ```bash
   python scripts/check_structure.py docs/your-page.md   # structure: must pass
   vale docs/your-page.md                                # wording: fix what it flags
   mkdocs serve                                          # preview at http://127.0.0.1:8000
   ```

4. If you add a new page, add it to the `nav:` in `mkdocs.yml`, under the group for its type.

### Change a style rule

1. Edit [`STYLE_GUIDE.md`](STYLE_GUIDE.md). Each rule has a tag on the line above it, like `<!-- rule id=max_steps check=structure types=how-to max_steps=7 -->`, which says which check enforces it and which page types it applies to.
2. Regenerate the rule files, and commit them with the guide:

   ```bash
   python scripts/build_rules.py    # rewrites checklist.yaml and content_types.yaml
   ```

If you skip step 2, the guide-sync check fails the PR and tells you to run it.

### Measure the Claude reviewer

This is how you find out whether Claude's style advice can be trusted. You label the pages yourself, then compare Claude's answers with yours. Neither labeling tool ever shows you Claude's answers.

**1. Label the pages.** There are 62 questions: each page, against each Claude rule that applies to its type. Pick one way:

- **One question at a time, in the terminal:**

  ```bash
  python scripts/label.py
  ```

  Each page is shown once, then its rules one at a time. Press `y` if the page follows the rule, or `n` if it breaks it. Your answers save as you go. Press `q` to stop and run it again later to continue.

- **Every page in one file:**

  ```bash
  python scripts/review_sheet.py export    # writes eval/review-sheet.md
  ```

  Open `eval/review-sheet.md`. Every rule starts checked ("the page follows it"). Read each page and uncheck any rule it breaks, then save and run:

  ```bash
  python scripts/review_sheet.py import    # writes eval/labels.json
  ```

  The import records that the labels came from the review sheet, so anyone reading the numbers knows how they were made.

**2. Run the comparison** (needs an API key; a full run is 14 short API calls per model):

```bash
export ANTHROPIC_API_KEY=...
python scripts/eval_judge.py --model claude-haiku-4-5-20251001 --model claude-sonnet-5
```

The report shows agreement, the always-pass baseline, Cohen's κ, and every question where Claude and you disagreed, with Claude's reasoning. If you change the rules after labeling, the comparison refuses to run until you relabel, because the old answers no longer match the questions.

### Run it on your own copy of the repo

1. Fork or push the repo to GitHub.
2. Add a repository secret named `ANTHROPIC_API_KEY`: **Settings → Secrets and variables → Actions**.
3. Turn on the site: **Settings → Pages → Source: GitHub Actions**. It redeploys on every push to `main`.
4. Open PRs from branches in the same repo. PRs from forks don't get secrets, so the Claude review can't run on them.

## Content types

Every page declares one type at the top:

| Type | Use it when the reader wants to... | Example |
|---|---|---|
| `tutorial` | learn by doing one thing from start to finish | [Get started with Tally](docs/getting-started.md) |
| `how-to` | finish one specific task | [Turn on dark mode](docs/dark-mode.md) |
| `reference` | look something up | [Keyboard shortcuts](docs/keyboard-shortcuts.md) |
| `troubleshooting` | fix something that went wrong | [Sync problems](docs/troubleshooting-sync.md) |
| `landing` | find their way around (the home page only) | [Home](docs/index.md) |

The type decides which structure rules and which Claude rules apply. For example, only how-tos have the 7-step limit, and reference pages can't have numbered steps.

## How accurate is the Claude reviewer?

**Status: labeling in progress.** The table below fills in once the hand labels are done.

The answer key is `eval/labels.json`: for each page, and each Claude rule that applies to its type, does the page follow the rule? That's 62 judgments on 14 pages.

Some pages break the style guide on purpose, so every check has something real to catch. They aren't listed here, so the hand labels stay blind.

| Model | Agreement | Always-pass baseline | Cohen's κ | Misses | False alarms |
|---|---|---|---|---|---|
| `claude-haiku-4-5-20251001` | __% | __% | __ | __ | __ |
| `claude-sonnet-5` | __% | __% | __ | __ | __ |

How to read it:

- **Agreement:** how often Claude's answer matched the hand label.
- **Always-pass baseline:** most pages follow most rules, so a "reviewer" that always says pass would already score this. Claude's agreement only means something above it.
- **Cohen's κ:** agreement beyond chance. 0 means no better than guessing, and 1 means perfect.
- **Misses:** the page broke the rule and Claude said it passed. **False alarms:** the opposite.

When Claude gives no answer, it counts as wrong, so none of these numbers are inflated. n = 62 is small, so treat them as directional.

## Demo PRs

Four PRs that show each check doing its job:

1. **Style problems.** Edit `docs/streak-freeze.md` and `docs/edit-a-habit.md`. Vale flags "just," and Claude flags the missing outcome, the multi-action step, and the intro that doesn't say who the page is for.
2. **UI rename.** In `app/ui_strings.json`, change `"Save changes"` → `"Save"` and `"Cloud sync"` → `"Sync"`. The drift check fails and lists the 11 lines that need updating.
3. **Clean PR.** A small fix to `docs/delete-account.md`. Everything passes.
4. **Structure problems.** Add `docs/pause-a-habit.md` with `type: how-to`, 8 numbered steps, and a `> **Note:**` callout. The structure check fails with two annotations: `max_steps` on step 8 and `warnings_only` on the note.

## Repo layout

```
STYLE_GUIDE.md                    # the guide; the source for checklist.yaml and content_types.yaml
templates/                        # one skeleton page per content type
docs/                             # 15 sample pages, some with planted problems
checklist.yaml                    # generated: rules Claude grades
content_types.yaml                # generated: structure rules per type
app/ui_strings.json               # stand-in for product code: UI labels
eval/labels.json                  # hand labels (the answer key)
styles/DemoDocs/                  # custom Vale rules
mkdocs.yml                        # site config; nav grouped by content type
scripts/build_rules.py            # STYLE_GUIDE.md -> generated rule files (--check in CI)
scripts/check_structure.py        # rule-based structure checks
scripts/judge.py                  # Claude grader (Anthropic SDK, forced tool use for structured output)
scripts/review_pages.py           # grades the pages changed in a PR
scripts/label.py                  # labeling, one question at a time
scripts/review_sheet.py           # labeling, every page in one editable file
scripts/eval_judge.py             # compares Claude with the labels: agreement, baseline, kappa
scripts/ui_drift.py               # flags docs that mention changed UI text
scripts/site_hooks.py             # publishes the style guide on the site
.github/workflows/docs-pr.yml     # every PR: sync, structure, tests, Vale, Claude review, drift
.github/workflows/judge-eval.yml  # run by hand: measures Claude's accuracy
.github/workflows/deploy-site.yml # every push to main: builds and deploys the site
```

## Limitations and next steps

- The drift check uses exact matching, so docs that paraphrase a label ("the save button") aren't caught. Next step: fuzzy matching, or asking Claude to confirm likely matches.
- The labels are one person's judgment. A second labeler would show how much people agree with each other, which is the ceiling for any reviewer.
- The structure check can tell that a troubleshooting page has headings, but not that they name symptoms. The guide leaves that to human review.
- Real products keep UI strings in localization files (`.json`, `.strings`, `.po`). `ui_drift.py` would need a small loader for each format.

## Credits

Style guide decisions and eval labels by Jared Chapman; drafting and code written with Claude Code. Tally is fictional.
