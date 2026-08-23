"""Map the actionable band: which thresholds can resolve neighbourhoods at all.

    python sweep_threshold.py

Phase 0 measured this on a 2 km downtown box and found that a threshold outside
the day's temperature range resolves nothing. That result was real but it was
about the BOX: over 4 km2 the spatial spread in overnight low is ~0.1-0.5 degC,
so almost every threshold falls outside it. Over the whole 1,053 sq mi AOI the
spatial spread is 10.9-13.5 degC, and the band of thresholds that can resolve
anything is correspondingly wide.

This script sweeps the threshold across the full city AOI on the most severe day
of the study window, so the band is measured at the scale a heat plan actually
operates at.

One call per threshold, 4,220 credits each, cached after the first run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import study  # noqa: E402
from cache import CachedFortyGuard, OfflineCacheMiss, has_key  # noqa: E402
from parse import parse_heatmap  # noqa: E402
from schema import c_to_f  # noqa: E402

#: The hottest day of the published window: the plan itself records 118 degF at
#: Sky Harbor on 7 August 2025.
DAY = "2025-08-07"

#: Spans well below and well above the day's spatial range, so both collapses
#: are captured. 40.5556 degC (105 degF) is Action 1.1's own threshold and is
#: already cached from the published analysis.
THRESHOLDS_C = [20.0, 25.0, 30.0, 35.0, 40.5556, 45.0]

OUT = Path(__file__).parent / "data" / "results" / "threshold_sweep.json"


def main() -> int:
    aoi = study.city_aoi()
    fg = CachedFortyGuard(verbose=True)

    print("=" * 78)
    print(f"Threshold sweep - full city AOI, {DAY}")
    print("=" * 78)
    print(f"  AOI         {study.city_aoi_sq_mi():,.0f} sq mi at "
          f"{study.GRANULARITY_M} m")
    print(f"  API key     {'present' if has_key() else 'ABSENT - cache only'}")
    print(f"  thresholds  {len(THRESHOLDS_C)}\n")

    # The day's actual spatial range, for reading the sweep against.
    band = None
    try:
        tcm = parse_heatmap(fg.heatmap(
            polygon_aoi=aoi, start_date=DAY, filter_type=3,
            granularity=study.GRANULARITY_M, analytic_type="tcm",
            label=f"phx-city tcm {DAY}")["result"], "tcm")
        lo = min(t.props["min_temperature"] for t in tcm.tiles)
        hi = max(t.props["max_temperature"] for t in tcm.tiles)
        band = (lo, hi)
        print(f"  That day spanned {lo:.2f} - {hi:.2f} degC "
              f"({c_to_f(lo):.1f} - {c_to_f(hi):.1f} degF) across "
              f"{len(tcm):,} tiles.\n")
    except OfflineCacheMiss:
        pass

    rows = []
    for thr in THRESHOLDS_C:
        try:
            hm = parse_heatmap(fg.heatmap(
                polygon_aoi=aoi, start_date=DAY, filter_type=3,
                granularity=study.GRANULARITY_M, analytic_type="exceedance",
                threshold=thr, direction="above",
                label=f"phx-city exceedance {DAY} t{thr:.4f}")["result"],
                "exceedance")
        except OfflineCacheMiss as exc:
            print(f"  t{thr:<8g} SKIPPED - {str(exc).splitlines()[0]}")
            continue

        v = [t.value for t in hm.tiles if t.value is not None]
        if not v:
            continue
        n = len(v)
        # Saturation: the share of tiles the condition holds for at all.
        fired = sum(1 for x in v if x > 0)
        rows.append({
            "threshold_c": thr,
            "threshold_f": round(c_to_f(thr), 1),
            "n_tiles": n,
            "mean_hours": sum(v) / n,
            "min_hours": min(v),
            "max_hours": max(v),
            "spread_hours": max(v) - min(v),
            "distinct_values": len(set(v)),
            "distinct_share": len(set(v)) / n,
            "saturation_index": fired / n,
        })

    print(f"\n  {'thresh':>16s}{'sat_idx':>9s}{'distinct':>10s}"
          f"{'dist/n':>8s}{'spread_h':>10s}{'mean_h':>8s}")
    for r in rows:
        flag = ""
        if r["saturation_index"] >= 0.95:
            flag = "  <- everything fires"
        elif r["saturation_index"] <= 0.05:
            flag = "  <- nothing fires"
        print(f"  {r['threshold_c']:>7.2f}C/{r['threshold_f']:>5.0f}F"
              f"{r['saturation_index']:>9.3f}{r['distinct_values']:>10,}"
              f"{r['distinct_share']:>8.3f}{r['spread_hours']:>10.2f}"
              f"{r['mean_hours']:>8.2f}{flag}")

    actionable = [r for r in rows
                  if 0.05 < r["saturation_index"] < 0.95
                  and r["distinct_values"] > 10]
    print(f"\n  ACTIONABLE BAND: {len(actionable)} of {len(rows)} thresholds "
          f"resolve neighbourhoods")
    if actionable:
        print(f"    {min(r['threshold_f'] for r in actionable):.0f} degF "
              f"to {max(r['threshold_f'] for r in actionable):.0f} degF")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "day": DAY,
        "aoi_sq_mi": round(study.city_aoi_sq_mi(), 1),
        "granularity_m": study.GRANULARITY_M,
        "day_range_c": list(band) if band else None,
        "rows": rows,
        "actionable_thresholds_f": [r["threshold_f"] for r in actionable],
        "note": ("Saturation index is the share of tiles where the condition "
                 "holds at all. exceedance returns small negative values on "
                 "some tiles, so it is a smoothed field rather than a raw hour "
                 "count; 'fires' is therefore value > 0."),
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.relative_to(Path(__file__).parent)}")
    print(f"  cache/network: {fg.stats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
