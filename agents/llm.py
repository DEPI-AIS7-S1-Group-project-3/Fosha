"""The ONLY file that talks to Gemini. Everything else receives an `llm` function,
so tests can pass in a fake and never need internet or an API key.

Contract: generate(prompt, system=None, json_mode=False) never raises. It returns
    {"ok": True, "text": "...", "model": "..."}  or  {"ok": False, "error": "..."}
Settings come from the environment (.env): GEMINI_API_KEY, GEMINI_MODEL (optional).
Temporary errors (503 overloaded, 429 rate limit) are retried a couple of times.
"""
import os
import time
from typing import Any, Dict, Optional

DEFAULT_MODEL = "gemini-2.5-flash"  # newest models were often overloaded (504/503) in testing
MAX_ATTEMPTS = 3
REQUEST_TIMEOUT_MS = 25_000
BACKOFF_SECONDS = (1.0, 3.0)  # wait before attempt 2, then attempt 3
TRANSIENT_MARKERS = ("503", "504", "deadline", "unavailable", "429", "resource_exhausted", "overloaded",
                     "high demand", "timed out", "timeout")


def _is_transient(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in TRANSIENT_MARKERS)


def _call_gemini(api_key: str, model: str, prompt: str, system: Optional[str], json_mode: bool) -> str:
    from google import genai
    from google.genai import types

    # Cap each call so an overloaded model fails fast instead of hanging the chat for minutes.
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS))
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=0.0 if json_mode else 0.3,
        response_mime_type="application/json" if json_mode else None,
    )
    response = client.models.generate_content(model=model, contents=prompt, config=config)
    return response.text or ""


def generate(prompt: str, system: Optional[str] = None, json_mode: bool = False) -> Dict[str, Any]:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:  # .env loading is optional; real env vars still work
        pass

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"ok": False, "error": "GEMINI_API_KEY is not set (put it in your .env file)"}
    model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)

    for attempt in range(MAX_ATTEMPTS):
        try:
            text = _call_gemini(api_key, model, prompt, system, json_mode)
        except Exception as exc:  # network, quota, bad key, bad model name, ...
            message = str(exc)
            if _is_transient(message) and attempt < MAX_ATTEMPTS - 1:
                time.sleep(BACKOFF_SECONDS[attempt])
                continue
            return {"ok": False, "error": f"Gemini call failed: {message}"}
        if not text:
            return {"ok": False, "error": "Gemini returned an empty response"}
        return {"ok": True, "text": text, "model": model}
    return {"ok": False, "error": "Gemini call failed"}  # unreachable, keeps the contract explicit