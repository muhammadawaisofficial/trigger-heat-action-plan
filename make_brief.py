"""Produce the ranked action brief.

    python make_brief.py               # deterministic ranking + verified prose
    python make_brief.py --no-llm      # ranking with templated prose only

Writes docs/action_brief.md and prints the top items. Every recommendation
carries its clause, page, verbatim sentence and named department, so a reader
can check any line against the published plan.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import study  # noqa: E402
from brief import narrate, rank  # noqa: E402
from schema import load_clauses  # noqa: E402

RESULTS = Path("data/results/divergence.json")
POP = Path("data/zones/phoenix_villages_population.json")
OUT = Path("docs/action_brief.md")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true",
                    help="skip narration, use deterministic sentences")
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()

    if not RESULTS.exists():
        print("Run `python run_analysis.py` first.")
        return 2

    res = json.loads(RESULTS.read_text(encoding="utf-8"))
    pop = (json.loads(POP.read_text(encoding="utf-8")).get("villages", {})
           if POP.exists() else {})
    clauses = {c.clause_id: c for c in load_clauses(study.GOLDEN_CLAUSES)}

    recs = rank(res, clauses, pop)
    if not recs:
        print("No silent zones in this window; nothing to brief.")
        return 0

    if not args.no_llm:
        print(f"narrating {len(recs)} recommendations...")
        recs = narrate(recs)
    else:
        for r in recs:
            r.narration = r.fallback()

    verified = sum(1 for r in recs if r.narration_verified)
    generated = sum(1 for r in recs
                    if r.narration_verified and r.narration != r.fallback())

    # ------------------------------------------------------------------ print
    print(f"\n{'#':>3} {'village':<22s} {'pop':>10s} {'clause':<24s} "
          f"{'silent':>7s} {'severity':>12s}")
    print("-" * 86)
    for r in recs[:args.top]:
        print(f"{r.rank:>3} {r.zone_name:<22s} "
              f"{(f'{r.population:,}' if r.population else '-'):>10s} "
              f"{r.clause_id:<24s} {len(r.silent_days):>7} {r.severity:>12,.0f}")

    print(f"\n  {len(recs)} recommendations, {generated} model-narrated and "
          f"number-verified, {len(recs)-generated} deterministic")
    unver = [r for r in recs if not r.narration_verified]
    if unver:
        print(f"  {len(unver)} narration(s) REJECTED for untraceable numbers:")
        for r in unver[:5]:
            print(f"    {r.zone_name} / {r.clause_id}: {r.unverified_numbers}")

    # ----------------------------------------------------------------- write
    L: list[str] = []
    A = L.append
    A("# Action brief — Phoenix heat response")
    A("")
    A(f"Ranked by exposed population-days of unmet condition, over "
      f"{res['summary']['window'][0]} to {res['summary']['window'][1]}.")
    A("")
    A("Each item states a measured condition, the clause of the "
      f"{study.PLAN_TITLE} that governs it, the page it appears on, and the "
      "department the plan names. **No sentence below contains a number that "
      "the pipeline did not compute** — generated prose is checked against the "
      "computed facts and replaced with deterministic text if any figure is "
      "untraceable.")
    A("")
    A("> The comparator throughout is a **citywide proxy** — the area-weighted "
      "mean over the whole city AOI, a stand-in for station-based sensing, not "
      "a real station feed.")
    A("")
    A("---")
    A("")
    for r in recs:
        A(f"## {r.rank}. {r.zone_name}"
          + (f" — {r.population:,} residents" if r.population else ""))
        A("")
        A(r.narration)
        A("")
        A("| | |")
        A("|---|---|")
        A(f"| **Clause** | `{r.clause_id}` |")
        A(f"| **Action** | {r.action} |")
        A(f"| **Responsible** | {', '.join(r.actor) or '—'} |")
        A(f"| **Threshold** | {r.threshold_f:g} °F |")
        A(f"| **Days condition met** | {r.days_met} |")
        A(f"| **Days citywide trigger fired** | {r.days_proxy_fired} |")
        A(f"| **Silent days** | {len(r.silent_days)} — {', '.join(r.silent_days)} |")
        if r.worst_day:
            A(f"| **Worst day** | {r.worst_day} at {r.worst_value_f:g} °F |")
        if r.lead_days is not None:
            A(f"| **Lead over citywide** | {r.lead_days} day(s) |")
        A(f"| **Source** | page {r.source_page} of the published plan |")
        A("")
        A(f"> *“{r.source_text}”*")
        A("")
        A(f"— {study.PLAN_TITLE}, page {r.source_page} "
          f"([open]({study.PLAN_URL}#page={r.source_page}))")
        A("")
        A("---")
        A("")

    A(f"*{len(recs)} recommendations. {generated} narrated by a language model "
      f"and number-verified against computed facts; the remainder are "
      f"deterministic. Ranking is entirely deterministic. Thermal data: "
      f"FortyGuard Temperature API.*")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"\n  written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
