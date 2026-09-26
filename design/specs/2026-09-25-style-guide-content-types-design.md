# Design: Style guide, content types, and a measured Claude reviewer

**Date:** 2026-09-25
**Status:** Approved in brainstorming; pending written-spec review

## Goal

Extend the existing Tally docs-quality demo so it shows both halves of a docs-engineering job: **writing the standards** and **building the system that enforces them**. The style guide is the single source of truth. The Claude reviewer's checklist is generated from it, and CI fails if the two drift apart.

Target audience: reviewers of an application for Anthropic's "Technical Documentation and Content Engineer, Claude Docs" role. The JD asks for information architecture, a style guide, "a standard set of content types", AI-assisted review, and quality guardrails.

## Decisions (made by Jared)

| Topic | Decision |
|---|---|
| Guide ↔ checklist | Style guide is the single source; checklist is generated; CI checks sync |
| Content types | Declared in frontmatter and enforced by a rule-based check |
| Authorship | Jared makes each style decision; Claude drafts prose; README states this |
| Voice | Second person ("you"); steps start with a verb |
| Headings | Sentence case; task headings start with a verb |
| UI labels | Bold, exact on-screen text |
| Callouts | Warnings only for data loss or actions that can't be undone; no other notes |
| Banned words | just / simply / easily; please; e.g. / i.e. / etc.; click |
| Verb for UI actions | "select" (works on phone and web); replaces "tap" and "click" |
| Step limit | Max 7 numbered steps per how-to |
| Links | Link text describes the target; never "click here" / "here" |
| Content types | Tutorial, How-to, Reference, Troubleshooting; `landing` for index, exempt |
| Site | MkDocs on GitHub Pages, nav grouped by content type |
| Labels | Jared relabels blind with a CLI tool |

## Repo changes

```
STYLE_GUIDE.md                 NEW   the guide; also published on the site
templates/                     NEW   one skeleton per type: how-to.md, tutorial.md, reference.md, troubleshooting.md
docs/*.md                      EDIT  add frontmatter `type:`; "tap" → "select"
checklist.yaml                 GEN   from STYLE_GUIDE.md; header "Generated — do not edit"
content_types.yaml             GEN   required structure per type, from STYLE_GUIDE.md
scripts/build_rules.py         NEW   STYLE_GUIDE.md → checklist.yaml + content_types.yaml; --check mode for CI
scripts/check_structure.py     NEW   rule-based type/section/step checks
scripts/label.py               NEW   blind labeling CLI
scripts/judge.py               EDIT  sends only the rules that apply to the page's type
scripts/eval_judge.py          EDIT  skips non-applicable pairs; adds baseline + Cohen's kappa
styles/DemoDocs/*.yml          EDIT  add rules: Minimizers, Latin, Click, LinkText (existing Filler/Please/HeadingCase kept or merged)
mkdocs.yml                     NEW   site config and nav
.github/workflows/docs-pr.yml  EDIT  add sync check and structure check
.github/workflows/deploy-site.yml NEW build MkDocs, deploy to GitHub Pages on push to main
README.md                      EDIT  enforcement table, accuracy table with new columns, provenance line, 4th demo PR
```

## Enforcement split

| Kind of rule | Example | Enforced by | Blocks PR? |
|---|---|---|---|
| Word-level | no "simply", no "click", no "e.g." | Vale | No (annotations) |
| Structural | type declared, required sections, ≤7 steps | `check_structure.py` | Yes |
| Judgment | intro states audience, one action per step | Claude, accuracy measured | No (advisory) |
| Product sync | docs mention a renamed UI label | `ui_drift.py` | Yes |
| Guide sync | checklist differs from the guide | `build_rules.py --check` | Yes |

## Style guide format

Sections, in order: Who this is for · Voice · Headings · UI labels · Words to avoid · Links · Callouts · Content types · How these rules are checked.

Each rule is preceded by a tag comment and followed by a one-line *Why:*:

```markdown
<!-- rule id=prereqs_first check=claude types=how-to,tutorial -->
**Put prerequisites before the steps.** Anything the reader needs before starting
(an account, a permission, a setting turned on) goes in the intro or a
"Before you start" section, never during or after the steps.

*Why:* a reader who finds out at step 4 that they needed an account has wasted three steps.
```

Tag grammar: `<!-- rule id=<snake_case> check=<vale|structure|claude|drift> [types=<comma list>] -->`.
- `types` is omitted to mean "all four types".
- The rule text is the first paragraph after the tag. For `claude` rules, the bold sentence plus the rest of that paragraph becomes the checklist `rule:` text.
- `structure` rules carry their machine parameters in the tag instead of prose, e.g. `<!-- rule id=max_steps check=structure types=how-to max_steps=7 -->`.
- `vale` and `drift` rules are documentation only. `build_rules.py` validates their tags but emits nothing for them.
- The MkDocs page renders a small "Checked by: {check}" label for each rule (a tiny MkDocs hook or a CSS rule on a generated span; implementation detail left to the plan).

Draft *Why:* lines are written by Claude. Jared reviews and rewrites any he wouldn't say himself.

## Content types

| Type | Pages | Required structure (structure check) | Claude rules that apply |
|---|---|---|---|
| how-to | change-password, cloud-sync, create-a-habit, dark-mode, delete-account, edit-a-habit, export-data, reminders, share-progress, streak-freeze | intro paragraph before the first list · a numbered list · ≤7 steps | intro_audience, prereqs_first, one_action_per_step, no_undefined_jargon, outcome_stated |
| tutorial | getting-started | intro · `## Before you start` · numbered steps · `## Next steps` | same 5 |
| reference | keyboard-shortcuts, faq | intro · no numbered lists | intro_audience, no_undefined_jargon |
| troubleshooting | troubleshooting-sync | intro · one or more `##` headings, each naming a symptom | intro_audience, one_action_per_step, no_undefined_jargon |
| landing | index | none (exempt) | none |

Total judgments: 10×5 + 1×5 + 2×2 + 1×3 = **62**.

The five Claude rules keep their current ids and wording so the existing planted failures still apply.

Structure check also enforces, for all non-landing pages: frontmatter `type` present and one of the known types; exactly one H1.

## Labeling (`scripts/label.py`)

- Iterates the 62 applicable (page, rule) pairs in a random order seeded per session.
- Shows page text and one rule. Input: `y` = follows the rule, `n` = breaks it, `s` = skip, `q` = save and quit.
- Never displays Claude output or any existing label values.
- Resumable: already-answered pairs are skipped on the next run.
- Writes `eval/labels.json`:
  ```json
  {
    "meta": {"labeler": "Jared Chapman", "date": "2026-09-26", "rules_hash": "<sha256 of checklist.yaml + content_types.yaml>"},
    "labels": {"dark-mode.md": {"intro_audience": false, "...": true}}
  }
  ```
- The old `eval/labels.json` is moved to `eval/labels.previous.json` and not used by the eval.

## Accuracy report (`scripts/eval_judge.py`)

- Evaluates only applicable pairs that have a label.
- Warns and exits non-zero if `rules_hash` in labels differs from the current rules (labels are stale).
- Per model it reports agreement %, always-pass baseline %, Cohen's κ, misses (labeled fail, judged pass), false alarms (labeled pass, judged fail), and unknowns.
- "Unknown" answers count as disagreements.
- README accuracy table gains the baseline and κ columns and states n and the labeler.

## CI (`docs-pr.yml`) order

1. `python scripts/build_rules.py --check` — fail if generated files differ from committed ones.
2. `python scripts/check_structure.py docs` — fail on violations; emit GitHub `::error file=...,line=...::` annotations.
3. Vale on changed docs — annotations only.
4. Claude review on changed docs, scoped by type — advisory. An API error prints "review unavailable" and does not fail the job.
5. `python scripts/ui_drift.py` — fail on drift (existing).

`deploy-site.yml`: on push to `main`, `mkdocs build` and deploy to GitHub Pages. `STYLE_GUIDE.md` is included in the site nav.

## Demo PRs (README)

1. Style problems (existing).
2. UI rename (existing).
3. Clean PR (existing).
4. **New:** add a how-to with 8 steps and no `type:`; the structure check fails with two annotations.

## Error handling

- `build_rules.py` fails with a clear message on: duplicate rule id, unknown `check`, unknown type in `types`, a tag with no following paragraph, a `structure` rule with a parameter the structure checker doesn't understand.
- `check_structure.py` reports every violation, not only the first.
- `label.py` writes after every answer, so a crash loses at most one answer.

## Testing

Pytest, no API key needed (Claude is faked, as today):
- rule extraction: tags parsed, types defaulting, each error case above
- sync check: detects a hand-edited `checklist.yaml`
- structure check: each type's pass case and each failure (missing type, unknown type, missing section, 8 steps, numbered list on reference page)
- judge scoping: a reference page is sent only its 2 rules
- eval: non-applicable pairs skipped; κ and baseline computed correctly on a small fixed example; stale-hash warning
- label.py: save, resume, skip
- all 13 existing tests still pass

## Publishing and provenance

- `git init` locally; public GitHub repo `thejaredchapman/docs-quality-demo`; GitHub Pages for the site. **Nothing is pushed without Jared's explicit go-ahead.**
- README line: "Style guide decisions and eval labels by Jared Chapman; drafting and code written with Claude Code."
- All content is the fictional Tally app. No AbbVie material.

## Out of scope

- Fuzzy/paraphrase matching in the drift check (already listed as a next step in the README).
- A second labeler for inter-rater agreement (listed as a next step).
- Search analytics or reader-feedback widgets on the site.

## Jared's manual steps

1. Review and rewrite *Why:* lines in the style guide.
2. Run `python scripts/label.py` (~30 minutes).
3. Run the accuracy eval once with an API key and paste the numbers into the README.
4. Approve the GitHub push and add the `ANTHROPIC_API_KEY` secret.
