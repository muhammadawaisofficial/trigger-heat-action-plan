"""The hero result, derived from `persistence` rather than `exceedance`.

    python sweep_dwell.py

WHY THIS SCRIPT EXISTS

An earlier derivation of the threshold x dwell grid read hours-above-threshold
from ``exceedance``. That was wrong on two counts:

1. PROVENANCE. docs/api_findings.md section 9 establishes that ``exceedance``
   returns NEGATIVE values citywide (down to -2.51 h on 2025-08-07). Hours above
   a threshold cannot be negative, so the field is smoothed or interpolated
   rather than counted. A dwell claim quoted to three decimal places cannot rest
   on it. Worse, the "as written" baseline was itself contaminated: a saturation
   of 0.989 at dwell>0h means 1.1% of tiles read <= 0 hours above 105 degF on a
   day that peaked at 109.6 degF, which is undershoot rather than a real result.

2. SEMANTICS. ``exceedance`` is a TOTAL of qualifying hours. "Above 105 degF for
   more than nine hours" describes a CONTINUOUS SPELL. Exceedance would count
   three separate three-hour spells as nine hours; persistence would not. For a
   dwell rule, persistence is the correct analytic independent of the data
   quality question.

``persistence`` is trustworthy at ``filter_type=3`` and only there -- at
``filter_type=4`` it clamps to roughly 8 hours regardless of the truth. See
api_findings.md section 2. This script uses filter_type=3 exclusively, one call
per threshold, and validates the result before reporting it.

The dwell axis is free: one persistence response per threshold gives the longest
run per tile, and every dwell requirement is a comparison against it.
"""

from __future__ import annotations

import json
import sys
from math import log2
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import study  # noqa: E402
from cache import CachedFortyGuard, OfflineCacheMiss, has_key  # noqa: E402
from parse import parse_heatmap  # noqa: E402
from schema import c_to_f  # noqa: E402

DAY = "2025-08-07"
THRESHOLDS_C = [20.0, 25.0, 30.0, 35.0, 40.5556, 45.0]
DWELL_H = [0, 1, 3, 6, 9, 12, 18]

OUT = Path(__file__).parent / "data" / "results" / "dwell_grid.json"


def bits(p: float) -> float:
    """Binary entropy of the firing share, in bits."""
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -(p * log2(p) + (1 - p) * log2(1 - p))


def main() -> int:
    aoi = study.city_aoi()
    fg = CachedFortyGuard(verbose=True)

    print("=" * 78)
    print(f"Threshold x dwell grid from PERSISTENCE - full city AOI, {DAY}")
    print("=" * 78)
    print(f"  AOI       {study.city_aoi_sq_mi():,.0f} sq mi at {study.GRANULARITY_M} m")
    print(f"  analytic  persistence, filter_type=3 (longest continuous run)")
    print(f"  API key   {'present' if has_key() else 'ABSENT - cache only'}\n")

    grids: dict[float, list[float]] = {}
    validation: list[dict] = []

    for thr in THRESHOLDS_C:
        try:
            raw = fg.heatmap(
                polygon_aoi=aoi, start_date=DAY, filter_type=3,
                granularity=study.GRANULARITY_M, analytic_type="persistence",
                threshold=thr, direction="above",
                label=f"phx-city persistence {DAY} ft3 t{thr:.4f}")["result"]
        except OfflineCacheMiss as exc:
            print(f"  t{thr:<8g} SKIPPED - {str(exc).splitlines()[0]}")
            continue
        pv = [t.value for t in parse_heatmap(raw, "persistence").tiles
              if t.value is not None]
        if not pv:
            continue
        grids[thr] = pv

        # ---- validation, before any of this is reported
        row = {"threshold_c": thr, "threshold_f": round(c_to_f(thr), 1),
               "n_tiles": len(pv), "min": min(pv), "max": max(pv),
               "negatives": sum(1 for v in pv if v < 0),
               "over_24h": sum(1 for v in pv if v > 24.0),
               "distinct": len(set(pv))}
        # Total hours above threshold can never be less than the longest run.
        try:
            ev = [t.value for t in parse_heatmap(fg.heatmap(
                polygon_aoi=aoi, start_date=DAY, filter_type=3,
                granularity=study.GRANULARITY_M, analytic_type="exceedance",
                threshold=thr, direction="above",
                label=f"phx-city exceedance {DAY} t{thr:.4f}")["result"],
                "exceedance").tiles if t.value is not None]
            if len(ev) == len(pv):
                bad = sum(1 for e, p in zip(ev, pv) if p > e + 1e-6)
                row["tiles_where_run_exceeds_total"] = bad
        except OfflineCacheMiss:
            pass
        validation.append(row)

    if not grids:
        print("\n  Nothing fetched. Needs an API key on first run.")
        return 2

    # -------------------------------------------------------- validation report
    print("\n" + "=" * 78)
    print("VALIDATION - is persistence sane citywide before we quote it?")
    print("=" * 78)
    print(f"  {'thresh':>12s}{'min':>8s}{'max':>8s}{'neg':>7s}{'>24h':>7s}"
          f"{'distinct':>10s}{'run>total':>11s}")
    ok = True
    for r in validation:
        bad = r.get("tiles_where_run_exceeds_total")
        flags = []
        if r["negatives"]:
            flags.append("NEGATIVES")
            ok = False
        if r["over_24h"]:
            flags.append(">24h")
            ok = False
        if bad:
            flags.append("RUN>TOTAL")
            ok = False
        print(f"  {r['threshold_f']:>10.0f}F{r['min']:>8.2f}{r['max']:>8.2f}"
              f"{r['negatives']:>7}{r['over_24h']:>7}{r['distinct']:>10,}"
              f"{(bad if bad is not None else '-'):>11}"
              f"{'  ' + ','.join(flags) if flags else ''}")
    print(f"\n  {'PASS - persistence is usable' if ok else 'FAIL - see flags above'}")
    print("  Checks: no negative runs, none longer than a day, and no tile whose")
    print("  longest continuous run exceeds its own total qualifying hours.")

    # ------------------------------------------------------------- the grid
    print("\n" + "=" * 78)
    print("TARGETING BITS - binary entropy of the firing share")
    print("=" * 78)
    print("  A trigger emits one bit per tile: fire or don't. This is how much")
    print("  information that bit carries. 1.0 = an even split. 0.0 = it says")
    print("  the same thing everywhere, whether everywhere or nowhere.\n")
    print("  " + " " * 8 + "".join(f"{('>' + str(d) + 'h'):>9s}" for d in DWELL_H))

    rows = []
    best = None
    for thr in sorted(grids):
        pv = grids[thr]
        n = len(pv)
        cells = []
        for d in DWELL_H:
            p = sum(1 for v in pv if v > d) / n
            b = bits(p)
            cells.append({"dwell_h": d, "saturation_index": round(p, 6),
                          "targeting_bits": round(b, 6),
                          "actionable": 0.05 < p < 0.95})
            if best is None or b > best["targeting_bits"]:
                best = {"threshold_f": round(c_to_f(thr), 1), "dwell_h": d,
                        "saturation_index": round(p, 6), "targeting_bits": round(b, 6)}
        rows.append({"threshold_c": thr, "threshold_f": round(c_to_f(thr), 1),
                     "n_tiles": n, "cells": cells})
        print(f"  {c_to_f(thr):>5.0f}F  " +
              "".join(f"{c['targeting_bits']:>9.3f}" for c in cells))

    print("\n  same grid as SATURATION INDEX (share of tiles firing)")
    print("  " + " " * 8 + "".join(f"{('>' + str(d) + 'h'):>9s}" for d in DWELL_H))
    for r in rows:
        print(f"  {r['threshold_f']:>5.0f}F  " +
              "".join(f"{c['saturation_index']:>9.3f}" for c in r["cells"]))

    # ------------------------------------------------------ monotonicity
    # Two directions, and they check different things.
    #
    # Along DWELL: saturation must not rise as the dwell requirement rises.
    #   This is guaranteed by construction -- count(v > d) cannot grow as d
    #   grows -- so it validates the counting code in this script, not the API.
    #   Asserted anyway: it is the cheapest possible guard on the arithmetic
    #   behind the headline.
    #
    # Along THRESHOLD: saturation must not rise as the threshold rises. This one
    #   compares SEPARATE API RESPONSES, so it is a genuine check on the data.
    #   A violation would mean more of the city sustains a run above a hotter
    #   threshold than above a cooler one, which is impossible.
    print("\n" + "=" * 78)
    print("MONOTONICITY")
    print("=" * 78)
    mono_bad: list[str] = []

    for r in rows:
        sats = [c["saturation_index"] for c in r["cells"]]
        for a, b, da, db in zip(sats, sats[1:], DWELL_H, DWELL_H[1:]):
            if b > a + 1e-9:
                mono_bad.append(
                    f"dwell: t{r['threshold_f']:.0f}F saturation rose "
                    f"{a:.6f} -> {b:.6f} from >{da}h to >{db}h")
    print(f"  along dwell      {len(DWELL_H) - 1} steps x {len(rows)} thresholds"
          f"   {'OK' if not mono_bad else 'VIOLATION'}")
    print(f"                   (guaranteed by construction; checks this script's"
          f" arithmetic)")

    before = len(mono_bad)
    for i in range(len(DWELL_H)):
        col = [(r["threshold_f"], r["cells"][i]["saturation_index"]) for r in rows]
        for (fa, sa), (fb, sb) in zip(col, col[1:]):
            if sb > sa + 1e-9:
                mono_bad.append(
                    f"threshold: at >{DWELL_H[i]}h saturation rose "
                    f"{sa:.6f} -> {sb:.6f} from {fa:.0f}F to {fb:.0f}F")
    print(f"  along threshold  {len(rows) - 1} steps x {len(DWELL_H)} dwells"
          f"   {'OK' if len(mono_bad) == before else 'VIOLATION'}")
    print(f"                   (compares separate API responses; checks the data)")

    if mono_bad:
        ok = False
        print(f"\n  {len(mono_bad)} violation(s):")
        for m in mono_bad[:12]:
            print(f"    {m}")

    n_cells = sum(len(r["cells"]) for r in rows)
    lit = sum(1 for r in rows for c in r["cells"] if c["targeting_bits"] > 0.9)
    act = sum(1 for r in rows for c in r["cells"] if c["actionable"])

    # The plan's own rule: Action 1.1's threshold, no dwell requirement.
    as_written = None
    for r in rows:
        if abs(r["threshold_c"] - 40.5556) < 1e-3:
            as_written = r["cells"][0]

    print(f"\n  {n_cells} cells. {lit} carry more than 0.9 bits. {act} are actionable.")
    if as_written and best:
        print(f"\n  Action 1.1 as written  -- above {c_to_f(40.5556):.0f} degF, no dwell "
              f"requirement:")
        print(f"    saturation {as_written['saturation_index']:.3f}   "
              f"targeting {as_written['targeting_bits']:.3f} bits")
        print(f"  Best cell in the grid  -- above {best['threshold_f']:.0f} degF for "
              f"more than {best['dwell_h']} h:")
        print(f"    saturation {best['saturation_index']:.3f}   "
              f"targeting {best['targeting_bits']:.3f} bits")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "day": DAY,
        "analytic": "persistence",
        "filter_type": 3,
        "provenance": (
            "Longest continuous run of hours above threshold, per tile, from "
            "POST /v1/heatmap analytic_type=persistence at filter_type=3. NOT "
            "derived from exceedance: that field returns negative values "
            "citywide (api_findings.md section 9) so it is smoothed rather than "
            "counted, and it reports a TOTAL of qualifying hours where a dwell "
            "rule describes a CONTINUOUS spell. persistence is unusable at "
            "filter_type=4, where it clamps to roughly 8 h regardless of the "
            "truth (api_findings.md section 2); filter_type=3 is used throughout."),
        "aoi_sq_mi": round(study.city_aoi_sq_mi(), 1),
        "granularity_m": study.GRANULARITY_M,
        "dwell_hours": DWELL_H,
        "validation": validation,
        "monotonicity_violations": mono_bad,
        "validation_passed": ok,
        "rows": rows,
        "as_written": as_written,
        "best": best,
        "n_cells": n_cells,
        "cells_above_0p9_bits": lit,
        "actionable_cells": act,
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(Path(__file__).parent)}")
    print(f"  cache/network: {fg.stats}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
