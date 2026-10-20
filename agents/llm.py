"""The ONLY file that talks to a language model. Everything else receives an `llm`
function, so tests can pass in a fake and never need internet or an API key.

Contract: generate(prompt, system=None, json_mode=False) never raises. It returns
    {"ok": True, "text": "...", "model": "provider/model"}  or  {"ok": False, "error": "..."}

Providers are tried in order, and within each provider its models in order:
  * Groq (GROQ_API_KEY): fast open models. In testing (Oct 2026) gpt-oss-120b,
    gpt-oss-20b and qwen3.8-27b each read our real Arabic/English requests 6/6
    correctly in under a second.
  * Gemini (GEMINI_API_KEY): backup. Its calls took 7-12s and the free tier ran
    out of daily quota during development.
A provider without a key is skipped. A model that is out of quota, overloaded or
failing is skipped at once; only a brief rate-limit blip is retried on the same model.

Settings (.env): GROQ_API_KEY, GEMINI_API_KEY, LLM_PROVIDERS (default "groq,gemini"),
GROQ_MODEL / GROQ_FALLBACK_MODELS, GEMINI_MODEL / GEMINI_FALLBACK_MODELS.
"""
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

DEFAULTS = {
    "groq": ("openai/gpt-oss-120b", ("openai/gpt-oss-20b", "qwen/qwen3.8-27b")),
    "gemini": ("gemini-3-flash-preview", ("gemini-2.5-flash", "gemini-3.1-flash-lite")),
}
KEY_VARS = {"groq": "GROQ_API_KEY", "gemini": "GEMINI_API_KEY"}
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MAX_ATTEMPTS = 2           # per model
REQUEST_TIMEOUT_S = 25     # an overloaded model fails fast instead of hanging the chat
BACKOFF_SECONDS = (1.0,)   # wait before the second attempt on the same model
SKIP_MODEL_MARKERS = ("perday", "per day", "tokens per day", "requests per day", "quota", "404", "not_found",
                      "model_decommissioned", "503", "504", "deadline", "unavailable", "overloaded",
                      "high demand", "timed out", "timeout")
TRANSIENT_MARKERS = ("429", "rate_limit", "resource_exhausted") + SKIP_MODEL_MARKERS


def _is_transient(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in TRANSIENT_MARKERS)


def _skip_model(message: str) -> bool:
    """Daily quota gone, model missing, or overloaded: retrying this model now won't help."""
    lowered = message.lower().replace(" ", "")
    return any(marker.replace(" ", "") in lowered for marker in SKIP_MODEL_MARKERS)


def _models(provider: str) -> List[str]:
    prefix = provider.upper()
    primary_default, fallback_default = DEFAULTS[provider]
    primary = os.environ.get(f"{prefix}_MODEL", primary_default)
    extra = os.environ.get(f"{prefix}_FALLBACK_MODELS")
    fallbacks = [m.strip() for m in extra.split(",")] if extra is not None else list(fallback_default)
    return list(dict.fromkeys([primary, *[m for m in fallbacks if m]]))


def _chain() -> List[Tuple[str, str, str]]:
    """(provider, model, api_key) in the order they should be tried."""
    providers = [p.strip().lower() for p in os.environ.get("LLM_PROVIDERS", "groq,gemini").split(",")]
    chain = []
    for provider in providers:
        key = os.environ.get(KEY_VARS.get(provider, ""), "").strip()
        if provider in DEFAULTS and key:
            chain += [(provider, model, key) for model in _models(provider)]
    return chain


# ---------------------------------------------------------------- Groq (OpenAI-compatible)
def _call_groq(api_key: str, model: str, prompt: str, system: Optional[str], json_mode: bool) -> str:
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    body: Dict[str, Any] = {"model": model, "messages": messages, "temperature": 0.0 if json_mode else 0.3}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    # Extraction and wording don't need long reasoning; it only adds latency.
    if "gpt-oss" in model:
        body["reasoning_effort"] = "low"
    elif "qwen" in model:
        body["reasoning_effort"] = "none"
    req = urllib.request.Request(GROQ_URL, data=json.dumps(body).encode("utf-8"), headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
        "User-Agent": "Fosha-RehlaGuide/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # keep the status and Groq's reason (e.g. rate limit kind)
        raise RuntimeError(f"{exc.code} {exc.read().decode('utf-8', 'replace')[:300]}") from None
    return (data["choices"][0]["message"].get("content") or "").strip()


# ---------------------------------------------------------------- Gemini
def _thinking(types: Any, model: str) -> Any:
    """Thinking was most of Gemini's latency (an 11s intent call for 260 characters).
    2.5 models take a budget (0 = off); 3.x models take a level ("low" is the lowest
    every 3.x flash model accepts)."""
    if "2.5" in model:
        return types.ThinkingConfig(thinking_budget=0)
    return types.ThinkingConfig(thinking_level="low")


def _call_gemini(api_key: str, model: str, prompt: str, system: Optional[str], json_mode: bool) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_S * 1000))
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=0.0 if json_mode else 0.3,
        response_mime_type="application/json" if json_mode else None,
        thinking_config=_thinking(types, model),
    )
    response = client.models.generate_content(model=model, contents=prompt, config=config)
    return response.text or ""


CALLERS = {"groq": "_call_groq", "gemini": "_call_gemini"}


def generate(prompt: str, system: Optional[str] = None, json_mode: bool = False) -> Dict[str, Any]:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:  # .env loading is optional; real env vars still work
        pass

    chain = _chain()
    if not chain:
        return {"ok": False, "error": "No LLM key set: put GROQ_API_KEY or GEMINI_API_KEY in your .env file"}
    errors = []
    for provider, model, key in chain:
        call = globals()[CALLERS[provider]]  # looked up at call time so tests can patch it
        for attempt in range(MAX_ATTEMPTS):
            try:
                text = call(key, model, prompt, system, json_mode)
            except Exception as exc:  # network, quota, bad key, bad model name, ...
                message = str(exc)
                if not _skip_model(message) and _is_transient(message) and attempt < MAX_ATTEMPTS - 1:
                    time.sleep(BACKOFF_SECONDS[attempt])
                    continue
                errors.append(f"{provider}/{model}: {message[:120]}")
                break                           # next model, no waiting
            if not text:
                errors.append(f"{provider}/{model}: empty response")
                break
            return {"ok": True, "text": text, "model": f"{provider}/{model}"}
    return {"ok": False, "error": "LLM call failed on every model: " + " | ".join(errors)}
