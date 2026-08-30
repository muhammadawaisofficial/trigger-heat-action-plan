"""Geometry helpers: AOI construction and area, in GeoJSON [lon, lat] order.

Everything here is longitude-first. The single most common way to silently
destroy a spatial analysis is to build a polygon in [lat, lon] order -- the
request is accepted, tiles come back, and they describe somewhere in the Indian
Ocean.
"""

from __future__ import annotations

import math

EARTH_R_KM = 6371.0088
KM_PER_DEG_LAT = 110.574
SQ_KM_PER_SQ_MI = 2.589988


def km_per_deg_lon(lat_deg: float) -> float:
    """East-west scale shrinks with latitude; at 33.45N a degree is ~92.9 km."""
    return 111.320 * math.cos(math.radians(lat_deg))


def feature_collection(ring: list[tuple[float, float]]) -> dict:
    """Wrap a closed [lon, lat] ring as the FeatureCollection the API expects."""
    if ring[0] != ring[-1]:
        ring = [*ring, ring[0]]  # the API requires first == last
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {},
            "geometry": {"type": "Polygon", "coordinates": [[list(p) for p in ring]]},
        }],
    }


def bbox_aoi(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> dict:
    """Construct a GeoJSON FeatureCollection bounding box AOI.

    Args:
        min_lon: Minimum longitude (west bound).
        min_lat: Minimum latitude (south bound).
        max_lon: Maximum longitude (east bound).
        max_lat: Maximum latitude (north bound).

    Returns:
        GeoJSON FeatureCollection dict formatted with closed coordinates ring.
    """
    return feature_collection([
        (min_lon, min_lat), (max_lon, min_lat),
        (max_lon, max_lat), (min_lon, max_lat), (min_lon, min_lat),
    ])


def square_aoi(center_lat: float, center_lon: float, side_km: float) -> dict:
    """Construct a square AOI of specified side length centred on a given point.

    Args:
        center_lat: Center point latitude in degrees.
        center_lon: Center point longitude in degrees.
        side_km: Side length of the bounding square in kilometres.

    Returns:
        GeoJSON FeatureCollection bounding box covering the target area.
    """
    dlat = side_km / KM_PER_DEG_LAT / 2
    dlon = side_km / km_per_deg_lon(center_lat) / 2
    return bbox_aoi(center_lon - dlon, center_lat - dlat,
                    center_lon + dlon, center_lat + dlat)


def ring_area_sq_km(ring: list[tuple[float, float]], ref_lat: float | None = None) -> float:
    """Planar shoelace area of a small [lon, lat] ring, in square kilometres.

    An equirectangular approximation about the ring's own mean latitude. Over a
    city-sized AOI the error is well under a percent, and it avoids pulling in a
    projection dependency for what is only ever used as an aggregation weight.
    """
    if len(ring) < 3:
        return 0.0
    pts = ring[:-1] if ring[0] == ring[-1] else ring
    if len(pts) < 3:
        return 0.0

    lat0 = ref_lat if ref_lat is not None else sum(p[1] for p in pts) / len(pts)
    kx = km_per_deg_lon(lat0)
    ky = KM_PER_DEG_LAT

    xs = [p[0] * kx for p in pts]
    ys = [p[1] * ky for p in pts]

    total = 0.0
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        total += xs[i] * ys[j] - xs[j] * ys[i]
    return abs(total) / 2.0


def aoi_area_sq_km(aoi: dict) -> float:
    ring = aoi["features"][0]["geometry"]["coordinates"][0]
    return ring_area_sq_km([(p[0], p[1]) for p in ring])


def sq_km_to_sq_mi(v: float) -> float:
    return v / SQ_KM_PER_SQ_MI


def aoi_bounds(aoi: dict) -> tuple[float, float, float, float]:
    ring = aoi["features"][0]["geometry"]["coordinates"][0]
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return min(lons), min(lats), max(lons), max(lats)
