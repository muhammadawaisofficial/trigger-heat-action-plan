"""Free-cooling hours per tile: the thermal input to a siting decision.

    python fetch_sites.py

A data centre can run on outside air -- "free cooling", or economiser mode --
whenever ambient temperature sits below the return-air setpoint. Below that line
the chillers idle and the cooling load collapses; above it, mechanical cooling
runs and the electricity bill scales with how far above and for how long.

ASHRAE's recommended envelope is 18-27 degC, and economiser operation is usually
keyed to a return-air setpoint around 24 degC (75 degF). Published figures put
Phoenix and Houston at roughly 1,000-2,000 free-cooling hours a year against
4,000-6,000 for Minneapolis or Seattle, which is why climate dominates data
centre siting economics.

Every one of those figures is a CITY-level number. This script computes the same
quantity at 100 m, per tile, across a whole city -- because the free-cooling
hours available on one side of Phoenix are not the free-cooling hours available
on the other, and nobody sites a building on a city average.

METHOD. ``exceedance`` with ``direction="below"`` at the setpoint returns, per
tile, the count of hours that day spent below it. That is the free-cooling hour
count directly. This is the first use of the "below" direction anywhere in the
project; every other analytic here asks how hot it got.

HONESTY. This is a seven-day sample over the hottest week of the study year, not
an annual total, and it is reported as such. Worst-case week is the right frame
for sizing mechanical cooling anyway -- a chiller plant is specified for the
design day, not the average one -- but the number must not be presented as an
annual figure, and it is not.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import study  # noqa: E402
from aggregate import ZoneAggregator, load_zones  # noqa: E402
from cache import CachedFortyGuard, OfflineCacheMiss, has_key  # noqa: E402
from parse import parse_heatmap  # noqa: E402
from schema import c_to_f  # noqa: E402

#: ASHRAE-aligned economiser setpoint. Free cooling is available below this.
SETPOINT_C = 24.0

#: A stricter setpoint, for a conservative operator running a tighter envelope.
SETPOINT_STRICT_C = 18.0

DAYS = [f"2025-08-{d:02d}" for d in range(2, 9)]
OUT = Path(__file__).parent / "data" / "results" / "site_cooling.json"


def main() -> int:
    fg = CachedFortyGuard(verbose=True)
    aoi = study.city_aoi()
    zones = load_zones(study.ZONES_PATH, name_field=study.ZONE_NAME_FIELD)

    print("=" * 74)
    print("Free-cooling hours per tile -- exceedance, direction=below")
    print("=" * 74)
    print(f"  city      {study.CITY}")
    print(f"  setpoints {SETPOINT_C:g} degC ({c_to_f(SETPOINT_C):.0f} degF) "
          f"and {SETPOINT_STRICT_C:g} degC ({c_to_f(SETPOINT_STRICT_C):.0f} degF)")
    print(f"  window    {DAYS[0]} .. {DAYS[-1]}  ({len(DAYS)} days)")
    print(f"  API key   {'present' if has_key() else 'ABSENT - cache only'}\n")

    agg = None
    per_zone: dict[str, dict] = {}
    tile_stats: list[dict] = []

    for setpoint in (SETPOINT_C, SETPOINT_STRICT_C):
        key = f"{setpoint:g}"
        for day in DAYS:
            try:
                hm = parse_heatmap(fg.heatmap(
                    polygon_aoi=aoi, start_date=day, filter_type=3,
                    granularity=study.GRANULARITY_M, analytic_type="exceedance",
                    threshold=setpoint, direction="below",
                    label=f"{study.CITY_SLUG} freecool {day} below{key}")["result"],
                    "exceedance")
            except OfflineCacheMiss as exc:
                print(f"  {day} below{key}: SKIPPED - {str(exc).splitlines()[0]}")
                continue

            if agg is None:
                agg = ZoneAggregator(zones, hm.tiles,
                                     cache_key=study.ZONE_WEIGHT_KEY)
            vals = [t.value for t in hm.tiles if t.value is not None]
            tile_stats.append({
                "day": day, "setpoint_c": setpoint, "n_tiles": len(vals),
                "min_h": round(min(vals), 3), "max_h": round(max(vals), 3),
                "mean_h": round(sum(vals) / len(vals), 3),
                "spread_h": round(max(vals) - min(vals), 3),
            })
            for r in agg.aggregate(hm):
                z = per_zone.setdefault(
                    r.zone_id, {"zone_id": r.zone_id, "name": r.name,
                                "free_hours": {}, "days": {}})
                z["days"].setdefault(key, {})[day] = round(r.value, 3)

    if not per_zone:
        print("\n  Nothing fetched. Needs an API key on first run.")
        return 2

    for z in per_zone.values():
        for key, days in z["days"].items():
            z["free_hours"][key] = round(sum(days.values()), 2)

    rows = sorted(per_zone.values(),
                  key=lambda z: -z["free_hours"].get(f"{SETPOINT_C:g}", 0))
    best, worst = rows[0], rows[-1]
    b = best["free_hours"][f"{SETPOINT_C:g}"]
    w = worst["free_hours"][f"{SETPOINT_C:g}"]

    print(f"\n  {'zone':<26s}{'free h @24C':>13s}{'free h @18C':>13s}")
    for z in rows:
        print(f"  {z['name']:<26s}{z['free_hours'].get('24', 0):>13.1f}"
              f"{z['free_hours'].get('18', 0):>13.1f}")

    print(f"\n  Best  site: {best['name']:<24s} {b:6.1f} free-cooling hours")
    print(f"  Worst site: {worst['name']:<24s} {w:6.1f} free-cooling hours")
    print(f"  Spread    : {b - w:6.1f} hours over {len(DAYS)} days "
          f"({(b - w) / len(DAYS):.1f} h/day)")
    print(f"\n  Tile-level spread within the city, per day:")
    for t in tile_stats[:len(DAYS)]:
        print(f"    {t['day']}  {t['min_h']:5.1f} - {t['max_h']:5.1f} h  "
              f"spread {t['spread_h']:5.1f} h across {t['n_tiles']:,} tiles")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "city": study.CITY,
        "window": [DAYS[0], DAYS[-1]],
        "n_days": len(DAYS),
        "setpoint_c": SETPOINT_C,
        "setpoint_strict_c": SETPOINT_STRICT_C,
        "method": (
            "exceedance with direction=below at the economiser setpoint returns, "
            "per tile, the hours that day spent below it -- the free-cooling hour "
            "count directly. Aggregated to zones area-weighted."),
        "caveat": (
            "A seven-day sample over the hottest week of the study year, NOT an "
            "annual total. Worst-case week is the correct frame for sizing "
            "mechanical cooling, since a chiller plant is specified for the "
            "design day rather than the average one, but this must not be read "
            "as an annual free-cooling figure."),
        "ashrae_note": (
            "ASHRAE recommended envelope 18-27 degC; economiser operation is "
            "commonly keyed to a return-air setpoint near 24 degC / 75 degF."),
        "zones": rows,
        "tile_stats": tile_stats,
        "best": {"zone": best["name"], "free_hours": b},
        "worst": {"zone": worst["name"], "free_hours": w},
        "spread_hours": round(b - w, 2),
    }, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.name}   cache/network {fg.stats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
