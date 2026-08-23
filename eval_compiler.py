"""Score the automatic clause compiler against the hand-built golden set.

Reports precision and recall for clause detection, plus per-field accuracy on
the fields that change what the evaluator actually does: the kind
classification, the threshold, the metric, and the page anchor.

Two honesty measures are built in.

First, matching is done on the action the clause is about, not on the clause_id
string, so the compiler is not penalised for naming a clause differently. Where
one action carries two thresholds (the cooling ordinance does), the pair is
resolved by threshold.

Second, disagreements are adjudicated rather than simply counted. Several of
them are cases where the compiler's reading of the document is as defensible as
ours, or better. Reporting those as flat errors would understate the compiler
and, worse, would hide that our own reference set makes editorial choices.

    python eval_compiler.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import study  # noqa: E402
from compile import compile_plan  # noqa: E402
from llm import LLMUnavailable  # noqa: E402
from schema import Clause, load_clauses  # noqa: E402

#: Disagreements where the document genuinely supports both readings. Recorded
#: explicitly so the score can be reported both ways instead of quietly
#: crediting ourselves with being right.
ADJUDICATED = {
    ("operator", "PHX-2026-A3.1-EVAP"): (
        "The ordinance says units must 'cool all livable rooms TO 86 degF'. We "
        "encoded the violation direction (above); the compiler encoded the "
        "requirement direction (below). Both describe the same rule."),
    ("operator", "PHX-2026-A3.1-AC"): (
        "As above, for the 82 degF air-conditioning threshold."),
    ("scope", "PHX-2026-A2.1"): (
        "Cooling centres are specific facilities. We recorded the plan's stated "
        "TARGET POPULATION (citywide); the compiler recorded the physical scope "
        "(site). Defensible either way."),
    ("scope", "PHX-2026-A2.2"): ("As above."),
    ("scope", "PHX-2026-A2.3"): ("As above."),
    ("scope", "PHX-2026-A2.4"): ("As above."),
    ("scope", "PHX-2026-A2.5"): ("As above."),
    ("scope", "PHX-2026-A2.6"): ("As above."),
    ("actor", "PHX-2026-BENCH-HIGH110"): (
        "A season-severity statistic has no department attached in the "
        "document. We assigned OHRM as plan owner; the compiler left it empty, "
        "which is the more literal reading."),
    ("threshold_source", "PHX-2026-A4.2"): (
        "The plan states NO temperature for the Extreme Heat Warning trigger. "
        "The compiler correctly emitted none. Our golden set adds a documented "
        "110 degF proxy so the clause can be evaluated at all. The compiler is "
        "the more faithful reading of the document here."),
}


def is_bench(c: Clause) -> bool:
    return c.action_id is None


def match(gold: list[Clause], pred: list[Clause]) -> tuple[list, list, list]:
    """Pair predictions to references by what the clause is about.

    Returns (pairs, unmatched_gold, unmatched_pred).
    """
    gleft, pleft = list(gold), list(pred)
    pairs: list[tuple[Clause, Clause]] = []

    def take(gsel, psel):
        """Pair up two candidate pools, resolving ties by threshold."""
        for g in list(gsel):
            if g not in gleft:
                continue
            cands = [p for p in psel if p in pleft]
            if not cands:
                continue
            # Prefer the candidate with the same threshold; otherwise the only
            # one available.
            same = [p for p in cands if p.threshold_source == g.threshold_source]
            pick = same[0] if same else cands[0]
            pairs.append((g, pick))
            gleft.remove(g)
            pleft.remove(pick)

    # Actions: group by action_id.
    action_ids = {c.action_id for c in gold if c.action_id}
    for aid in sorted(action_ids):
        take([g for g in gold if g.action_id == aid],
             [p for p in pred if p.action_id == aid])

    # Benchmarks: group by (metric, threshold).
    for g in [g for g in gold if is_bench(g)]:
        if g not in gleft:
            continue
        cands = [p for p in pleft if is_bench(p)
                 and p.metric == g.metric
                 and p.threshold_source == g.threshold_source]
        if cands:
            pairs.append((g, cands[0]))
            gleft.remove(g)
            pleft.remove(cands[0])

    return pairs, gleft, pleft


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def main() -> int:
    print("Compiling the plan automatically and scoring against the golden set\n")

    gold = load_clauses(study.GOLDEN_CLAUSES)
    try:
        res = compile_plan(study.PLAN_PDF)
    except LLMUnavailable as exc:
        print(f"Cannot run the compiler:\n  {exc}")
        return 2

    print(f"  provider / model         {res.provider} / {res.model}")
    print(f"  source                   {'committed cache' if res.cached else 'live API call'}")
    print(f"  clauses proposed         {res.raw_proposals}")
    print(f"  accepted after verify    {len(res.accepted)}")
    print(f"  rejected                 {len(res.rejected)}")
    print(f"  quote verification rate  {res.quote_verification_rate:.1%}")
    print("\n  Every accepted clause carries a quote that was found verbatim on the")
    print("  page it cites. Rejection is automatic and silent to the model.")

    if res.rejected:
        print("\n  Rejected proposals:")
        for r in res.rejected[:10]:
            print(f"    {r.get('clause_id', '?'):<26s} p{r.get('source_page')}  {r['_reason']}")

    pairs, miss, spur = match(gold, res.accepted)

    p, r, f1 = prf(len(pairs), len(spur), len(miss))
    print("\n" + "=" * 74)
    print("CLAUSE DETECTION")
    print("=" * 74)
    print(f"  reference clauses   {len(gold)}")
    print(f"  predicted clauses   {len(res.accepted)}")
    print(f"  matched             {len(pairs)}")
    print(f"  missed              {len(miss)}")
    print(f"  spurious            {len(spur)}")
    print(f"\n  precision {p:.3f}   recall {r:.3f}   F1 {f1:.3f}")

    # The split that matters: prose actions vs tabular benchmarks.
    ga = [g for g in gold if not is_bench(g)]
    gb = [g for g in gold if is_bench(g)]
    ma = [g for g, _ in pairs if not is_bench(g)]
    mb = [g for g, _ in pairs if is_bench(g)]
    print(f"\n  actions        {len(ma)}/{len(ga)} recall {len(ma)/len(ga):.1%}"
          f"   (narrative prose, one per action)")
    print(f"  benchmarks     {len(mb)}/{len(gb)} recall {len(mb)/len(gb):.1%}"
          f"   (numbers embedded in tables and review text)")

    if miss:
        print("\n  Missed:")
        for g in miss:
            print(f"    {g.clause_id:<26s} p{g.source_page:<3d} {g.kind}")
    if spur:
        print("\n  Spurious:")
        for c in spur:
            print(f"    {c.clause_id:<26s} p{c.source_page:<3d} {c.kind}  {c.action[:40]}")

    # ------------------------------------------------------------ field level
    print("\n" + "=" * 74)
    print("FIELD ACCURACY (over matched clauses)")
    print("=" * 74)
    fields = {
        "kind": lambda c: c.kind,
        "metric": lambda c: c.metric,
        "threshold_source": lambda c: c.threshold_source,
        "operator": lambda c: c.operator,
        "source_page": lambda c: c.source_page,
        "scope": lambda c: c.scope,
        "actor": lambda c: frozenset(c.actor),
    }

    adjudicated_hits: list[tuple[str, str, str]] = []
    print(f"  {'field':<18s} {'strict':>10s} {'adjudicated':>14s}")
    print("  " + "-" * 46)
    for name, get in fields.items():
        strict = 0
        adjudged = 0
        for g, pr in pairs:
            if get(g) == get(pr):
                strict += 1
                adjudged += 1
            elif (name, g.clause_id) in ADJUDICATED:
                adjudged += 1
                adjudicated_hits.append((name, g.clause_id,
                                         ADJUDICATED[(name, g.clause_id)]))
        n = len(pairs)
        print(f"  {name:<18s} {strict:>4}/{n:<4} {strict/n:>3.0%} "
              f"{adjudged:>6}/{n:<4} {adjudged/n:>3.0%}")

    if adjudicated_hits:
        print("\n  Adjudicated disagreements -- the document supports both readings:")
        seen = set()
        for fld, cid, why in adjudicated_hits:
            k = (fld, cid)
            if k in seen:
                continue
            seen.add(k)
            print(f"\n    {cid}  [{fld}]")
            for line in _wrap(why, 68):
                print(f"      {line}")

    # ------------------------------------------------- the decisive classification
    print("\n" + "=" * 74)
    print("THE CLASSIFICATION THAT DRIVES THE HEADLINE")
    print("=" * 74)
    print("  Whether an action is conditioned on heat or runs on the calendar is")
    print("  the finding this project reports. If the compiler gets that wrong,")
    print("  nothing else matters.\n")
    agree = sum(1 for g, pr in pairs if g.is_conditional == pr.is_conditional)
    kind_ok = sum(1 for g, pr in pairs if g.kind == pr.kind)
    print(f"  conditional vs calendar agreement   {agree}/{len(pairs)}  "
          f"{agree/len(pairs):.1%}")
    print(f"  full five-way kind agreement        {kind_ok}/{len(pairs)}  "
          f"{kind_ok/len(pairs):.1%}")
    print(f"\n  reference: {sum(1 for c in gold if c.is_conditional)} conditional, "
          f"{sum(1 for c in gold if c.kind == 'scheduled')} calendar-activated")
    print(f"  compiler : {sum(1 for c in res.accepted if c.is_conditional)} conditional, "
          f"{sum(1 for c in res.accepted if c.kind == 'scheduled')} calendar-activated")
    return 0


def _wrap(text: str, width: int) -> list[str]:
    out, line = [], ""
    for w in text.split():
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    if line:
        out.append(line)
    return out


if __name__ == "__main__":
    raise SystemExit(main())
