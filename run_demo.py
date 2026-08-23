"""The one command. Prints the headline number in a few seconds, offline.

    python run_demo.py

No API key, no network, no waiting. Reads the committed results produced by
run_analysis.py. Use `python verify_all.py` to re-derive everything from the
cached API responses instead of trusting this file, and `python run_analysis.py`
to re-run the analysis itself.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

REPO = Path(__file__).resolve().parent
RESULTS = REPO / "data" / "results" / "divergence.json"
REPLICATION = REPO / "data" / "results" / "divergence_2026-08-16_2026-08-22.json"

W = 76


def rule(ch: str = "=") -> None:
    print(ch * W)


def main() -> int:
    if not RESULTS.exists():
        print("No results committed. Run `python run_analysis.py` first.")
        return 2

    res = json.loads(RESULTS.read_text(encoding="utf-8"))
    s, inv, st = res["summary"], res["inventory"], res["study"]
    clauses = {c["clause_id"]: c for c in res["clauses"]}
    head = clauses.get("PHX-2026-BENCH-LOW90")

    print()
    rule()
    print("  TRIGGER — the Heat Action Plan Compiler".center(W))
    rule()
    print(f"  {st['plan']}")
    print(f"  {st['city']} · {len(res['zones'])} {st['zone_unit']}s · "
          f"{st['aoi_sq_mi']:,.0f} sq mi at {st['granularity_m']} m")
    print(f"  Study window {s['window'][0]} to {s['window'][1]}")
    print()

    rule("-")
    print("  THE NUMBER")
    rule("-")
    if s.get("population_exposed"):
        pe, pt = s["population_exposed"], s["population_total"]
        print()
        print(f"      {pe:,} people — {pe/pt:.0%} of {st['city'].split(',')[0]} — live in")
        print(f"      {s['silent_zones']} of {len(res['zones'])} {st['zone_unit']}s that met the City's own")
        print(f"      overnight-heat benchmark on days the citywide")
        print(f"      reading never fired.")
        print()

    if head and head.get("worst_false_calm"):
        day, proxy_c, nz, max_c = head["worst_false_calm"]
        thr = head["threshold_f"]
        print(f"  Worst single day — {day}:")
        print(f"      citywide average overnight low   {proxy_c*9/5+32:>6.1f} degF")
        print(f"      the City's own threshold         {thr:>6.1f} degF   -> did NOT fire")
        print(f"      {st['zone_unit']}s actually above it     {nz:>6} of {len(res['zones'])}")
        print(f"      hottest of them                  {max_c*9/5+32:>6.1f} degF")
        print()

    rule("-")
    print("  WHAT THE PLAN ACTUALLY CONDITIONS ON")
    rule("-")
    print(f"      {inv['total']:>3}  clauses compiled from the published PDF")
    print(f"      {inv['scheduled']:>3}  activate on the CALENDAR, not on temperature")
    print(f"      {inv['conditional']:>3}  are conditioned on heat at all"
          f"  (all {inv['citywide_scope']} scoped citywide)")
    print()

    rule("-")
    print("  DIVERGENCE")
    rule("-")
    print(f"      silent zones        {s['silent_zones']} of {len(res['zones'])}")
    print(f"      silent zone-days    {s['silent_zone_days']}")
    print(f"      false-calm days     {len(s.get('false_calm_days', []))} of {s['days']}"
          f"   ({', '.join(s.get('false_calm_days', []))})")
    if s.get("median_lead_days") is not None:
        print(f"      median lead time    {s['median_lead_days']:.0f} days")
    print()

    if REPLICATION.exists():
        r = json.loads(REPLICATION.read_text(encoding="utf-8"))["summary"]
        rule("-")
        print("  REPLICATION — same pipeline, live data a year later")
        rule("-")
        print(f"      {'':<22s}{'2025 published':>16s}{'2026 live':>14s}")
        print(f"      {'silent zones':<22s}{s['silent_zones']:>16}{r['silent_zones']:>14}")
        print(f"      {'silent zone-days':<22s}{s['silent_zone_days']:>16}"
              f"{r['silent_zone_days']:>14}")
        if s.get("population_exposed") and r.get("population_exposed"):
            print(f"      {'population exposed':<22s}{s['population_exposed']:>16,}"
                  f"{r['population_exposed']:>14,}")
        print(f"      {'false-calm days':<22s}"
              f"{len(s.get('false_calm_days', [])):>16}"
              f"{len(r.get('false_calm_days', [])):>14}")
        print(f"\n      Window {r['window'][0]} to {r['window'][1]}, fetched from the")
        print(f"      live API — data this analysis had never seen.")
        print()

    rule("-")
    print("  HONESTY")
    rule("-")
    print("      The comparator is an area-weighted mean over the whole city AOI:")
    print("      a PROXY for station-based sensing, not a real station feed. It is")
    print("      a best-case single sensor, so every figure above is a LOWER BOUND.")
    print()
    print("      All thermal data is FortyGuard. No external weather source is")
    print("      used anywhere in this pipeline.")
    print()
    rule()
    print("  python verify_all.py     re-derive everything from cached responses")
    print("  streamlit run app.py     the map and clause browser")
    print("  docs/trigger_divergence_report.md    the full write-up")
    rule()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
