"""Aggregate tiles to administrative zones by area-weighted overlap.

Tiles are a regular grid; urban village boundaries are not. A nearest-tile or
centroid-in-polygon lookup silently discards most of a zone and biases the
result toward whatever the boundary happens to clip. Every tile that overlaps a
zone contributes, weighted by the area of the overlap:

    zone_value = sum(tile_value * overlap_area) / sum(overlap_area)

At 100 m granularity a Phoenix urban village contains thousands of tiles, so
this is not a rounding detail -- the boundary tiles are a real fraction of a
small village and they are systematically the ones nearest other land uses.

Areas are computed in an equal-area projection about the city's own latitude
rather than in raw degrees, because a degree of longitude at 33.4 N is only
0.83 of a degree of latitude and unprojected areas would overweight
east-west extent.
"""

from __future__ import annotations

import gzip
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from shapely.geometry import Polygon, shape
from shapely.strtree import STRtree

from parse import Heatmap, Tile

REPO_ROOT = Path(__file__).resolve().parent.parent
WEIGHT_DIR = REPO_ROOT / "data" / "cache" / "zone_weights"

# Local equal-area scaling about the study area's own latitude. The constant
# cancels in a weighted mean, but it keeps reported areas in real square
# kilometres -- and it must follow the city, since a degree of longitude is
# 92.9 km at Phoenix and 111 km at the equator.
_LAT0 = 33.5                                    # replaced by set_projection()
_KX = 111.320 * math.cos(math.radians(_LAT0))   # km per degree longitude
_KY = 110.574                                    # km per degree latitude


def set_projection(centre_lat: float) -> None:
    """Re-centre the local projection on a different city."""
    global _LAT0, _KX
    _LAT0 = centre_lat
    _KX = 111.320 * math.cos(math.radians(centre_lat))


def _project(lon: float, lat: float) -> tuple[float, float]:
    return lon * _KX, lat * _KY


def _project_ring(ring: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
    return [_project(x, y) for x, y in ring]


@dataclass
class Zone:
    """One administrative unit, with its geometry pre-projected."""

    zone_id: str
    name: str
    geom: Polygon           # projected to local km
    area_sq_km: float
    props: dict

    @property
    def area_sq_mi(self) -> float:
        return self.area_sq_km / 2.589988


@dataclass
class ZoneValue:
    """A zone's aggregated value for one heatmap."""

    zone_id: str
    name: str
    value: float
    n_tiles: int
    covered_sq_km: float
    coverage: float          # fraction of the zone actually covered by tiles

    def __repr__(self) -> str:
        return (f"ZoneValue({self.name}, {self.value:.3f}, "
                f"{self.n_tiles} tiles, coverage {self.coverage:.1%})")


def _to_polygon(geometry: dict) -> Polygon | None:
    """Project a GeoJSON geometry into local km, dissolving multipolygons."""
    try:
        g = shape(geometry)
    except Exception:  # noqa: BLE001 - malformed geometry is skipped, not fatal
        return None
    if g.is_empty:
        return None

    def proj(poly):
        ext = _project_ring(poly.exterior.coords)
        ints = [_project_ring(r.coords) for r in poly.interiors]
        return Polygon(ext, ints)

    if g.geom_type == "Polygon":
        out = proj(g)
    elif g.geom_type == "MultiPolygon":
        parts = [proj(p) for p in g.geoms]
        out = max(parts, key=lambda p: p.area) if len(parts) == 1 else None
        if out is None:
            from shapely.ops import unary_union
            out = unary_union(parts)
    else:
        return None

    if not out.is_valid:
        out = out.buffer(0)  # repair self-intersections rather than drop the zone
    return out if not out.is_empty else None


def load_zones(path: str | Path, name_field: str = "NAME",
               id_field: str | None = None) -> list[Zone]:
    """Load administrative boundaries from a GeoJSON FeatureCollection."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    zones: list[Zone] = []
    for i, ft in enumerate(data.get("features", [])):
        poly = _to_polygon(ft.get("geometry") or {})
        if poly is None:
            continue
        props = ft.get("properties") or {}
        name = str(props.get(name_field, f"zone_{i}"))
        zid = str(props.get(id_field)) if id_field else name.lower().replace(" ", "_")
        zones.append(Zone(zone_id=zid, name=name, geom=poly,
                          area_sq_km=poly.area, props=props))
    return zones


class ZoneAggregator:
    """Reusable tile->zone aggregator for a fixed tile grid.

    The overlap weights depend only on geometry, so they are computed once and
    reused for every heatmap sharing that grid. With 272,917 tiles and 15
    villages that is the difference between seconds and minutes per call.
    """

    def __init__(self, zones: list[Zone], tiles: list[Tile],
                 cache_key: str | None = None) -> None:
        self.zones = zones
        self.tile_index: list[int] = []
        self._weights: dict[str, list[tuple[int, float]]] = {}

        # Overlap weights depend only on geometry, and building them over
        # 272,917 tiles takes ~30 s. Every heatmap on the same grid reuses them.
        path = (WEIGHT_DIR / f"{cache_key}.json.gz") if cache_key else None
        if path is not None and path.exists():
            try:
                with gzip.open(path, "rt", encoding="utf-8") as fh:
                    raw = json.load(fh)
                if raw.get("n_tiles") == len(tiles) and \
                        raw.get("zone_ids") == [z.zone_id for z in zones]:
                    self._weights = {k: [(int(i), float(w)) for i, w in v]
                                     for k, v in raw["weights"].items()}
                    return
            except (OSError, EOFError, json.JSONDecodeError, KeyError):
                pass  # rebuild rather than trust a damaged weight cache

        self._build(tiles)

        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            with gzip.open(tmp, "wt", encoding="utf-8") as fh:
                json.dump({
                    "n_tiles": len(tiles),
                    "zone_ids": [z.zone_id for z in zones],
                    "weights": self._weights,
                }, fh, separators=(",", ":"))
            tmp.replace(path)

    def _build(self, tiles: list[Tile]) -> None:
        polys, keep = [], []
        for i, t in enumerate(tiles):
            if len(t.ring) < 4:
                continue
            p = Polygon(_project_ring(t.ring))
            if p.is_empty or not p.is_valid:
                continue
            polys.append(p)
            keep.append(i)

        tree = STRtree(polys)
        for z in self.zones:
            pairs: list[tuple[int, float]] = []
            for j in tree.query(z.geom):
                p = polys[int(j)]
                if not p.intersects(z.geom):
                    continue
                a = p.intersection(z.geom).area
                if a > 0:
                    pairs.append((keep[int(j)], a))
            self._weights[z.zone_id] = pairs

    def aggregate(self, hm: Heatmap) -> list[ZoneValue]:
        """Area-weighted mean of tile values within each zone."""
        out: list[ZoneValue] = []
        for z in self.zones:
            num = den = 0.0
            n = 0
            for idx, w in self._weights[z.zone_id]:
                if idx >= len(hm.tiles):
                    continue
                v = hm.tiles[idx].value
                if v is None:
                    continue
                num += v * w
                den += w
                n += 1
            value = num / den if den else float("nan")
            out.append(ZoneValue(
                zone_id=z.zone_id, name=z.name, value=value, n_tiles=n,
                covered_sq_km=den, coverage=den / z.area_sq_km if z.area_sq_km else 0.0,
            ))
        return out

    def aggregate_field(self, hm: Heatmap, field: str) -> list[ZoneValue]:
        """Area-weighted mean of a named tcm property (e.g. max_temperature)."""
        out: list[ZoneValue] = []
        for z in self.zones:
            num = den = 0.0
            n = 0
            for idx, w in self._weights[z.zone_id]:
                if idx >= len(hm.tiles):
                    continue
                v = hm.tiles[idx].props.get(field)
                if not isinstance(v, (int, float)):
                    continue
                num += v * w
                den += w
                n += 1
            out.append(ZoneValue(
                zone_id=z.zone_id, name=z.name,
                value=num / den if den else float("nan"),
                n_tiles=n, covered_sq_km=den,
                coverage=den / z.area_sq_km if z.area_sq_km else 0.0,
            ))
        return out


def tile_areas(tiles: list[Tile]) -> list[float]:
    """Projected area of every tile, in square kilometres.

    Depends only on the grid, which is fixed for an AOI and granularity, so
    callers compute this once and reuse it for every heatmap on that grid.
    Rebuilding it per call means constructing 272,917 polygons each time.
    """
    out = []
    for t in tiles:
        if len(t.ring) < 4:
            out.append(0.0)
            continue
        out.append(Polygon(_project_ring(t.ring)).area)
    return out


def area_weighted_mean(hm: Heatmap, field: str | None = None,
                       areas: list[float] | None = None) -> float:
    """Area-weighted mean across every tile in a heatmap.

    This is the citywide-proxy baseline: what a single sensor reading would be
    if it perfectly represented the whole AOI. It is a PROXY for station-based
    sensing, not a station feed, and must be labelled as such wherever reported.

    Pass ``areas`` from :func:`tile_areas` to avoid rebuilding tile geometry.
    """
    if areas is None:
        areas = tile_areas(hm.tiles)

    num = den = 0.0
    for t, a in zip(hm.tiles, areas):
        if a <= 0:
            continue
        v = t.props.get(field) if field else t.value
        if not isinstance(v, (int, float)):
            continue
        num += v * a
        den += a
    return num / den if den else float("nan")
