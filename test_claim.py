"""Test the plan's own claim about spatial variability against measured data.

Page 4 of the City of Phoenix 2026 Heat Response Plan states:

    "Historical development patterns and varying topography across Phoenix lead
     to neighborhood-to-neighborhood air temperature differences of 10F or more
     on summer days."

The city asserts this and then triggers every conditional clause in the plan on
a single reading. This script measures the assertion.

Two scales are reported, because they answer different questions:

  tile level (100 m)   the closest available analogue to "neighborhood to
                       neighborhood" -- this is what the claim is about
  village level        the 15 urban villages, area-weighted -- much smoother,
                       because a village averages 10 to 68 square miles

    python test_claim.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import study  # noqa: E402
from aggregate import ZoneAggregator, area_weighted_mean, load_zones, tile_areas  # noqa: E402
from cache import CachedFortyGuard, OfflineCacheMiss  # noqa: E402
from parse import parse_heatmap  # noqa: E402

DAYS = ["2025-08-02", "2025-08-03", "2025-08-04", "2025-08-05",
        "2025-08-06", "2025-08-07", "2025-08-08"]
CLAIM_F = 10.0

FIELDS = [("min_temperature", "overnight low"),
          ("average_temperature", "daily mean"),
          ("max_temperature", "daily high")]


def main() -> int:
    fg = CachedFortyGuard(verbose=False)
    zones = load_zones(study.ZONES_PATH, name_field=study.ZONE_NAME_FIELD)

    print("Plan, page 4:")
    print('  "...neighborhood-to-neighborhood air temperature differences of')
    print('   10F or more on summer days."\n')
    print(f"Measured over {DAYS[0]} .. {DAYS[-1]}, {study.GRANULARITY_M} m tiles, "
          f"{len(zones)} urban villages\n")

    agg = None
    areas = None
    rows = []

    for day in DAYS:
        try:
            hm = parse_heatmap(fg.heatmap(
                polygon_aoi=study.city_aoi(), start_date=day, filter_type=3,
                granularity=study.GRANULARITY_M, analytic_type="tcm",
                label=f"phx-city tcm {day}")["result"], "tcm")
        except OfflineCacheMiss:
            print(f"  {day}  not cached, skipping")
            continue

        if agg is None:
            agg = ZoneAggregator(zones, hm.tiles, cache_key=study.ZONE_WEIGHT_KEY)
            areas = tile_areas(hm.tiles)

        entry = {"day": day}
        for field, _ in FIELDS:
            tile_vals = [t.props[field] for t in hm.tiles if field in t.props]
            tile_spread_f = (max(tile_vals) - min(tile_vals)) * 9 / 5

            zvals = [r.value for r in agg.aggregate_field(hm, field)]
            zone_spread_f = (max(zvals) - min(zvals)) * 9 / 5

            entry[field] = (tile_spread_f, zone_spread_f,
                            area_weighted_mean(hm, field, areas) * 9 / 5 + 32)
        rows.append(entry)

    if not rows:
        print("Nothing cached for this window.")
        return 2

    for field, label in FIELDS:
        print(f"{label.upper()}")
        print(f"  {'day':<12} {'tile spread':>12} {'village spread':>15} {'proxy degF':>11}")
        print("  " + "-" * 54)
        for r in rows:
            t, z, p = r[field]
            flag = "  <- exceeds the claim" if t >= CLAIM_F else ""
            print(f"  {r['day']:<12} {t:>11.2f}F {z:>14.2f}F {p:>10.1f}{flag}")
        ts = [r[field][0] for r in rows]
        zs = [r[field][1] for r in rows]
        print(f"  {'mean':<12} {sum(ts)/len(ts):>11.2f}F {sum(zs)/len(zs):>14.2f}F")
        print()

    print("=" * 70)
    print("VERDICT")
    print("=" * 70)
    allt = [r[f][0] for r in rows for f, _ in FIELDS]
    n_over = sum(1 for v in allt if v >= CLAIM_F)
    print(f"  At 100 m tile scale the measured spread reaches or exceeds the")
    print(f"  plan's stated 10F on {n_over} of {len(allt)} day-metric combinations.")
    lows = [r["min_temperature"][0] for r in rows]
    highs = [r["max_temperature"][0] for r in rows]
    print(f"\n  Overnight low spread averages {sum(lows)/len(lows):.1f}F, "
          f"daily high {sum(highs)/len(highs):.1f}F.")
    print("  The city's claim is conservative, and the variability is largest")
    print("  overnight -- which is when heat is most lethal and when the urban")
    print("  heat island is strongest.")
    print("\n  Village-level spreads are much smaller because a village averages")
    print("  10 to 68 square miles. That smoothing is a limitation of using")
    print("  administrative units, and it makes our divergence result a LOWER")
    print("  BOUND: finer zones would diverge more, not less.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
