"""Compile a published Heat Action Plan into machine-readable clauses.

The language model does exactly one job here: read the document and propose
structured clauses, each carrying a verbatim quote and the page it came from.
It decides nothing. It never sees temperature data, never evaluates a
condition, and never produces a number that reaches the results.

**The anti-hallucination guarantee is architectural, not a prompt instruction.**
Every proposed clause is checked against the extracted text of the page it
claims to cite. A clause whose ``source_text`` does not appear verbatim on its
stated page is REJECTED and never reaches the evaluator. A model that invents a
quote produces nothing; it cannot produce a wrong answer, only an empty one.

Rejections are counted and reported, because the rejection rate is itself a
measurement of extraction quality.

Responses are cached to disk keyed on (provider, model, prompt, document hash)
so the compiled output ships with the repository and a judge reproduces it with
no LLM key at all.

The provider is swappable (see src/llm.py) precisely because the guarantee
above does not depend on the model. A weaker free model produces a lower
extraction score, which we report; it cannot produce a confidently wrong
citation.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

from llm import LLMUnavailable, available_provider, complete_json
from schema import CLAUSE_KINDS, DEPARTMENT_KEY, METRICS, Clause

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPILE_CACHE = REPO_ROOT / "data" / "cache" / "compile"


#: Glyph normalisation. The plan renders the degree sign through an embedded
#: font that pdfplumber emits as a private-use codepoint, so a quote copied
#: from the model will not byte-match the extracted page without this.
_SUBS = {
    "": "°", "": "°", "": "",
    "’": "'", "‘": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", " ": " ",
}


def norm(s: str) -> str:
    """Normalise for quote comparison: glyphs, quotes, dashes, whitespace."""
    for a, b in _SUBS.items():
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


@dataclass
class PlanText:
    """Extracted document text, one entry per page."""

    pages: dict[int, str]
    doc_hash: str

    @classmethod
    def from_pdf(cls, path: str | Path) -> "PlanText":
        pages: dict[int, str] = {}
        with pdfplumber.open(path) as pdf:
            for i, p in enumerate(pdf.pages, 1):
                pages[i] = p.extract_text() or ""
        blob = "\n".join(f"[p{n}]\n{t}" for n, t in sorted(pages.items()))
        return cls(pages=pages, doc_hash=hashlib.sha256(blob.encode()).hexdigest()[:16])

    def as_prompt_document(self) -> str:
        return "\n\n".join(
            f"<page number=\"{n}\">\n{self.pages[n]}\n</page>" for n in sorted(self.pages)
        )


@dataclass
class CompileResult:
    """What the compiler produced, and what was thrown away."""

    accepted: list[Clause] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)   # proposal + reason
    raw_proposals: int = 0
    provider: str = ""
    model: str = ""
    cached: bool = False
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def quote_verification_rate(self) -> float:
        return len(self.accepted) / self.raw_proposals if self.raw_proposals else 0.0


# --------------------------------------------------------------------- schema

CLAUSE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "clauses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "clause_id": {"type": "string"},
                    "action_id": {"type": ["string", "null"]},
                    "strategy_id": {"type": ["string", "null"]},
                    "action": {"type": "string"},
                    "actor": {"type": "array", "items": {"type": "string"}},
                    "source_page": {"type": "integer"},
                    "source_text": {"type": "string"},
                    "kind": {"type": "string", "enum": list(CLAUSE_KINDS)},
                    "metric": {"type": "string", "enum": list(METRICS)},
                    "operator": {"type": ["string", "null"], "enum": ["above", "below", None]},
                    "threshold_source": {"type": ["number", "null"]},
                    "duration_hours": {"type": ["integer", "null"]},
                    "scope": {"type": "string",
                              "enum": ["citywide", "district", "site", "indoor"]},
                    "extraction_conf": {"type": "number"},
                    "extraction_note": {"type": "string"},
                    "evaluable": {"type": "boolean"},
                    "not_evaluable_reason": {"type": "string"},
                },
                "required": [
                    "clause_id", "action_id", "strategy_id", "action", "actor",
                    "source_page", "source_text", "kind", "metric", "operator",
                    "threshold_source", "duration_hours", "scope",
                    "extraction_conf", "extraction_note", "evaluable",
                    "not_evaluable_reason",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["clauses"],
    "additionalProperties": False,
}


SYSTEM = """\
You compile published municipal Heat Action Plans into machine-readable rules.

You are an extractor. You do not evaluate conditions, rank anything, or decide \
what a city should do. You read the document and report what it says.

RULES

1. `source_text` MUST be copied character-for-character from the page you cite. \
Do not paraphrase, summarise, join sentences from different places, or fix \
typos. If you cannot quote it exactly, do not emit the clause. Every quote is \
checked against the page automatically and any that does not match is discarded.

2. `source_page` MUST be the page number the quote actually appears on, taken \
from the <page number="..."> wrapper.

3. Thresholds are recorded in the units the document uses. Phoenix writes \
Fahrenheit; put the Fahrenheit number in `threshold_source`. Never convert.

4. Classify `kind` honestly. This distinction is the point of the exercise:
   - operative_trigger  : a temperature condition the plan says causes an action
                          ("when temperatures exceed 105F, X is implemented")
   - external_trigger   : conditional, but the condition is defined by another
                          body ("when the National Weather Service issues ...")
   - indoor_standard    : a habitability threshold for indoor air, not a trigger
                          on outdoor conditions
   - planning_benchmark : a temperature used to describe or plan for climate,
                          with no action attached
   - scheduled          : no thermal condition at all; runs on the calendar
                          ("throughout the heat season", "every Saturday")

   Most actions in most heat plans are `scheduled`. Do not invent a trigger for \
an action that does not state one. Reporting an action as scheduled when it is \
scheduled is the correct answer, not a failure.

5. `actor` uses the department abbreviations exactly as the document's own \
department key defines them.

6. `extraction_conf` is your genuine confidence in [0,1]. Use `extraction_note` \
to record any inference you made, especially a duration inferred from words \
like "sustained" or "consecutive", or a threshold read from a table rather \
than prose.

7. Emit one clause per action in the plan's action inventory, plus one per \
distinct planning benchmark. If a single sentence carries two thresholds, emit \
two clauses and say so in `extraction_note`.
"""

USER_INSTRUCTION = """\
Compile every action and planning benchmark in this Heat Action Plan.

Use clause_id format: PHX-2026-A<action_id> for actions (e.g. PHX-2026-A1.1), \
and PHX-2026-BENCH-<SHORTNAME> for planning benchmarks.

Return every action in the plan's inventory, including the ones with no \
temperature condition.
"""


def _cache_path(doc_hash: str, provider: str, model: str) -> Path:
    key = hashlib.sha256(
        f"{provider}|{model}|{doc_hash}|{SYSTEM}|{USER_INSTRUCTION}".encode())
    return COMPILE_CACHE / f"{key.hexdigest()[:20]}.json.gz"


def _any_cached(doc_hash: str) -> Path | None:
    """Any committed compile for this document, whichever model produced it.

    Lets a judge with no LLM key reproduce the reported score without needing
    to know which provider we ran.
    """
    if not COMPILE_CACHE.exists():
        return None
    for p in sorted(COMPILE_CACHE.glob("*.json.gz")):
        hit = _load_cache(p)
        if hit and hit.get("doc_hash") == doc_hash:
            return p
    return None


def _load_cache(p: Path) -> dict | None:
    if not p.exists():
        return None
    try:
        with gzip.open(p, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, EOFError, json.JSONDecodeError):
        return None


def _save_cache(p: Path, obj: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(p, "wt", encoding="utf-8") as fh:
        json.dump(obj, fh, separators=(",", ":"))


def propose(plan: PlanText, provider: str | None = None, model: str | None = None,
            refresh: bool = False) -> tuple[list[dict], dict]:
    """Ask the model for clause proposals.

    Returns (proposals, provenance). Provenance records which provider and
    model produced them and whether they came from the committed cache.
    """
    from llm import DEFAULT_MODELS, DEFAULT_PROVIDER

    provider = provider or DEFAULT_PROVIDER
    model = model or os.getenv("TRIGGER_LLM_MODEL") or DEFAULT_MODELS.get(provider, "")

    if not refresh:
        path = _cache_path(plan.doc_hash, provider, model)
        hit = _load_cache(path)
        if hit is None:
            alt = _any_cached(plan.doc_hash)
            hit = _load_cache(alt) if alt else None
        if hit is not None:
            return hit["clauses"], {
                "provider": hit.get("provider", provider),
                "model": hit.get("model", model),
                "cached": True,
                "input_tokens": (hit.get("usage") or {}).get("input_tokens", 0),
                "output_tokens": (hit.get("usage") or {}).get("output_tokens", 0),
            }

    if available_provider() is None:
        raise LLMUnavailable(
            "No compiled output is cached for this document and no LLM key is set.\n"
            "  Set GEMINI_API_KEY (free: aistudio.google.com/apikey) to recompile,\n"
            "  or use the committed cache produced by the published run."
        )

    res = complete_json(
        system=SYSTEM,
        user_parts=[plan.as_prompt_document(), USER_INSTRUCTION],
        schema=CLAUSE_JSON_SCHEMA,
        provider=provider,
        model=model,
    )
    clauses = res.data.get("clauses", [])

    _save_cache(_cache_path(plan.doc_hash, res.provider, res.model), {
        "provider": res.provider, "model": res.model,
        "doc_hash": plan.doc_hash, "clauses": clauses,
        "usage": {"input_tokens": res.input_tokens,
                  "output_tokens": res.output_tokens},
    })
    return clauses, {
        "provider": res.provider, "model": res.model, "cached": False,
        "input_tokens": res.input_tokens, "output_tokens": res.output_tokens,
    }


def verify_and_build(proposals: list[dict], plan: PlanText) -> CompileResult:
    """Reject any proposal whose quote is not verbatim on its stated page."""
    res = CompileResult(raw_proposals=len(proposals))
    pages = {n: norm(t) for n, t in plan.pages.items()}

    for p in proposals:
        page = p.get("source_page")
        quote = p.get("source_text") or ""

        if page not in pages:
            res.rejected.append({**p, "_reason": f"page {page} is not in the document"})
            continue
        if not quote.strip():
            res.rejected.append({**p, "_reason": "empty source_text"})
            continue
        if norm(quote) not in pages[page]:
            res.rejected.append({
                **p, "_reason": f"quote not found verbatim on page {page}"})
            continue

        # Department codes must exist in the plan's own key.
        bad = [a for a in (p.get("actor") or []) if a not in DEPARTMENT_KEY]
        if bad:
            res.rejected.append({**p, "_reason": f"actor code(s) not in department key: {bad}"})
            continue

        try:
            res.accepted.append(Clause(
                clause_id=p["clause_id"],
                source_text=quote,
                source_page=page,
                kind=p["kind"],
                metric=p["metric"],
                action=p["action"],
                actor=list(p.get("actor") or []),
                operator=p.get("operator"),
                threshold_source=p.get("threshold_source"),
                duration_hours=p.get("duration_hours"),
                scope=p.get("scope") or "citywide",
                action_id=p.get("action_id"),
                strategy_id=p.get("strategy_id"),
                extraction_conf=float(p.get("extraction_conf", 0.0)),
                extraction_note=p.get("extraction_note") or "",
                evaluable=bool(p.get("evaluable", True)),
                not_evaluable_reason=p.get("not_evaluable_reason") or "",
            ).validate())
        except Exception as exc:  # noqa: BLE001 - schema violations are rejections
            res.rejected.append({**p, "_reason": f"schema validation: {exc}"})

    return res


def compile_plan(pdf_path: str | Path, provider: str | None = None,
                 model: str | None = None, refresh: bool = False) -> CompileResult:
    plan = PlanText.from_pdf(pdf_path)
    proposals, prov = propose(plan, provider=provider, model=model, refresh=refresh)
    res = verify_and_build(proposals, plan)
    res.provider = prov["provider"]
    res.model = prov["model"]
    res.cached = prov["cached"]
    res.input_tokens = prov.get("input_tokens", 0)
    res.output_tokens = prov.get("output_tokens", 0)
    return res
