"""Wet-bulb per metro: the variable the evaporative-cooling decision turns on.

    python fetch_wetbulb.py

Dry-bulb temperature says how hot the air is. WET-BULB says how much cooling you
can get out of evaporating water into it, which is the entire question when
choosing between evaporative and mechanical cooling.

The industry's core dilemma is that saving electricity often means wasting water.
Evaporative cooling is far more energy-efficient than mechanical chilling -- but
only where the wet-bulb is low, and a low wet-bulb means dry air, which tends to
mean a dry region. So the places where evaporative cooling works best are
frequently the places least able to spare the water. Microsoft reports a WUE of
1.52 L/kWh in Arizona against 0.02 in Singapore.

Without this measurement the siting model cannot choose between evaporative and
mechanical for any site that free cooling will not carry, and it says so rather
than guessing.

/v1/env_params is a per-POINT endpoint, so this samples each metro at its centre
rather than gridding it -- one call per metro. That is a real limitation:
wet-bulb varies across a metro just as dry-bulb does, and a single centre point
cannot resolve that. It is recorded in the output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from cache import CachedFortyGuard, has_key  # noqa: E402
from schema import c_to_f  # noqa: E402

REPO = Path(__file__).parent
METROS = json.loads((REPO / "data" / "metros.json").read_text(encoding="utf-8"))
NATIONAL = REPO / "data" / "results" / "national.json"
OUT = REPO / "data" / "results" / "wetbulb.json"

WETBULB_LIMIT_C = 24.0     # above this, evaporative cooling is largely ineffective


def main() -> int:
    if not NATIONAL.exists():
        print("Run fetch_national.py first: this needs each metro's measured "
              "air temperature as the env_params input.")
        return 2

    nat = json.loads(NATIONAL.read_text(encoding="utf-8"))
    day = nat["design_day"]
    temps = {m["id"]: m.get("mean_daily_high_f") for m in nat["metros"]}

    fg = CachedFortyGuard(verbose=False)
    print("=" * 74)
    print(f"Wet-bulb per metro -- env_params, {day}")
    print("=" * 74)
    print(f"  metros  {len(METROS['metros'])}   one point each, at the metro centre")
    print(f"  API key {'present' if has_key() else 'ABSENT - cache only'}\n")

    rows = []
    for i, m in enumerate(METROS["metros"], 1):
        f = temps.get(m["id"])
        if f is None:
            continue
        t_c = (f - 32.0) * 5.0 / 9.0
        try:
            r = fg.env_params(
                latitude=round(m["lat"], 5), longitude=round(m["lon"], 5),
                temperature=round(t_c, 2), start_date=day, filter_type=3,
                analysis=["wet_bulb_temperature_celsius",
                          "relative_humidity_percent",
                          "heat_index_celsius"],
                label=f"wetbulb {m['id']} {day}")["result"]
            loc = (r.get("locations") or [{}])[0]
            # The series live under "parameters", not "analysis", and the
            # endpoint returns EVERY parameter it knows regardless of which
            # were requested -- so the requested list narrows nothing.
            an = loc.get("parameters") or {}
            def series(k):
                v = an.get(k)
                return [x for x in v if isinstance(x, (int, float))] if isinstance(v, list) else []
            wb = series("wet_bulb_temperature_celsius")
            rh = series("relative_humidity_percent")
            hi = series("heat_index_celsius")
            if not wb:
                print(f"  {i:>2}/{len(METROS['metros'])} {m['name']:<20s} no wet-bulb returned")
                continue
            row = {
                "id": m["id"], "name": m["name"],
                "wet_bulb_mean_c": round(sum(wb) / len(wb), 2),
                "wet_bulb_max_c": round(max(wb), 2),
                "rh_mean_pct": round(sum(rh) / len(rh), 1) if rh else None,
                "heat_index_max_c": round(max(hi), 2) if hi else None,
                "air_temp_input_f": round(f, 2),
            }
            row["evaporative_effective"] = row["wet_bulb_max_c"] < WETBULB_LIMIT_C
            rows.append(row)
            print(f"  {i:>2}/{len(METROS['metros'])} {m['name']:<20s} "
                  f"wet-bulb {row['wet_bulb_mean_c']:>5.1f} degC mean / "
                  f"{row['wet_bulb_max_c']:>5.1f} max   RH "
                  f"{row['rh_mean_pct'] if row['rh_mean_pct'] is not None else '--':>5}%   "
                  f"{'evaporative OK' if row['evaporative_effective'] else 'evaporative POOR'}")
        except Exception as exc:  # noqa: BLE001
            print(f"  {i:>2}/{len(METROS['metros'])} {m['name']:<20s} "
                  f"{type(exc).__name__}: {str(exc)[:70]}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "day": day, "n_metros": len(rows),
        "wetbulb_limit_c": WETBULB_LIMIT_C,
        "method": ("/v1/env_params sampled at each metro centre, using that "
                   "metro's own measured mean daily high as the temperature "
                   "input. One point per metro."),
        "caveat": ("env_params is a per-POINT endpoint, so this is a single "
                   "centre sample and cannot resolve wet-bulb variation ACROSS a "
                   "metro -- which is real, and is the same limitation this "
                   "project criticises elsewhere. The free-cooling term is "
                   "gridded at 100 m; this term is not."),
        "metros": rows,
    }, indent=2), encoding="utf-8")
    print(f"\n  {len(rows)} metros -> {OUT.name}   cache/network {fg.stats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
