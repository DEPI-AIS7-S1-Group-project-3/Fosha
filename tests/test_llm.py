"""Retry behaviour of agents.llm.generate, with the Gemini call and sleep mocked out."""
import os
from unittest import mock

from agents import llm

ENV = {"LLM_PROVIDERS": "gemini", "GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "model-a",
       "GEMINI_FALLBACK_MODELS": "model-b"}


def run(side_effect):
    with mock.patch.dict(os.environ, ENV), \
            mock.patch("agents.llm._call_gemini", side_effect=side_effect) as call, \
            mock.patch("agents.llm.time.sleep") as sleep:
        result = llm.generate("hi")
    return result, call.call_count, sleep.call_count


def test_brief_rate_limit_is_retried_on_the_same_model():
    result, calls, sleeps = run([RuntimeError("429 RESOURCE_EXHAUSTED per minute"), "hello"])
    assert result["ok"] and result["text"] == "hello" and result["model"] == "gemini/model-a"
    assert calls == 2 and sleeps == 1


def test_overloaded_model_falls_through_to_the_next_without_waiting():
    result, calls, sleeps = run([RuntimeError("503 UNAVAILABLE high demand"), "hello"])
    assert result["ok"] and result["model"] == "gemini/model-b" and calls == 2 and sleeps == 0


def test_daily_quota_skips_the_model():
    quota = RuntimeError("429 RESOURCE_EXHAUSTED GenerateRequestsPerDayPerProjectPerModel-FreeTier")
    result, calls, sleeps = run([quota, "hello"])
    assert result["ok"] and result["model"] == "gemini/model-b" and sleeps == 0


def test_gives_up_when_every_model_fails():
    result, calls, _ = run(RuntimeError("404 NOT_FOUND model retired"))
    assert result["ok"] is False and calls == 2 and "every model" in result["error"]


def test_empty_response_is_an_error():
    result, calls, _ = run(["", ""])
    assert result["ok"] is False and "empty" in result["error"]

def test_providers_are_tried_in_order_and_keyless_ones_skipped():
    env = {"LLM_PROVIDERS": "groq,gemini", "GROQ_API_KEY": "g-key", "GEMINI_API_KEY": "m-key",
           "GROQ_MODEL": "fast", "GROQ_FALLBACK_MODELS": "", "GEMINI_MODEL": "slow", "GEMINI_FALLBACK_MODELS": ""}
    with mock.patch.dict(os.environ, env), \
            mock.patch("agents.llm._call_groq", side_effect=RuntimeError("429 rate_limit_exceeded: tokens per day")) as groq, \
            mock.patch("agents.llm._call_gemini", return_value="from gemini") as gemini, \
            mock.patch("agents.llm.time.sleep"):
        result = llm.generate("hi")
    assert result == {"ok": True, "text": "from gemini", "model": "gemini/slow"}
    assert groq.call_count == 1 and gemini.call_count == 1  # daily limit: no retry on groq
    with mock.patch.dict(os.environ, {**env, "GROQ_API_KEY": ""}), \
            mock.patch("agents.llm._call_groq") as groq, \
            mock.patch("agents.llm._call_gemini", return_value="ok"):
        assert llm.generate("hi")["model"] == "gemini/slow" and groq.call_count == 0
