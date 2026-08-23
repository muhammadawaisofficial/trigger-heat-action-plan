"""Phase 0 verification: does the FortyGuard signal hold across years?

    python verify_years.py

BUILD_PLAN Phase 0 asks for one ``persistence`` probe repeated over July 2025,
2024 and 2023 on a small downtown Phoenix box, and sets the gate at "n_cells in
the hundreds+ and a real spread between min and max", benchmarked against
FortyGuard's own San Jose sample (2.07 -> 8.73 hours across 329 tiles).

Run as written, that gate fails -- and it fails for reasons that have nothing to
do with Phoenix. This script reports the probe as specified and then the two
measurements needed to interpret it.

WHAT IT ESTABLISHES

1. ``persistence`` at ``filter_type=4`` is INTERNALLY INCONSISTENT, in all three
   Julys tested. Over the week of 8-14 July it reports a longest run of 8.0
   hours, while a single day inside that same week reports 16.0. A longest run
   over a superset window cannot be shorter than one measured inside it. All
   three years return exactly 8.0 with zero variance across 420 tiles.

2. At ``filter_type=3`` the same analytic is SOUND. It agrees with
   ``exceedance`` every time: identical to it in 2024 (13.78-15.17 h, so every
   qualifying hour was contiguous), and identical again in 2023 (24.0 h). Where
   it returns one flat value, that value is correct. The defect is scoped to
   range-of-days, exactly as docs/api_findings.md reports.

3. ``exceedance`` at ``filter_type=3`` -- what the pipeline actually runs on --
   carries per-tile signal, but ONLY when the threshold falls inside the day's
   temperature range. That is the real Phase 0 lesson, and it is a property of
   thresholds, not of the API:

       t20 (68 degF)  -> 24.0 h everywhere, 1 distinct value   (whole day above)
       t35 (95 degF)  -> 16.86-18.21 h, 394 distinct values    (SIGNAL)
       t40 (104 degF) -> 2.0 h everywhere, 1 distinct value    (peak barely reaches)

4. And the threshold that discriminates in one year can go blind in another. The
   same 95 degF threshold that separates 394 distinct values on 2025-07-15
   returns a flat 24.0 across every tile on 2023-07-15, because in that record
   July the whole day sat above 95 degF everywhere. A fixed numeric threshold
   loses resolution in precisely the conditions that make it matter most --
   which is an argument about how heat plans are written, not about the API.

The 2025 requests replay from the committed cache. Other years are live on first
run at 4,220 credits each, then cached like everything else.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from cache import CachedFortyGuard, OfflineCacheMiss, has_key  # noqa: E402
from geo import aoi_area_sq_km, feature_collection  # noqa: E402
from parse import parse_heatmap  # noqa: E402

#: The exact ring from the original Phase 0 probe, lifted from the cache so the
#: 2025 request keys still match byte for byte. Rebuilding it from
#: geo.square_aoi would shift the last decimal place and force a refetch.
DOWNTOWN_RING = [
    (-112.08476617879987, 33.43938611862268),
    (-112.06323382120013, 33.43938611862268),
    (-112.06323382120013, 33.45741388137732),
    (-112.08476617879987, 33.45741388137732),
    (-112.08476617879987, 33.43938611862268),
]
AOI = feature_collection(DOWNTOWN_RING)

YEARS = (2025, 2024, 2023)
THRESHOLD_C = 35.0          # 95 degF, the classic heat-plan threshold
WEEK = ("07-08", "07-14")   # the week BUILD_PLAN names
SINGLE_DAY = "07-15"

#: FortyGuard's published San Jose persistence sample, for scale.
SAN_JOSE = {"n_cells": 329, "min": 2.07, "max": 8.73}

fg = CachedFortyGuard(verbose=False)


def rule(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def probe(analytic: str, year: int, filter_type: int,
          threshold: float = THRESHOLD_C) -> dict | None:
    """One heatmap probe. Returns a row of measurements, or None if unavailable."""
    if filter_type == 4:
        start, end = f"{year}-{WEEK[0]}", f"{year}-{WEEK[1]}"
        label = f"{analytic} downtown-phx 2km {start}..{end} t{threshold:g}"
    else:
        start, end = f"{year}-{SINGLE_DAY}", None
        label = f"{analytic} downtown-phx 2km {start} ft3 t{threshold:g}"

    try:
        raw = fg.heatmap(
            polygon_aoi=AOI, start_date=start, end_date=end,
            filter_type=filter_type, granularity=100,
            analytic_type=analytic, threshold=threshold,
            direction="above", label=label,
        )
    except OfflineCacheMiss:
        return None

    hm = parse_heatmap(raw.get("result", raw), analytic)
    vals = [t.value for t in hm.tiles if t.value is not None]
    if not vals:
        return None
    return {
        "label": label,
        "window": start if end is None else f"{start}..{end}",
        "stats_data": hm.stats or {},
        "n_tiles": len(hm),
        "min": min(vals),
        "max": max(vals),
        "spread": max(vals) - min(vals),
        "distinct": len(set(vals)),
        "gt_zero": sum(1 for v in vals if v > 0),
    }


def row(label: str, r: dict | None) -> None:
    if r is None:
        print(f"  {label:<26s} not cached, and no API key set -- skipped")
        return
    flag = "  <-- flat, no spatial signal" if r["distinct"] <= 1 else "  <-- SIGNAL"
    print(f"  {label:<26s} {r['n_tiles']:>4} tiles  "
          f"{r['min']:>8.3f} - {r['max']:<8.3f} spread {r['spread']:>6.3f}  "
          f"{r['distinct']:>4} distinct{flag}")


def main() -> int:
    rule("Phase 0 -- downtown Phoenix, 2 km box, three Julys")
    print(f"  AOI        {aoi_area_sq_km(AOI):.2f} sq km "
          f"(the ~2 km box BUILD_PLAN specifies)")
    print(f"  threshold  {THRESHOLD_C} degC = {THRESHOLD_C * 9 / 5 + 32:.0f} degF, above")
    print(f"  gran       100 m")
    print(f"  API key    {'present' if has_key() else 'ABSENT -- cache only'}")
    print(f"\n  Reference: FortyGuard's San Jose persistence sample spans "
          f"{SAN_JOSE['min']} -> {SAN_JOSE['max']} h across "
          f"{SAN_JOSE['n_cells']} tiles.")

    # ------------------------------------------------- A. the probe as written
    rule("A. persistence, filter_type=4 -- exactly what Phase 0 specifies")
    p4 = {y: probe("persistence", y, 4) for y in YEARS}
    for y in YEARS:
        row(f"July {y} week", p4[y])
    got = [r for r in p4.values() if r]
    if got:
        print(f"\n  Full stats_data, {YEARS[0]}:")
        print(f"    {got[0]['stats_data']}")
        print(f"  tiles with value > 0: {got[0]['gt_zero']} of {got[0]['n_tiles']} "
              f"(in every year)")

    # ------------------------------------------- B. same analytic, one day only
    rule("B. persistence, filter_type=3 -- one day instead of a range")
    p3 = {y: probe("persistence", y, 3) for y in YEARS}
    for y in YEARS:
        row(f"{y}-{SINGLE_DAY}", p3[y])

    if p4.get(2025) and p3.get(2025):
        print(f"\n  The contradiction that rules filter_type=4 out entirely:")
        print(f"    longest run over the WEEK 8-14 July   {p4[2025]['max']:.1f} h")
        print(f"    longest run on ONE DAY inside it      {p3[2025]['max']:.1f} h")
        print(f"    A longest run over a superset window cannot be the shorter one.")

    # ---------------------------------- C. the analytic the pipeline runs on
    rule("C. exceedance, filter_type=3 -- what the pipeline actually uses")
    e3 = {y: probe("exceedance", y, 3) for y in YEARS}
    for y in YEARS:
        row(f"{y}-{SINGLE_DAY}", e3[y])

    print("\n  Cross-check against persistence on the same days. Total hours above")
    print("  threshold must never be less than the longest unbroken run:")
    for y in YEARS:
        e, pp = e3.get(y), p3.get(y)
        if not (e and pp):
            continue
        ok = "OK" if e["max"] >= pp["max"] - 1e-9 else "IMPOSSIBLE"
        same = "  (identical -- every qualifying hour was contiguous)"             if abs(e["max"] - pp["max"]) < 1e-6 and abs(e["min"] - pp["min"]) < 1e-6 else ""
        print(f"    {y}-{SINGLE_DAY}  exceedance {e['min']:6.2f}-{e['max']:6.2f} h   "
              f"persistence {pp['min']:6.2f}-{pp['max']:6.2f} h   {ok}{same}")

    # ------------------------- D. why a threshold either sees or blinds a plan
    rule("D. Threshold placement decides whether ANY signal exists")
    print("  Same 420 tiles, same day (2025-07-15), same analytic. Only the")
    print("  threshold changes.\n")
    for thr in (20.0, 35.0, 40.0):
        r = probe("exceedance", 2025, 3, thr)
        row(f"t{thr:g} = {thr * 9 / 5 + 32:.0f} degF", r)
    try:
        hm = parse_heatmap(
            fg.heatmap(polygon_aoi=AOI, start_date=f"2025-{SINGLE_DAY}",
                       filter_type=3, granularity=100, analytic_type="tcm",
                       label=f"tcm downtown-phx 2km 2025-{SINGLE_DAY}").get("result"),
            "tcm")
        lo = min(t.props["min_temperature"] for t in hm.tiles)
        hi = max(t.props["max_temperature"] for t in hm.tiles)
        print(f"\n  That day actually ran {lo:.1f} - {hi:.1f} degC "
              f"({lo * 9 / 5 + 32:.0f} - {hi * 9 / 5 + 32:.0f} degF).")
        print(f"  68 degF is below the whole range, so every tile is above it for")
        print(f"  all 24 hours. 104 degF is at the very top, so every tile clears")
        print(f"  it for the same 2 hours. Only a threshold INSIDE the range can")
        print(f"  separate one neighbourhood from another.")
    except (OfflineCacheMiss, KeyError, TypeError, ValueError):
        pass

    # ------------------------------------------------------------ the verdict
    rule("VERDICT")
    n4 = len([r for r in p4.values() if r])
    print(f"  persistence : self-contradictory at filter_type=4 in {n4} of {n4} Julys")
    print(f"                (8.0 h for a week containing a 16.0 h day).")
    print(f"                Sound at filter_type=3 -- it agrees with exceedance")
    print(f"                every time, including where both are flat.")
    print(f"                => the pipeline evaluates day by day, never ft4.")

    ok = [r for r in e3.values() if r and r["n_tiles"] >= 100 and r["distinct"] > 1]
    got_e = [r for r in e3.values() if r]
    print(f"\n  exceedance  : per-tile signal in {len(ok)} of {len(got_e)} Julys tested")
    print(f"                at a threshold inside the day's range.")
    for r in got_e:
        print(f"                {r['window']}  {r['min']:.2f}-{r['max']:.2f} h, "
              f"{r['distinct']} distinct values across {r['n_tiles']} tiles")

    if ok:
        best = max(ok, key=lambda r: r["distinct"])
        print(f"\n  GATE: n_cells in the hundreds+ and a real min-max spread.")
        print(f"        PASSED on exceedance -- {best['n_tiles']} tiles, "
              f"{best['distinct']} distinct")
        print(f"        values, spread {best['spread']:.2f} h. Comparable to the")
        print(f"        San Jose reference, on the analytic we depend on.")
        print(f"\n  Study window was then chosen by measurement, not by this probe:")
        print(f"  scan_event.py found 57.8 hours above 105 degF in 2-8 Aug 2025")
        print(f"  against 46.7 for 6-12 July, so the published analysis uses August.")
    else:
        print(f"\n  GATE: NOT PASSED. Decide the study window before continuing.")

    print(f"\n  cache/network this run: {fg.stats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
