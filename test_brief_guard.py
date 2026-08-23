"""Prove the narration guard rejects numbers the pipeline did not compute.

A claim that generated prose "cannot state an uncomputed number" is worth
nothing unless the rejection path is demonstrated. This runs the guard against
sentences that are deliberately wrong and asserts that each is caught.

    python test_brief_guard.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from brief import verify_narration  # noqa: E402

FACTS = {
    "zone": "Maryvale",
    "population": 226766,
    "threshold_degF": 90.0,
    "days_condition_met_in_window": 4,
    "days_citywide_trigger_fired": 2,
    "days_met_while_citywide_silent": 2,
    "silent_days": ["2025-08-02", "2025-08-08"],
    "worst_day": "2025-08-08",
    "zone_value_on_worst_day_degF": 93.9,
    "lead_days_over_citywide": 4,
}

CASES: list[tuple[str, bool, str]] = [
    ("Maryvale reached 93.9 degF on 2025-08-08 while the citywide trigger "
     "fired on 2 days.", True, "every figure is a supplied fact"),
    ("Maryvale met the 90 degF condition on 4 days; 226,766 residents live "
     "there.", True, "threshold, day count and population all supplied"),
    ("Maryvale reached 97.4 degF, affecting 226,766 residents.",
     False, "97.4 was never computed"),
    ("An estimated 340,000 residents were affected across 6 days.",
     False, "population and day count both invented"),
    ("Heat killed 12 people in Maryvale.",
     False, "casualty figure is not a computed fact"),
    ("The overnight low exceeded the threshold by 3.9 degF.",
     False, "a derived margin we did not hand the model"),
]


def main() -> int:
    print("Narration guard: every number in generated prose must trace to a "
          "computed fact\n")
    failures = 0

    for text, expect_ok, why in CASES:
        ok, bad = verify_narration(text, FACTS)
        passed = ok == expect_ok
        failures += not passed
        verdict = "ACCEPT" if ok else "REJECT"
        want = "ACCEPT" if expect_ok else "REJECT"
        print(f"  [{'PASS' if passed else 'FAIL'}] expected {want}, got {verdict}"
              f"   ({why})")
        print(f"         \"{text}\"")
        if bad:
            print(f"         untraceable: {bad}")
        print()

    print("=" * 72)
    if failures:
        print(f"{failures} case(s) behaved unexpectedly.")
        return 1

    print("All cases behaved as expected.")
    print()
    print("Honest limit of this guard: it verifies NUMBERS, not claims. A purely")
    print("qualitative fabrication carrying no digits would pass it. That risk is")
    print("handled separately -- the model is given only computed facts and no")
    print("temperature data, and the ranking it narrates is produced entirely in")
    print("deterministic code. The guard closes the failure mode that actually")
    print("matters for a briefing document: a plausible wrong figure.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
