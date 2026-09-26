"""Tests for judge.py. A fake client stands in for Claude, so no API key or network is needed."""
from types import SimpleNamespace

import anthropic
import httpx

from judge import judge_page, load_checklist

CHECKLIST = [{"id": "intro_audience", "rule": "r1"}, {"id": "outcome_stated", "rule": "r2"}]


class FakeClient:
    """Pretends to be anthropic.Anthropic(): returns a canned reply or raises an error."""

    def __init__(self, tool_input=None, error=None):
        self.tool_input = tool_input
        self.error = error
        self.last_request = None
        self.messages = self  # so code can call client.messages.create(...)

    def create(self, **kwargs):
        self.last_request = kwargs
        if self.error:
            raise self.error
        return SimpleNamespace(content=[SimpleNamespace(type="tool_use", input=self.tool_input)])


def test_returns_verdict_for_each_item():
    client = FakeClient(tool_input={"results": [
        {"item": "intro_audience", "passed": True, "reason": "Says who it's for."},
        {"item": "outcome_stated", "passed": False, "reason": "Ends after the steps."},
    ]})
    verdicts = judge_page("# Page", CHECKLIST, client=client)
    assert verdicts["intro_audience"]["passed"] is True
    assert verdicts["outcome_stated"] == {"passed": False, "reason": "Ends after the steps."}


def test_forces_the_report_tool():
    client = FakeClient(tool_input={"results": []})
    judge_page("# Page", CHECKLIST, client=client)
    assert client.last_request["tool_choice"] == {"type": "tool", "name": "report_checklist"}
    assert client.last_request["temperature"] == 0


def test_skipped_and_unexpected_items():
    client = FakeClient(tool_input={"results": [
        {"item": "intro_audience", "passed": True, "reason": "ok"},
        {"item": "made_up_item", "passed": False, "reason": "?"},
    ]})
    verdicts = judge_page("# Page", CHECKLIST, client=client)
    assert set(verdicts) == {"intro_audience", "outcome_stated"}
    assert verdicts["outcome_stated"]["passed"] is None  # skipped -> unknown


def test_api_error_marks_everything_unknown():
    error = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
    verdicts = judge_page("# Page", CHECKLIST, client=FakeClient(error=error))
    assert all(v["passed"] is None for v in verdicts.values())


def test_real_checklist_loads():
    ids = [item["id"] for item in load_checklist()]
    assert "intro_audience" in ids
