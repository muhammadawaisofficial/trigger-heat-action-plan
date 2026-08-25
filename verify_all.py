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
    ("-m pytest tests/ -q", "unit + UI tests (cache, units, parsers, rendered app)"),
    ("build_golden.py", "every clause quote appears verbatim on its cited page"),
    ("verify_api.py", "measured FortyGuard API behaviour"),
    ("verify_years.py", "the same probe across three Julys (2025/2024/2023)"),
    ("sweep_threshold.py", "citywide threshold sweep: the actionable band"),
    ("test_aggregate.py", "tile-to-zone aggregation vs brute force"),
    ("test_claim.py", "the plan's own 10 degF spatial claim"),
    ("test_brief_guard.py", "generated prose cannot state an uncomputed number"),
    ("eval_compiler.py", "compiler precision / recall / F1"),
    ("run_analysis.py", "THE HEADLINE NUMBER"),
    ("make_report.py", "regenerate the standalone research report"),
    ("make_brief.py --no-llm", "regenerate the ranked action brief"),
]

#: The published result. Any drift here is a failure, not a curiosity.
#: Two halves of one finding: a fixed trigger under-fires where the citywide
#: mean sits below it, and over-fires where severity clears it everywhere.
EXPECTED = {
    # A. under-trigger -- coverage failure
    "silent_zones": 10,
    "silent_zone_days": 20,
    "median_lead_days": 4,
    "population_exposed": 1184971,
    # B. over-trigger -- targeting failure
    "clause_days": 35,
    "actionable_clause_days": 8,
    "over_triggered_clause_days": 11,
    "under_triggered_clause_days": 16,
}

#: The live-2026 replication, asserted only if its results file is present.
#: Checked because the value of a replication is that it stays reproducible.
EXPECTED_REPLICATION = {
    "file": "divergence_2026-08-16_2026-08-22.json",
    "silent_zones": 9,
    "silent_zone_days": 18,
    "population_exposed": 958205,
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
        n, act = s.get("clause_days"), s.get("actionable_clause_days")
        print("\n  THE PAIRED HEADLINE")
        print("  One flaw, two failure modes, severity-dependent. A trigger keyed")
        print("  to a single fixed number under-fires where the citywide mean sits")
        print("  below it and over-fires where severity clears it everywhere at")
        print("  once. Saturation is the mechanism; lost coverage is the consequence.")
        if pe and pt:
            print(f"\n  A. UNDER-TRIGGER (coverage). {pe:,} of {pt:,} people "
                  f"({pe/pt:.0%} of")
            print(f"     Phoenix) live in villages that met the City's own")
            print(f"     overnight-heat benchmark on days the citywide reading")
            print(f"     never fired.")
        if n and act is not None:
            print(f"\n  B. OVER-TRIGGER (targeting). On {n - act} of {n} clause-days "
                  f"({(n-act)/n:.0%}) the")
            print(f"     plan gave no basis for choosing where to send anyone: it")
            print(f"     fired either almost everywhere or almost nowhere.")

    # ------------------------------------------ the retraction is reproducible
    # sweep_dwell.py exits non-zero on purpose: it is the retracted dwell
    # derivation plus the validation harness that killed it. A judge should be
    # able to reproduce the FAILURE, so we assert the failure rather than
    # hiding the script. If it ever starts passing, that is news -- either the
    # API changed or our harness broke, and both need a human.
    print("\n  RETRACTED FINDING (must still fail):")
    ok_dwell, secs, _ = run("sweep_dwell.py", env)
    dg = REPO / "data" / "results" / "dwell_grid.json"
    if ok_dwell:
        drift.append("sweep_dwell.py PASSED validation; the retraction in "
                     "api_findings.md section 8 may no longer hold")
        print("  DRIFT sweep_dwell.py now passes -- re-examine the retraction")
    else:
        print(f"  OK   sweep_dwell.py fails validation as documented ({secs:.0f}s)")
    if dg.exists():
        d = json.loads(dg.read_text(encoding="utf-8"))
        bad = [v for v in d.get("validation", [])
               if v.get("negatives") or v.get("over_24h")
               or v.get("tiles_where_run_exceeds_total")]
        print(f"  OK   {len(bad)} of {len(d.get('validation', []))} thresholds "
              f"return impossible persistence values")

    # --------------------------------------------- assert the recovery result
    # What survives after the dwell retraction: a percentile threshold, on the
    # three clauses backed by tcm temperatures. Asserted because it is the only
    # constructive result the project still makes, so a regression here would
    # quietly reduce the submission to a pure deficit finding.
    if res_path.exists():
        res = json.loads(res_path.read_text(encoding="utf-8"))
        recs = res.get("recovery") or []
        usable = [r for r in recs if r.get("percentile")]
        print("\n  C. RECOVERY. Same data, a different rule:")
        if not recs:
            drift.append("no recovery results were produced")
            print("  DRIFT no recovery results")
        elif not usable:
            drift.append("no percentile recovery survived; the project would "
                         "have no constructive result left")
            print("  DRIFT no percentile recovery survived")
        for r in recs:
            if r.get("recovery_available") is False:
                print(f"  OK   {r.get('clause_id','?'):<24s} no measurable "
                      f"recovery design (dwell retracted)")
                continue
            fixed = r.get("fixed", {})
            best = r.get("percentile") or {}
            print(f"  OK   {fixed.get('clause_id','?'):<24s} "
                  f"{fixed.get('targeting_bits', 0):.3f} -> "
                  f"{best.get('targeting_bits', 0):.3f} bits "
                  f"via {best.get('design','?')}, "
                  f"{r.get('zones_recovered', 0)} zones recovered")

    # ------------------------------------------ assert the replication window
    rep_path = REPO / "data" / "results" / EXPECTED_REPLICATION["file"]
    if rep_path.exists():
        print("\n  Replication on live 2026 data:")
        rs = json.loads(rep_path.read_text(encoding="utf-8"))["summary"]
        for k in ("silent_zones", "silent_zone_days", "population_exposed"):
            want, got = EXPECTED_REPLICATION[k], rs.get(k)
            mark = "OK  " if got == want else "DRIFT"
            print(f"  {mark} {k:<22s} expected {want:>10,}  got "
                  f"{got if got is not None else 'missing':>10}")
            if got != want:
                drift.append(f"replication {k}: expected {want}, got {got}")
        print("\n  The same structure appears a year later on data the pipeline")
        print("  had never seen, which is what makes the finding a property of")
        print("  the city rather than of one week.")
    else:
        print("\n  (replication window not present in this checkout - skipped)")

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
