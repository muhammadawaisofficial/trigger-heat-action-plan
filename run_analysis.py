"""TRIGGER: compile a Heat Action Plan, re-run it on 2 m data, measure the gap.

This is the one command that reproduces the headline number.

    python run_analysis.py                  # from the committed cache, no key
    python run_analysis.py --refresh        # re-fetch from the API (needs a key)

Every determination is a deterministic comparison against FortyGuard data. No
language model is involved in any number this prints.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import study  # noqa: E402
from aggregate import ZoneAggregator, load_zones  # noqa: E402
from cache import CachedFortyGuard, OfflineCacheMiss, cache_report, has_key  # noqa: E402
from diverge import DivergenceReport, diverge_clause  # noqa: E402
from evaluate import Evaluator, evaluable  # noqa: E402
from parse import parse_heatmap  # noqa: E402
from schema import c_to_f, inventory, load_clauses  # noqa: E402

POP_PATH = Path(__file__).parent / "data" / "zones" / "phoenix_villages_population.json"


def load_population() -> dict[str, dict]:
    """Per-village population, if the Census join has been built.

    Optional: the divergence result stands without it, but "N people" is a far
    more meaningful statement than "N polygons".
    """
    if not POP_PATH.exists():
        return {}
    return json.loads(POP_PATH.read_text(encoding="utf-8")).get("villages", {})

# Selected by measurement, not assumption: the most severe consecutive 7 days
# between 1 Jul and 15 Aug 2025 by hours above the 105 degF threshold that
# Action 1.1 of the plan names. See scan_event.py. Independently corroborated
# by the plan itself, which records the seasonal high of 118 degF at Sky
# Harbor on 7 August and calls August the hottest month of the summer (p.6).
DEFAULT_START = "2025-08-02"
DEFAULT_END = "2025-08-08"


def daterange(start: str, end: str) -> list[str]:
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    return [(a + timedelta(days=i)).isoformat() for i in range((b - a).days + 1)]


def rule(t: str) -> None:
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=DEFAULT_START)
    ap.add_argument("--end", default=DEFAULT_END)
    ap.add_argument("--refresh", action="store_true",
                    help="allow live API calls on cache miss")
    args = ap.parse_args()

    days = daterange(args.start, args.end)

    rule("TRIGGER - Heat Action Plan Compiler")
    print(f"  city            {study.CITY}")
    print(f"  plan            {study.PLAN_TITLE}")
    print(f"  zones           {len(days) and ''}{study.ZONE_UNIT}s from {study.ZONES_SOURCE}")
    print(f"  AOI             {study.city_aoi_sq_mi():,.0f} sq mi, granularity "
          f"{study.GRANULARITY_M} m, one call per day")
    print(f"  window          {days[0]} .. {days[-1]}  ({len(days)} days)")
    print(f"  API key present {has_key()}"
          f"{'' if has_key() else '  -> running fully from the committed cache'}")

    # ---------------------------------------------------------- compilation
    rule("[A] COMPILE - the plan as machine-readable rules")
    clauses = load_clauses(study.GOLDEN_CLAUSES)
    inv = inventory(clauses)
    print(f"  clauses compiled from the published plan : {inv['total']}")
    print(f"    conditional on temperature             : {inv['conditional']}")
    print(f"    activated by the calendar, not heat    : {inv['scheduled']}")
    print(f"    indoor habitability standards          : {inv['by_kind'].get('indoor_standard', 0)}")
    print(f"    planning benchmarks                    : "
          f"{inv['by_kind'].get('planning_benchmark', 0)}")
    print(f"\n  Of the {inv['conditional']} clauses the plan does condition on heat, "
          f"{inv['citywide_scope']} are\n  scoped citywide - one reading decides for all "
          f"{study.city_aoi_sq_mi():,.0f} sq mi.")

    todo = [c for c in clauses if evaluable(c)]
    print(f"\n  evaluable against 2 m data: {len(todo)}")
    for c in todo:
        print(f"    {c.clause_id:<24s} {c.metric:<14s} {c.operator} "
              f"{c.threshold_source:g} degF ({c.threshold_c:.2f} degC)   p{c.source_page}")

    # ------------------------------------------------------------ evaluation
    rule("[B] EVALUATE - every clause against every zone, day by day")
    zones = load_zones(study.ZONES_PATH, name_field=study.ZONE_NAME_FIELD)
    pop = load_population()
    aoi = study.city_aoi()
    fg = CachedFortyGuard(verbose=False)

    if not has_key() and args.refresh:
        print("  --refresh requested but no API key is set; running from cache.")

    # One heatmap is needed just to establish the tile grid for the weights.
    try:
        probe = parse_heatmap(fg.heatmap(
            polygon_aoi=aoi, start_date=days[0], filter_type=3,
            granularity=study.GRANULARITY_M, analytic_type="tcm",
            label=f"phx-city tcm {days[0]}")["result"], "tcm")
    except OfflineCacheMiss as exc:
        print(f"\n  Cannot start: {exc}")
        return 2

    print(f"  tiles per call  {len(probe):,}")
    agg = ZoneAggregator(zones, probe.tiles, cache_key=study.ZONE_WEIGHT_KEY)
    print(f"  zones           {len(zones)} {study.ZONE_UNIT}s")

    ev = Evaluator(fg, agg, aoi, granularity=study.GRANULARITY_M)

    per_clause = {}
    for c in todo:
        try:
            per_clause[c.clause_id] = ev.evaluate_window(c, days)
            fired = sum(len(r.fired_zones) for r in per_clause[c.clause_id])
            pdays = sum(1 for r in per_clause[c.clause_id] if r.proxy_fired)
            print(f"    {c.clause_id:<24s} zone-days met {fired:>4}   "
                  f"proxy days fired {pdays}/{len(days)}")
        except OfflineCacheMiss as exc:
            print(f"    {c.clause_id:<24s} SKIPPED - {str(exc).splitlines()[0]}")

    if not per_clause:
        print("\n  Nothing evaluated. Run with an API key to populate the cache.")
        return 2

    # ------------------------------------------------------------ divergence
    rule("[C] DIVERGE - what citywide sensing costs")
    report = DivergenceReport(window=days)
    for cid, results in per_clause.items():
        report.clauses.append(diverge_clause(results))

    cl = {c.clause_id: c for c in clauses}
    for d in report.clauses:
        c = cl[d.clause_id]
        print(f"\n  {d.clause_id}  -  {c.action}")
        print(f"    threshold {c.threshold_source:g} degF   page {c.source_page}   "
              f"actor {', '.join(c.actor_full)}")
        print(f"    citywide proxy fired on {len(d.proxy_fired_days)}/{len(days)} days"
              f"{'  <- NEVER' if not d.proxy_fired_days else ''}")
        print(f"    zones meeting the condition: {d.zones_ever_met}/{len(zones)}"
              f"   zone-days: {d.zone_fired_day_count}")
        if d.silent_zones:
            print(f"    SILENT ZONES: {len(d.silent_zones)} zones met it on days the "
                  f"proxy did not ({d.silent_zone_days} zone-days)")
            if pop:
                exposed = sum(pop[z]["population"] for z in d.silent_zones if z in pop)
                total = sum(v["population"] for v in pop.values())
                print(f"      population in those zones: {exposed:,} "
                      f"({exposed/total:.0%} of the city)")
                worst = sorted((pop[z]["population"], pop[z]["name"])
                               for z in d.silent_zones if z in pop)[::-1][:3]
                print(f"      largest: " + ", ".join(f"{n} ({p:,})" for p, n in worst))
        if d.median_lead_days is not None:
            print(f"    median lead: {d.median_lead_days:.0f} day(s) ahead of the proxy")
        if d.false_calm_days:
            w = d.worst_false_calm
            print(f"    FALSE CALM on {len(d.false_calm_days)}/{len(days)} days: proxy said no "
                  f"while zones said yes")
            if w:
                unit = "degF" if c.metric != "air_temperature" else "h"
                conv = (lambda v: v * 9 / 5 + 32) if c.metric != "air_temperature" else (lambda v: v)
                print(f"      worst: {w[0]} - proxy {conv(w[1]):.1f} {unit} vs threshold "
                      f"{c.threshold_source:g} degF, but {w[2]} zones met it "
                      f"(highest {conv(w[3]):.1f} {unit})")
        if d.is_false_calm:
            print(f"    FALSE-CALM CLAUSE: never fired citywide, fired "
                  f"{d.zone_fired_day_count} zone-days hyperlocally")

    # -------------------------------------------------------------- headline
    rule("HEADLINE")
    s = report.summary()
    print(f"  Window                {s['window'][0]} .. {s['window'][1]} ({s['days']} days)")
    print(f"  Clauses evaluated     {s['clauses_evaluated']}")
    print(f"  Silent zones          {s['silent_zones']} of {len(zones)} {study.ZONE_UNIT}s")
    if pop:
        exposed = sum(pop[z]["population"] for z in report.silent_zone_ids if z in pop)
        total = sum(v["population"] for v in pop.values())
        print(f"  Population exposed    {exposed:,} of {total:,} "
              f"({exposed/total:.0%} of Phoenix)")
    print(f"  Silent zone-days      {s['silent_zone_days']}")
    print(f"  False-calm days       {len(s['false_calm_days'])} of {s['days']}"
          f"  {', '.join(s['false_calm_days'])}")
    print(f"  False-calm clauses    {len(s['false_calm_clauses'])}"
          f"{'  ' + ', '.join(s['false_calm_clauses']) if s['false_calm_clauses'] else ''}")
    if s["median_lead_days"] is not None:
        print(f"  Median lead time      {s['median_lead_days']:.0f} day(s)")
    print(f"\n  Baseline: {report.baseline_label}")

    # ----------------------------------------------------------------- write
    study.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = study.RESULTS_DIR / "divergence.json"
    out.write_text(json.dumps({
        "study": {
            "city": study.CITY, "plan": study.PLAN_TITLE, "plan_url": study.PLAN_URL,
            "zones_source": study.ZONES_SOURCE, "zone_unit": study.ZONE_UNIT,
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
            # Per-zone, per-day determinations so the UI needs no geometry work
            # and the whole demo runs from this one file.
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
    }, indent=2), encoding="utf-8")

    rep = cache_report()
    print(f"\n  results -> {out.relative_to(study.REPO_ROOT)}")
    print(f"  {fg.summary()}   cache on disk {rep['total_bytes']/1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
