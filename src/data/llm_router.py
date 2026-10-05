"""
OmniRoute — OpenRouter model router with automatic failover.

One key, many models. Every LLM call in the dashboard goes through `chat()`,
which walks a priority-ordered model chain and steps down to the next model
whenever the current one runs out of tokens/credits, gets rate-limited, or
goes down.

Failover is belt-and-braces — two independent layers:

  1. Server-side  — the request carries OpenRouter's `models` array, so
     OpenRouter itself walks the remaining chain on rate-limits, context-length
     errors, moderation flags and provider downtime, without a round-trip.
  2. Client-side  — if the whole request still comes back with a failover
     status (402 out of credits, 429 rate limited, 5xx), we re-issue against
     the chain with the dead head dropped. Covers account-level credit
     exhaustion, which OpenRouter cannot route around on its own.

Config (.env):
  OPENROUTER_API_KEY   required to use OpenRouter
  OPENROUTER_MODELS    optional, comma-separated chain (overrides DEFAULT_CHAIN)
  OPENROUTER_APP_URL   optional, sent as HTTP-Referer for OpenRouter attribution

If OPENROUTER_API_KEY is absent but ANTHROPIC_API_KEY is present, the router
transparently falls back to calling the Anthropic API direct, so the dashboard
keeps working during the key handover.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Priority order: best model first, cheapest/most-available last.
# Every id verified against https://openrouter.ai/api/v1/models
DEFAULT_CHAIN: List[str] = [
    "anthropic/claude-opus-5",
    "anthropic/claude-sonnet-5",
    "openai/gpt-5.2",
    "google/gemini-3.1-pro-preview",
    "deepseek/deepseek-v4-pro",
]

# Statuses that mean "this model/account is done — try the next one".
FAILOVER_STATUSES = {402, 408, 409, 429, 500, 502, 503, 504}

DEFAULT_TIMEOUT = 120

# Last route taken, for UI display. Populated by every successful call.
LAST_ROUTE: Dict[str, Any] = {"model": None, "attempts": [], "fell_back": False}


class RouterError(RuntimeError):
    """Every model in the chain failed."""


# ── config ────────────────────────────────────────────────────────────────────
def model_chain() -> List[str]:
    """The active fallback chain, from OPENROUTER_MODELS or the default."""
    raw = os.getenv("OPENROUTER_MODELS", "").strip()
    if raw:
        chain = [m.strip() for m in raw.split(",") if m.strip()]
        if chain:
            return chain
    return list(DEFAULT_CHAIN)


def _openrouter_key() -> str:
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    return "" if not key or "your_openrouter" in key else key


def _anthropic_key() -> str:
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    return "" if not key or "your_anthropic" in key else key


def is_available() -> bool:
    """True if any route to a model exists."""
    return bool(_openrouter_key() or _anthropic_key())


def active_backend() -> str:
    """'openrouter', 'anthropic' (direct fallback), or 'none'."""
    if _openrouter_key():
        return "openrouter"
    if _anthropic_key():
        return "anthropic"
    return "none"


# ── OpenRouter transport ──────────────────────────────────────────────────────
def _headers(key: str) -> Dict[str, str]:
    h = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "X-Title": "Black Raven Protocol",
    }
    referer = os.getenv("OPENROUTER_APP_URL", "").strip()
    if referer:
        h["HTTP-Referer"] = referer
    return h


def _post(key: str, payload: Dict[str, Any], timeout: int) -> requests.Response:
    return requests.post(
        OPENROUTER_URL, headers=_headers(key), json=payload, timeout=timeout
    )


def _extract(body: Dict[str, Any]) -> Tuple[str, str]:
    """(text, model_that_served_it) from an OpenRouter chat completion."""
    choices = body.get("choices") or []
    if not choices:
        raise RouterError(f"Empty response from router: {str(body)[:300]}")
    text = (choices[0].get("message") or {}).get("content") or ""
    return text, body.get("model") or "?"


# ── direct-Anthropic fallback (used only when no OpenRouter key is set) ───────
def _anthropic_direct(
    messages: List[Dict[str, str]],
    system: Optional[str],
    max_tokens: int,
) -> Tuple[str, str]:
    import anthropic

    # First Anthropic model in the chain, stripped of the vendor prefix.
    model = "claude-opus-5"
    for m in model_chain():
        if m.startswith("anthropic/"):
            model = m.split("/", 1)[1]
            break

    client = anthropic.Anthropic(api_key=_anthropic_key())
    kwargs: Dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system
    resp = client.messages.create(**kwargs)
    text = "".join(b.text for b in resp.content if b.type == "text")
    return text, f"anthropic-direct/{model}"


# ── the one entry point ───────────────────────────────────────────────────────
def chat(
    messages: List[Dict[str, str]],
    system: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: Optional[float] = None,
    models: Optional[List[str]] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """
    Send a conversation and get the reply text, whatever it takes.

    `messages` is [{"role": "user"|"assistant", "content": str}, ...].
    Walks the model chain until one answers; raises RouterError if none do.
    """
    text, _model, _attempts = chat_verbose(
        messages,
        system=system,
        max_tokens=max_tokens,
        temperature=temperature,
        models=models,
        timeout=timeout,
    )
    return text


def chat_verbose(
    messages: List[Dict[str, str]],
    system: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: Optional[float] = None,
    models: Optional[List[str]] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Tuple[str, str, List[str]]:
    """Same as chat(), but returns (text, model_used, attempt_log)."""
    chain = list(models) if models else model_chain()
    if not chain:
        raise RouterError("Model chain is empty — check OPENROUTER_MODELS.")

    payload_messages: List[Dict[str, str]] = []
    if system:
        payload_messages.append({"role": "system", "content": system})
    payload_messages.extend(messages)

    key = _openrouter_key()
    attempts: List[str] = []

    if not key:
        if not _anthropic_key():
            raise RouterError(
                "No OPENROUTER_API_KEY (and no ANTHROPIC_API_KEY) configured in .env"
            )
        text, model = _anthropic_direct(messages, system, max_tokens)
        attempts.append(f"{model}: ok (no OpenRouter key — direct fallback)")
        LAST_ROUTE.update({"model": model, "attempts": attempts, "fell_back": False})
        return text, model, attempts

    # Client-side step-down. Attempt i sends the chain from i onward, so
    # OpenRouter can still route inside the remaining models on its own.
    for i in range(len(chain)):
        remaining = chain[i:]
        payload: Dict[str, Any] = {
            "models": remaining,
            "messages": payload_messages,
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            payload["temperature"] = temperature

        try:
            resp = _post(key, payload, timeout)
        except requests.RequestException as exc:
            attempts.append(f"{remaining[0]}: transport error ({type(exc).__name__})")
            continue

        if resp.status_code in FAILOVER_STATUSES:
            attempts.append(f"{remaining[0]}: HTTP {resp.status_code} — stepping down")
            continue

        if resp.status_code >= 400:
            # 400/401/403 are our fault (bad key, bad payload) — no point walking.
            raise RouterError(
                f"OpenRouter HTTP {resp.status_code}: {resp.text[:300]}"
            )

        try:
            body = resp.json()
        except ValueError:
            attempts.append(f"{remaining[0]}: non-JSON response — stepping down")
            continue

        # OpenRouter can return 200 with an error envelope.
        if isinstance(body.get("error"), dict):
            code = body["error"].get("code")
            msg = body["error"].get("message", "")
            attempts.append(f"{remaining[0]}: error {code} {msg[:120]} — stepping down")
            continue

        text, served_by = _extract(body)
        attempts.append(f"{served_by}: ok")
        LAST_ROUTE.update(
            {
                "model": served_by,
                "attempts": attempts,
                "fell_back": served_by.split(":")[0] != chain[0],
            }
        )
        return text, served_by, attempts

    # Whole chain exhausted — last resort: Anthropic direct, if a key exists.
    if _anthropic_key():
        try:
            text, model = _anthropic_direct(messages, system, max_tokens)
            attempts.append(f"{model}: ok (last-resort direct Anthropic)")
            LAST_ROUTE.update(
                {"model": model, "attempts": attempts, "fell_back": True}
            )
            return text, model, attempts
        except Exception as exc:  # noqa: BLE001 — reported in the raise below
            attempts.append(f"anthropic-direct: {type(exc).__name__}: {exc}")

    LAST_ROUTE.update({"model": None, "attempts": attempts, "fell_back": True})
    raise RouterError(
        "Every model in the chain failed:\n  " + "\n  ".join(attempts)
    )


def route_status() -> str:
    """One-line summary of the last route, for the dashboard footer."""
    model = LAST_ROUTE.get("model")
    if not model:
        return "no call yet"
    return f"{model}{'  (fell back)' if LAST_ROUTE.get('fell_back') else ''}"
