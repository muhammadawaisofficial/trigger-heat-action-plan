"""Disk cache for every FortyGuard API response.

Three jobs:

1. Never pay credits twice for the same request.
2. Let a judge clone this repo with **no API key** and reproduce the headline
   number offline. That is a stated deliverable, so the client is constructed
   lazily -- importing this module, or calling it for anything already cached,
   never needs a key.
3. Stay small enough to commit.

On (3): a 473 sq mi heatmap at 100 m granularity is 122,542 tiles and 130 MB of
raw JSON, which no repository should carry. Measured on this data, tile
*geometry* is 87% of that payload -- and the tile grid is byte-identical across
every call that shares an AOI and granularity (verified: identical tile_id
sequence and identical geometry, across calls differing only in threshold).

So the cache is split:

    grids/<grid_key>.json.gz        geometry, written once per (AOI, granularity)
    responses/<req_key>.json.gz     columnar values + stats, one per request

Reassembly is transparent -- ``heatmap()`` returns exactly the shape the API
returned, so nothing downstream knows the difference.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

#: Network-layer failures that say nothing about whether the task succeeded.
#: A dropped or truncated body on a 130 MB response is a transport problem,
#: not a task failure -- re-poll rather than re-submit and pay again.
try:
    import requests.exceptions as _rex
    _TRANSPORT_ERRORS: tuple = (
        _rex.ChunkedEncodingError, _rex.ConnectionError,
        _rex.ReadTimeout, _rex.ContentDecodingError,
    )
except Exception:  # noqa: BLE001 - requests is a hard dep of the client
    _TRANSPORT_ERRORS = ()

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / "data" / "cache"
GRID_DIR = CACHE_DIR / "grids"
RESP_DIR = CACHE_DIR / "responses"


class OfflineCacheMiss(RuntimeError):
    """Cache miss with no API key available.

    Raised instead of a confusing auth error so the offline failure mode reads
    clearly: this exact request was never cached and cannot be fetched.
    """


def _canonical(payload: Any) -> str:
    """Stable JSON: sorted keys, no incidental whitespace.

    Float formatting matters -- 35.0 and 35 must hash identically, which
    json.dumps guarantees by emitting 35.0 for both.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha(text: str, n: int = 20) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:n]


def cache_key(endpoint: str, payload: dict) -> str:
    return _sha(f"{endpoint}|{_canonical(payload)}")


def has_key() -> bool:
    return bool(os.getenv("FORTYGUARD_API_KEY"))


def _read_gz(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, EOFError, json.JSONDecodeError):
        # A truncated write (interrupted run) must not poison the cache.
        return None


def _write_gz(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        json.dump(obj, fh, separators=(",", ":"))
    tmp.replace(path)  # atomic - a killed run leaves no half-written entry


# --------------------------------------------------------------- compaction


def _split_heatmap(result: dict) -> tuple[dict, dict]:
    """Split an API heatmap result into (grid, compact response).

    Values are stored columnar -- one array per property name -- which both
    compresses far better than per-tile objects and keeps tcm (three
    temperature fields) and the analysis types (a single ``value``) on one code
    path.
    """
    feats = (result or {}).get("map_data", {}).get("features", []) or []

    geometries = [f.get("geometry") for f in feats]
    tile_ids = [f.get("properties", {}).get("tile_id") for f in feats]
    grid = {"tile_ids": tile_ids, "geometries": geometries}

    columns: dict[str, list] = {}
    for f in feats:
        for k, v in (f.get("properties") or {}).items():
            if k == "tile_id":
                continue
            columns.setdefault(k, []).append(v)

    compact = {
        "n_tiles": len(feats),
        "columns": columns,
        "stats_data": (result or {}).get("stats_data"),
        "map_data_type": (result or {}).get("map_data", {}).get("type", "FeatureCollection"),
    }
    return grid, compact


def _rebuild_heatmap(grid: dict, compact: dict) -> dict:
    """Inverse of _split_heatmap -- returns the original API result shape."""
    tile_ids = grid["tile_ids"]
    geometries = grid["geometries"]
    columns = compact.get("columns", {})

    features = []
    for i, (tid, geom) in enumerate(zip(tile_ids, geometries)):
        props = {"tile_id": tid}
        for k, col in columns.items():
            if i < len(col):
                props[k] = col[i]
        features.append({"type": "Feature", "properties": props, "geometry": geom})

    return {
        "map_data": {"type": compact.get("map_data_type", "FeatureCollection"),
                     "features": features},
        "stats_data": compact.get("stats_data"),
    }


class CachedFortyGuard:
    """Wraps the official client. Reads disk first, calls the API only on a miss."""

    def __init__(self, verbose: bool = True) -> None:
        self._client = None
        self.verbose = verbose
        self.stats = {"hits": 0, "misses": 0, "writes": 0, "grids_written": 0}

    # The client is only built when we actually have to hit the network, so
    # offline runs never touch the auth path.
    def _get_client(self):
        if self._client is None:
            from fortyguard.client import FortyGuardClient

            self._client = FortyGuardClient()
        return self._client

    def _wait_resilient(self, client, activity_id: str, label: str = "",
                        timeout: float = 2400.0, poll: float = 5.0) -> dict:
        """Poll an activity to completion, surviving a flaky status endpoint.

        The status endpoint 404s briefly right after submit (documented eventual
        consistency) and, under concurrency, returns 502/503/504 gateway errors.
        Neither means the task failed -- the work continues server-side. The
        official client raises on the 5xx family, so polling is handled here
        rather than by patching the vendored client.

        Only an explicit terminal ``failed``/``error`` status, or the deadline,
        ends this loop unsuccessfully.
        """
        from fortyguard.exceptions import (
            ActivityNotReadyError, FortyGuardError, TaskFailedError, TaskTimeoutError,
        )

        transient_markers = ("500", "502", "503", "504", "timeout", "Timeout",
                             "Gateway", "temporarily")
        deadline = time.monotonic() + timeout
        transient = 0

        while True:
            if time.monotonic() >= deadline:
                raise TaskTimeoutError(
                    f"Activity {activity_id} did not complete within {timeout:.0f}s "
                    f"({transient} transient status errors along the way)")
            try:
                data = client.get_status(activity_id)
            except ActivityNotReadyError:
                time.sleep(poll)
                continue
            except _TRANSPORT_ERRORS as exc:
                # A truncated or dropped body on a 130 MB response says nothing
                # about the task, which has already completed server-side.
                transient += 1
                if self.verbose and transient in (1, 5, 20):
                    print(f"  [poll] {label}: transport error "
                          f"({type(exc).__name__}) #{transient}, retrying")
                time.sleep(min(poll * 1.5 ** min(transient, 6), 30.0))
                continue
            except FortyGuardError as exc:
                msg = str(exc)
                if any(m in msg for m in transient_markers):
                    transient += 1
                    if self.verbose and transient in (1, 5, 20):
                        print(f"  [poll] {label}: transient status error "
                              f"#{transient}, still waiting")
                    # Back off gently; the task is still running server-side.
                    time.sleep(min(poll * 1.5 ** min(transient, 6), 30.0))
                    continue
                raise

            status = str(data.get("status", "")).lower()
            if status in ("completed", "succeeded"):
                return data.get("result", data)
            if status in ("failed", "error"):
                raise TaskFailedError(
                    f"Activity {activity_id} failed: {data.get('message') or data}")
            time.sleep(poll)

    def _miss_guard(self, label: str, key: str, path: Path) -> None:
        if not has_key():
            # Relative for readability, absolute if the cache has been pointed
            # outside the repo (tests do this). relative_to raises rather than
            # falling back, which would replace this helpful error with an
            # opaque pathlib ValueError.
            try:
                shown = path.relative_to(REPO_ROOT)
            except ValueError:
                shown = path
            raise OfflineCacheMiss(
                f"No cached response for {label} ({key}) and "
                f"FORTYGUARD_API_KEY is not set.\n"
                f"  Expected: {shown}\n"
                f"  This repo ships the cache for the published analysis; a miss "
                f"means this request differs from any committed run."
            )

    # ---------------------------------------------------------------- heatmap

    def heatmap(
        self,
        polygon_aoi: dict,
        start_date: str,
        filter_type: int,
        granularity: int = 100,
        end_date: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        analytic_type: str = "tcm",
        threshold: float | None = None,
        direction: str | None = None,
        label: str = "",
    ) -> dict:
        """POST /v1/heatmap, cached. Returns ``{"result": {...}}``.

        ``persistence`` is deliberately not special-cased here, but note it is
        only trustworthy at ``filter_type=3`` -- see docs/api_findings.md.
        """
        payload = {
            "polygon_aoi": polygon_aoi,
            "date_time": {
                k: v
                for k, v in {
                    "start_date": start_date,
                    "filter_type": filter_type,
                    "end_date": end_date,
                    "start_time": start_time,
                    "end_time": end_time,
                }.items()
                if v is not None
            },
            "granularity": granularity,
            "analytic_type": analytic_type,
        }
        if threshold is not None:
            payload["threshold"] = threshold
        if direction is not None:
            payload["direction"] = direction

        key = cache_key("/v1/heatmap", payload)
        rpath = RESP_DIR / f"{key}.json.gz"
        entry = _read_gz(rpath)

        if entry is not None:
            grid = _read_gz(GRID_DIR / f"{entry['grid_key']}.json.gz")
            if grid is not None:
                self.stats["hits"] += 1
                if self.verbose:
                    print(f"  [cache HIT ] {label or 'heatmap'} ({key})")
                return {"activity_id": entry.get("activity_id"),
                        "result": _rebuild_heatmap(grid, entry["compact"])}
            # Grid missing: the entry is unusable, fall through and refetch.
            if self.verbose:
                print(f"  [cache] orphaned entry (missing grid): {key}")

        self.stats["misses"] += 1
        self._miss_guard(label or "heatmap", key, rpath)

        if self.verbose:
            print(f"  [cache MISS] {label or 'heatmap'} ({key}) -> calling API")

        client = self._get_client()
        # Submit and poll separately so a flaky status read cannot cost us the
        # task. Re-polling an activity is free; re-submitting would spend
        # credits again on work the server has already done.
        activity_id = client.create_heatmap(
            polygon_aoi=polygon_aoi,
            start_date=start_date,
            filter_type=filter_type,
            granularity=granularity,
            end_date=end_date,
            start_time=start_time,
            end_time=end_time,
            analytic_type=analytic_type,
            threshold=threshold,
            direction=direction,
            wait=False,
        )
        result = self._wait_resilient(client, activity_id, label=label or "heatmap")
        resp = {"activity_id": activity_id, "result": result}
        grid, compact = _split_heatmap(result)

        grid_key = _sha(_canonical(grid))
        gpath = GRID_DIR / f"{grid_key}.json.gz"
        if not gpath.exists():
            _write_gz(gpath, grid)
            self.stats["grids_written"] += 1

        _write_gz(rpath, {
            "label": label,
            "endpoint": "/v1/heatmap",
            "cache_key": key,
            "grid_key": grid_key,
            "request": payload,
            "activity_id": resp.get("activity_id"),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "compact": compact,
        })
        self.stats["writes"] += 1
        return {"activity_id": resp.get("activity_id"), "result": result}

    # ------------------------------------------------------------- env_params

    def env_params(
        self,
        latitude: float,
        longitude: float,
        temperature: float,
        start_date: str,
        filter_type: int = 3,
        start_time: str | None = None,
        end_time: str | None = None,
        analysis: list[str] | None = None,
        label: str = "",
    ) -> dict:
        """POST /v1/env_params, cached.

        ``filter_type`` accepts only 1, 2 or 3 here -- this endpoint has no
        range-of-days mode, unlike the heatmap endpoint. On the Hackathon plan
        ``analysis`` is capped at 3 parameters per request.
        """
        payload = {
            "latitude": latitude,
            "longitude": longitude,
            "temperature": temperature,
            "date_time": {
                k: v
                for k, v in {
                    "start_date": start_date,
                    "filter_type": filter_type,
                    "start_time": start_time,
                    "end_time": end_time,
                }.items()
                if v is not None
            },
        }
        if analysis:
            payload["analysis"] = list(analysis)

        return self._simple("/v1/env_params", payload, label, lambda: (
            self._get_client().environmental_parameters(
                latitude=latitude, longitude=longitude, temperature=temperature,
                start_date=start_date, filter_type=filter_type,
                start_time=start_time, end_time=end_time, analysis=analysis,
                verbose=self.verbose, timeout=900.0,
            )
        ))

    def _simple(self, endpoint: str, payload: dict, label: str,
                fetch: Callable[[], Any]) -> Any:
        """Cache path for small responses that need no tile compaction."""
        key = cache_key(endpoint, payload)
        slug = endpoint.strip("/").replace("/", "_")
        path = RESP_DIR / slug / f"{key}.json.gz"

        entry = _read_gz(path)
        if entry is not None:
            self.stats["hits"] += 1
            if self.verbose:
                print(f"  [cache HIT ] {label or endpoint} ({key})")
            return entry["response"]

        self.stats["misses"] += 1
        self._miss_guard(label or endpoint, key, path)
        if self.verbose:
            print(f"  [cache MISS] {label or endpoint} ({key}) -> calling API")

        response = fetch()
        _write_gz(path, {
            "label": label, "endpoint": endpoint, "cache_key": key,
            "request": payload,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "response": response,
        })
        self.stats["writes"] += 1
        return response

    def api_usage(self) -> dict:
        """Credit and plan summary. Cached so repeated runs stay offline."""
        return self._simple(
            "/v1/system/fetch-api-key-usage", {}, "api key usage",
            lambda: self._get_client().fetch_api_key_usage(),
        )

    def summary(self) -> str:
        s = self.stats
        return (f"cache: {s['hits']} hit(s), {s['misses']} miss(es), "
                f"{s['writes']} written, {s['grids_written']} grid(s)")


def iter_entries() -> list[dict]:
    """Metadata for every cached heatmap response (no tile payload rebuilt)."""
    out = []
    for p in sorted(RESP_DIR.glob("*.json.gz")):
        e = _read_gz(p)
        if e:
            out.append({k: v for k, v in e.items() if k != "compact"} |
                       {"n_tiles": (e.get("compact") or {}).get("n_tiles")})
    return out


def replay(label: str) -> dict:
    """Rebuild a cached heatmap result by its label.

    Verification scripts use this instead of reconstructing the AOI, so they
    reproduce exactly the request that was measured and cannot drift from it
    when a geometry helper changes.
    """
    for p in sorted(RESP_DIR.glob("*.json.gz")):
        e = _read_gz(p)
        if e and e.get("label") == label:
            grid = _read_gz(GRID_DIR / f"{e['grid_key']}.json.gz")
            if grid is None:
                raise KeyError(f"Cached entry {label!r} is missing its grid.")
            return _rebuild_heatmap(grid, e["compact"])
    known = sorted({(_read_gz(p) or {}).get("label", "") for p in RESP_DIR.glob("*.json.gz")})
    raise KeyError(f"No cached entry labelled {label!r}. Known labels:\n  " +
                   "\n  ".join(k for k in known if k))


def list_cache() -> list[dict]:
    """Every cached request, in human-readable form, newest first.

    One row per stored response: what it represents, what was asked for, and
    how big the answer was. This is the index a reader needs to audit an
    offline run -- without it, ``data/cache/`` is a directory of hashes.
    """
    rows = []
    for e in iter_entries():
        req = e.get("request") or {}
        dt = req.get("date_time") or {}
        window = dt.get("start_date", "")
        if dt.get("end_date"):
            window += f"..{dt['end_date']}"
        rows.append({
            "label": e.get("label", ""),
            "endpoint": e.get("endpoint", ""),
            "analytic_type": req.get("analytic_type", ""),
            "window": window,
            "filter_type": dt.get("filter_type"),
            "threshold_c": req.get("threshold"),
            "direction": req.get("direction"),
            "granularity_m": req.get("granularity"),
            "n_tiles": e.get("n_tiles"),
            "fetched_at": e.get("fetched_at", ""),
            "cache_key": e.get("cache_key", ""),
        })
    return sorted(rows, key=lambda r: r["fetched_at"], reverse=True)


def write_manifest(path: str | Path | None = None) -> Path:
    """Write ``data/cache/MANIFEST.md``: what every cached response represents.

    Committed alongside the cache so a judge can see exactly which requests the
    offline result was derived from, without running anything.
    """
    rows = list_cache()
    out = Path(path) if path else CACHE_DIR / "MANIFEST.md"
    rep = cache_report()

    lines = [
        "# Cache manifest",
        "",
        "Auto-generated by `src.cache.write_manifest()`. Every API response this",
        "project has ever received is stored here, so the full analysis reproduces",
        "with no API key and no network access.",
        "",
        f"- **{rep['responses']} responses**, {rep['response_bytes'] / 1e6:.1f} MB",
        f"- **{rep['grids']} tile grids**, {rep['grid_bytes'] / 1e6:.1f} MB "
        f"(shared: a grid is byte-identical across every call on the same AOI "
        f"and granularity, so it is stored once)",
        f"- **{rep['total_bytes'] / 1e6:.1f} MB total**",
        "",
        "| Request | Analytic | Window | ft | Threshold °C | Dir | Gran | Tiles | Fetched |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        thr = f"{r['threshold_c']:g}" if r["threshold_c"] is not None else "—"
        lines.append(
            f"| {r['label'] or r['endpoint']} | {r['analytic_type'] or '—'} | "
            f"{r['window'] or '—'} | {r['filter_type'] or '—'} | {thr} | "
            f"{r['direction'] or '—'} | {r['granularity_m'] or '—'} | "
            f"{r['n_tiles'] or '—'} | {(r['fetched_at'] or '')[:10]} |")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def cache_report() -> dict:
    """Sizes and counts, for the README and the offline manifest."""
    def _du(d: Path) -> int:
        return sum(p.stat().st_size for p in d.rglob("*") if p.is_file()) if d.exists() else 0

    return {
        "grids": len(list(GRID_DIR.glob("*.json.gz"))) if GRID_DIR.exists() else 0,
        "responses": len(list(RESP_DIR.rglob("*.json.gz"))) if RESP_DIR.exists() else 0,
        "grid_bytes": _du(GRID_DIR),
        "response_bytes": _du(RESP_DIR),
        "total_bytes": _du(CACHE_DIR),
    }
