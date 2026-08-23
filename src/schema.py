"""The Clause: a Heat Action Plan sentence turned into an executable rule.

This module owns the unit chain. Phoenix writes thresholds in Fahrenheit; the
FortyGuard heatmap ``threshold`` parameter is Celsius. That conversion happens
HERE and nowhere else. Sending 105 where 40.56 was meant computes hours above
105 degC and silently returns all zeros.

Every clause carries the verbatim sentence and the page it came from, because
the whole point of compiling a legal instrument is that a reader can check the
compilation against the source.

A note on ``kind``. Not every numeric temperature in a plan is an operative
trigger, and conflating them would overstate what the document actually
mandates. Four kinds are distinguished:

    operative_trigger   "...implemented when temperatures exceed 105 degF"
                        A condition the plan says causes an action.
    external_trigger    "...when the National Weather Service issues an
                        Extreme Heat Warning". Conditional, but the condition
                        is defined outside this document.
    indoor_standard     A habitability threshold for indoor air, not a trigger
                        for outdoor conditions.
    planning_benchmark  A temperature the plan uses to describe or plan for
                        climate, without attaching an action to it.
    scheduled           No thermal condition at all -- runs on the calendar.

Only ``operative_trigger`` and ``external_trigger`` can generate a FIRED /
NOT FIRED determination. The others are compiled and reported so the inventory
is complete and the reader can see what the plan does and does not condition.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------- unit chain

def f_to_c(fahrenheit: float) -> float:
    """The only Fahrenheit-to-Celsius conversion in this codebase."""
    return (fahrenheit - 32.0) * 5.0 / 9.0


def c_to_f(celsius: float) -> float:
    """Inverse, for display only. Never send the result to the API."""
    return celsius * 9.0 / 5.0 + 32.0


# ------------------------------------------------------------- vocabularies

CLAUSE_KINDS = (
    "operative_trigger",
    "external_trigger",
    "indoor_standard",
    "planning_benchmark",
    "scheduled",
)

#: Kinds that produce a FIRED / NOT FIRED determination against thermal data.
EVALUABLE_KINDS = ("operative_trigger", "external_trigger", "planning_benchmark")

METRICS = (
    "air_temperature",      # instantaneous 2 m air temperature
    "daily_high",           # daily maximum
    "daily_low",            # daily minimum (overnight)
    "heat_index",
    "apparent_temperature",
    "wet_bulb_temperature",
    "external_warning",     # a named advisory issued by another agency
    "indoor_air_temperature",
    "none",                 # scheduled actions carry no metric
)

OPERATORS = ("above", "below")
SCOPES = ("citywide", "district", "site", "indoor")

#: Department key, verbatim from the plan's own table on page 11 -- the
#: ``actor`` field pre-structured by the document itself.
#:
#: This is MUTATED IN PLACE by ``set_vocabulary`` when a city profile loads, so
#: modules that did ``from schema import DEPARTMENT_KEY`` keep seeing the active
#: city's departments. Rebinding it would silently leave them on Phoenix.
DEPARTMENT_KEY = {
    "OHRM": "Office of Heat Response and Mitigation",
    "COMMS": "Communications",
    "VOL": "Volunteer Programs",
    "OAC": "Arts and Culture",
    "HSD": "Human Services",
    "HR": "Human Resources",
    "NSD": "Neighborhood Services",
    "OPH": "Public Health",
    "OEM": "Office of Emergency Management",
    "PWD": "Public Works Department",
    "PRD": "Parks and Recreation Department",
    "WSD": "Water Services Department",
    "PTD": "Public Transit Department",
    "LRT": "Light Rail Transit",
    "OHS": "Office of Homeless Solutions",
    "FIN": "Finance Department",
    "INNOV": "Office of Innovation",
    # Present in the action table but absent from the printed key.
    "FIRE": "Fire Department",
    "LIB": "Library",
    "LAW": "Law Department",
}

STRATEGIES = {
    "1": "Equip first responders for effective heat response",
    "2": "Provide publicly accessible cool space and drinking water",
    "3": "Support cool and safe home environments",
    "4": "Support cool and safe mobility and recreation",
    "5": "Implement heat safety measures for workers",
    "6": "Educate the community and engage with partners",
}


def set_vocabulary(department_key: dict[str, str] | None = None,
                   strategies: dict[str, str] | None = None) -> None:
    """Point the validator at a different city's departments and strategies.

    Mutates in place rather than rebinding, so existing imports follow.
    """
    if department_key:
        DEPARTMENT_KEY.clear()
        DEPARTMENT_KEY.update(department_key)
    if strategies:
        STRATEGIES.clear()
        STRATEGIES.update(strategies)


class ClauseValidationError(ValueError):
    """A clause failed validation. Never silently repaired."""


@dataclass
class Clause:
    """One compiled rule, traceable to a page and a verbatim sentence."""

    clause_id: str
    source_text: str                  # verbatim, mandatory
    source_page: int                  # mandatory
    kind: str
    metric: str
    action: str
    actor: list[str] = field(default_factory=list)   # department codes

    operator: str | None = None
    threshold_source: float | None = None            # as written, degF
    threshold_unit_source: str = "F"
    duration_hours: int | None = None
    scope: str = "citywide"
    action_id: str | None = None                     # e.g. "1.1"
    strategy_id: str | None = None
    lead_time_req_h: int | None = None
    extraction_conf: float = 1.0
    extraction_note: str = ""
    evaluable: bool = True
    not_evaluable_reason: str = ""

    # -------------------------------------------------------------- derived

    @property
    def threshold_c(self) -> float | None:
        """Celsius value to send to the API. Converted in exactly one place."""
        if self.threshold_source is None:
            return None
        if self.threshold_unit_source.upper().startswith("C"):
            return float(self.threshold_source)
        return f_to_c(float(self.threshold_source))

    @property
    def actor_full(self) -> list[str]:
        return [DEPARTMENT_KEY.get(a, a) for a in self.actor]

    @property
    def strategy(self) -> str:
        return STRATEGIES.get(self.strategy_id or "", "")

    @property
    def is_conditional(self) -> bool:
        """Does the plan attach this action to a condition, rather than a date?"""
        return self.kind in ("operative_trigger", "external_trigger")

    def label(self) -> str:
        if self.threshold_source is None:
            return f"{self.clause_id}: {self.action}"
        return (f"{self.clause_id}: {self.metric} {self.operator} "
                f"{self.threshold_source:g} degF ({self.threshold_c:.2f} degC)")

    # ----------------------------------------------------------- validation

    def validate(self) -> "Clause":
        e = []
        if not self.source_text.strip():
            e.append("source_text is mandatory and must be verbatim")
        if not isinstance(self.source_page, int) or self.source_page < 1:
            e.append(f"source_page must be a positive int, got {self.source_page!r}")
        if self.kind not in CLAUSE_KINDS:
            e.append(f"kind {self.kind!r} not in {CLAUSE_KINDS}")
        if self.metric not in METRICS:
            e.append(f"metric {self.metric!r} not in {METRICS}")
        if self.scope not in SCOPES:
            e.append(f"scope {self.scope!r} not in {SCOPES}")
        if not 0.0 <= self.extraction_conf <= 1.0:
            e.append(f"extraction_conf must be in [0,1], got {self.extraction_conf}")

        # A threshold is meaningless without a direction to compare against.
        if self.threshold_source is not None and self.operator not in OPERATORS:
            e.append(f"threshold given but operator is {self.operator!r}")
        if self.operator is not None and self.threshold_source is None:
            e.append("operator given but no threshold")

        # Anything the pipeline will actually evaluate needs a full condition.
        if self.evaluable and self.kind in EVALUABLE_KINDS:
            if self.kind != "external_trigger" and self.threshold_source is None:
                e.append(f"kind={self.kind} is evaluable but carries no threshold")
        if not self.evaluable and not self.not_evaluable_reason:
            e.append("evaluable=False requires not_evaluable_reason")

        # Only enforced when the city profile actually supplies a key. A city
        # whose plan prints no department list should not fail every clause.
        if DEPARTMENT_KEY:
            for a in self.actor:
                if a not in DEPARTMENT_KEY:
                    e.append(f"actor {a!r} is not in the plan's department key")

        if e:
            raise ClauseValidationError(
                f"{self.clause_id} failed validation:\n  - " + "\n  - ".join(e))
        return self

    # ------------------------------------------------------------ transport

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["threshold_c"] = self.threshold_c
        d["actor_full"] = self.actor_full
        d["strategy"] = self.strategy
        d["is_conditional"] = self.is_conditional
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Clause":
        # Derived fields are recomputed, never trusted from the file.
        known = {k: v for k, v in d.items()
                 if k in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**known)


# ------------------------------------------------------------------- io

def load_clauses(path: str | Path) -> list[Clause]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data["clauses"] if isinstance(data, dict) else data
    return [Clause.from_dict(r).validate() for r in rows]


def save_clauses(clauses: list[Clause], path: str | Path, meta: dict | None = None) -> None:
    payload = {
        "meta": meta or {},
        "clauses": [c.to_dict() for c in clauses],
    }
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def inventory(clauses: list[Clause]) -> dict[str, Any]:
    """Structural summary of a compiled plan.

    The counts here are a headline finding in their own right: how much of a
    published heat plan is actually conditioned on heat.
    """
    by_kind: dict[str, int] = {}
    for c in clauses:
        by_kind[c.kind] = by_kind.get(c.kind, 0) + 1
    return {
        "total": len(clauses),
        "by_kind": by_kind,
        "conditional": sum(1 for c in clauses if c.is_conditional),
        "scheduled": sum(1 for c in clauses if c.kind == "scheduled"),
        "evaluable": sum(1 for c in clauses if c.evaluable and c.kind in EVALUABLE_KINDS),
        "citywide_scope": sum(1 for c in clauses if c.is_conditional and c.scope == "citywide"),
    }
