"""Ask Claude to grade one docs page against the style checklist.

Adapted from evalforge-lite's judge.py, but uses the Anthropic SDK directly and
forced tool use, so the answer always comes back as structured data (no regex parsing).
"""
import anthropic
import yaml

from common import REPO_ROOT

DEFAULT_MODEL = "claude-sonnet-5"
CHECKLIST_PATH = REPO_ROOT / "checklist.yaml"

SYSTEM_PROMPT = """You are a strict technical-writing reviewer.
Grade the page against each checklist item, and nothing else.
If an item doesn't apply to the page (for example, a rule about steps on a page with no steps), mark it passed.
Report every checklist item exactly once, using its id."""

# Describes the exact shape of the answer we want back.
# Claude has to "call" this tool, so the reply always has this shape.
REPORT_TOOL = {
    "name": "report_checklist",
    "description": "Report pass/fail for each style checklist item.",
    "input_schema": {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "item": {"type": "string"},     # checklist item id, e.g. "intro_audience"
                        "passed": {"type": "boolean"},  # True = the page follows the rule
                        "reason": {"type": "string"},   # one sentence explaining why
                    },
                    "required": ["item", "passed", "reason"],
                },
            }
        },
        "required": ["results"],
    },
}


def load_checklist(path=CHECKLIST_PATH):
    """Return the checklist as a list of {"id": ..., "rule": ...} dicts."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)["items"]


def format_checklist(items):
    """Turn the checklist into plain text lines for the prompt."""
    return "\n".join(f"- {item['id']}: {item['rule']}" for item in items)


def judge_page(page_text, checklist_items, model=DEFAULT_MODEL, client=None):
    """Grade one page. Returns {item_id: {"passed": True/False/None, "reason": str}}.

    "passed" is None (unknown) if the API call fails or Claude skips an item,
    so one bad reply never crashes the workflow.
    """
    if client is None:
        # Reads ANTHROPIC_API_KEY from the environment automatically
        client = anthropic.Anthropic()

    # Start with every item marked unknown, then fill in what Claude reports
    verdicts = {
        item["id"]: {"passed": None, "reason": "No answer from the judge."}
        for item in checklist_items
    }

    try:
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            temperature=0,  # makes answers more consistent from run to run
            system=SYSTEM_PROMPT,
            tools=[REPORT_TOOL],
            # Force Claude to answer through the tool instead of plain text
            tool_choice={"type": "tool", "name": "report_checklist"},
            messages=[{
                "role": "user",
                "content": f"Checklist:\n{format_checklist(checklist_items)}\n\nPage:\n{page_text}",
            }],
        )
    except anthropic.APIError as error:
        for verdict in verdicts.values():
            verdict["reason"] = f"API error: {error}"
        return verdicts

    # Find the tool call in the reply; its input is already a Python dict
    tool_call = next((block for block in response.content if block.type == "tool_use"), None)
    if tool_call is None:
        return verdicts

    for result in tool_call.input.get("results", []):
        item_id = result.get("item")
        passed = result.get("passed")
        # Ignore ids we didn't ask about, and answers that aren't a clear True/False
        if item_id in verdicts and isinstance(passed, bool):
            verdicts[item_id] = {"passed": passed, "reason": result.get("reason", "")}
    return verdicts
