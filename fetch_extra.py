"""Close the two remaining FortyGuard API gaps, and answer a real question with them.

    python fetch_extra.py

Until now the pipeline used three of the four heatmap analytics (tcm, exceedance,
persistence) and none of /v1/env_params. Both gaps are closed here, and neither is
decoration -- each answers a question the headline raises but cannot settle.

1. time_of_measure -- WHEN does each village peak?
   The finding is that ten villages stay hot overnight while the citywide number
   does not. time_of_measure gives the hour of peak per tile, in UTC, which
   converted to Phoenix local time shows whether silent zones peak LATER than the
   rest of the city. A later peak is the signature of heat retention in built
   mass, which is a physical explanation for the divergence rather than just a
   restatement of it.

2. env_params -- is dry-bulb temperature even the right thing to trigger on?
   The plan triggers on air temperature. Humidity is what makes a Phoenix night
   dangerous, and heat index is what emergency physicians actually use. Sampling
   heat_index_celsius at each village centroid on the worst day says whether the
   ranking changes when humidity is accounted for.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import study  # noqa: E402
from cache import CachedFortyGuard, OfflineCacheMiss, has_key  # noqa: E402
from parse import parse_heatmap, utc_hour_to_local  # noqa: E402

DAY = "2025-08-08"          # the worst false-calm day in the published window
OUT = Path(__file__).parent / "data" / "results" / "extra_analytics.json"


def centroid(ring) -> tuple[float, float]:
    pts = [p for p in ring if isinstance(p, (list, tuple)) and len(p) == 2]
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def main() -> int:
    fg = CachedFortyGuard(verbose=True)
    aoi = study.city_aoi()
    out: dict = {"day": DAY, "timezone_note": study.TIMEZONE_NOTE}

    print("=" * 74)
    print(f"Closing the API gaps -- time_of_measure and env_params, {DAY}")
    print("=" * 74)
    print(f"  API key {'present' if has_key() else 'ABSENT - cache only'}\n")

    # ------------------------------------------------ 1. time_of_measure
    print("1. time_of_measure -- hour of peak per tile, UTC -> Phoenix local")
    try:
        hm = parse_heatmap(fg.heatmap(
            polygon_aoi=aoi, start_date=DAY, filter_type=3,
            granularity=study.GRANULARITY_M, analytic_type="time_of_measure",
            label=f"phx-city time_of_measure {DAY}")["result"], "time_of_measure")

        from aggregate import ZoneAggregator, load_zones
        zones = load_zones(study.ZONES_PATH, name_field=study.ZONE_NAME_FIELD)
        agg = ZoneAggregator(zones, hm.tiles, cache_key=study.ZONE_WEIGHT_KEY)

        div = json.loads(
            (Path(__file__).parent / "data" / "results" / "divergence.json")
            .read_text(encoding="utf-8"))
        silent = set()
        for c in div["clauses"]:
            silent |= set(c.get("silent_zones") or [])

        rows = []
        for r in agg.aggregate(hm):
            rows.append({
                "zone_id": r.zone_id, "name": r.name,
                "peak_hour_utc": round(r.value, 2),
                "peak_hour_local": round(utc_hour_to_local(r.value), 2),
                "silent": r.zone_id in silent,
            })
        rows.sort(key=lambda x: x["peak_hour_local"])
        out["time_of_measure"] = rows

        sil = [r["peak_hour_local"] for r in rows if r["silent"]]
        oth = [r["peak_hour_local"] for r in rows if not r["silent"]]
        print(f"   {len(rows)} villages")
        for r in rows:
            h = r["peak_hour_local"]
            print(f"     {r['name']:<24s} peaks {int(h):02d}:{int((h%1)*60):02d} local"
                  f"{'   [SILENT ZONE]' if r['silent'] else ''}")
        if sil and oth:
            d = sum(sil) / len(sil) - sum(oth) / len(oth)
            out["peak_hour_gap"] = round(d, 3)
            print(f"\n   Silent zones peak {abs(d):.2f} h "
                  f"{'LATER' if d > 0 else 'EARLIER'} than the rest, on average.")
    except Exception as exc:  # noqa: BLE001
        # time_of_measure did not complete at city scale: 2400 s and 40
        # transient status errors on 272,917 tiles. Recorded as a measured API
        # limit rather than retried forever, and it must not prevent env_params
        # from running.
        out["time_of_measure_error"] = f"{type(exc).__name__}: {exc}"
        print(f"   FAILED at city scale: {type(exc).__name__}")
        print(f"   {str(exc)[:150]}")
        print("   Recorded as a measured limit. Retrying on the 2 km box instead.")
        try:
            from geo import feature_collection
            RING = [(-112.08476617879987, 33.43938611862268),
                    (-112.06323382120013, 33.43938611862268),
                    (-112.06323382120013, 33.45741388137732),
                    (-112.08476617879987, 33.45741388137732),
                    (-112.08476617879987, 33.43938611862268)]
            small = parse_heatmap(fg.heatmap(
                polygon_aoi=feature_collection(RING), start_date=DAY,
                filter_type=3, granularity=100, analytic_type="time_of_measure",
                label=f"downtown-phx time_of_measure {DAY}")["result"],
                "time_of_measure")
            v = [t.value for t in small.tiles if t.value is not None]
            loc = [utc_hour_to_local(x) for x in v]
            out["time_of_measure_small_aoi"] = {
                "n_tiles": len(v), "utc_min": min(v), "utc_max": max(v),
                "local_min": min(loc), "local_max": max(loc),
                "distinct": len(set(v)),
                "note": "2 km downtown box. The city-scale request timed out.",
            }
            print(f"   2 km box OK: {len(v)} tiles, peak hour "
                  f"{min(loc):.0f}-{max(loc):.0f} local, {len(set(v))} distinct")
        except Exception as exc2:  # noqa: BLE001
            print(f"   2 km box also failed: {type(exc2).__name__}")
            out["time_of_measure_small_aoi_error"] = str(exc2)

    # ------------------------------------------------------ 2. env_params
    print("\n2. env_params -- heat index at each village centroid")
    try:
        import geojson_zones  # noqa: F401
    except ImportError:
        pass
    try:
        geo = json.loads((Path(__file__).parent / "data" / "zones" /
                          "phoenix_villages_raw.geojson").read_text(encoding="utf-8"))
        div = json.loads(
            (Path(__file__).parent / "data" / "results" / "divergence.json")
            .read_text(encoding="utf-8"))
        det = None
        for c in div["clauses"]:
            if c["clause_id"] == "PHX-2026-BENCH-LOW90":
                det = next((d for d in c["determinations"] if d["day"] == DAY), None)
        vals = {z["zone_id"]: z for z in (det or {}).get("zones", [])}

        env_rows = []
        for ft in geo["features"]:
            zid = str(ft["properties"].get("NAME", "")).lower().replace(" ", "_")
            if zid not in vals:
                continue
            ring = ft["geometry"]["coordinates"]
            while isinstance(ring[0][0], (list, tuple)):
                ring = ring[0]
            lon, lat = centroid(ring)
            temp_c = vals[zid]["value"]
            try:
                r = fg.env_params(
                    latitude=round(lat, 5), longitude=round(lon, 5),
                    temperature=round(temp_c, 2),
                    start_date=DAY, filter_type=3, start_time="05:00",
                    analysis=["heat_index_celsius", "relative_humidity_percent",
                              "apparent_temperature_celsius"],
                    label=f"env {zid} {DAY}")
            except Exception as exc:  # noqa: BLE001
                print(f"   {zid}: {type(exc).__name__} {str(exc)[:90]}")
                continue
            env_rows.append({"zone_id": zid, "name": vals[zid]["name"],
                             "air_temp_c": round(temp_c, 2), "raw": r})
        out["env_params"] = env_rows
        print(f"   {len(env_rows)} villages sampled")
    except Exception as exc:  # noqa: BLE001
        print(f"   skipped: {type(exc).__name__} {exc}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\n  wrote {OUT.name}   cache/network {fg.stats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
