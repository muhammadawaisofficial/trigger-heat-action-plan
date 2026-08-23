"""The action brief: ranked recommendations, each traceable to a clause.

The ranking is deterministic. The prose is generated. The two are kept apart on
purpose, and the boundary is enforced rather than requested.

How the boundary is enforced
----------------------------
The model is given a JSON block of already-computed facts and nothing else --
no temperature data, no thresholds it has not been handed, no freedom to
recompute anything. It writes one sentence per recommendation.

Then **every number that appears in the generated sentence is checked against
the facts it was given.** A figure the model invented, rounded differently, or
carried over from another zone does not appear in a computed fact and is
flagged. Narration that fails the check is replaced by a deterministic
fallback sentence assembled from the facts themselves.

So the brief degrades to plain templated English if the model misbehaves. It
never states a number the pipeline did not compute.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from llm import LLMUnavailable, complete_json
from schema import Clause


@dataclass
class Recommendation:
    """One ranked action, with the facts that justify it."""

    rank: int
    zone_id: str
    zone_name: str
    population: int | None
    clause_id: str
    action: str
    actor: list[str]
    source_page: int
    source_text: str
    threshold_f: float
    days_met: int
    days_proxy_fired: int
    silent_days: list[str]
    worst_day: str | None
    worst_value_f: float | None
    lead_days: int | None
    severity: float
    narration: str = ""
    narration_verified: bool = True
    unverified_numbers: list[str] = field(default_factory=list)

    def facts(self) -> dict:
        """Exactly what the model is allowed to know."""
        return {
            "zone": self.zone_name,
            "population": self.population,
            "clause_id": self.clause_id,
            "action": self.action,
            "responsible_departments": self.actor,
            "threshold_degF": self.threshold_f,
            "days_condition_met_in_window": self.days_met,
            "days_citywide_trigger_fired": self.days_proxy_fired,
            "days_met_while_citywide_silent": len(self.silent_days),
            "silent_days": self.silent_days,
            "worst_day": self.worst_day,
            "zone_value_on_worst_day_degF": self.worst_value_f,
            "lead_days_over_citywide": self.lead_days,
        }

    def fallback(self) -> str:
        """Deterministic English, used when narration cannot be verified."""
        who = ", ".join(self.actor) or "the responsible department"
        pop = f"{self.population:,} residents" if self.population else "residents"
        s = (f"{self.zone_name} ({pop}) met the {self.threshold_f:g} degF condition "
             f"on {self.days_met} of the days in the window")
        if self.silent_days:
            s += (f", including {len(self.silent_days)} day(s) when the citywide "
                  f"trigger did not fire")
        s += f". {who} is named for this action in the plan."
        return s


# ------------------------------------------------------------------ ranking

def rank(results: dict, clauses: dict[str, Clause],
         population: dict[str, dict]) -> list[Recommendation]:
    """Rank zone-clause pairs by exposed population-days of silent risk.

    severity = population x days the condition was met while the citywide
    trigger stayed silent. Population is the exposure; silent days are the
    unmet obligation. Zones with no silent days score zero and are excluded --
    the plan already covers them.
    """
    out: list[Recommendation] = []

    for c in results["clauses"]:
        cid = c["clause_id"]
        clause = clauses.get(cid)
        if clause is None or not c["silent_zones"]:
            continue

        # Which days was each zone silent-but-hot?
        silent_by_zone: dict[str, list[str]] = {}
        value_by_zone: dict[str, dict[str, float]] = {}
        for det in c["determinations"]:
            proxy_fired = det["proxy"]["fired"]
            for z in det["zones"]:
                value_by_zone.setdefault(z["zone_id"], {})[det["day"]] = z["value"]
                if z["fired"] and not proxy_fired:
                    silent_by_zone.setdefault(z["zone_id"], []).append(det["day"])

        leads = {z["zone_id"]: z for z in c["zone_leads"]}

        for zid, sdays in silent_by_zone.items():
            zl = leads.get(zid, {})
            pop = (population.get(zid) or {}).get("population")
            worst_day = max(sdays, key=lambda d: value_by_zone[zid][d])
            worst_c = value_by_zone[zid][worst_day]
            out.append(Recommendation(
                rank=0,
                zone_id=zid,
                zone_name=zl.get("zone_name", zid),
                population=pop,
                clause_id=cid,
                action=c["action"],
                actor=c["actor"],
                source_page=c["source_page"],
                source_text=c["source_text"],
                threshold_f=c["threshold_f"],
                days_met=zl.get("days_met", len(sdays)),
                days_proxy_fired=len(c["proxy_fired_days"]),
                silent_days=sorted(sdays),
                worst_day=worst_day,
                worst_value_f=round(worst_c * 9 / 5 + 32, 1),
                lead_days=zl.get("lead_days"),
                severity=(pop or 0) * len(sdays),
            ))

    out.sort(key=lambda r: -r.severity)
    for i, r in enumerate(out, 1):
        r.rank = i
    return out


# -------------------------------------------------------------- verification

_NUM = re.compile(r"\d[\d,]*\.?\d*")


def _numbers_in(text: str) -> list[str]:
    return [m.group(0) for m in _NUM.finditer(text)]


def _allowed_numbers(facts: dict) -> set[str]:
    """Every rendering of every number the model was given."""
    ok: set[str] = set()

    def add(v):
        if v is None or isinstance(v, bool):
            return
        if isinstance(v, (int, float)):
            ok.add(f"{v:g}")
            ok.add(f"{v:,}" if isinstance(v, int) else f"{v:.1f}")
            ok.add(str(v))
            if float(v).is_integer():
                ok.add(str(int(v)))
                ok.add(f"{int(v):,}")
        elif isinstance(v, str):
            # Dates carry digits; allow their components.
            for part in re.split(r"[-/ :]", v):
                if part.isdigit():
                    ok.add(part.lstrip("0") or "0")
                    ok.add(part)
            ok.add(v)
        elif isinstance(v, (list, tuple)):
            add(len(v))
            for x in v:
                add(x)

    for v in facts.values():
        add(v)
    return ok


def verify_narration(text: str, facts: dict) -> tuple[bool, list[str]]:
    """Is every number in the prose traceable to a fact we handed the model?"""
    allowed = _allowed_numbers(facts)
    bad = []
    for n in _numbers_in(text):
        clean = n.rstrip(".")
        if clean in allowed or clean.replace(",", "") in {a.replace(",", "") for a in allowed}:
            continue
        bad.append(n)
    return (not bad), bad


# ---------------------------------------------------------------- narration

SYSTEM = """\
You write one sentence of operational English per item for a city heat-response \
briefing.

You are given computed facts. You may only restate those facts. You must not \
introduce any number that is not in the facts, must not estimate, must not \
infer causes, and must not recommend anything the facts do not support.

Every number you write is checked against the facts automatically. A number \
that is not there causes the sentence to be discarded.

Write plainly, as an operations note to a named department. No adjectives about \
severity, no urgency language, no speculation about health outcomes. State what \
was measured and who is named for it.
"""

NARRATION_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "clause_id": {"type": "string"},
                    "zone": {"type": "string"},
                    "sentence": {"type": "string"},
                },
                "required": ["clause_id", "zone", "sentence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def narrate(recs: list[Recommendation], provider: str | None = None,
            model: str | None = None) -> list[Recommendation]:
    """Attach one verified sentence to each recommendation.

    On any failure -- no key, model unavailable, unverifiable numbers -- the
    deterministic fallback sentence is used instead. The brief is never blocked
    on the model and never carries an unverified figure.
    """
    payload = [{"clause_id": r.clause_id, "zone": r.zone_name, **r.facts()}
               for r in recs]

    try:
        res = complete_json(
            system=SYSTEM,
            user_parts=[json.dumps({"items": payload}, indent=2),
                        "Write one sentence per item, in the same order."],
            schema=NARRATION_SCHEMA,
            provider=provider,
            model=model,
        )
        by_key = {(i.get("clause_id"), i.get("zone")): i.get("sentence", "")
                  for i in res.data.get("items", [])}
    except (LLMUnavailable, Exception):  # noqa: BLE001 - fall back, never fail
        by_key = {}

    for r in recs:
        sentence = by_key.get((r.clause_id, r.zone_name), "")
        if not sentence:
            r.narration = r.fallback()
            r.narration_verified = True   # deterministic text is trivially valid
            continue
        ok, bad = verify_narration(sentence, r.facts())
        if ok:
            r.narration = sentence
            r.narration_verified = True
        else:
            r.narration = r.fallback()
            r.narration_verified = False
            r.unverified_numbers = bad
    return recs
