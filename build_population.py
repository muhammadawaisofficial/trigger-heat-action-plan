"""Join US Census population onto Phoenix urban villages.

"Silent zones" is a stronger finding as a count of people than as a count of
polygons, so this builds a static per-village population file.

Method: areal interpolation. Census block groups are the finest geography with
published population that also has public boundaries. Each block group's
population is apportioned to a village in proportion to the share of the block
group's area that falls inside that village:

    village_pop = sum over block groups of  bg_pop * (overlap_area / bg_area)

The standing caveat is that this assumes population is uniformly distributed
within a block group. Block groups are small (600-3,000 people by design) and
village boundaries in Phoenix largely follow the same arterial grid that block
groups do, so the error is modest -- but it is an approximation, and the output
records it as one.

Sources
  population  US Census ACS 5-year 2023, table B01003_001E, via api.census.gov
  geometry    US Census TIGERweb ACS2023, Census Block Groups layer

    CENSUS_API_KEY=... python build_population.py
"""

from __future__ import annotations

import gzip
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from shapely.geometry import shape  # noqa: E402
from shapely.strtree import STRtree  # noqa: E402

import study  # noqa: E402
from aggregate import _project_ring, _to_polygon, load_zones  # noqa: E402

STATE, COUNTY = "04", "013"          # Arizona, Maricopa County
OUT = Path("data/zones/phoenix_villages_population.json")
CACHE = Path("data/cache/census")

CENSUS_POP = ("https://api.census.gov/data/2023/acs/acs5"
              "?get=NAME,B01003_001E&for=block%20group:*&in=state:{s}+county:{c}&key={k}")
TIGER = ("https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/"
         "tigerWMS_ACS2023/MapServer/10/query")


def _get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "TRIGGER/1.0"})
    return urllib.request.urlopen(req, timeout=timeout).read()


def fetch_population(key: str) -> dict[str, int]:
    """GEOID -> population for every block group in the county."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / "acs2023_bg_population.json.gz"
    if cached.exists():
        with gzip.open(cached, "rt", encoding="utf-8") as fh:
            return json.load(fh)

    raw = json.loads(_get(CENSUS_POP.format(s=STATE, c=COUNTY, k=key)))
    header, rows = raw[0], raw[1:]
    i_pop = header.index("B01003_001E")
    i_st, i_co = header.index("state"), header.index("county")
    i_tr, i_bg = header.index("tract"), header.index("block group")

    out: dict[str, int] = {}
    for r in rows:
        geoid = f"{r[i_st]}{r[i_co]}{r[i_tr]}{r[i_bg]}"
        try:
            pop = int(r[i_pop])
        except (TypeError, ValueError):
            continue
        # Census uses negative sentinels for suppressed values.
        if pop >= 0:
            out[geoid] = pop

    with gzip.open(cached, "wt", encoding="utf-8") as fh:
        json.dump(out, fh)
    return out


def fetch_geometry() -> dict[str, dict]:
    """GEOID -> GeoJSON geometry, paged through the TIGERweb record limit."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / "tigerweb_bg_geometry.json.gz"
    if cached.exists():
        with gzip.open(cached, "rt", encoding="utf-8") as fh:
            return json.load(fh)

    feats: dict[str, dict] = {}
    offset = 0
    while True:
        params = {
            "where": f"STATE='{STATE}' AND COUNTY='{COUNTY}'",
            "outFields": "GEOID",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
            "resultOffset": str(offset),
            "resultRecordCount": "1000",
        }
        url = f"{TIGER}?{urllib.parse.urlencode(params)}"
        body = json.loads(_get(url))
        got = body.get("features") or []
        for ft in got:
            gid = (ft.get("properties") or {}).get("GEOID")
            if gid and ft.get("geometry"):
                feats[gid] = ft["geometry"]
        print(f"    fetched {len(got):>5} block groups (offset {offset}), "
              f"total {len(feats):,}")
        if len(got) < 1000:
            break
        offset += 1000
        time.sleep(0.3)

    with gzip.open(cached, "wt", encoding="utf-8") as fh:
        json.dump(feats, fh)
    return feats


def main() -> int:
    key = os.getenv("CENSUS_API_KEY")
    print("Joining Census population onto Phoenix urban villages\n")

    print("  1. block-group population (ACS 5-year 2023, B01003_001E)")
    try:
        pop = fetch_population(key or "")
    except Exception as exc:  # noqa: BLE001
        print(f"     failed: {exc}")
        print("     Set CENSUS_API_KEY (free: api.census.gov/data/key_signup.html)")
        return 2
    print(f"     {len(pop):,} block groups, {sum(pop.values()):,} people in "
          f"Maricopa County")

    print("\n  2. block-group geometry (TIGERweb ACS2023)")
    geoms = fetch_geometry()
    print(f"     {len(geoms):,} geometries")

    print("\n  3. areal interpolation onto villages")
    zones = load_zones(study.ZONES_PATH, name_field=study.ZONE_NAME_FIELD)

    bg_polys, bg_ids = [], []
    for gid, g in geoms.items():
        if gid not in pop:
            continue
        poly = _to_polygon(g)
        if poly is None or poly.area <= 0:
            continue
        bg_polys.append(poly)
        bg_ids.append(gid)

    tree = STRtree(bg_polys)
    result = {}
    assigned_total = 0.0

    for z in zones:
        total = 0.0
        n_bg = 0
        for j in tree.query(z.geom):
            j = int(j)
            poly = bg_polys[j]
            if not poly.intersects(z.geom):
                continue
            inter = poly.intersection(z.geom).area
            if inter <= 0:
                continue
            share = inter / poly.area
            total += pop[bg_ids[j]] * share
            n_bg += 1
        result[z.zone_id] = {
            "name": z.name,
            "population": int(round(total)),
            "area_sq_mi": round(z.area_sq_mi, 2),
            "density_per_sq_mi": int(round(total / z.area_sq_mi)) if z.area_sq_mi else 0,
            "block_groups_touched": n_bg,
        }
        assigned_total += total

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "meta": {
            "method": ("areal interpolation of Census block-group population onto "
                       "urban village boundaries, weighted by overlap area"),
            "assumption": ("population is uniformly distributed within a block "
                           "group; this is an approximation"),
            "population_source": "US Census ACS 5-year 2023, table B01003_001E",
            "geometry_source": "US Census TIGERweb ACS2023, Census Block Groups",
            "county": "Maricopa County, Arizona (FIPS 04013)",
            "county_population": sum(pop.values()),
            "assigned_to_villages": int(round(assigned_total)),
        },
        "villages": result,
    }, indent=2), encoding="utf-8")

    print(f"\n  {'village':<24s} {'population':>12s} {'per sq mi':>11s} {'BGs':>6s}")
    print("  " + "-" * 58)
    for zid, v in sorted(result.items(), key=lambda kv: -kv[1]["population"]):
        print(f"  {v['name']:<24s} {v['population']:>12,} "
              f"{v['density_per_sq_mi']:>11,} {v['block_groups_touched']:>6}")
    print("  " + "-" * 58)
    print(f"  {'TOTAL in villages':<24s} {int(round(assigned_total)):>12,}")
    print(f"\n  Phoenix city population (2020 census) is about 1,608,000, so a")
    print(f"  village total near that figure indicates the join is sound.")
    print(f"\n  written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
