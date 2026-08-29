"""The plan's own clauses, evaluated live, right now, city-scale.

This is the answer to "can this run on real, live data" that actually proves
it rather than arguing for it: it runs the SAME evaluation code the published
headline runs on -- ``aggregate.ZoneAggregator`` and ``evaluate.Evaluator``,
unmodified -- against the most recent complete day, fetched from FortyGuard on
demand. Not a separate demo of liveness. The real pipeline, pointed at now.

WHY THIS IS CHEAP DESPITE BEING FULL CITY SCALE

Four of the plan's five evaluable clauses share one product: `tcm`, the same
heatmap call regardless of which of the four is being tested (only the
threshold each is COMPARED against differs, and that comparison happens after
the fetch, in Python). So evaluating all four for one day costs exactly ONE
live call -- 272,917 tiles, the whole city, the same cost as a tiny box, per
finding 4 of docs/api_findings.md. There is no reason to shrink this to a
demo-sized box.

The fifth evaluable clause, PHX-2026-A1.1, is measured through `exceedance` in
hours rather than through `tcm` in degrees, and is excluded here for the same
reason heatwave.py excludes it from its own chart: mixing an hours-denominated
series into a temperature comparison is the unit-chain trap this project
documents, not a feature to add casually. It remains fully covered in the
historical, cached analysis on the home page above this section.

WHY YESTERDAY, NOT TODAY

The API serves measured history; "today" before the day has fully elapsed
returns an incomplete or empty response. One day back is safely populated,
using the same rule liveprobe.py already establishes for the same reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import study
from aggregate import ZoneAggregator, load_zones
from cache import CachedFortyGuard
from evaluate import Evaluator, evaluable
from liveprobe import probe_day
from schema import load_clauses

#: Metrics backed by `tcm` -- one shared live call regardless of how many of
#: these clauses are evaluated. PHX-2026-A1.1 (`air_temperature`, exceedance,
#: hours) is deliberately excluded; see module docstring.
TEMPERATURE_METRICS = {"daily_high", "daily_low"}


@dataclass
class LiveClause:
    clause_id: str
    threshold_f: float
    proxy_fired: bool
    proxy_f: float | None
    zones: list[dict] = field(default_factory=list)


@dataclass
class LiveConditions:
    day: str
    clauses: list[LiveClause]
    was_fetched_live: bool  # False only when every value replayed today's cache


def _to_f(value: float, units: str) -> float:
    return value * 9 / 5 + 32 if units == "degC" else value


def run(day: str | None = None, population: dict | None = None) -> LiveConditions:
    """Evaluate every temperature-backed clause for one real day, live.

    Raises whatever CachedFortyGuard raises on a genuine miss with no key, or
    on a real API failure -- the caller renders both as a message, never lets
    either crash the page.
    """
    day = day or probe_day()
    population = population or {}

    clauses = [c for c in load_clauses(study.GOLDEN_CLAUSES)
              if evaluable(c) and c.metric in TEMPERATURE_METRICS]
    if not clauses:
        return LiveConditions(day=day, clauses=[], was_fetched_live=False)

    zones = load_zones(study.ZONES_PATH, name_field=study.ZONE_NAME_FIELD)
    aoi = study.city_aoi()
    fg = CachedFortyGuard(verbose=False)

    # Establishes the tile grid the zone weights are built from. Shares its
    # cache entry with every daily_high/daily_low clause's own tcm fetch below,
    # so this is not a second network call -- it is the same one, read once.
    from parse import parse_heatmap
    probe = parse_heatmap(fg.heatmap(
        polygon_aoi=aoi, start_date=day, filter_type=3,
        granularity=study.GRANULARITY_M, analytic_type="tcm",
        label=f"{study.CITY_SLUG} live-conditions tcm {day}")["result"], "tcm")
    agg = ZoneAggregator(zones, probe.tiles, cache_key=study.ZONE_WEIGHT_KEY)
    ev = Evaluator(fg, agg, aoi, granularity=study.GRANULARITY_M,
                  city_slug=study.CITY_SLUG)

    out = []
    for c in clauses:
        r = ev.evaluate_window(c, [day])[0]
        if not r.zones:
            continue
        units = r.zones[0].units
        out.append(LiveClause(
            clause_id=c.clause_id, threshold_f=c.threshold_source,
            proxy_fired=r.proxy_fired,
            proxy_f=_to_f(r.proxy.value, units) if r.proxy else None,
            zones=[{"name": z.zone_name, "value_f": _to_f(z.value, units),
                    "missed": z.fired and not r.proxy_fired,
                    "population": (population.get(z.zone_id) or {}).get("population") or 0}
                   for z in r.zones]))

    return LiveConditions(day=day, clauses=out, was_fetched_live=fg.stats["misses"] > 0)
