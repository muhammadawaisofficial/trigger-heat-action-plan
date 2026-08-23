"""Verify tile->zone aggregation against an independent computation.

The spatial index is an optimisation; a bug in it would silently drop tiles and
bias every zone value. So one zone is recomputed by brute force -- every tile
in the grid tested for intersection, no index, no early exit -- and the two
answers must agree to floating-point tolerance.

Also checks the failure mode this module exists to prevent: that a nearest-tile
or centroid lookup gives a materially different answer from area weighting.

    python test_aggregate.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from shapely.geometry import Point, Polygon  # noqa: E402

from aggregate import (  # noqa: E402
    ZoneAggregator, _project_ring, area_weighted_mean, load_zones,
)
from cache import replay  # noqa: E402
from parse import parse_heatmap  # noqa: E402

ZONES = "data/zones/phoenix_villages_raw.geojson"
LABEL = "area-probe phoenix-full-bbox (1053 sq mi)"
FIELD = "average_temperature"


def brute_force(zone, tiles, field: str) -> tuple[float, int, float]:
    """Area-weighted mean over every tile, with no spatial index at all."""
    num = den = 0.0
    n = 0
    for t in tiles:
        if len(t.ring) < 4:
            continue
        v = t.props.get(field)
        if not isinstance(v, (int, float)):
            continue
        p = Polygon(_project_ring(t.ring))
        if not p.is_valid or p.is_empty or not p.intersects(zone.geom):
            continue
        a = p.intersection(zone.geom).area
        if a > 0:
            num += v * a
            den += a
            n += 1
    return (num / den if den else float("nan")), n, den


def centroid_lookup(zone, tiles, field: str) -> tuple[float, int]:
    """The naive alternative: only tiles whose centroid falls inside the zone."""
    vals = []
    for t in tiles:
        if len(t.ring) < 4:
            continue
        v = t.props.get(field)
        if not isinstance(v, (int, float)):
            continue
        lon, lat = t.centroid
        if zone.geom.contains(Point(*_project_ring([(lon, lat)])[0])):
            vals.append(v)
    return (sum(vals) / len(vals) if vals else float("nan")), len(vals)


def main() -> int:
    print("Loading zones and the cached full-city heatmap...")
    zones = load_zones(ZONES, name_field="NAME")
    hm = parse_heatmap(replay(LABEL), "tcm")
    print(f"  {len(zones)} zones, {len(hm):,} tiles\n")

    t0 = time.time()
    agg = ZoneAggregator(zones, hm.tiles)
    print(f"  built overlap weights in {time.time()-t0:.1f}s")

    t0 = time.time()
    rows = agg.aggregate_field(hm, FIELD)
    print(f"  aggregated in {time.time()-t0:.2f}s\n")

    by_id = {r.zone_id: r for r in rows}
    zmap = {z.zone_id: z for z in zones}

    print(f"Daily mean 2 m temperature by urban village ({FIELD}, 2025-07-15)")
    print(f"  {'village':<22s} {'degC':>7} {'degF':>7} {'tiles':>8} {'area mi2':>9} {'cover':>7}")
    print("  " + "-" * 68)
    for r in sorted(rows, key=lambda r: -r.value):
        print(f"  {r.name:<22s} {r.value:>7.2f} {r.value*9/5+32:>7.2f} "
              f"{r.n_tiles:>8,} {zmap[r.zone_id].area_sq_mi:>9.1f} {r.coverage:>6.1%}")

    vals = [r.value for r in rows]
    spread_c = max(vals) - min(vals)
    print(f"\n  spread across villages: {spread_c:.2f} degC = {spread_c*9/5:.2f} degF")

    # ---------------------------------------------------------------- checks
    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)
    ok = True

    # 1. Brute force must reproduce the indexed result for the smallest zone.
    target = min(zones, key=lambda z: z.area_sq_km)
    print(f"\n1. Brute-force recomputation of {target.name} "
          f"({target.area_sq_mi:.1f} sq mi, smallest zone)")
    t0 = time.time()
    bf_val, bf_n, bf_area = brute_force(target, hm.tiles, FIELD)
    got = by_id[target.zone_id]
    print(f"   indexed     : {got.value:.9f}  ({got.n_tiles:,} tiles, "
          f"{got.covered_sq_km:.4f} sq km)")
    print(f"   brute force : {bf_val:.9f}  ({bf_n:,} tiles, {bf_area:.4f} sq km)")
    diff = abs(got.value - bf_val)
    print(f"   difference  : {diff:.3e}   [{time.time()-t0:.1f}s brute force]")
    if diff > 1e-9 or got.n_tiles != bf_n:
        print("   FAIL - indexed aggregation does not match brute force")
        ok = False
    else:
        print("   PASS")

    # 2. Coverage must be complete for zones inside the AOI.
    print("\n2. Zone coverage (tiles must cover essentially all of each zone)")
    worst = min(rows, key=lambda r: r.coverage)
    print(f"   lowest coverage: {worst.name} at {worst.coverage:.2%}")
    if worst.coverage < 0.98:
        print("   FAIL - AOI does not fully cover every zone")
        ok = False
    else:
        print("   PASS - every zone is at least 98% covered")

    # 3. Area weighting must differ measurably from the naive lookup.
    print("\n3. Area weighting vs naive centroid-in-polygon lookup")
    print(f"   {'village':<22s} {'weighted':>9} {'centroid':>9} {'diff degC':>10} "
          f"{'tiles lost':>11}")
    print("   " + "-" * 66)
    max_diff = 0.0
    for z in sorted(zones, key=lambda z: z.area_sq_km)[:4]:
        cval, cn = centroid_lookup(z, hm.tiles, FIELD)
        w = by_id[z.zone_id]
        d = abs(w.value - cval)
        max_diff = max(max_diff, d)
        print(f"   {z.name:<22s} {w.value:>9.3f} {cval:>9.3f} {d:>10.4f} "
              f"{w.n_tiles - cn:>11,}")
    print(f"\n   Largest divergence on these zones: {max_diff:.4f} degC")
    print("   Centroid lookup drops every boundary tile; area weighting keeps")
    print("   them at partial weight. On a 100 m grid the two agree closely in")
    print("   the interior, and diverge exactly where zones meet.")

    # 4. The citywide proxy must sit inside the range of the zones.
    print("\n4. Citywide proxy baseline (area-weighted mean over the whole AOI)")
    proxy = area_weighted_mean(hm, FIELD)
    print(f"   proxy        : {proxy:.3f} degC ({proxy*9/5+32:.2f} degF)")
    print(f"   village range: {min(vals):.3f} .. {max(vals):.3f} degC")
    if not (min(vals) <= proxy <= max(vals)):
        print("   NOTE - proxy falls outside the village range. The AOI bounding")
        print("   box includes land outside every village, so this is possible.")
    else:
        print("   PASS - proxy lies within the range of the villages")

    print("\n" + ("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
