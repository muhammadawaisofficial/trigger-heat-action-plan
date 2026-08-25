"""National panel: one comparable thermal measurement per US metro.

    python fetch_national.py            # the design day
    python fetch_national.py --days 3   # add days for heat-wave runs

WHY A PANEL AND NOT A GRID

Full national coverage at 100 m is not reachable on this budget, and saying so is
more useful than pretending otherwise. The API accepts roughly 1,053 mi² of land
per call; the continental US is about 3.1 million mi². Covering it would take
around 3,000 calls, and the account holds 472. Off by a factor of six.

So this samples instead: 30 metros spanning every US climate zone and including
the real data-centre markets, because a siting comparison that omits Ashburn or
Hillsboro is not a siting comparison. Each metro gets an identical 10 km box on
its urban core, so the measurements are directly comparable -- same granularity,
same box size, same day, same analytics. That is how siting studies are actually
conducted; nobody grids a continent to choose a building site.

WHAT IS FETCHED, PER METRO PER DAY

  exceedance, direction=below, 24 degC   free-cooling hours at the ASHRAE-aligned
                                         economiser setpoint
  exceedance, direction=below, 18 degC   free-cooling hours for a tighter envelope
  tcm                                    daily min / mean / max air temperature

Three calls per metro per day. The design day costs 90 calls; each extra day
costs another 90, which is why extra days are opt-in.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from cache import CachedFortyGuard, OfflineCacheMiss, has_key  # noqa: E402
from geo import aoi_area_sq_km, sq_km_to_sq_mi, square_aoi  # noqa: E402
from parse import parse_heatmap  # noqa: E402
from schema import c_to_f  # noqa: E402

REPO = Path(__file__).parent
METROS = json.loads((REPO / "data" / "metros.json").read_text(encoding="utf-8"))
OUT = REPO / "data" / "results" / "national.json"

#: A hot summer day that is meaningfully hot across the whole country, so one
#: date is comparable everywhere. Mid-July is the climatological peak for most
#: of the continental US.
DESIGN_DAY = "2025-07-15"

SETPOINT_C = 24.0          # ASHRAE-aligned economiser setpoint
SETPOINT_STRICT_C = 18.0   # tighter envelope


def days_from(start: str, n: int) -> list[str]:
    d = date.fromisoformat(start)
    return [(d + timedelta(days=i)).isoformat() for i in range(n)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=1,
                    help="consecutive days from the design day (3 calls/metro/day)")
    ap.add_argument("--start", default=DESIGN_DAY)
    args = ap.parse_args()

    days = days_from(args.start, args.days)
    fg = CachedFortyGuard(verbose=False)
    box = METROS["sample_box_km"]

    print("=" * 78)
    print("National panel -- one comparable measurement per metro")
    print("=" * 78)
    print(f"  metros    {len(METROS['metros'])}")
    print(f"  box       {box:g} km per metro")
    print(f"  days      {', '.join(days)}")
    print(f"  calls     {len(METROS['metros']) * len(days) * 3} "
          f"({len(METROS['metros']) * len(days) * 3 * 4220:,} credits)")
    print(f"  API key   {'present' if has_key() else 'ABSENT - cache only'}\n")

    rows: list[dict] = []
    for i, m in enumerate(METROS["metros"], 1):
        aoi = square_aoi(m["lat"], m["lon"], box)
        rec = {"id": m["id"], "name": m["name"], "lat": m["lat"], "lon": m["lon"],
               "market": m["market"], "zone": m["zone"],
               "area_sq_mi": round(sq_km_to_sq_mi(aoi_area_sq_km(aoi)), 1),
               "days": {}}
        ok = True

        for day in days:
            d: dict = {}
            for sp, key in ((SETPOINT_C, "free24"), (SETPOINT_STRICT_C, "free18")):
                try:
                    hm = parse_heatmap(fg.heatmap(
                        polygon_aoi=aoi, start_date=day, filter_type=3,
                        granularity=100, analytic_type="exceedance",
                        threshold=sp, direction="below",
                        label=f"national {m['id']} {day} below{sp:g}")["result"],
                        "exceedance")
                    v = [t.value for t in hm.tiles if t.value is not None]
                    d[key] = {"mean": round(sum(v) / len(v), 3),
                              "min": round(min(v), 3), "max": round(max(v), 3),
                              "n_tiles": len(v)}
                except (OfflineCacheMiss, Exception) as exc:  # noqa: BLE001
                    d[key] = {"error": type(exc).__name__}
                    ok = False

            try:
                hm = parse_heatmap(fg.heatmap(
                    polygon_aoi=aoi, start_date=day, filter_type=3,
                    granularity=100, analytic_type="tcm",
                    label=f"national {m['id']} {day} tcm")["result"], "tcm")
                mn = [t.props["min_temperature"] for t in hm.tiles
                      if "min_temperature" in t.props]
                mx = [t.props["max_temperature"] for t in hm.tiles
                      if "max_temperature" in t.props]
                av = [t.props["average_temperature"] for t in hm.tiles
                      if "average_temperature" in t.props]
                d["tcm"] = {
                    "min_f": round(c_to_f(min(mn)), 2),
                    "max_f": round(c_to_f(max(mx)), 2),
                    "mean_f": round(c_to_f(sum(av) / len(av)), 2),
                    "overnight_low_f": round(c_to_f(sum(mn) / len(mn)), 2),
                    "daily_high_f": round(c_to_f(sum(mx) / len(mx)), 2),
                    "spread_f": round(c_to_f(max(mx)) - c_to_f(min(mn)), 2),
                    "n_tiles": len(av),
                }
            except (OfflineCacheMiss, Exception) as exc:  # noqa: BLE001
                d["tcm"] = {"error": type(exc).__name__}
                ok = False

            rec["days"][day] = d

        # Window totals, used by every downstream ranking.
        f24 = [v["free24"]["mean"] for v in rec["days"].values()
               if "mean" in v.get("free24", {})]
        f18 = [v["free18"]["mean"] for v in rec["days"].values()
               if "mean" in v.get("free18", {})]
        hi = [v["tcm"]["daily_high_f"] for v in rec["days"].values()
              if "daily_high_f" in v.get("tcm", {})]
        lo = [v["tcm"]["overnight_low_f"] for v in rec["days"].values()
              if "overnight_low_f" in v.get("tcm", {})]
        rec["free_hours_24"] = round(sum(f24), 2) if f24 else None
        rec["free_hours_18"] = round(sum(f18), 2) if f18 else None
        rec["mean_daily_high_f"] = round(sum(hi) / len(hi), 2) if hi else None
        rec["mean_overnight_low_f"] = round(sum(lo) / len(lo), 2) if lo else None
        rec["complete"] = ok
        rows.append(rec)

        flag = "" if ok else "  (partial)"
        fh = rec["free_hours_24"]
        print(f"  {i:>2}/{len(METROS['metros'])} {m['name']:<20s} "
              f"free {fh if fh is not None else '--':>6} h   "
              f"high {rec['mean_daily_high_f'] or '--':>6} degF{flag}")

    done = [r for r in rows if r["complete"]]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "design_day": args.start, "days": days, "n_days": len(days),
        "box_km": box, "setpoint_c": SETPOINT_C,
        "setpoint_strict_c": SETPOINT_STRICT_C,
        "n_metros": len(rows), "n_complete": len(done),
        "coverage_note": (
            "A 30-metro panel, not a national grid. The API accepts roughly "
            "1,053 sq mi of land per call and the continental US is about 3.1 "
            "million sq mi, so full coverage would take around 3,000 calls "
            "against a 472-call budget. Every metro is sampled identically -- "
            "same 10 km box, same granularity, same day, same analytics -- so "
            "the comparison between them is sound even though the coverage is "
            "a sample."),
        "metros": rows,
    }, indent=2), encoding="utf-8")
    print(f"\n  {len(done)}/{len(rows)} complete -> {OUT.name}")
    print(f"  cache/network {fg.stats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
