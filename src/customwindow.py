"""Run the full analysis over any window the user asks for, from the app.

The published result is one week of August 2025. This runs the SAME pipeline --
evaluate.Evaluator, aggregate.ZoneAggregator, diverge -- over any dates the API
will serve, and writes a results file in exactly the shape app.py already
renders. So a custom window is not a second, lesser view of the data. It is the
headline analysis, pointed somewhere else.

WHAT IT COSTS, MEASURED RATHER THAN GUESSED

Two calls per day, not one per clause. Four of the five evaluable clauses are
backed by `tcm` and share a single call; only PHX-2026-A1.1 needs its own
`exceedance` request at its own threshold. Credits are flat at 4,220 per call
regardless of area, so a seven-day window is 14 calls and roughly 59,000
credits, and each full-city call runs about 60 to 120 seconds when it is
healthy.

PARTIAL RUNS ARE NOT WASTED

Every call is cached on the way in, keyed by its request payload. A run that
dies halfway through leaves every completed day on disk, so the next attempt
replays those instantly and only fetches what is still missing. Long windows
are therefore resumable rather than all-or-nothing, which matters because the
API's own documented failure mode is a long hang rather than a fast error.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

import study
from aggregate import ZoneAggregator, load_zones
from cache import CachedFortyGuard
from diverge import DivergenceReport, diverge_clause, saturation_clause
from evaluate import Evaluator, evaluable
from parse import parse_heatmap
from schema import inventory, load_clauses

#: The API serves 2019-01-01 through roughly twelve hours ahead of now.
EARLIEST = date(2019, 1, 1)

#: Flat per call, whatever the area -- see docs/api_findings.md finding 4.
CREDITS_PER_CALL = 4_220

#: Measured wall-clock for a healthy full-city call, in seconds.
SECONDS_PER_CALL = (60, 120)

Progress = Callable[[str, int, int], None]


def latest_servable() -> date:
    """One day back. "Today" can be requested before the day has elapsed and
    comes back incomplete, so the newest safely complete day is yesterday."""
    from datetime import datetime, timezone
    return (datetime.now(timezone.utc) - timedelta(days=1)).date()


def daterange(start: str, end: str) -> list[str]:
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    return [(a + timedelta(days=i)).isoformat() for i in range((b - a).days + 1)]


def calls_per_day() -> int:
    """One shared `tcm` call, plus one `exceedance` call per distinct threshold.

    Derived from the clause set rather than hardcoded, so adding a clause with a
    new threshold changes the estimate instead of quietly invalidating it.
    """
    clauses = [c for c in load_clauses(study.GOLDEN_CLAUSES) if evaluable(c)]
    tcm = any(c.metric in ("daily_high", "daily_low", "external_warning")
              for c in clauses)
    exceedance_thresholds = {round(c.threshold_c, 4) for c in clauses
                             if c.metric == "air_temperature"}
    return int(tcm) + len(exceedance_thresholds)


def estimate(start: str, end: str) -> dict:
    """What this window will cost, before committing to it."""
    days = daterange(start, end)
    calls = len(days) * calls_per_day()
    return {
        "days": len(days),
        "calls": calls,
        "credits": calls * CREDITS_PER_CALL,
        "seconds_low": calls * SECONDS_PER_CALL[0],
        "seconds_high": calls * SECONDS_PER_CALL[1],
    }


def results_filename(start: str, end: str) -> str:
    return f"divergence_{start}_{end}.json"


def already_analysed(start: str, end: str) -> Path | None:
    p = study.results_path(results_filename(start, end))
    return p if p.exists() else None


def analyse(start: str, end: str, progress: Progress | None = None) -> dict:
    """Run the whole pipeline over one window and return the results dict.

    Raises OfflineCacheMiss with no key and no cache, or a FortyGuard error on a
    genuine API failure. The caller renders either as a message; this must never
    be allowed to take a page down.
    """
    days = daterange(start, end)
    note = progress or (lambda *_: None)

    clauses = load_clauses(study.GOLDEN_CLAUSES)
    todo = [c for c in clauses if evaluable(c)]
    inv = inventory(clauses)

    zones = load_zones(study.ZONES_PATH, name_field=study.ZONE_NAME_FIELD)
    pop_path = study.REPO_ROOT / study.CITY_PROFILE.population_path
    pop = (json.loads(pop_path.read_text(encoding="utf-8")).get("villages", {})
           if pop_path.exists() else {})
    aoi = study.city_aoi()
    fg = CachedFortyGuard(verbose=False)

    note("Establishing the tile grid", 0, len(todo) + 1)
    probe = parse_heatmap(fg.heatmap(
        polygon_aoi=aoi, start_date=days[0], filter_type=3,
        granularity=study.GRANULARITY_M, analytic_type="tcm",
        label=f"{study.CITY_SLUG} tcm {days[0]}")["result"], "tcm")
    agg = ZoneAggregator(zones, probe.tiles, cache_key=study.ZONE_WEIGHT_KEY)
    ev = Evaluator(fg, agg, aoi, granularity=study.GRANULARITY_M,
                   city_slug=study.CITY_SLUG)

    per_clause = {}
    for i, c in enumerate(todo, 1):
        note(f"Evaluating {c.clause_id} over {len(days)} days", i, len(todo) + 1)
        per_clause[c.clause_id] = ev.evaluate_window(c, days)

    report = DivergenceReport(window=days)
    for results in per_clause.values():
        report.clauses.append(diverge_clause(results))
        report.saturations.append(saturation_clause(results))

    cl = {c.clause_id: c for c in clauses}
    s = report.summary()
    out = {
        "study": {
            "city": study.CITY, "plan": study.PLAN_TITLE,
            "plan_url": study.PLAN_URL, "zones_source": study.ZONES_SOURCE,
            "zone_unit": study.ZONE_UNIT,
            "aoi_sq_mi": round(study.city_aoi_sq_mi(), 1),
            "granularity_m": study.GRANULARITY_M,
            "timezone_note": study.TIMEZONE_NOTE,
        },
        "inventory": inv,
        "summary": s | ({
            "population_exposed": sum(pop[z]["population"]
                                      for z in report.silent_zone_ids if z in pop),
            "population_total": sum(v["population"] for v in pop.values()),
        } if pop else {}),
        "population_source": ("US Census ACS 5-year 2023 block groups, areally "
                              "interpolated onto village boundaries") if pop else None,
        "clauses": [{
            "clause_id": d.clause_id,
            "action": cl[d.clause_id].action,
            "source_page": cl[d.clause_id].source_page,
            "source_text": cl[d.clause_id].source_text,
            "actor": cl[d.clause_id].actor_full,
            "threshold_f": cl[d.clause_id].threshold_source,
            "threshold_c": cl[d.clause_id].threshold_c,
            "proxy_fired_days": d.proxy_fired_days,
            "zone_fired_day_count": d.zone_fired_day_count,
            "silent_zones": sorted(d.silent_zones),
            "silent_zone_days": d.silent_zone_days,
            "median_lead_days": d.median_lead_days,
            "is_false_calm": d.is_false_calm,
            "false_calm_days": d.false_calm_days,
            "worst_false_calm": d.worst_false_calm,
            "zone_leads": [asdict(z) for z in d.zone_leads],
            "determinations": [{
                "day": r.day,
                "proxy": {"value": r.proxy.value, "fired": r.proxy.fired,
                          "units": r.proxy.units, "margin": r.proxy.margin},
                "zones": [{"zone_id": z.zone_id, "name": z.zone_name,
                           "value": z.value, "fired": z.fired,
                           "margin": z.margin, "units": z.units}
                          for z in r.zones],
            } for r in per_clause[d.clause_id]],
        } for d in report.clauses],
        "zones": [{"zone_id": z.zone_id, "name": z.name,
                   "area_sq_mi": round(z.area_sq_mi, 1),
                   "population": pop.get(z.zone_id, {}).get("population")}
                  for z in zones],
        "saturation": [sat.summary() for sat in report.saturations],
    }
    return out


def save(result: dict, start: str, end: str) -> Path:
    """Persist a completed window so it joins the selectable list.

    Never writes divergence.json: that filename is the published result that
    verify_all.py asserts against, and an exploratory run must not be able to
    overwrite the number the whole submission rests on.
    """
    name = results_filename(start, end)
    assert name != "divergence.json", "refusing to overwrite the published window"
    path = study.results_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return path
