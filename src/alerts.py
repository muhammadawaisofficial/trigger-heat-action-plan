"""Divergence alerts: fire on an unexecuted legal obligation, not on a temperature.

Every heat product alerts on heat. "It is 108 degrees in your neighbourhood" is
true, and an emergency manager already knows it. It does not tell them whether
anyone is *required* to do anything, who that is, or what they are required to
do.

This module emits a different kind of alert. It fires when a compiled clause of
the city's own heat plan was MET in a neighbourhood while the citywide reading
stayed below its threshold -- that is, when a legal obligation was incurred
locally and the instrument that triggers it never noticed. The alert therefore
carries a named department, a page number and a verbatim sentence, because those
are what turn a reading into an action someone is accountable for.

DESIGN, GROUNDED IN THE ALERTING LITERATURE

  Severity tiers.        Red alerts are read as credible and drive behaviour;
                         yellow draws the weakest response. Tiers here are
                         earned by measured exposure, not assigned by feel, so a
                         red alert stays rare enough to remain credible.

  Name the local impact. Focus on local health impact and affected population
                         motivates response far more than an abstract
                         temperature. Every alert names the neighbourhood and
                         the number of residents.

  Cite the authority.    Consistency between the alert and the official
                         instrument is what earns trust. Every alert quotes the
                         clause verbatim and links the page it came from.

  Be actionable.         An alert with no named actor is a weather report. Each
                         one carries the department the plan itself names.

WHAT DECIDES, AND WHAT DOES NOT

Detection is entirely deterministic: comparisons against computed values, no
model involved. A language model may narrate an alert into prose, but only over
facts already computed, and the narration is checked number-by-number against
them before it is shown. If a single figure cannot be traced, the deterministic
text is used instead. The model never decides whether to alert, at what severity,
or about whom.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

#: Severity tiers. Thresholds are on exposed residents, so a red alert is earned
#: by scale of impact rather than by how hot it sounds.
RED_POPULATION = 100_000
AMBER_POPULATION = 25_000


@dataclass
class Alert:
    """One clause, met in one zone, on one day the citywide trigger stayed quiet."""

    alert_id: str
    day: str
    zone_id: str
    zone_name: str
    population: int | None
    clause_id: str
    clause_action: str
    source_page: int
    source_text: str
    actor: list[str]
    threshold_f: float
    measured_f: float
    proxy_f: float
    units: str
    city: str
    plan_title: str
    plan_url: str

    @property
    def margin_f(self) -> float:
        """How far the neighbourhood was over the line."""
        return self.measured_f - self.threshold_f

    @property
    def proxy_shortfall_f(self) -> float:
        """How far the citywide reading sat BELOW the line. The near miss."""
        return self.threshold_f - self.proxy_f

    @property
    def severity(self) -> str:
        p = self.population or 0
        if p >= RED_POPULATION:
            return "RED"
        if p >= AMBER_POPULATION:
            return "AMBER"
        return "YELLOW"

    @property
    def headline(self) -> str:
        return (f"{self.zone_name}: obligation incurred, citywide trigger silent")

    def message(self) -> str:
        """The alert as a duty officer would read it. Deterministic."""
        pop = f"{self.population:,} residents" if self.population else "residents"
        return (
            f"{self.severity} — {self.zone_name}, {self.day}\n"
            f"{self.zone_name} reached {self.measured_f:.1f} °F against the "
            f"{self.threshold_f:g} °F threshold in clause {self.clause_id} "
            f"({self.margin_f:+.1f} °F over). The citywide reading was "
            f"{self.proxy_f:.1f} °F — {self.proxy_shortfall_f:.1f} °F below the "
            f"threshold — so no citywide trigger fired.\n"
            f"{pop} are in this area. The plan names "
            f"{', '.join(self.actor) or 'no department'} for this action.\n"
            f"Authority: {self.plan_title}, page {self.source_page}."
        )

    def to_dict(self) -> dict[str, Any]:
        """Machine-readable payload, for a queue, a webhook or a duty roster."""
        return {
            "alert_id": self.alert_id,
            "severity": self.severity,
            "issued_for": self.day,
            "city": self.city,
            "zone": {"id": self.zone_id, "name": self.zone_name,
                     "population": self.population},
            "condition": {
                "clause_id": self.clause_id,
                "threshold_f": self.threshold_f,
                "measured_f": round(self.measured_f, 2),
                "margin_f": round(self.margin_f, 2),
                "citywide_proxy_f": round(self.proxy_f, 2),
                "citywide_shortfall_f": round(self.proxy_shortfall_f, 2),
                "citywide_fired": False,
            },
            "obligation": {
                "action": self.clause_action,
                "responsible": self.actor,
                "authority": {
                    "document": self.plan_title,
                    "page": self.source_page,
                    "quote": self.source_text,
                    "url": f"{self.plan_url}#page={self.source_page}",
                },
            },
            "baseline_note": (
                "The citywide comparator is an area-weighted mean over the whole "
                "city AOI, used as a proxy for station-based sensing. It is not a "
                "real station feed, and it is a best-case single sensor, so this "
                "alert is a lower bound."),
            "generated_by": "deterministic comparison; no language model involved",
        }


def detect(results: dict, population: dict[str, dict] | None = None,
           city: str = "", plan_title: str = "", plan_url: str = "",
           day: str | None = None) -> list[Alert]:
    """Every clause-zone-day where an obligation was incurred and missed.

    Purely a comparison over values already computed by the evaluator. Sorted by
    severity, then by exposed population, so the top of the list is where finite
    crews should go first.
    """
    population = population or {}
    zones = {z["zone_id"]: z for z in results.get("zones", [])}
    out: list[Alert] = []

    for clause in results.get("clauses", []):
        for det in clause.get("determinations", []):
            if day and det["day"] != day:
                continue
            if det["proxy"]["fired"]:
                continue                      # the city noticed; no divergence
            units = det["zones"][0]["units"] if det["zones"] else "degC"
            to_f = (lambda v: v * 9 / 5 + 32) if units == "degC" else (lambda v: v)

            for z in det["zones"]:
                if not z["fired"]:
                    continue
                zid = z["zone_id"]
                out.append(Alert(
                    alert_id=f"{clause['clause_id']}|{zid}|{det['day']}",
                    day=det["day"], zone_id=zid, zone_name=z["name"],
                    population=population.get(zid, {}).get("population"),
                    clause_id=clause["clause_id"],
                    clause_action=clause.get("action", ""),
                    source_page=clause.get("source_page", 0),
                    source_text=clause.get("source_text", ""),
                    actor=clause.get("actor") or [],
                    threshold_f=clause.get("threshold_f", 0.0),
                    measured_f=to_f(z["value"]),
                    proxy_f=to_f(det["proxy"]["value"]),
                    units=units, city=city,
                    plan_title=plan_title, plan_url=plan_url,
                ))

    order = {"RED": 0, "AMBER": 1, "YELLOW": 2}
    out.sort(key=lambda a: (order[a.severity], -(a.population or 0), a.day))
    return out


def summarise(alerts: Iterable[Alert]) -> dict[str, Any]:
    alerts = list(alerts)
    by_zone: dict[str, int] = {}
    for a in alerts:
        by_zone[a.zone_id] = by_zone.get(a.zone_id, 0) + 1
    exposed = sum((a.population or 0) for a in
                  {a.zone_id: a for a in alerts}.values())
    return {
        "alerts": len(alerts),
        "red": sum(1 for a in alerts if a.severity == "RED"),
        "amber": sum(1 for a in alerts if a.severity == "AMBER"),
        "yellow": sum(1 for a in alerts if a.severity == "YELLOW"),
        "zones": len(by_zone),
        "population_exposed": exposed,
        "days": sorted({a.day for a in alerts}),
    }
