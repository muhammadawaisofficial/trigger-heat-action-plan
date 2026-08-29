"""Both tile schemas, one parser -- and the coordinate order that hides bugs.

SPEC.md trap 3: code written against ``tcm`` finds nothing in an exceedance
response, because the field is ``properties.value`` rather than
``properties.average_temperature``. Nothing raises; you just get zeros.

SPEC.md geometry rule: GeoJSON coordinates are [lon, lat]. Building a polygon
in [lat, lon] order is accepted by everything downstream and silently describes
somewhere in the Indian Ocean.
"""

from __future__ import annotations

import pytest

from parse import (ANALYSIS_TYPES, TCM_FIELDS, parse_heatmap, set_utc_offset,
                   tcm_field, utc_hour_to_local)

# A real Phoenix tile: 100 m square near the downtown probe box.
PHX_RING = [[-112.0740, 33.4484], [-112.0729, 33.4484],
            [-112.0729, 33.4493], [-112.0740, 33.4493],
            [-112.0740, 33.4484]]


def _response(props: dict, stats: dict | None = None, ring=None) -> dict:
    return {
        "map_data": {"type": "FeatureCollection", "features": [{
            "type": "Feature",
            "properties": props,
            "geometry": {"type": "Polygon", "coordinates": [ring or PHX_RING]},
        }]},
        "stats_data": stats or {},
    }


# ------------------------------------------------------------- both schemas

def test_analysis_schema_reads_properties_value():
    hm = parse_heatmap(_response(
        {"tile_id": 7, "value": 16.86},
        {"analytic_type": "exceedance", "units": "hour", "n_cells": 1}))
    assert hm.analytic_type == "exceedance"
    assert hm.units == "hour"
    assert len(hm) == 1
    assert hm.tiles[0].tile_id == 7
    assert hm.tiles[0].value == pytest.approx(16.86)


def test_tcm_schema_reads_average_temperature():
    hm = parse_heatmap(_response({
        "tile_id": 7, "average_temperature": 39.41,
        "min_temperature": 35.07, "max_temperature": 42.56,
    }, {"temperature_stats": {"mean": 39.41}}), "tcm")
    assert hm.analytic_type == "tcm"
    assert hm.tiles[0].value == pytest.approx(39.41)
    # The individual fields must remain reachable, not be flattened away.
    for f in TCM_FIELDS:
        assert f in hm.tiles[0].props


@pytest.mark.parametrize("analytic", ANALYSIS_TYPES)
def test_every_analysis_type_takes_the_value_path(analytic):
    hm = parse_heatmap(_response({"tile_id": 1, "value": 3.0},
                                 {"analytic_type": analytic}), analytic)
    assert hm.tiles[0].value == 3.0


def test_analytic_type_inferred_when_stats_are_missing():
    """404-adjacent responses sometimes arrive without stats_data."""
    assert parse_heatmap(_response({"tile_id": 1, "average_temperature": 40.0})
                         ).analytic_type == "tcm"
    assert parse_heatmap(_response({"tile_id": 1, "value": 4.0})
                         ).analytic_type == "analysis"


def test_tcm_field_on_an_exceedance_response_raises():
    """The schema-divergence bug this module exists to prevent.

    Asking a tcm question of an exceedance response must fail loudly. Returning
    an empty list here is what produces a confident zero downstream.
    """
    hm = parse_heatmap(_response({"tile_id": 1, "value": 16.86},
                                 {"analytic_type": "exceedance"}))
    with pytest.raises(ValueError, match="exceedance"):
        tcm_field(hm, "average_temperature")


def test_tcm_field_rejects_a_field_that_is_not_a_tcm_field():
    hm = parse_heatmap(_response({"tile_id": 1, "average_temperature": 40.0}), "tcm")
    with pytest.raises(ValueError, match="not a tcm field"):
        tcm_field(hm, "value")


# ------------------------------------------------- [lon, lat], never [lat, lon]

def test_phoenix_tile_lands_in_phoenix():
    """The coordinate-order assertion BUILD_PLAN Phase 1 requires by name.

    Phoenix is near lon -112, lat +33. Swap the order and you get lon +33,
    lat -112 -- an impossible latitude, but nothing in the stack objects.
    """
    hm = parse_heatmap(_response({"tile_id": 1, "value": 1.0}))
    lon, lat = hm.tiles[0].centroid
    assert -112.5 < lon < -111.9, f"longitude {lon} is not in Phoenix"
    assert 33.2 < lat < 34.0, f"latitude {lat} is not in Phoenix"
    # And the swap must be detectable, not merely absent.
    assert not (-90 <= lon <= 90 and abs(lat) > 90), "coordinates look swapped"


def test_ring_is_lon_first_in_storage_order():
    hm = parse_heatmap(_response({"tile_id": 1, "value": 1.0}))
    for x, y in hm.tiles[0].ring:
        assert x < 0, "first element must be longitude (negative in Arizona)"
        assert y > 0, "second element must be latitude (positive in Arizona)"


def test_bounds_are_min_lon_min_lat_max_lon_max_lat():
    hm = parse_heatmap(_response({"tile_id": 1, "value": 1.0}))
    min_lon, min_lat, max_lon, max_lat = hm.tiles[0].bounds
    assert min_lon < max_lon < 0
    assert 0 < min_lat < max_lat


def test_a_swapped_polygon_is_visibly_wrong():
    """Guard the guard: feed it [lat, lon] and confirm the check would fire."""
    swapped = [[p[1], p[0]] for p in PHX_RING]
    hm = parse_heatmap(_response({"tile_id": 1, "value": 1.0}, ring=swapped))
    lon, lat = hm.tiles[0].centroid
    assert not (-112.5 < lon < -111.9), "the Phoenix assertion must fail here"


# ------------------------------------------------------------- UTC to local

def test_utc_hour_converts_to_phoenix_local():
    """SPEC.md trap 2: time_of_measure is UTC; Arizona is UTC-7 year-round."""
    set_utc_offset(-7)
    assert utc_hour_to_local(22) == 15   # the example given in SPEC.md
    assert utc_hour_to_local(0) == 17    # must wrap, not go negative
    assert utc_hour_to_local(6) == 23


def test_local_hour_is_always_in_range():
    set_utc_offset(-7)
    for h in range(24):
        assert 0 <= utc_hour_to_local(h) < 24


def test_utc_offset_is_configurable_for_other_cities():
    set_utc_offset(-5)
    assert utc_hour_to_local(22) == 17
    set_utc_offset(-7)  # restore; module state is global
    assert utc_hour_to_local(22) == 15
