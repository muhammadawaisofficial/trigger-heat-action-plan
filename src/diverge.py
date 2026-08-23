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


# ==================================================================== over-trigger
#
# The same flaw, read from the other end. A trigger keyed to one fixed number
# fails in two directions depending on severity:
#
#   under-trigger   the citywide reading sits below the threshold while
#                   neighbourhoods sit above it. Coverage failure. Measured
#                   above as silent zones, population missed, lead time.
#
#   over-trigger    the threshold is cleared almost everywhere at once, so the
#                   rule fires but says nothing about where to go first.
#                   Targeting failure. Measured here.
#
# These are not two findings. Saturation is the mechanism; coverage loss is the
# consequence. A fixed threshold can only resolve variation it sits inside, and
# how much variation exists depends on severity and on the area being sensed.


@dataclass
class ClauseSaturation:
    """Over-trigger diagnostics for one clause across the window."""

    clause_id: str
    days: list[str] = field(default_factory=list)
    #: day -> TileStats.to_dict(), plus "severity_c"
    per_day: list[dict] = field(default_factory=list)

    @property
    def days_over_triggered(self) -> list[str]:
        return [d["day"] for d in self.per_day if d["failure_mode"] == "over_trigger"]

    @property
    def days_under_triggered(self) -> list[str]:
        return [d["day"] for d in self.per_day if d["failure_mode"] == "under_trigger"]

    @property
    def days_actionable(self) -> list[str]:
        return [d["day"] for d in self.per_day if d["actionable"]]

    @property
    def max_saturation(self) -> tuple[str, float] | None:
        if not self.per_day:
            return None
        w = max(self.per_day, key=lambda d: d["saturation_index"])
        return (w["day"], w["saturation_index"])

    @property
    def mean_saturation(self) -> float | None:
        v = [d["saturation_index"] for d in self.per_day]
        return sum(v) / len(v) if v else None

    def summary(self) -> dict:
        return {
            "clause_id": self.clause_id,
            "days": len(self.per_day),
            "days_actionable": len(self.days_actionable),
            "days_over_triggered": len(self.days_over_triggered),
            "days_under_triggered": len(self.days_under_triggered),
            "mean_saturation_index": (round(self.mean_saturation, 4)
                                      if self.mean_saturation is not None else None),
            "max_saturation": self.max_saturation,
            "per_day": self.per_day,
        }


def saturation_clause(results: Iterable[ClauseDayResult]) -> ClauseSaturation:
    """Collect per-day tile diagnostics for one clause."""
    results = sorted(results, key=lambda r: r.day)
    if not results:
        raise ValueError("no results to summarise")
    out = ClauseSaturation(clause_id=results[0].clause_id,
                           days=[r.day for r in results])
    for r in results:
        if r.tiles is None:
            continue
        row = r.tiles.to_dict()
        row["day"] = r.day
        row["severity_c"] = round(r.severity_c, 4) if r.severity_c is not None else None
        out.per_day.append(row)
    return out


# ------------------------------------------------------------- severity sweep

def severity_sweep(saturations: Iterable[ClauseSaturation]) -> dict:
    """Discrimination against severity, one row per clause per day.

    The expected shape is an inverted U: at low severity nothing clears the
    threshold, at high severity everything does, and targeting value exists
    only in between. Whether that shape actually appears in a given window is
    an empirical question -- a window chosen FOR severity samples only the hot
    end, and this function reports the range it actually covered so the reader
    can see whether the claim is testable on this data.
    """
    rows = []
    for sat in saturations:
        for d in sat.per_day:
            if d.get("severity_c") is None:
                continue
            rows.append({
                "clause_id": sat.clause_id,
                "day": d["day"],
                "severity_c": d["severity_c"],
                "severity_f": round(d["severity_c"] * 9 / 5 + 32, 2),
                "saturation_index": d["saturation_index"],
                "distinct_values": d["distinct_values"],
                "discrimination": d["discrimination"],
                "targeting_bits": d["targeting_bits"],
                "spread": d["spread"],
                "actionable": d["actionable"],
                "failure_mode": d["failure_mode"],
            })
    rows.sort(key=lambda r: (r["clause_id"], r["severity_c"]))

    sev = [r["severity_c"] for r in rows]
    n_act = sum(1 for r in rows if r["actionable"])
    bits = [r["targeting_bits"] for r in rows]
    return {
        "rows": rows,
        "n_points": len(rows),
        "severity_range_c": [min(sev), max(sev)] if sev else None,
        "severity_span_c": round(max(sev) - min(sev), 3) if sev else None,
        "actionable_points": n_act,
        "mean_targeting_bits": round(sum(bits) / len(bits), 4) if bits else None,
        "zero_bit_points": sum(1 for b in bits if b == 0.0),
        "over_triggered_points": sum(1 for r in rows
                                     if r["failure_mode"] == "over_trigger"),
        "under_triggered_points": sum(1 for r in rows
                                      if r["failure_mode"] == "under_trigger"),
        "axes": {
            "x": "severity_c - mean tile temperature over the AOI that day, degC",
            "y": ("targeting_bits - binary entropy of the firing share, 0 to 1. "
                  "1 bit when the trigger splits the city evenly, 0 bits when it "
                  "says the same thing everywhere. This is the axis that "
                  "collapses at BOTH ends of severity."),
            "y_alt": ("discrimination - distinct values as a share of tiles. "
                      "Weak at city scale: 272,917 floats always carry tens of "
                      "thousands of distinct values, so it never reaches zero "
                      "however useless the trigger is."),
        },
        "caveat": ("The published window was selected for severity, so it "
                   "samples the hot end of the range only. A wide severity "
                   "span is needed to observe both arms of the curve; the span "
                   "actually covered is reported above."),
    }


@dataclass
class DivergenceReport:
    """The headline result across every evaluated clause."""

    window: list[str]
    clauses: list[ClauseDivergence] = field(default_factory=list)
    saturations: list[ClauseSaturation] = field(default_factory=list)
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

    # ------------------------------------------------- over-trigger headline

    @property
    def clause_day_pairs(self) -> int:
        return sum(len(s.per_day) for s in self.saturations)

    @property
    def actionable_clause_days(self) -> int:
        return sum(len(s.days_actionable) for s in self.saturations)

    @property
    def over_triggered_clause_days(self) -> int:
        return sum(len(s.days_over_triggered) for s in self.saturations)

    @property
    def under_triggered_clause_days(self) -> int:
        return sum(len(s.days_under_triggered) for s in self.saturations)

    @property
    def worst_saturation(self) -> tuple[str, str, float] | None:
        """(clause_id, day, saturation_index) for the most saturated pairing."""
        best = None
        for s in self.saturations:
            for d in s.per_day:
                cand = (s.clause_id, d["day"], d["saturation_index"])
                if best is None or cand[2] > best[2]:
                    best = cand
        return best

    def summary(self) -> dict:
        n = self.clause_day_pairs
        return {
            "window": [self.window[0], self.window[-1]] if self.window else [],
            "days": len(self.window),
            "clauses_evaluated": len(self.clauses),

            # ---- A. under-trigger: coverage failure (unchanged)
            "median_lead_days": self.median_lead_days,
            "silent_zones": len(self.silent_zone_ids),
            "silent_zone_days": self.total_silent_zone_days,
            "false_calm_clauses": [c.clause_id for c in self.false_calm_clauses],
            "false_calm_days": sorted(self.false_calm_days),

            # ---- B. over-trigger: targeting failure
            "clause_days": n,
            "actionable_clause_days": self.actionable_clause_days,
            "actionable_share": (round(self.actionable_clause_days / n, 4)
                                 if n else None),
            "over_triggered_clause_days": self.over_triggered_clause_days,
            "under_triggered_clause_days": self.under_triggered_clause_days,
            "worst_saturation": self.worst_saturation,

            "baseline": self.baseline_label,
            "framing": ("One flaw, two failure modes, severity-dependent. A "
                        "trigger keyed to a single fixed number under-fires "
                        "where the citywide mean sits below it and over-fires "
                        "where severity clears it everywhere at once. "
                        "Saturation is the mechanism; lost coverage is the "
                        "consequence."),
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
