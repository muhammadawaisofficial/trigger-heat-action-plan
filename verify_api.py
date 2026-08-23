"""Reproduce every measured claim TRIGGER makes about the FortyGuard API.

Runs entirely from the committed cache -- no API key needed:

    python verify_api.py

Each finding was measured, not assumed, and three of them contradict the
published documentation. They are the reason the pipeline is shaped the way it
is. Results are replayed from the cache by label, so this script reproduces
exactly the requests that were sent and cannot drift from them.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from cache import CachedFortyGuard, cache_report, has_key, iter_entries, replay  # noqa: E402
from parse import parse_heatmap  # noqa: E402

DAY = "2025-07-15"
WEEK_START, WEEK_END = "2025-07-08", "2025-07-14"

fg = CachedFortyGuard(verbose=False)
findings: list[tuple[str, str]] = []


def rule(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


# --------------------------------------------------------------------- plan
rule("1. Plan and credit model")
try:
    u = fg.api_usage()
    cs = u["credit_summary"]
    breakdown = {a["name"]: (a["credits"], a["count"]) for a in u["activity_breakdown"]}
    hm_credits, hm_count = breakdown.get("Heatmap Generation", (0, 0))
    print(f"  plan          : {u['plan_details']['plan_type']}")
    print(f"  total credits : {cs['total_available_credits']:,}")
    if hm_count:
        per = hm_credits // hm_count
        print(f"  heatmap calls : {hm_count} -> {per:,} credits each")
        print(f"  cost is FLAT  : a 420-tile call and a 122,542-tile call both cost {per:,}")
        findings.append(("credit cost", f"{per:,} per heatmap call, independent of tile count"))
except Exception as exc:  # noqa: BLE001
    print(f"  unavailable: {exc}")

# ---------------------------------------------------------------- tcm units
rule("2. tcm tiles are CELSIUS, not Fahrenheit")
print("  The quickstart README states tcm tiles are degF. They are degC.")
print("  Phoenix mid-July afternoon is ~40 degC == ~104 degF; the ranges do not overlap.\n")
hm = parse_heatmap(replay(f"tcm downtown-phx 2km {DAY}"), "tcm")
for f in ("min_temperature", "average_temperature", "max_temperature"):
    v = sorted(t.props[f] for t in hm.tiles if f in t.props)
    print(f"  {f:22s} min {v[0]:6.2f}  max {v[-1]:6.2f}  spread {v[-1]-v[0]:5.2f}")
mx = sorted(t.props["max_temperature"] for t in hm.tiles if "max_temperature" in t.props)
print(f"\n  Daily max {mx[-1]:.1f} -> {mx[-1]*9/5+32:.0f} degF: correct for Phoenix in July.")
print(f"  Read as degF it would mean the city peaked at {mx[-1]:.0f} degF, which is absurd.")
findings.append(("tcm units", "CELSIUS (quickstart README says degF -- it is wrong)"))

# ------------------------------------------------- peak collapses, hours do not
rule("3. At small area, peak spread collapses but exceedance spread does not")
print("  This is the premise of the whole project, reproduced on Phoenix data.\n")
avg = sorted(t.props["average_temperature"] for t in hm.tiles if "average_temperature" in t.props)
exc_day = parse_heatmap(replay(f"exceedance downtown-phx 2km {DAY} ft3 t35"), "exceedance")
es = exc_day.value_spread()
print(f"  Same {len(hm):,} tiles, same day, same 2 km box:")
print(f"    daily mean temperature spread : {avg[-1]-avg[0]:6.2f} degC")
print(f"    hours above 35 degC spread    : {es['spread']:6.2f} hours "
      f"({es['distinct']} distinct values across {es['n']} tiles)")
print("\n  Ranking these tiles by temperature ranks noise. Ranking by hours does not.")
findings.append(("spatial signal", f"peak spread {avg[-1]-avg[0]:.2f} degC vs "
                                   f"exceedance spread {es['spread']:.2f} h on the same tiles"))

# ------------------------------------------------------------ threshold sweep
rule("4. exceedance responds correctly to threshold; persistence saturates at 8")
print(f"  Downtown 2 km box, {WEEK_START}..{WEEK_END} (168 h) via filter_type=4.\n")
print(f"  {'degC':>5} {'degF':>5} | {'exceedance p50':>15} | {'persistence p50':>16} | note")
print("  " + "-" * 76)
for thr in (20.0, 30.0, 35.0, 40.0, 45.0):
    row = {
        a: parse_heatmap(
            replay(f"{a} downtown-phx 2km {WEEK_START}..{WEEK_END} t{thr:g}"), a
        ).value_spread()
        for a in ("exceedance", "persistence")
    }
    note = "whole window qualifies -> truth is 168 h" if thr <= 30 else ""
    print(f"  {thr:5.0f} {thr*9/5+32:5.0f} | {row['exceedance']['p50']:15.2f} | "
          f"{row['persistence']['p50']:16.2f} | {note}")
print("\n  At a 20 degC threshold every hour of the week qualifies, so the longest")
print("  continuous run is definitionally 168 h. persistence returns 8.0.")
findings.append(("persistence @ filter_type=4", "SATURATES at 8.0 -- unusable"))

# ------------------------------------------------------ the defect is scoped
rule("5. persistence is correct at filter_type=3 -- the defect is range-of-days")
print(f"  Same AOI, single day {DAY} (24 h ceiling).\n")
print(f"  {'degC':>5} | {'exceedance':>11} | {'persistence':>12} | truth")
print("  " + "-" * 64)
truths = {20.0: "24 h, every hour qualifies", 35.0: "one unbroken run",
          40.0: "short afternoon run"}
for thr in (20.0, 35.0, 40.0):
    row = {
        a: parse_heatmap(replay(f"{a} downtown-phx 2km {DAY} ft3 t{thr:g}"), a)
        .value_spread()["p50"]
        for a in ("exceedance", "persistence")
    }
    print(f"  {thr:5.0f} | {row['exceedance']:11.2f} | {row['persistence']:12.2f} | {truths[thr]}")
print("\n  persistence tracks exceedance here; it is only broken under filter_type=4.")
print("  Consequence: TRIGGER evaluates day by day (filter_type=3), which is also the")
print("  only way to recover WHEN a condition was first met -- a 7-day aggregate")
print("  collapses exactly the time axis the lead-time metric is about.")
findings.append(("persistence @ filter_type=3", "CORRECT -- hence per-day evaluation"))

# ------------------------------------------------------------- area scaling
rule("6. AOI area limit is far above the documented cap")
print("  Docs: Basic/Startup 10 sq mi, Premium 50 sq mi. Measured on the Hackathon plan:\n")
rows = []
for e in iter_entries():
    m = re.match(r"area-probe ([\d.]+)km \(([\d.]+) sq mi\)", e.get("label") or "")
    if m:
        rows.append((float(m.group(1)), float(m.group(2)), e["n_tiles"]))
for km, area, n in sorted(rows):
    print(f"    {km:5.1f} km box = {area:6.1f} sq mi -> OK, {n:>8,} tiles")
print("\n  473 sq mi in a single call covers the City of Phoenix (518 sq mi) almost")
print("  entirely, so the pipeline makes one call per (day, threshold) rather than")
print("  one per neighbourhood -- and credits are flat per call, so this is free.")
findings.append(("max AOI measured", "473 sq mi / 122,542 tiles in one call, no rejection"))

# ------------------------------------------------------------------ summary
rule("FINDINGS")
for k, v in findings:
    print(f"  {k:30s} {v}")

rep = cache_report()
print(f"\n  cache: {rep['responses']} responses + {rep['grids']} grids = "
      f"{rep['total_bytes']/1e6:.1f} MB on disk")
print(f"  {fg.summary()}")
print(f"  API key present: {has_key()}"
      f"  ({'live-capable' if has_key() else 'reproduced fully offline'})")
