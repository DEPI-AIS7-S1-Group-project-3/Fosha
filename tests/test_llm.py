"""Retry behaviour of agents.llm.generate, with the Gemini call and sleep mocked out."""
import os
from unittest import mock

from agents import llm

ENV = {"GEMINI_API_KEY": "test-key"}


def run(side_effect):
    with mock.patch.dict(os.environ, ENV), \
            mock.patch("agents.llm._call_gemini", side_effect=side_effect) as call, \
            mock.patch("agents.llm.time.sleep") as sleep:
        result = llm.generate("hi")
    return result, call.call_count, sleep.call_count


def test_transient_error_is_retried_then_succeeds():
    result, calls, sleeps = run([RuntimeError("503 UNAVAILABLE high demand"), "hello"])
    assert result["ok"] and result["text"] == "hello" and calls == 2 and sleeps == 1


def test_gives_up_after_max_attempts():
    result, calls, _ = run(RuntimeError("503 UNAVAILABLE"))
    assert result["ok"] is False and calls == llm.MAX_ATTEMPTS


def test_permanent_error_is_not_retried():
    result, calls, sleeps = run(RuntimeError("404 NOT_FOUND model retired"))
    assert result["ok"] is False and calls == 1 and sleeps == 0


def test_empty_response_is_an_error():
    result, calls, _ = run([""])
    assert result["ok"] is False and "empty" in result["error"]