"""Warm the cache for a study window, fetching calls concurrently.

Each heatmap request is submit-and-poll and takes ~2 minutes of mostly waiting,
so fetching them one at a time wastes most of the wall clock. This issues them
in parallel and lets the cache layer deduplicate.

Cache writes are atomic (temp file then replace) and keyed by request, so
concurrent writers cannot corrupt an entry. Two threads that happen to produce
the same tile grid write identical bytes to the same path, which is harmless.

    python prefetch.py --start 2025-08-02 --end 2025-08-08
"""

from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import study  # noqa: E402
from cache import CachedFortyGuard, has_key  # noqa: E402
from schema import load_clauses  # noqa: E402
from evaluate import METRIC_PRODUCT, evaluable  # noqa: E402


def daterange(start: str, end: str) -> list[str]:
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    return [(a + timedelta(days=i)).isoformat() for i in range((b - a).days + 1)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2025-08-02")
    ap.add_argument("--end", default="2025-08-08")
    ap.add_argument("--workers", type=int, default=5)
    args = ap.parse_args()

    if not has_key():
        print("FORTYGUARD_API_KEY is not set; nothing to prefetch.")
        return 1

    days = daterange(args.start, args.end)
    clauses = [c for c in load_clauses(study.GOLDEN_CLAUSES) if evaluable(c)]
    aoi = study.city_aoi()

    # Build the distinct set of requests the evaluator will make. Several
    # clauses share one tcm call per day, so deduplicate before fetching.
    jobs: dict[tuple, dict] = {}
    for c in clauses:
        product, _ = METRIC_PRODUCT[c.metric]
        for d in days:
            if product == "tcm":
                jobs[("tcm", d)] = dict(
                    polygon_aoi=aoi, start_date=d, filter_type=3,
                    granularity=study.GRANULARITY_M, analytic_type="tcm",
                    label=f"phx-city tcm {d}")
            else:
                thr = round(c.threshold_c, 4)
                jobs[("exc", d, thr)] = dict(
                    polygon_aoi=aoi, start_date=d, filter_type=3,
                    granularity=study.GRANULARITY_M, analytic_type="exceedance",
                    threshold=thr, direction=c.operator or "above",
                    label=f"phx-city exceedance {d} t{thr:.4f}")

    print(f"window {days[0]} .. {days[-1]}  ({len(days)} days)")
    print(f"{len(jobs)} distinct requests, {args.workers} at a time\n")

    fg = CachedFortyGuard(verbose=False)
    t0 = time.time()
    done = 0

    def fetch(kw):
        started = time.time()
        fg.heatmap(**kw)
        return kw["label"], time.time() - started

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(fetch, kw): kw["label"] for kw in jobs.values()}
        for fut in as_completed(futs):
            done += 1
            try:
                label, secs = fut.result()
                print(f"  [{done:>2}/{len(jobs)}] {label:<46s} {secs:6.0f}s")
            except Exception as exc:  # noqa: BLE001
                print(f"  [{done:>2}/{len(jobs)}] {futs[fut]:<46s} FAILED "
                      f"{type(exc).__name__}: {str(exc)[:90]}")

    print(f"\n  {fg.summary()}")
    print(f"  wall clock {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
