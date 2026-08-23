"""Run every check in the project and report pass/fail.

One command to confirm the whole thing works, offline, with no API key:

    python verify_all.py

This is what a judge should run first. It executes each script in turn, checks
the exit status, and asserts that the headline figures are the ones we publish
-- so a silent change in any upstream stage shows up here as a failure rather
than as a quietly different number.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent

#: Keys are removed from the environment so this proves the offline path.
STRIP = ("FORTYGUARD_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
         "CENSUS_API_KEY", "ANTHROPIC_API_KEY")

CHECKS = [
    ("build_golden.py", "every clause quote appears verbatim on its cited page"),
    ("verify_api.py", "measured FortyGuard API behaviour"),
    ("test_aggregate.py", "tile-to-zone aggregation vs brute force"),
    ("test_claim.py", "the plan's own 10 degF spatial claim"),
    ("test_brief_guard.py", "generated prose cannot state an uncomputed number"),
    ("eval_compiler.py", "compiler precision / recall / F1"),
    ("run_analysis.py", "THE HEADLINE NUMBER"),
    ("make_report.py", "regenerate the standalone research report"),
    ("make_brief.py --no-llm", "regenerate the ranked action brief"),
]

#: The published result. Any drift here is a failure, not a curiosity.
EXPECTED = {
    "silent_zones": 10,
    "silent_zone_days": 20,
    "median_lead_days": 4,
    "population_exposed": 1184971,
}


def run(cmd: str, env: dict) -> tuple[bool, float, str]:
    t0 = time.time()
    proc = subprocess.run([sys.executable, *cmd.split()], cwd=REPO, env=env,
                          capture_output=True, text=True, timeout=2400)
    return proc.returncode == 0, time.time() - t0, (proc.stdout + proc.stderr)


def main() -> int:
    env = {k: v for k, v in os.environ.items() if k not in STRIP}
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    print("=" * 74)
    print("TRIGGER — full verification")
    print("=" * 74)
    print("  Running with every API key removed from the environment, so this")
    print("  exercises the offline path a judge will use.\n")

    failures: list[tuple[str, str]] = []
    for cmd, what in CHECKS:
        print(f"  {cmd:<26s} {what}")
        ok, secs, out = run(cmd, env)
        if ok:
            print(f"  {'':<26s} PASS ({secs:.0f}s)\n")
        else:
            print(f"  {'':<26s} FAIL ({secs:.0f}s)\n")
            failures.append((cmd, out[-1500:]))

    # ------------------------------------------------- assert the headline
    print("=" * 74)
    print("HEADLINE INTEGRITY")
    print("=" * 74)
    res_path = REPO / "data" / "results" / "divergence.json"
    drift: list[str] = []
    if not res_path.exists():
        drift.append("data/results/divergence.json was not produced")
    else:
        s = json.loads(res_path.read_text(encoding="utf-8"))["summary"]
        for k, want in EXPECTED.items():
            got = s.get(k)
            mark = "OK  " if got == want else "DRIFT"
            print(f"  {mark} {k:<22s} expected {want:>10,}  got "
                  f"{got if got is not None else 'missing':>10}")
            if got != want:
                drift.append(f"{k}: expected {want}, got {got}")

        pe, pt = s.get("population_exposed"), s.get("population_total")
        if pe and pt:
            print(f"\n  {pe:,} of {pt:,} people ({pe/pt:.0%} of Phoenix) live in "
                  f"villages that met")
            print(f"  the City's own overnight-heat benchmark on days the citywide "
                  f"reading never fired.")

    print("\n" + "=" * 74)
    if failures or drift:
        print("RESULT: FAILED")
        print("=" * 74)
        for cmd, out in failures:
            print(f"\n--- {cmd} ---")
            print(out)
        for d in drift:
            print(f"  headline drift: {d}")
        return 1

    print("RESULT: ALL CHECKS PASSED")
    print("=" * 74)
    print("  Every figure reproduced offline with no API key.")
    print("  Next: `streamlit run app.py` for the interface.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
