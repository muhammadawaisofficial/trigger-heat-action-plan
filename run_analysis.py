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
from diverge import (DivergenceReport, diverge_clause, saturation_clause,  # noqa: E402
                     severity_sweep)
from evaluate import METRIC_PRODUCT, Evaluator, evaluable  # noqa: E402
from recover import (NotRecomputable, dwell_recovery,  # noqa: E402
                     percentile_recovery, zones_recovered)
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
    ap.add_argument("--out", default=None,
                    help="results filename (default divergence.json for the "
                         "published window, divergence_<start>_<end>.json "
                         "otherwise, so other windows never clobber the "
                         "published result)")
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
        report.saturations.append(saturation_clause(results))

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

    # ------------------------------------------ over-trigger / saturation
    rule("[C2] SATURATION - does the trigger fire selectively enough to act on?")
    print("  Measured on raw tiles, before any aggregation: 15 zone averages")
    print("  say nothing about whether the underlying field had structure.")
    print("  A clause is ACTIONABLE only if it fires somewhere between 5% and")
    print("  95% of tiles AND resolves more than 10 distinct values.\n")
    for sat in report.saturations:
        print(f"  {sat.clause_id}")
        print(f"    {'day':<12s}{'severity':>10s}{'sat_idx':>9s}"
              f"{'distinct':>10s}{'spread':>9s}  verdict")
        for d in sat.per_day:
            sev = (f"{d['severity_c'] * 9 / 5 + 32:.1f}F"
                   if d.get("severity_c") is not None else "-")
            print(f"    {d['day']:<12s}{sev:>10s}{d['saturation_index']:>9.3f}"
                  f"{d['distinct_values']:>10,}{d['spread']:>9.2f}  "
                  f"{d['failure_mode']}")
        if sat.mean_saturation is not None:
            print(f"    mean saturation {sat.mean_saturation:.3f}   "
                  f"actionable on {len(sat.days_actionable)}/{len(sat.per_day)} days")

    # -------------------------------------------------------- severity sweep
    rule("[C3] SEVERITY SWEEP - discrimination against severity")
    sweep = severity_sweep(report.saturations)
    if sweep["n_points"]:
        print(f"  {sweep['n_points']} clause-days   severity span "
              f"{sweep['severity_span_c']:.2f} degC "
              f"({sweep['severity_range_c'][0] * 9/5 + 32:.1f} - "
              f"{sweep['severity_range_c'][1] * 9/5 + 32:.1f} degF)")
        print(f"  actionable {sweep['actionable_points']}   "
              f"over-triggered {sweep['over_triggered_points']}   "
              f"under-triggered {sweep['under_triggered_points']}\n")
        print(f"  mean targeting {sweep['mean_targeting_bits']:.4f} bits   "
              f"zero-bit points {sweep['zero_bit_points']}/{sweep['n_points']}\n")
        print(f"  {'severity':>10s}{'bits':>8s}{'sat_idx':>9s}{'discrim':>9s}  clause / day")
        for r in sweep["rows"]:
            bar = "#" * int(round(r["targeting_bits"] * 24))
            print(f"  {r['severity_f']:>9.1f}F{r['targeting_bits']:>8.3f}"
                  f"{r['saturation_index']:>9.3f}{r['discrimination']:>9.4f}  "
                  f"{r['clause_id']} {r['day']} {bar}")
        print(f"\n  {sweep['caveat']}")
        sweep_path = study.results_path("severity_sweep.json")
        sweep_path.parent.mkdir(parents=True, exist_ok=True)
        sweep_path.write_text(json.dumps(sweep, indent=2), encoding="utf-8")
        print(f"  -> {sweep_path.relative_to(study.REPO_ROOT)}")

    # -------------------------------------------------------------- recovery
    rule("[D] RECOVERY - would a different trigger design resolve more?")
    print("  Same tiles, same day, same analytic. Only the rule changes.")
    print("  No API call: the percentile arm is a recomputation over cached")
    print("  tiles, which is why it is free.\n")
    recoveries = []
    for c in todo:
        sat = next((s for s in report.saturations if s.clause_id == c.clause_id), None)
        if sat is None or not sat.per_day:
            continue
        # The day this clause was least able to discriminate.
        worst = max(sat.per_day, key=lambda d: d["saturation_index"])
        day = worst["day"]
        product, tcm_field = METRIC_PRODUCT[c.metric]
        try:
            hm, tf = ev._heatmap(c, day)
        except OfflineCacheMiss:
            continue
        rows = (agg.aggregate_field(hm, tf) if tf else agg.aggregate(hm))
        zvals = [(r.name, r.value) for r in rows]
        try:
            fixed, pct = percentile_recovery(c, hm, tf, day, 90.0, zvals)
        except NotRecomputable:
            # An exceedance clause cannot be re-thresholded for free, but its
            # DWELL requirement can be changed at no cost: the hours are
            # already in the cached response. This is the cheapest of the three
            # designs and the only one deployable as written -- a clause edit,
            # no new instrument and no percentile.
            dwells = dwell_recovery(c, hm, day, zone_values=zvals)
            as_written = dwells[0]
            best = max(dwells, key=lambda r: r.targeting_bits)
            recoveries.append({
                "fixed": as_written.to_dict(),
                "dwell_sweep": [r.to_dict() for r in dwells],
                "best_dwell": best.to_dict(),
                "zones_recovered": zones_recovered(as_written, best),
            })
            print(f"  {c.clause_id}  on {day} (its most saturated day)")
            print(f"    threshold {as_written.threshold_f:.0f} degF held fixed; "
                  f"only the dwell requirement changes.")
            print(f"    {'design':<12s}{'sat_idx':>9s}{'bits':>8s}{'zones':>7s}")
            for r in dwells:
                mark = "  <- BEST" if r is best else ""
                mark += "  <- the plan as written" if r is as_written else ""
                print(f"    {r.design:<12s}{r.saturation_index:>9.3f}"
                      f"{r.targeting_bits:>8.3f}{r.zones_fired:>7}{mark}")
            print(f"    as written {as_written.targeting_bits:.3f} bits "
                  f"-> best {best.targeting_bits:.3f} bits ({best.design})")
            print(f"    zones_recovered {zones_recovered(as_written, best)}")
            print(f"    {best.note}")
            continue
        except ValueError:
            continue
        rec = zones_recovered(fixed, pct)
        recoveries.append({"fixed": fixed.to_dict(), "percentile": pct.to_dict(),
                           "zones_recovered": rec})
        print(f"  {c.clause_id}  on {day} (its most saturated day)")
        for r in (fixed, pct):
            print(f"    {r.design:<11s} thr {r.threshold_f:>6.1f} degF   "
                  f"sat {r.saturation_index:>6.3f}   distinct {r.distinct_values:>7,}   "
                  f"zones {r.zones_fired:>2}   "
                  f"{'ACTIONABLE' if r.actionable else 'not actionable'}")
        print(f"    zones_recovered {rec}")
        if pct.zone_names_fired:
            print(f"    would target: {', '.join(pct.zone_names_fired[:5])}"
                  f"{' ...' if len(pct.zone_names_fired) > 5 else ''}")
        print(f"    {pct.note}")

    # -------------------------------------------------------------- headline
    rule("HEADLINE - one flaw, two failure modes")
    s = report.summary()
    print(f"  {s['framing']}\n")
    print(f"  Window                {s['window'][0]} .. {s['window'][1]} ({s['days']} days)")
    print(f"  Clauses evaluated     {s['clauses_evaluated']}")
    print(f"\n  A. UNDER-TRIGGER (coverage failure)")
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

    print(f"\n  B. OVER-TRIGGER (targeting failure)")
    print(f"  Clause-days           {s['clause_days']}")
    if s["actionable_share"] is not None:
        print(f"  Actionable            {s['actionable_clause_days']} of "
              f"{s['clause_days']} ({s['actionable_share']:.0%})")
    print(f"  Over-triggered        {s['over_triggered_clause_days']}"
          f"   (fired on >95% of tiles: no basis for targeting)")
    print(f"  Under-triggered       {s['under_triggered_clause_days']}"
          f"   (fired on <5% of tiles: no coverage)")
    if s["worst_saturation"]:
        cid, day, si = s["worst_saturation"]
        print(f"  Worst saturation      {si:.3f} - {cid} on {day}")

    print(f"\n  Baseline: {report.baseline_label}")

    # ----------------------------------------------------------------- write
    # The published window keeps the canonical filename; any other window gets
    # its own, so an exploratory run cannot silently replace the headline that
    # verify_all.py asserts against.
    if args.out:
        name = args.out
    elif (args.start, args.end) == (DEFAULT_START, DEFAULT_END):
        name = "divergence.json"
    else:
        name = f"divergence_{args.start}_{args.end}.json"
    out = study.results_path(name)
    out.parent.mkdir(parents=True, exist_ok=True)
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
        "saturation": [s.summary() for s in report.saturations],
        "severity_sweep": sweep,
        "recovery": recoveries,
    }, indent=2), encoding="utf-8")

    rep = cache_report()
    print(f"\n  results -> {out.relative_to(study.REPO_ROOT)}")
    print(f"  {fg.summary()}   cache on disk {rep['total_bytes']/1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
