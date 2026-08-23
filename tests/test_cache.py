"""The cache: a second identical call must make ZERO network requests.

This is the property the whole submission rests on. A judge clones the repo with
no API key and reproduces the headline number; if the cache misses, they get an
exception instead of a result.

These tests never touch the network. The miss path is exercised against a stub
client, so a failure here is a bug in the cache, not a connectivity problem.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import cache as cache_mod
from cache import (OfflineCacheMiss, CachedFortyGuard, cache_key, iter_entries,
                   list_cache, replay, write_manifest)

RING = [[-112.08, 33.44], [-112.06, 33.44], [-112.06, 33.46],
        [-112.08, 33.46], [-112.08, 33.44]]
AOI = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "properties": {},
     "geometry": {"type": "Polygon", "coordinates": [RING]}}]}


def _fake_result(n=3):
    return {"map_data": {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"tile_id": i, "value": 10.0 + i},
         "geometry": {"type": "Polygon", "coordinates": [RING]}}
        for i in range(n)]},
        "stats_data": {"analytic_type": "exceedance", "units": "hour", "n_cells": n}}


class StubClient:
    """Stands in for the vendored client and counts submissions.

    Mirrors the two-step contract the real client has: ``create_heatmap``
    submits and returns an ``activity_id``, then ``get_status`` is polled until
    it reports completed. ``calls`` counts submissions, which is what "made a
    network request" means here.
    """

    def __init__(self):
        self.calls = 0
        self.status_polls = 0

    def create_heatmap(self, **kwargs):
        self.calls += 1
        return {"activity_id": f"stub-activity-{self.calls}"}

    def get_status(self, activity_id):
        self.status_polls += 1
        return {"status": "completed", "result": _fake_result()}


@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    """Point every cache directory at a temp dir so the committed cache is safe.

    Also reports a key as present. These tests exercise the write-then-read
    path against a stub client; without this the offline guard fires first and
    the fetch path is never reached. The test that *wants* the guard overrides
    this back to False.
    """
    for name, sub in (("CACHE_DIR", ""), ("GRID_DIR", "grids"),
                      ("RESP_DIR", "responses")):
        monkeypatch.setattr(cache_mod, name, tmp_path / sub if sub else tmp_path)
    monkeypatch.setattr(cache_mod, "has_key", lambda: True)
    (tmp_path / "grids").mkdir(parents=True, exist_ok=True)
    (tmp_path / "responses").mkdir(parents=True, exist_ok=True)
    return tmp_path


# ------------------------------------------------------------- keying

def test_key_is_stable_across_calls():
    payload = {"a": 1, "b": [2, 3]}
    assert cache_key("/v1/heatmap", payload) == cache_key("/v1/heatmap", payload)


def test_key_ignores_dict_ordering():
    """Canonical JSON with sorted keys, or the same request caches twice."""
    assert (cache_key("/v1/heatmap", {"a": 1, "b": 2})
            == cache_key("/v1/heatmap", {"b": 2, "a": 1}))


def test_key_changes_with_the_request():
    base = {"threshold": 35.0, "direction": "above"}
    assert cache_key("/v1/heatmap", base) != cache_key(
        "/v1/heatmap", {**base, "threshold": 35.01})
    assert cache_key("/v1/heatmap", base) != cache_key(
        "/v1/heatmap", {**base, "direction": "below"})


def test_key_separates_endpoints():
    p = {"x": 1}
    assert cache_key("/v1/heatmap", p) != cache_key("/v1/env_params", p)


# ------------------------------------------------------- miss then hit

def test_first_call_misses_second_call_makes_no_network_request(isolated_cache,
                                                               monkeypatch):
    """The acceptance criterion for Phase 1, stated exactly."""
    stub = StubClient()
    fg = CachedFortyGuard(verbose=False)
    monkeypatch.setattr(fg, "_get_client", lambda: stub)

    kw = dict(polygon_aoi=AOI, start_date="2025-07-15", filter_type=3,
              granularity=100, analytic_type="exceedance", threshold=35.0,
              direction="above", label="test probe")

    first = fg.heatmap(**kw)
    assert stub.calls == 1
    assert fg.stats["misses"] == 1 and fg.stats["writes"] == 1

    second = fg.heatmap(**kw)
    assert stub.calls == 1, "a cached request must not reach the client"
    assert fg.stats["hits"] == 1

    assert second["result"]["map_data"] == first["result"]["map_data"]
    assert second["result"]["stats_data"] == first["result"]["stats_data"]


def test_a_different_threshold_is_a_different_entry(isolated_cache, monkeypatch):
    stub = StubClient()
    fg = CachedFortyGuard(verbose=False)
    monkeypatch.setattr(fg, "_get_client", lambda: stub)
    kw = dict(polygon_aoi=AOI, start_date="2025-07-15", filter_type=3,
              granularity=100, analytic_type="exceedance", direction="above")
    fg.heatmap(**kw, threshold=35.0, label="t35")
    fg.heatmap(**kw, threshold=40.0, label="t40")
    assert stub.calls == 2


def test_round_trip_preserves_tile_values_and_geometry(isolated_cache, monkeypatch):
    """The columnar split must be lossless, or every number downstream shifts."""
    stub = StubClient()
    fg = CachedFortyGuard(verbose=False)
    monkeypatch.setattr(fg, "_get_client", lambda: stub)
    kw = dict(polygon_aoi=AOI, start_date="2025-07-15", filter_type=3,
              granularity=100, analytic_type="exceedance", threshold=35.0,
              direction="above", label="lossless")
    fresh = fg.heatmap(**kw)["result"]
    rebuilt = fg.heatmap(**kw)["result"]
    for a, b in zip(fresh["map_data"]["features"], rebuilt["map_data"]["features"]):
        assert a["properties"] == b["properties"]
        assert a["geometry"]["coordinates"] == b["geometry"]["coordinates"]


# ------------------------------------------------------- offline guarantee

def test_offline_miss_raises_a_named_error(isolated_cache, monkeypatch):
    """With no key and no cached entry, fail with a clear message.

    Not a generic exception, and definitely not an empty result: a judge who
    requests an uncached window must be told that is what happened.
    """
    monkeypatch.delenv("FORTYGUARD_API_KEY", raising=False)
    monkeypatch.setattr(cache_mod, "has_key", lambda: False)
    fg = CachedFortyGuard(verbose=False)
    with pytest.raises(OfflineCacheMiss):
        fg.heatmap(polygon_aoi=AOI, start_date="1999-01-01", filter_type=3,
                   granularity=100, analytic_type="exceedance", threshold=35.0,
                   direction="above", label="never fetched")


# ------------------------------------------ the committed cache is intact

def test_committed_cache_is_populated():
    entries = iter_entries()
    assert len(entries) > 50, f"expected the committed cache, found {len(entries)}"


def test_every_committed_entry_has_a_grid_and_a_label():
    for e in iter_entries():
        assert e.get("grid_key"), f"{e.get('cache_key')} has no grid_key"
        assert e.get("label"), f"{e.get('cache_key')} has no human-readable label"


def test_replay_returns_the_measured_request():
    hm = replay("exceedance downtown-phx 2km 2025-07-15 ft3 t35")
    feats = hm["map_data"]["features"]
    assert len(feats) == 420
    assert hm["stats_data"]["analytic_type"] == "exceedance"


def test_replay_names_known_labels_when_it_fails():
    with pytest.raises(KeyError, match="Known labels"):
        replay("no such label")


def test_list_cache_and_manifest(tmp_path):
    rows = list_cache()
    assert rows and all("label" in r for r in rows)
    out = write_manifest(tmp_path / "MANIFEST.md")
    text = out.read_text(encoding="utf-8")
    assert "Cache manifest" in text
    assert "downtown-phx" in text
