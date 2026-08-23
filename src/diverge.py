"""Trigger Divergence: what citywide sensing costs, measured in three ways.

Given the same compiled clauses evaluated twice -- once per urban village,
once against a single citywide number -- this module quantifies the gap.

    lead_time          For each clause and zone, how much earlier the zone met
                       the condition than the citywide proxy did. Reported in
                       DAYS from the daily evaluation, and in HOURS where an
                       hourly drill-down is available.

    silent_zones       Zones that met the condition on days the citywide proxy
                       never did. These are people the plan legally covers and
                       the sensor operationally misses.

    false_calm         Clauses that never activated under citywide sensing over
                       the whole window, but would have activated N times under
                       hyperlocal sensing.

Every number here is a count or a difference over deterministic comparisons.
Nothing is modelled, estimated or generated.

Honesty rule, enforced in the output: the comparator is an area-weighted mean
over the full AOI, used as a proxy for station-based sensing. It is not a real
station feed, and every structure this module emits carries that label.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Iterable

from evaluate import ClauseDayResult

BASELINE_LABEL = ("citywide proxy (area-weighted AOI mean) - a stand-in for "
                  "station-based sensing, not a station feed")


@dataclass
class ZoneLead:
    """One zone's lead over the citywide proxy for one clause."""

    clause_id: str
    zone_id: str
    zone_name: str
    first_met_day: str | None
    proxy_first_day: str | None
    lead_days: int | None       # positive: the zone met it first
    days_met: int
    days_proxy_met: int

    @property
    def never_seen_citywide(self) -> bool:
        return self.days_met > 0 and self.days_proxy_met == 0


@dataclass
class ClauseDivergence:
    """Divergence for one clause across the whole window."""

    clause_id: str
    days: list[str]
    zone_leads: list[ZoneLead] = field(default_factory=list)
    proxy_fired_days: list[str] = field(default_factory=list)
    zone_fired_day_count: int = 0        # sum over zones of days met
    silent_zone_days: int = 0            # zone-days met while proxy silent
    silent_zones: set[str] = field(default_factory=set)
    #: Days the citywide proxy read "no" while at least one zone read "yes".
    #: This is the operationally meaningful false calm: a clause can fire on
    #: some days overall and still leave whole neighbourhoods uncovered on the
    #: days it does not.
    false_calm_days: list[str] = field(default_factory=list)
    #: Worst single day: (day, proxy_value, n_zones_fired, max_zone_value)
    worst_false_calm: tuple[str, float, int, float] | None = None

    @property
    def median_lead_days(self) -> float | None:
        v = [z.lead_days for z in self.zone_leads if z.lead_days is not None and z.lead_days > 0]
        return statistics.median(v) if v else None

    @property
    def is_false_calm(self) -> bool:
        """Never fired citywide, but fired somewhere hyperlocally."""
        return not self.proxy_fired_days and self.zone_fired_day_count > 0

    @property
    def zones_ever_met(self) -> int:
        return sum(1 for z in self.zone_leads if z.days_met > 0)


def diverge_clause(results: Iterable[ClauseDayResult]) -> ClauseDivergence:
    """Compute divergence for one clause from its per-day evaluations."""
    results = sorted(results, key=lambda r: r.day)
    if not results:
        raise ValueError("no results to diverge")

    days = [r.day for r in results]
    clause_id = results[0].clause_id

    proxy_days = [r.day for r in results if r.proxy_fired]
    proxy_first = proxy_days[0] if proxy_days else None

    # Per zone: which days it met the condition.
    met: dict[str, list[str]] = {}
    names: dict[str, str] = {}
    for r in results:
        for d in r.zones:
            names[d.zone_id] = d.zone_name
            if d.fired:
                met.setdefault(d.zone_id, []).append(d.day)

    out = ClauseDivergence(clause_id=clause_id, days=days,
                           proxy_fired_days=proxy_days)

    for zid, zname in sorted(names.items(), key=lambda kv: kv[1]):
        zdays = sorted(met.get(zid, []))
        first = zdays[0] if zdays else None
        lead = None
        if first is not None and proxy_first is not None:
            lead = days.index(proxy_first) - days.index(first)
        elif first is not None and proxy_first is None:
            # Met locally, never met citywide: lead is undefined but the zone
            # is silent for the entire window. Counted in silent_zones instead.
            lead = None
        out.zone_leads.append(ZoneLead(
            clause_id=clause_id, zone_id=zid, zone_name=zname,
            first_met_day=first, proxy_first_day=proxy_first,
            lead_days=lead, days_met=len(zdays), days_proxy_met=len(proxy_days),
        ))
        out.zone_fired_day_count += len(zdays)

    # Silent zone-days: the condition met locally on a day the proxy was quiet.
    best: tuple[str, float, int, float] | None = None
    for r in results:
        if r.proxy_fired:
            continue
        fired = r.fired_zones
        if fired:
            out.false_calm_days.append(r.day)
            cand = (r.day, r.proxy.value if r.proxy else float("nan"),
                    len(fired), max(d.value for d in fired))
            if best is None or cand[2] > best[2]:
                best = cand
        for d in fired:
            out.silent_zone_days += 1
            out.silent_zones.add(d.zone_id)
    out.worst_false_calm = best

    return out


@dataclass
class DivergenceReport:
    """The headline result across every evaluated clause."""

    window: list[str]
    clauses: list[ClauseDivergence] = field(default_factory=list)
    baseline_label: str = BASELINE_LABEL

    # ------------------------------------------------------ headline numbers

    @property
    def median_lead_days(self) -> float | None:
        v = [c.median_lead_days for c in self.clauses if c.median_lead_days is not None]
        return statistics.median(v) if v else None

    @property
    def false_calm_clauses(self) -> list[ClauseDivergence]:
        return [c for c in self.clauses if c.is_false_calm]

    @property
    def silent_zone_ids(self) -> set[str]:
        s: set[str] = set()
        for c in self.clauses:
            s |= c.silent_zones
        return s

    @property
    def total_silent_zone_days(self) -> int:
        return sum(c.silent_zone_days for c in self.clauses)

    @property
    def false_calm_days(self) -> set[str]:
        """Days on which the proxy was silent somewhere it should not have been."""
        s: set[str] = set()
        for c in self.clauses:
            s |= set(c.false_calm_days)
        return s

    def summary(self) -> dict:
        return {
            "window": [self.window[0], self.window[-1]] if self.window else [],
            "days": len(self.window),
            "clauses_evaluated": len(self.clauses),
            "median_lead_days": self.median_lead_days,
            "silent_zones": len(self.silent_zone_ids),
            "silent_zone_days": self.total_silent_zone_days,
            "false_calm_clauses": [c.clause_id for c in self.false_calm_clauses],
            "false_calm_days": sorted(self.false_calm_days),
            "baseline": self.baseline_label,
        }


# ------------------------------------------------------------- hourly leads

@dataclass
class HourlyLead:
    """Hour-resolution crossing times for one clause on one day."""

    clause_id: str
    day: str
    zone_id: str
    zone_name: str
    first_hour_local: int | None     # Phoenix local hour the zone crossed
    proxy_hour_local: int | None
    lead_hours: int | None


def hourly_leads(clause_id: str, day: str,
                 zone_series: dict[str, list[tuple[int, float, str]]],
                 proxy_series: list[tuple[int, float]],
                 threshold_c: float) -> list[HourlyLead]:
    """First crossing hour per zone versus the proxy, on one day.

    ``zone_series`` maps zone_id -> [(local_hour, value_c, zone_name), ...].
    ``proxy_series`` is [(local_hour, value_c), ...]. Both must be in Phoenix
    local time; the conversion from the API's UTC hours happens upstream.
    """
    def first_cross(series):
        for h, v in series:
            if v > threshold_c:
                return h
        return None

    p_hour = first_cross(proxy_series)
    out: list[HourlyLead] = []
    for zid, rows in zone_series.items():
        rows = sorted(rows)
        name = rows[0][2] if rows else zid
        z_hour = first_cross([(h, v) for h, v, _ in rows])
        lead = (p_hour - z_hour) if (z_hour is not None and p_hour is not None) else None
        out.append(HourlyLead(
            clause_id=clause_id, day=day, zone_id=zid, zone_name=name,
            first_hour_local=z_hour, proxy_hour_local=p_hour, lead_hours=lead,
        ))
    return sorted(out, key=lambda h: (h.first_hour_local is None, h.first_hour_local or 0))
