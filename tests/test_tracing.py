"""Langfuse tracing (agents/tracing.py): off by default, never raises, never sends message text.

The first group needs no Langfuse package. The last group builds the real SDK with an in-memory
exporter (no server) and is skipped when the package is not installed (uv sync --extra observability).
"""
import os
from contextlib import contextmanager
from unittest import mock

import pytest

from agents import llm, tracing

SECRET_TEXT = "عايز اروح الاقصر ٣ ايام وميزانيتي ٥٠٠٠ جنيه"


@pytest.fixture(autouse=True)
def fresh_client():
    tracing.reset()
    yield
    tracing.reset()


# ---------------------------------------------------------------- off by default
def test_off_without_keys_and_helpers_are_noops():
    with mock.patch.dict(os.environ, {"LANGFUSE_PUBLIC_KEY": "", "LANGFUSE_SECRET_KEY": ""}):
        assert tracing.enabled() is False
        with tracing.trace("chat", tags=["keyword"]) as root, tracing.observation("x", as_type="generation") as obs:
            obs.update(model="m", usage_details={"input": 1, "output": 2}, metadata={"a": 1})
            root.score("top1_distance", 0.5)
        tracing.shutdown()  # nothing to flush, must not raise


def test_can_be_switched_off_even_with_keys():
    env = {"LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": "sk", "LANGFUSE_TRACING_ENABLED": "false"}
    with mock.patch.dict(os.environ, env):
        assert tracing.enabled() is False


def test_keys_but_missing_package_means_off_not_a_crash():
    env = {"LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": "sk"}
    with mock.patch.dict(os.environ, env), mock.patch.dict("sys.modules", {"langfuse": None}):
        assert tracing.enabled() is False


def test_errors_in_the_traced_code_still_propagate():
    with pytest.raises(ValueError):
        with tracing.observation("x"):
            raise ValueError("boom")


# ---------------------------------------------------------------- masking rules
def test_scrub_keeps_numbers_and_safe_fields_and_blanks_text():
    out = tracing.scrub({"status": "planned", "language": "ar", "model": "groq/openai/gpt-oss-120b",
                         "note": SECRET_TEXT, "n": 3, "ok": True, "dist": 0.9, "none": None,
                         "nested": {"query": "pyramids", "mode": "keyword"}, "list": [SECRET_TEXT, 2]})
    assert out["status"] == "planned" and out["language"] == "ar" and out["model"].startswith("groq/")
    assert out["n"] == 3 and out["ok"] is True and out["dist"] == 0.9 and out["none"] is None
    assert out["note"] == tracing.MASKED
    assert out["nested"] == {"query": tracing.MASKED, "mode": "keyword"}
    assert out["list"] == [tracing.MASKED, 2]
    assert SECRET_TEXT not in repr(out)


def test_top_level_strings_and_unknown_objects_are_blanked():
    assert tracing.mask(data=SECRET_TEXT) == tracing.MASKED
    assert tracing.mask(data=object()) == tracing.MASKED


# ---------------------------------------------------------------- what llm.generate reports
class FakeObservation:
    def __init__(self):
        self.updates = []

    def update(self, **fields):
        self.updates.append(fields)


class FakeClient:
    def __init__(self):
        self.observations = []

    @contextmanager
    def start_as_current_observation(self, **kwargs):
        obs = FakeObservation()
        obs.kwargs = kwargs
        self.observations.append(obs)
        yield obs


def install(client):
    tracing._client_obj, tracing._client_ready = client, True


ENV = {"LLM_PROVIDERS": "gemini", "GEMINI_API_KEY": "k", "GEMINI_MODEL": "model-a", "GEMINI_FALLBACK_MODELS": "model-b"}


def test_generation_records_model_usage_and_sizes_but_never_the_text():
    client = FakeClient()
    install(client)

    def fake_gemini(key, model, prompt, system, json_mode):
        llm._usage.set({"input": 11, "output": 4})
        return "reply text"

    with mock.patch.dict(os.environ, ENV), mock.patch("agents.llm._call_gemini", side_effect=fake_gemini):
        result = llm.generate(SECRET_TEXT, system="be nice")
    assert result["ok"]
    (obs,) = client.observations
    assert obs.kwargs["as_type"] == "generation" and obs.kwargs["name"] == "llm.generate"
    (update,) = obs.updates
    assert update["model"] == "gemini/model-a" and update["usage_details"] == {"input": 11, "output": 4}
    assert update["metadata"]["prompt_chars"] == len(SECRET_TEXT) and update["metadata"]["has_system"] is True
    assert update["metadata"]["reply_chars"] == len("reply text")
    assert "level" not in update  # healthy call: no warning
    everything = repr(obs.kwargs) + repr(obs.updates)
    assert SECRET_TEXT not in everything and "reply text" not in everything and "input" not in obs.kwargs


def test_fallback_is_a_warning_and_total_failure_is_an_error():
    client = FakeClient()
    install(client)
    with mock.patch.dict(os.environ, ENV), mock.patch("agents.llm.time.sleep"), \
            mock.patch("agents.llm._call_gemini", side_effect=[RuntimeError("503 UNAVAILABLE"), "ok"]):
        assert llm.generate("hi")["model"] == "gemini/model-b"
    assert client.observations[-1].updates[0]["level"] == "WARNING"
    assert client.observations[-1].updates[0]["metadata"]["failed_models"] == 1

    with mock.patch.dict(os.environ, ENV), mock.patch("agents.llm.time.sleep"), \
            mock.patch("agents.llm._call_gemini", side_effect=RuntimeError("404 NOT_FOUND")):
        assert llm.generate("hi")["ok"] is False
    failed = client.observations[-1].updates[0]
    assert failed["level"] == "ERROR" and "usage_details" not in failed
    assert "404" not in repr(failed)  # provider error text stays in the server log only


def test_usage_from_a_failed_attempt_does_not_leak_into_the_next_call():
    client = FakeClient()
    install(client)
    llm._usage.set({"input": 999, "output": 999})  # stale value from an earlier call
    with mock.patch.dict(os.environ, ENV), mock.patch("agents.llm._call_gemini", return_value="ok"):
        llm.generate("hi")
    assert "usage_details" not in client.observations[0].updates[0]


def test_a_broken_langfuse_never_breaks_the_llm_call():
    class Exploding:
        def start_as_current_observation(self, **kwargs):
            raise RuntimeError("langfuse down")

    install(Exploding())
    with mock.patch.dict(os.environ, ENV), mock.patch("agents.llm._call_gemini", return_value="fine"):
        assert llm.generate("hi")["text"] == "fine"


# ---------------------------------------------------------------- retrieval adapter span
def test_retrieval_span_has_counts_not_the_query():
    from agents import retrieval_adapter

    client = FakeClient()
    install(client)

    def fake_search(query, region, category, max_duration, top_k):
        return [{"metadata": {"id": 1}, "relevance_score": 0.8}]

    result = retrieval_adapter.search_attractions(SECRET_TEXT, region="Luxor", search_fn=fake_search)
    assert result["ok"]
    (obs,) = client.observations
    assert obs.kwargs["as_type"] == "retriever"
    meta = obs.updates[0]["metadata"]
    assert meta["n_results"] == len(result["results"]) and meta["query_chars"] == len(SECRET_TEXT)
    assert meta["region_filter"] is True and "Luxor" not in repr(obs.updates) and SECRET_TEXT not in repr(obs.updates)


# ---------------------------------------------------------------- the real SDK, no server
def real_sdk_exporter():
    pytest.importorskip("langfuse")
    from langfuse import Langfuse
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    install(Langfuse(public_key="pk", secret_key="sk", base_url="http://127.0.0.1:9", mask=tracing.mask,
                     span_exporter=exporter))
    return exporter


def test_real_sdk_blanks_text_even_if_a_caller_passes_it():
    exporter = real_sdk_exporter()
    with tracing.trace("chat", tags=["keyword"], mode="keyword") as root:
        with tracing.observation("llm.generate", as_type="generation") as gen:
            gen.update(model="groq/x", usage_details={"input": 5, "output": 7},
                       input=SECRET_TEXT, output=SECRET_TEXT, metadata={"note": SECRET_TEXT, "language": "ar"})
        root.update(metadata={"status": "planned", "free": SECRET_TEXT})
    tracing._client_obj.flush()
    spans = {s.name: dict(s.attributes) for s in exporter.get_finished_spans()}
    assert set(spans) == {"chat", "llm.generate"}
    dumped = repr(spans)
    assert SECRET_TEXT not in dumped
    assert spans["llm.generate"]["langfuse.observation.model.name"] == "groq/x"
    assert spans["llm.generate"]["langfuse.observation.metadata.language"] == '"ar"'
    assert spans["llm.generate"]["langfuse.observation.metadata.note"] == '"[masked]"'
    assert spans["chat"]["langfuse.trace.name"] == "chat"


# ---------------------------------------------------------------- the API
def test_api_traces_a_fresh_chat_once_and_never_the_message(tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from api import analytics, server

    client = FakeClient()
    install(client)
    message = "2 days in Luxor, I love temples"
    with mock.patch.object(server, "DEMO", True), mock.patch.object(server, "cache", server.ResponseCache()), \
            mock.patch.object(analytics, "LOG_PATH", tmp_path / "analytics.jsonl"):
        api = TestClient(server.app)
        first = api.post("/api/v1/chat", json={"message": message}).json()
        names = [o.kwargs["name"] for o in client.observations]
        api.post("/api/v1/chat", json={"message": message})  # cache hit: no pipeline, no new trace
    assert first["ok"] and names.count("chat") == 1
    assert {"chat", "intent.extract", "retrieval.search", "schedule", "reply.write"} <= set(names)
    assert len([o for o in client.observations if o.kwargs["name"] == "chat"]) == 1
    assert message not in repr([(o.kwargs, o.updates) for o in client.observations])
    chat = next(o for o in client.observations if o.kwargs["name"] == "chat")
    assert chat.updates[0]["metadata"]["status"] == "planned" and chat.updates[0]["metadata"]["mode"] == "demo"
