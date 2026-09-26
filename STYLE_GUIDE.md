# Tally docs style guide

This guide is for anyone on a Tally product team who writes or edits a help page. Follow it and your page will read like every other page on the site, and it will pass the automated checks on your pull request.

Each rule says what to do, why, and which check enforces it. A few pieces of guidance have no automated check. Reviewers catch those.

## Voice

<!-- rule id=address_reader check=vale -->
**Talk to the reader as "you," never as "we."** Write "You can export your history," not "We let you export your history" or "The user can export their history."

*Why:* the reader is the one doing the task. "We" puts the company in the sentence, and "the user" puts a stranger there.

Start every step with a verb: "Select **Save changes**," not "Now you'll want to select **Save changes**." Reviewers check this one by eye.

## Headings

<!-- rule id=single_h1 check=structure types=tutorial,how-to,reference,troubleshooting,landing -->
**Give each page exactly one title (`#` heading).**

*Why:* the title is what search results and the sidebar show. Two titles means the page is really two pages.

<!-- rule id=heading_case check=vale -->
**Write headings in sentence case, and start task headings with a verb.** Write "Turn on dark mode," not "Turn On Dark Mode" or "Dark mode settings."

*Why:* sentence case is faster to scan, and a verb tells the reader the page is about doing something.

## UI labels

<!-- rule id=ui_labels_bold check=drift -->
**Put button, menu, and setting names in bold, spelled exactly as they appear on screen.** Write "Select **Save changes**," with the same capitalization the app uses.

*Why:* the reader is matching your words to their screen. Exact text also lets the UI drift check find every page that mentions a label when the app renames it.

## Words to avoid

<!-- rule id=minimizers check=vale -->
**Don't write "just," "simply," or "easily."**

*Why:* if the reader is stuck, these words tell them the problem is them.

<!-- rule id=no_please check=vale -->
**Don't write "please" in instructions.**

*Why:* instructions are clearer without it, and it gives the reader nothing to act on.

<!-- rule id=no_latin check=vale -->
**Write "for example," "that is," and "and so on," not "e.g.," "i.e.," and "etc."**

*Why:* plain English is easier for readers whose first language isn't English, and easier to translate.

<!-- rule id=select_not_click check=vale -->
**Write "select," not "click" or "tap."**

*Why:* Tally runs on phones and on the web. "Select" is right on both, so one page works for everyone.

## Links

<!-- rule id=link_text check=vale -->
**Make link text say where the link goes.** Write "See `[Turn on cloud sync](cloud-sync.md)`," not "Select `[here](cloud-sync.md)`."

*Why:* screen readers can list a page's links on their own, and a list of "here, here, here" is useless. People who skim read the links first.

## Callouts

<!-- rule id=warnings_only check=structure -->
**Use a callout only to warn about data loss or an action that can't be undone, and make it a warning.** Everything else, including tips and notes, goes in the text.

*Why:* when every page has a few notes, readers learn to skip them, and then they skip the one warning that mattered.

Write a warning like this:

```markdown
!!! warning
    Deleting your account can't be undone.
```

The structure check makes sure every callout is a warning. Whether the warning is deserved is a reviewer's call.

## Content types

Every page declares its type at the top:

```yaml
---
type: how-to
---
```

<!-- rule id=type_declared check=structure types=tutorial,how-to,reference,troubleshooting,landing -->
**Declare one of these types in the page's frontmatter: `tutorial`, `how-to`, `reference`, `troubleshooting`, or `landing`.**

*Why:* the type decides which rules apply, so a page with no type can't be checked.

Only the home page uses `landing`, and it's exempt from the rules below.

| Type | Use it when the reader wants to... | Example | Template |
| --- | --- | --- | --- |
| Tutorial | learn Tally by doing one thing from start to finish | Get started with Tally | [tutorial.md](https://github.com/thejaredchapman/docs-quality-demo/blob/main/templates/tutorial.md) |
| How-to | finish one specific task | Turn on dark mode | [how-to.md](https://github.com/thejaredchapman/docs-quality-demo/blob/main/templates/how-to.md) |
| Reference | look something up | Keyboard shortcuts | [reference.md](https://github.com/thejaredchapman/docs-quality-demo/blob/main/templates/reference.md) |
| Troubleshooting | fix something that went wrong | Troubleshoot sync problems | [troubleshooting.md](https://github.com/thejaredchapman/docs-quality-demo/blob/main/templates/troubleshooting.md) |

If a page seems to need two types, it's two pages.

### Every page

<!-- rule id=intro_first check=structure -->
**Start with an intro paragraph between the title and anything else.**

*Why:* a page that opens with step 1 never tells the reader whether they're in the right place.

<!-- rule id=intro_audience check=claude -->
**The first paragraph says who the page is for or what the reader will accomplish.**

*Why:* readers decide in one sentence whether to keep reading. An intro that only describes the feature doesn't help them decide.

<!-- rule id=no_undefined_jargon check=claude -->
**Technical terms and acronyms a non-technical user wouldn't know are explained or avoided.**

*Why:* Tally's readers are building habits, not studying software. "OAuth" means nothing to most of them.

### Tutorials and how-tos

<!-- rule id=numbered_steps check=structure types=tutorial,how-to -->
**Write the task as numbered steps.**

*Why:* numbers let the reader keep their place when they look away to the app.

<!-- rule id=prereqs_first check=claude types=how-to,tutorial -->
**Anything the reader needs before starting (an account, a permission, a setting turned on) is stated before the steps, not during or after them.**

*Why:* a reader who finds out at step 4 that they needed an account has wasted three steps.

In a how-to, put prerequisites in the intro, or in a `## Before you start` section if there's more than one. In a tutorial, always use a `## Before you start` section.

<!-- rule id=one_action_per_step check=claude types=how-to,tutorial,troubleshooting -->
**Each numbered step asks the reader to do exactly one thing.**

*Why:* a step with three actions is where readers lose their place and skip one.

<!-- rule id=outcome_stated check=claude types=how-to,tutorial -->
**After the steps, the page tells the reader what happens or how to tell that it worked.**

*Why:* without it, the reader can't tell success from a silent failure.

### How-tos

<!-- rule id=max_steps check=structure types=how-to max_steps=7 -->
**Keep a how-to to 7 steps or fewer.**

*Why:* past 7 steps it's usually two tasks. Split it, or give the setup its own page.

### Tutorials

<!-- rule id=required_sections check=structure types=tutorial sections=before-you-start,next-steps -->
**Include a `## Before you start` section and a `## Next steps` section.**

*Why:* a tutorial is often a reader's first page. Tell them what to have ready, and where to go when they finish.

### Reference

<!-- rule id=no_numbered_lists check=structure types=reference -->
**Don't put numbered steps on a reference page.**

*Why:* reference is for looking things up. If the reader has to do something, that's a how-to, so link to it.

### Troubleshooting

<!-- rule id=symptom_headings check=structure types=troubleshooting -->
**Give each problem a `##` heading that describes what the reader sees.** Write "Your habits are different on each device," not "Force a sync."

*Why:* readers arrive with a symptom, not a fix. They scan for what's happening to them.

The structure check makes sure the headings exist. Whether they name symptoms is a reviewer's call.

## How these rules are checked

| Kind of rule | Example | Checked by | Blocks a pull request? |
| --- | --- | --- | --- |
| Word-level | no "simply," no "click" | Vale | No, it adds comments |
| Structure | type declared, 7 steps or fewer | Structure check | Yes |
| Judgment | the intro says who the page is for | Claude review | No, it gives advice |
| Product sync | a page mentions a renamed button | UI drift check | Yes |

Claude only reviews the judgment rules, and only the ones for the page's type. How often it agrees with a human reviewer is measured and published in the project README.

This guide is also the source for those checks. To change a rule, edit this file and run `python scripts/build_rules.py`. The pull request check fails if the generated files don't match the guide.
