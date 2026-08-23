"""One structured-extraction call, behind one interface, across providers.

The compiler needs exactly one capability: given a system prompt, a document
and a JSON schema, return JSON that validates against that schema. Nothing
else about the model matters, because correctness is enforced downstream by
mechanical quote verification rather than by trusting the model.

That is why the provider is swappable. The compiler's guarantee does not depend
on model quality; a weaker model simply scores lower on a measurement we
report. Supported:

    gemini      Google AI Studio (free tier) -- the default
    anthropic   Claude
    ollama      a local model, no key and no network

Set ``TRIGGER_LLM_PROVIDER`` and ``TRIGGER_LLM_MODEL`` to override.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

DEFAULT_PROVIDER = os.getenv("TRIGGER_LLM_PROVIDER", "gemini")

DEFAULT_MODELS = {
    # Flash tier by default. AI Studio's free tier covers the flash models;
    # the pro-preview models return 429 RESOURCE_EXHAUSTED without billing, so
    # they are deliberately not the default. This project never requires a paid
    # tier -- the published compiler score was produced on the free tier.
    "gemini": "gemini-3.5-flash",
    "anthropic": "claude-opus-5",
    "ollama": "llama3.1:8b",
}

#: Tried in order when the chosen model is unavailable or rate-limited.
#: Free-tier models only -- no pro/preview tier appears here, so a account
#: without billing degrades to a smaller model rather than failing or billing.
GEMINI_FALLBACKS = [
    "gemini-3.5-flash",
    "gemini-3.7-flash",
    "gemini-2.5-flash",
    "gemini-3.6-flash",
    "gemini-2.5-flash-lite",
]


@dataclass
class LLMResult:
    data: dict
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class LLMUnavailable(RuntimeError):
    """No provider could be reached. Callers fall back to the cache."""


# --------------------------------------------------------------------- gemini

def _to_gemini_schema(schema: dict) -> dict:
    """Translate a JSON Schema into the subset Gemini accepts.

    Gemini's ``responseSchema`` is OpenAPI-flavoured: it rejects
    ``additionalProperties``, expresses optionality with ``nullable`` rather
    than a type union, and ignores ``enum`` containing null. Passing a plain
    JSON Schema straight through is silently rejected or, worse, partially
    honoured -- so the translation is explicit.
    """
    if not isinstance(schema, dict):
        return schema

    out: dict = {}
    t = schema.get("type")

    if isinstance(t, list):
        # ["string", "null"] -> nullable string
        non_null = [x for x in t if x != "null"]
        out["type"] = (non_null[0] if non_null else "string").upper()
        if "null" in t:
            out["nullable"] = True
    elif isinstance(t, str):
        out["type"] = t.upper()

    if "enum" in schema:
        vals = [v for v in schema["enum"] if v is not None]
        if vals:
            out["enum"] = vals
            out["type"] = "STRING"
        if any(v is None for v in schema["enum"]):
            out["nullable"] = True

    if "description" in schema:
        out["description"] = schema["description"]

    if out.get("type") == "OBJECT" or "properties" in schema:
        out["type"] = "OBJECT"
        props = {k: _to_gemini_schema(v) for k, v in (schema.get("properties") or {}).items()}
        out["properties"] = props
        req = [r for r in (schema.get("required") or []) if r in props]
        if req:
            out["required"] = req
        # Deterministic key order keeps outputs comparable between runs.
        out["propertyOrdering"] = list(props.keys())

    if out.get("type") == "ARRAY" or "items" in schema:
        out["type"] = "ARRAY"
        out["items"] = _to_gemini_schema(schema.get("items") or {})

    return out


def _call_gemini(system: str, user_parts: list[str], schema: dict,
                 model: str) -> LLMResult:
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise LLMUnavailable("GEMINI_API_KEY is not set")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=key)
    gschema = _to_gemini_schema(schema)

    tried: list[str] = []
    candidates = [model] + [m for m in GEMINI_FALLBACKS if m != model]
    last_exc: Exception | None = None

    for m in candidates:
        tried.append(m)
        try:
            resp = client.models.generate_content(
                model=m,
                contents=[types.Content(
                    role="user",
                    parts=[types.Part(text=p) for p in user_parts],
                )],
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    response_schema=gschema,
                    # Deterministic extraction: we want the same clauses every
                    # run, not creative variety.
                    temperature=0.0,
                    max_output_tokens=60000,
                ),
            )
            text = resp.text
            if not text:
                raise LLMUnavailable(f"{m} returned no text")
            usage = getattr(resp, "usage_metadata", None)
            return LLMResult(
                data=json.loads(text),
                provider="gemini",
                model=m,
                input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
                output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
            )
        except Exception as exc:  # noqa: BLE001 - try the next model
            last_exc = exc
            msg = str(exc)
            # Only fall through on availability problems; a schema error would
            # fail identically on every model, so surface it immediately.
            if not any(s in msg for s in ("429", "404", "NOT_FOUND", "RESOURCE_EXHAUSTED",
                                          "UNAVAILABLE", "503", "500", "quota")):
                raise
            print(f"  [llm] {m} unavailable ({msg[:80]}), trying next")

    raise LLMUnavailable(f"All Gemini models failed. Tried {tried}. Last: {last_exc}")


# ------------------------------------------------------------------ anthropic

def _call_anthropic(system: str, user_parts: list[str], schema: dict,
                    model: str) -> LLMResult:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise LLMUnavailable("ANTHROPIC_API_KEY is not set")

    import anthropic

    client = anthropic.Anthropic()
    content = [{"type": "text", "text": p} for p in user_parts]
    # The document is the stable prefix, so cache it server-side.
    if content:
        content[0]["cache_control"] = {"type": "ephemeral"}

    with client.messages.stream(
        model=model,
        max_tokens=64000,
        system=system,
        thinking={"type": "adaptive"},
        output_config={"effort": "high",
                       "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": content}],
    ) as stream:
        resp = stream.get_final_message()

    if resp.stop_reason == "refusal":
        raise LLMUnavailable(f"model declined: {resp.stop_details}")

    text = next(b.text for b in resp.content if b.type == "text")
    return LLMResult(
        data=json.loads(text), provider="anthropic", model=model,
        input_tokens=resp.usage.input_tokens,
        output_tokens=resp.usage.output_tokens,
    )


# --------------------------------------------------------------------- ollama

def _call_ollama(system: str, user_parts: list[str], schema: dict,
                 model: str) -> LLMResult:
    import requests

    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        r = requests.post(f"{host}/api/chat", timeout=1800, json={
            "model": model,
            "system": system,
            "messages": [{"role": "user", "content": "\n\n".join(user_parts)}],
            "format": schema,   # ollama accepts a JSON schema directly
            "stream": False,
            "options": {"temperature": 0.0},
        })
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        raise LLMUnavailable(f"ollama at {host} unreachable: {exc}") from exc

    body = r.json()
    return LLMResult(data=json.loads(body["message"]["content"]),
                     provider="ollama", model=model)


# ---------------------------------------------------------------- entry point

def complete_json(system: str, user_parts: list[str], schema: dict,
                  provider: str | None = None,
                  model: str | None = None) -> LLMResult:
    """Return schema-validated JSON from whichever provider is configured."""
    provider = provider or DEFAULT_PROVIDER
    model = model or os.getenv("TRIGGER_LLM_MODEL") or DEFAULT_MODELS.get(provider)

    if provider == "gemini":
        return _call_gemini(system, user_parts, schema, model)
    if provider == "anthropic":
        return _call_anthropic(system, user_parts, schema, model)
    if provider == "ollama":
        return _call_ollama(system, user_parts, schema, model)
    raise LLMUnavailable(f"unknown provider {provider!r}")


def available_provider() -> str | None:
    """Which provider could actually run right now, if any."""
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        return "gemini"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    return None
