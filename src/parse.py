"""Turn a FortyGuard heatmap response into tiles, on one code path.

The API returns two different tile schemas and code written against one finds
nothing in the other:

    tcm                     properties = {tile_id, average_temperature,
                                          min_temperature, max_temperature}
    exceedance /
    persistence /
    time_of_measure         properties = {tile_id, value}

Units, measured rather than assumed (see docs/api_findings.md):

    tcm                     degrees CELSIUS.  The quickstart README says degF;
                            it is wrong. Downtown Phoenix on 2025-07-15 returned
                            max_temperature ~40.2, which is 104 degF, not 40 degF.
    exceedance              count of hours past the threshold. Not degree-hours.
    persistence             longest continuous run, in hours. Only trustworthy
                            at filter_type=3.
    time_of_measure         hour-of-day 0-23 of the peak, in UTC.

Geometry is GeoJSON: coordinates are [lon, lat], never [lat, lon].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

# Property name -> the analytic that produces it.
TCM_FIELDS = ("average_temperature", "min_temperature", "max_temperature")
VALUE_FIELD = "value"

#: Analytic types whose tiles carry ``properties.value``.
ANALYSIS_TYPES = ("exceedance", "persistence", "time_of_measure")

#: Default UTC offset. Arizona does not observe DST so a single constant is
#: correct there year-round; ``set_utc_offset`` changes it for other cities.
PHOENIX_UTC_OFFSET_H = -7
_UTC_OFFSET_H = PHOENIX_UTC_OFFSET_H


def set_utc_offset(hours: int) -> None:
    """Point the local-time conversion at a different city."""
    global _UTC_OFFSET_H
    _UTC_OFFSET_H = hours


@dataclass
class Tile:
    """One heatmap cell.

    ``value`` is the single number the analytic produced. For tcm it defaults to
    ``average_temperature`` so callers that only want "the number" have one,
    while the individual temperature fields stay available in ``props``.
    """

    tile_id: int
    value: float | None
    ring: list[tuple[float, float]]  # [(lon, lat), ...], closed
    props: dict[str, Any] = field(default_factory=dict)

    @property
    def centroid(self) -> tuple[float, float]:
        """(lon, lat) average of the ring, excluding the repeated closing vertex."""
        pts = self.ring[:-1] if len(self.ring) > 1 and self.ring[0] == self.ring[-1] else self.ring
        n = len(pts) or 1
        return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """(min_lon, min_lat, max_lon, max_lat)."""
        lons = [p[0] for p in self.ring]
        lats = [p[1] for p in self.ring]
        return min(lons), min(lats), max(lons), max(lats)


@dataclass
class Heatmap:
    """A parsed heatmap response."""

    analytic_type: str
    tiles: list[Tile]
    stats: dict[str, Any]
    units: str

    def __len__(self) -> int:
        return len(self.tiles)

    def values(self) -> list[float]:
        return [t.value for t in self.tiles if isinstance(t.value, (int, float))]

    def value_spread(self) -> dict[str, float]:
        v = sorted(self.values())
        if not v:
            return {}
        return {
            "n": len(v),
            "min": v[0],
            "p50": v[len(v) // 2],
            "max": v[-1],
            "spread": v[-1] - v[0],
            "distinct": len(set(v)),
        }


def _ring_of(geometry: dict) -> list[tuple[float, float]]:
    """Outer ring as [(lon, lat), ...].

    GeoJSON Polygon coordinates nest one level deeper than a LineString: the
    first element is the exterior ring. Reading that wrong silently yields a
    ring of two-element lists and every area computation collapses to zero.
    """
    if not geometry:
        return []
    coords = geometry.get("coordinates") or []
    if not coords:
        return []
    ring = coords[0] if geometry.get("type") == "Polygon" else coords
    return [(float(p[0]), float(p[1])) for p in ring if len(p) >= 2]


def parse_heatmap(result: dict, analytic_type: str | None = None) -> Heatmap:
    """Parse either tile schema into a uniform Heatmap.

    ``analytic_type`` may be passed explicitly; otherwise it is read from
    ``stats_data``, and failing that inferred from which properties are present.
    """
    result = result or {}
    stats = result.get("stats_data") or {}
    feats = (result.get("map_data") or {}).get("features") or []

    kind = analytic_type or stats.get("analytic_type")
    if kind is None:
        first = (feats[0].get("properties") if feats else {}) or {}
        kind = "tcm" if any(f in first for f in TCM_FIELDS) else "analysis"

    tiles: list[Tile] = []
    for f in feats:
        props = dict(f.get("properties") or {})
        tid = props.pop("tile_id", len(tiles))

        if VALUE_FIELD in props:
            val = props[VALUE_FIELD]
        elif "average_temperature" in props:
            val = props["average_temperature"]
        else:
            val = None

        tiles.append(Tile(
            tile_id=int(tid) if tid is not None else len(tiles),
            value=float(val) if isinstance(val, (int, float)) else None,
            ring=_ring_of(f.get("geometry") or {}),
            props=props,
        ))

    units = stats.get("units") or ("celsius" if kind == "tcm" else "hour")
    return Heatmap(analytic_type=str(kind), tiles=tiles, stats=stats, units=units)


def tcm_field(hm: Heatmap, field_name: str) -> list[float]:
    """Pull one temperature field off a tcm heatmap.

    Raises rather than returning an empty list, because a silent empty result
    here is exactly the schema-divergence bug this module exists to prevent.
    """
    if field_name not in TCM_FIELDS:
        raise ValueError(f"{field_name!r} is not a tcm field; expected one of {TCM_FIELDS}")
    out = [t.props[field_name] for t in hm.tiles if field_name in t.props]
    if not out and hm.tiles:
        raise ValueError(
            f"No tile carries {field_name!r}. This response is analytic_type="
            f"{hm.analytic_type!r}, whose tiles carry {VALUE_FIELD!r} instead."
        )
    return out


def utc_hour_to_local(utc_hour: float) -> float:
    """Convert a time_of_measure UTC hour to the active city's local time.

    Arizona is UTC-7 year-round (no DST), so UTC hour 22 is 15:00 local there.
    """
    return (utc_hour + _UTC_OFFSET_H) % 24


#: Retained name for the Phoenix-specific conversion.
utc_hour_to_phoenix = utc_hour_to_local


def summarize(hms: Iterable[Heatmap]) -> str:
    lines = []
    for hm in hms:
        s = hm.value_spread()
        lines.append(
            f"{hm.analytic_type:16s} n={s.get('n', 0):>7,} "
            f"min={s.get('min', 0):>8.2f} p50={s.get('p50', 0):>8.2f} "
            f"max={s.get('max', 0):>8.2f} distinct={s.get('distinct', 0):>6,} "
            f"[{hm.units}]"
        )
    return "\n".join(lines)
