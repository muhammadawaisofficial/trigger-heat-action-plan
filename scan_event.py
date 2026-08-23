"""Select the study heat event by measurement, not assumption.

Scans day by day over a small downtown AOI (420 tiles, cheap to store; every
call costs the same flat 4,220 credits regardless of area) and reports hours
above 105 degF -- the threshold Action 1.1 of the plan actually names.

105 degF is used rather than the 110 degF season benchmark because FortyGuard's
2 m model tops out near 107.6 degF over downtown Phoenix, so a 110 degF scan
returns zero for every day of the summer and cannot discriminate between them.
That gap between the model and the Sky Harbor station is itself recorded in
docs/api_findings.md.

    python scan_event.py --start 2025-07-01 --end 2025-08-15
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from cache import CachedFortyGuard  # noqa: E402
from geo import square_aoi  # noqa: E402
from parse import parse_heatmap  # noqa: E402
from schema import f_to_c  # noqa: E402

PHX_LAT, PHX_LON = 33.4484, -112.0740
SCAN_AOI = square_aoi(PHX_LAT, PHX_LON, 2.0)

# The threshold named in Action 1.1 of the plan (page 12).
ACTION_1_1_F = 105.0
ACTION_1_1_C = f_to_c(ACTION_1_1_F)


def daterange(start: str, end: str) -> list[str]:
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    return [(a + timedelta(days=i)).isoformat() for i in range((b - a).days + 1)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2025-07-01")
    ap.add_argument("--end", default="2025-08-15")
    ap.add_argument("--window", type=int, default=7, help="consecutive days to select")
    args = ap.parse_args()

    fg = CachedFortyGuard(verbose=False)
    days = daterange(args.start, args.end)

    print(f"Hours above {ACTION_1_1_F:.0f} degF ({ACTION_1_1_C:.2f} degC) per day, "
          f"downtown 2 km AOI")
    print(f"Threshold source: Action 1.1, page 12 of the plan\n")
    print(f"  {'date':<12} {'hours':>6}  profile")
    print("  " + "-" * 56)

    daily: dict[str, float] = {}
    for d in days:
        try:
            hm = parse_heatmap(fg.heatmap(
                polygon_aoi=SCAN_AOI, start_date=d, filter_type=3, granularity=100,
                analytic_type="exceedance", threshold=round(ACTION_1_1_C, 4),
                direction="above",
                label=f"scan day {d} exceedance t{ACTION_1_1_C:.4f}",
            )["result"], "exceedance")
            v = hm.value_spread()["p50"]
        except Exception as exc:  # noqa: BLE001
            print(f"  {d}  FAILED  {type(exc).__name__}: {str(exc)[:60]}")
            continue
        daily[d] = v
        print(f"  {d} {v:>6.1f}  {'#' * int(round(v))}")

    if not daily:
        print("\nNo days scanned successfully.")
        return 1

    keys = sorted(daily)
    w = args.window
    best, best_sum = None, -1.0
    for i in range(len(keys) - w + 1):
        win = keys[i:i + w]
        if date.fromisoformat(win[-1]) - date.fromisoformat(win[0]) != timedelta(days=w - 1):
            continue
        tot = sum(daily[k] for k in win)
        if tot > best_sum:
            best, best_sum = win, tot

    print("\n  " + "=" * 56)
    print(f"  scanned            {len(daily)} days")
    print(f"  days with any hour above {ACTION_1_1_F:.0f} degF: "
          f"{sum(1 for v in daily.values() if v > 0)}")
    hottest = max(daily.items(), key=lambda kv: kv[1])
    print(f"  single hottest day {hottest[0]} at {hottest[1]:.1f} h")
    if best:
        print(f"\n  MOST SEVERE {w}-DAY WINDOW: {best[0]} .. {best[-1]}")
        print(f"    total hours above {ACTION_1_1_F:.0f} degF: {best_sum:.1f}")
        print(f"    daily: {', '.join(f'{daily[k]:.1f}' for k in best)}")
    print(f"\n  {fg.summary()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
