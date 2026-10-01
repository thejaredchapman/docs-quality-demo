# Decisions so far: simpler core, providers, web UI, MCP (brainstorming in progress)

Not a spec yet. These are the decisions Jared made on 2026-09-30 / 2026-10-01, saved so the design can resume.

## Goal
Make docs-quality-demo easy for junior developers and tech writers: a web interface for writers, a new MCP server, one simple core underneath.

## Decided
- **MCP server:** add a new one in this repo (none exists today). It shares the core with the web UI.
- **Web UI jobs (all four):** check a page; start a new page from a template; label pages in the browser; get the AI review.
- **Providers:** users add their own credentials for Anthropic, OpenAI, OpenRouter, AWS Bedrock, Google Vertex, Microsoft Foundry. Keys stay on the user's machine.
- **Build order (4 pieces, each its own spec, plan, build):**
  1. Simple core + one command
  2. AI provider settings
  3. Web interface
  4. MCP server
- **Wording check:** built into the core (reads styles/DemoDocs/*.yml), so it works with no Vale install. CI keeps running full Vale.
- **Core structure (option A):** a `docsqa/` package installed with `pip install -e .`, one `docs-check` command (check all, check one page, `new`, `rules`, `label`, `eval`). Every problem prints file, line, what's wrong, how to fix. `scripts/` removed; CI, UI and MCP call the same functions.

## Next
Continue piece 1's design: remaining questions, then present the design section by section for approval, then write the spec.

## Note
Uncommitted local change by Jared: `temperature` removed from scripts/judge.py (newer models reject it), with its test updated. Keep it.
