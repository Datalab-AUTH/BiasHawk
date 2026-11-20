"""
The only place an LLM is constructed.

Open WebUI exposes an OpenAI-compatible API at <OPENWEBUI_BASE_URL>/api, so the
plain `openai` SDK talks to it directly. There is no provider switch and no
OpenAI code path: the old backend had `llm_choice="openai"` defaults scattered
across six modules, two of which raised at import time without an API key.

Embeddings go through the same server and the same client , see
`core.rag.embeddings`, which calls `client.embeddings.create()` against the
GPU-backed model rather than loading one onto the CPU.
"""

import logging
import threading
import time

from django.conf import settings
from openai import OpenAI

log = logging.getLogger("core.llm")

_client = None
_client_lock = threading.Lock()


class LLMError(RuntimeError):
    pass


def get_client():
    """One process-wide client; it holds a connection pool worth reusing."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                if not settings.OPENWEBUI_BASE_URL:
                    raise LLMError("OPENWEBUI_BASE_URL is not set.")
                if not settings.OPENWEBUI_API_KEY:
                    raise LLMError("OPENWEBUI_API_KEY is not set.")
                _client = OpenAI(
                    base_url=f"{settings.OPENWEBUI_BASE_URL}/api",
                    api_key=settings.OPENWEBUI_API_KEY,
                    timeout=settings.OPENWEBUI_TIMEOUT,
                    max_retries=0,  # retried below, with backoff we control
                )
    return _client


def chat(system, user, *, model=None, temperature=0.1, max_retries=3):
    """
    One chat completion. Returns the message text.

    Raises LLMError rather than returning an error string, so a failing job is
    recorded as failed and retried instead of writing an apology into a report ,
    which is what the old services did.
    """
    model = model or settings.OPENWEBUI_CHAT_MODEL
    client = get_client()
    delay = 5
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            started = time.monotonic()
            response = client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            content = (response.choices[0].message.content or "").strip()
            if content:
                log.info(
                    "chat model=%s attempt=%d elapsed=%.1fs chars=%d",
                    model, attempt, time.monotonic() - started, len(content),
                )
                return content
            last_error = "model returned empty content"
            log.warning("chat attempt %d/%d: %s", attempt, max_retries, last_error)
        except Exception as exc:
            last_error = exc
            log.warning("chat attempt %d/%d failed: %s", attempt, max_retries, exc)

        if attempt < max_retries:
            time.sleep(delay)
            delay *= 2

    raise LLMError(f"Open WebUI call failed after {max_retries} attempts: {last_error}")
