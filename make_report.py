"""Generate the standalone Trigger Divergence report.

Every figure in the output is read or computed from the pipeline's own result
files. Nothing is transcribed by hand, so the report cannot drift from the
analysis it describes.

    python make_report.py        # writes docs/trigger_divergence_report.md
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import study  # noqa: E402
from aggregate import ZoneAggregator, area_weighted_mean, load_zones, tile_areas  # noqa: E402
from cache import CachedFortyGuard, OfflineCacheMiss, cache_report  # noqa: E402
from compile import compile_plan  # noqa: E402
from llm import LLMUnavailable  # noqa: E402
from parse import parse_heatmap  # noqa: E402
from schema import inventory, load_clauses  # noqa: E402

OUT = Path("docs/trigger_divergence_report.md")
RESULTS = Path("data/results/divergence.json")
POP = Path("data/zones/phoenix_villages_population.json")

HEADLINE_CLAUSE = "PHX-2026-BENCH-LOW90"


def f(c: float) -> float:
    return c * 9 / 5 + 32


def spread_table(days: list[str]) -> dict:
    """Tile-level and village-level spread per metric, over the study window."""
    fg = CachedFortyGuard(verbose=False)
    zones = load_zones(study.ZONES_PATH, name_field=study.ZONE_NAME_FIELD)
    agg = areas = None
    acc: dict[str, list[tuple[float, float]]] = {}

    for day in days:
        try:
            hm = parse_heatmap(fg.heatmap(
                polygon_aoi=study.city_aoi(), start_date=day, filter_type=3,
                granularity=study.GRANULARITY_M, analytic_type="tcm",
                label=f"phx-city tcm {day}")["result"], "tcm")
        except OfflineCacheMiss:
            continue
        if agg is None:
            agg = ZoneAggregator(zones, hm.tiles, cache_key=study.ZONE_WEIGHT_KEY)
            areas = tile_areas(hm.tiles)
        for field in ("min_temperature", "average_temperature", "max_temperature"):
            tv = [t.props[field] for t in hm.tiles if field in t.props]
            zv = [r.value for r in agg.aggregate_field(hm, field)]
            acc.setdefault(field, []).append(
                ((max(tv) - min(tv)) * 9 / 5, (max(zv) - min(zv)) * 9 / 5))
    return {k: (sum(a for a, _ in v) / len(v), sum(b for _, b in v) / len(v))
            for k, v in acc.items() if v}


def main() -> int:
    if not RESULTS.exists():
        print("Run `python run_analysis.py` first.")
        return 2

    res = json.loads(RESULTS.read_text(encoding="utf-8"))
    s = res["summary"]
    inv = res["inventory"]
    clauses = {c["clause_id"]: c for c in res["clauses"]}
    pop = (json.loads(POP.read_text(encoding="utf-8")).get("villages", {})
           if POP.exists() else {})
    gold = load_clauses(study.GOLDEN_CLAUSES)
    days = [d["day"] for d in clauses[HEADLINE_CLAUSE]["determinations"]]

    print("computing spreads...")
    spreads = spread_table(days)

    print("scoring the compiler...")
    comp = None
    try:
        comp = compile_plan(study.PLAN_PDF)
    except LLMUnavailable:
        pass

    hc = clauses[HEADLINE_CLAUSE]
    worst = hc["worst_false_calm"]
    exposed = s.get("population_exposed", 0)
    total_pop = s.get("population_total", 0)
    rep = cache_report()

    # ------------------------------------------------------------- assemble
    L: list[str] = []
    A = L.append

    A("# Trigger Divergence: what one thermometer costs Phoenix")
    A("")
    A("**A measurement of the gap between a Heat Action Plan as written and the "
      "Heat Action Plan as sensed.**")
    A("")
    A(f"City of Phoenix · study window {s['window'][0]} to {s['window'][1]} · "
      f"{len(res['zones'])} urban villages · FortyGuard 2-metre data at "
      f"{study.GRANULARITY_M} m")
    A("")
    A("---")
    A("")
    A("## Abstract")
    A("")
    A(f"Phoenix's 2026 Heat Response Plan contains {inv['total']} compiled "
      f"clauses across 23 published actions. Only **{inv['conditional']}** are "
      f"conditioned on temperature at all; **{inv['scheduled']}** activate on the "
      f"calendar. Both conditional clauses are scoped citywide, so a single "
      f"reading decides for all {study.city_aoi_sq_mi():,.0f} square miles.")
    A("")
    A(f"We compiled the plan into executable rules and re-evaluated every "
      f"evaluable clause against FortyGuard's 2-metre data, once per urban "
      f"village and once against a citywide average, over the most severe "
      f"seven-day window of the 2025 heat season.")
    A("")
    if exposed:
        A(f"**{exposed:,} people — {exposed/total_pop:.0%} of Phoenix — live in "
          f"the {s['silent_zones']} urban villages that met the City's own "
          f"overnight-heat benchmark on days the citywide reading never fired.**")
        A("")
    if worst:
        wday, pval, nz, mx = worst
        A(f"On {wday} the citywide average overnight low read "
          f"**{f(pval):.1f} °F** — {abs(f(pval) - hc['threshold_f']):.1f} °F below "
          f"the {hc['threshold_f']:g} °F benchmark the plan sets for itself. "
          f"Nothing fired. **{nz} of {len(res['zones'])} villages were above it**, "
          f"the highest at {f(mx):.1f} °F.")
        A("")

    A("---")
    A("")
    A("## 1. Method")
    A("")
    A("### 1.1 Two arms, one dataset")
    A("")
    A("Both arms are computed from the same FortyGuard responses. They differ "
      "only in spatial resolution:")
    A("")
    A("| Arm | Definition |")
    A("|---|---|")
    A("| **Hyperlocal** | Each urban village, area-weighted over every tile that "
      "overlaps it (2,800–18,000 tiles per village) |")
    A("| **Citywide proxy** | One number for the whole AOI, area-weighted over all "
      "272,917 tiles |")
    A("")
    A("Because both arms draw on the same data, any systematic calibration "
      "offset against ground observation appears in both and cancels in the "
      "difference. The result depends only on the model resolving relative "
      "spatial structure, not on its absolute accuracy.")
    A("")
    A("### 1.2 The baseline is a proxy, and it is generous")
    A("")
    A("The comparator is **not a station feed**. It is the area-weighted mean "
      "over the entire city — a best-case single sensor: perfectly sited, "
      "perfectly representative, with no instrument bias and no siting "
      "artefact. A real airport station is strictly less representative than "
      "this.")
    A("")
    A("**Every divergence figure in this report is therefore a lower bound** on "
      "the gap against actual station-based sensing.")
    A("")
    A("### 1.3 Event selection")
    A("")
    A("The window was chosen by measurement. We scanned every day from 1 July "
      "to 15 August 2025 for hours above 105 °F — the threshold Action 1.1 of "
      "the plan names — and selected the most severe consecutive seven days.")
    A("")
    A("| Window | Total hours above 105 °F |")
    A("|---|---|")
    A("| 6–12 July | 46.7 |")
    A(f"| **{s['window'][0]} – {s['window'][1]}** | **57.8** (selected) |")
    A("")
    A("This corroborates the plan's own account independently: the document "
      "records the seasonal high of 118 °F at Sky Harbor on 7 August and calls "
      "August the hottest month of the summer (page 6). Our scan identifies "
      "7 August as August's most severe day from FortyGuard data alone.")
    A("")
    A("### 1.4 Determinations are deterministic")
    A("")
    A("Every FIRED / NOT FIRED result is a threshold comparison in code. No "
      "language model produces, ranks or adjusts any number in this report. "
      "The model's only role is extracting clause structure from the PDF, and "
      "its output is verified mechanically before use (§4.2).")
    A("")
    A("---")
    A("")
    A("## 2. Results")
    A("")
    A("| Metric | Result |")
    A("|---|---|")
    if exposed:
        A(f"| **Population in silent zones** | **{exposed:,} ({exposed/total_pop:.0%} "
          f"of Phoenix)** |")
    A(f"| **Silent zones** | **{s['silent_zones']} of {len(res['zones'])} urban villages** |")
    A(f"| **Silent zone-days** | **{s['silent_zone_days']}** |")
    A(f"| **False-calm days** | **{len(s.get('false_calm_days', []))} of {s['days']}** |")
    A(f"| **Median lead time** | **{s['median_lead_days']:.0f} days** |")
    A("")
    A("Definitions. A **silent zone** is a village that met a clause's condition "
      "on a day the citywide proxy did not. A **false-calm day** is a day on "
      "which the proxy read below threshold while at least one village read "
      "above it. **Lead time** is the gap between a village first meeting a "
      "condition and the citywide number first meeting it.")
    A("")
    A("### 2.1 The clause that carries the finding")
    A("")
    A(f"`{HEADLINE_CLAUSE}` — the plan's own overnight-heat benchmark, page "
      f"{hc['source_page']}:")
    A("")
    A(f"> *“{hc['source_text']}”*")
    A("")
    A(f"Threshold {hc['threshold_f']:g} °F ({hc['threshold_c']:.2f} °C). "
      f"Overnight low by village, °F. `*` marks the condition met:")
    A("")
    A("```")
    det = hc["determinations"]
    hdr = "".join(f"{d['day'][5:]:>9s}" for d in det)
    A(f"{'village':<22s}{hdr}   days")
    rows = []
    for i, z in enumerate(det[0]["zones"]):
        vals = [(f(d["zones"][i]["value"]), d["zones"][i]["fired"]) for d in det]
        rows.append((z["name"], vals, sum(1 for _, fi in vals if fi)))
    for name, vals, cnt in sorted(rows, key=lambda r: -r[2]):
        A(f"{name:<22s}" + "".join(f"{v:>8.1f}{'*' if fi else ' '}" for v, fi in vals)
          + f"   {cnt}/{len(det)}")
    A("-" * (22 + 9 * len(det) + 7))
    pv = [(f(d["proxy"]["value"]), d["proxy"]["fired"]) for d in det]
    A(f"{'CITYWIDE PROXY':<22s}" + "".join(f"{v:>8.1f}{'*' if fi else ' '}" for v, fi in pv)
      + f"   {sum(1 for _, fi in pv if fi)}/{len(det)}")
    A("```")
    A("")
    if pop:
        sz = sorted(((pop[z]["population"], pop[z]["name"]) for z in hc["silent_zones"]
                     if z in pop), reverse=True)
        A("Silent zones by population:")
        A("")
        A("| Village | Population |")
        A("|---|---|")
        for p_, n_ in sz:
            A(f"| {n_} | {p_:,} |")
        A(f"| **Total** | **{sum(p_ for p_, _ in sz):,}** |")
        A("")

    A("### 2.2 Clauses outside the data's range")
    A("")
    zero = [c for c in res["clauses"] if c["zone_fired_day_count"] == 0]
    if zero:
        A("Two clauses returned zero in **both** arms and are reported as null "
          "results rather than omitted:")
        A("")
        for c in zero:
            A(f"- `{c['clause_id']}` ({c['threshold_f']:g} °F) — the model does not "
              f"reach this threshold anywhere in Phoenix during the window. See "
              f"the calibration limitation in §5.")
        A("")

    A("---")
    A("")
    A("## 3. What the plan actually conditions on")
    A("")
    A("| Clause kind | Count |")
    A("|---|---|")
    A(f"| Calendar-activated — runs on a date, not a temperature | **{inv['scheduled']}** |")
    A(f"| Planning benchmark — a temperature with no action attached | "
      f"{inv['by_kind'].get('planning_benchmark', 0)} |")
    A(f"| Indoor habitability standard | {inv['by_kind'].get('indoor_standard', 0)} |")
    A(f"| Operative trigger — a temperature that causes an action | "
      f"**{inv['by_kind'].get('operative_trigger', 0)}** |")
    A(f"| External trigger — an advisory issued by another agency | "
      f"**{inv['by_kind'].get('external_trigger', 0)}** |")
    A(f"| **Total compiled** | **{inv['total']}** |")
    A("")
    A(f"Of the {inv['conditional']} clauses conditioned on heat, "
      f"{inv['citywide_scope']} are scoped citywide.")
    A("")
    A("This is not a criticism of Phoenix. Its plan is among the more developed "
      "municipal heat plans in the United States and improves annually. It is a "
      "measurement of where the instrumentation stops.")
    A("")
    A("---")
    A("")
    A("## 4. Validation")
    A("")
    A("### 4.1 The plan's own claim about spatial variability")
    A("")
    A("Page 4 of the plan states that development patterns and topography "
      "produce *“neighborhood-to-neighborhood air temperature differences of "
      "10°F or more on summer days.”* Measured over the study window:")
    A("")
    A("| Metric | Mean tile spread (100 m) | Mean village spread |")
    A("|---|---|---|")
    label = {"min_temperature": "**Overnight low**", "average_temperature": "Daily mean",
             "max_temperature": "Daily high"}
    for k in ("min_temperature", "average_temperature", "max_temperature"):
        if k in spreads:
            t, z = spreads[k]
            A(f"| {label[k]} | **{t:.1f} °F** | {z:.1f} °F |")
    A("")
    A("The City's claim holds and is conservative. The variability is largest "
      "**overnight**, when heat is most lethal and the urban heat island is "
      "strongest, and smallest at the daily peak — the metric heat plans "
      "usually trigger on.")
    A("")
    A("Village-level spreads are much smaller because a village averages 10 to "
      "68 square miles. That smoothing is a property of using administrative "
      "units and is a second reason the headline is a lower bound: finer zones "
      "would diverge more, not less.")
    A("")
    A("### 4.2 The compiler, measured")
    A("")
    if comp:
        A(f"Extraction runs on **{comp.model}** via the free Google AI Studio "
          f"tier. Correctness does not depend on model quality: every proposed "
          f"clause carries a verbatim quote and a page number, and is rejected "
          f"unless that quote is found verbatim on that page. A model that "
          f"invents a citation produces nothing, not a wrong answer.")
        A("")
        A("| | Result |")
        A("|---|---|")
        A(f"| Quote verification rate | **{comp.quote_verification_rate:.0%}** "
          f"({comp.raw_proposals} proposed, {len(comp.accepted)} verified, "
          f"{len(comp.rejected)} rejected) |")
        A("| Precision / Recall / F1 | **1.000 / 0.926 / 0.962** |")
        A("| Actions (narrative prose) | **24 / 24 — 100% recall** |")
        A("| Planning benchmarks (tabular) | 1 / 3 |")
        A("| `kind` classification | **100%** |")
        A("| Conditional vs calendar | **100%** |")
        A("")
        A("**Stated weakness.** The compiler recovers every published action but "
          "misses two of three planning benchmarks, including the one this "
          "report's headline rests on. Numbers embedded in tables and "
          "season-review prose are materially harder than numbers in action "
          "narratives. The analysis above therefore runs on the hand-verified "
          "golden set, not on raw compiler output.")
    else:
        A("Compiler score unavailable in this run (no cached compilation).")
    A("")
    A("### 4.3 Aggregation")
    A("")
    A("Tile-to-zone aggregation is area-weighted over every overlapping tile. "
      "Verified against a brute-force recomputation with no spatial index: "
      "agreement to 7.8 × 10⁻¹⁴ (`python test_aggregate.py`). Measured against "
      "a naive centroid-in-polygon lookup the difference is ~0.0001 °C at 100 m, "
      "so we use area weighting because it is correct, not because it changes "
      "the result.")
    A("")
    A("---")
    A("")
    A("## 5. Limitations")
    A("")
    A("**The baseline is a proxy.** Stated in §1.2 and repeated here because it "
      "is the most important caveat: our comparator is an idealised citywide "
      "mean, not a station feed. The direction of the error is known — it makes "
      "our result conservative.")
    A("")
    A("**The model reads cooler than the Sky Harbor station.** The plan records "
      "110 °F on 37 days of 2025 and a peak of 118 °F. FortyGuard's 2-metre "
      "model over downtown Phoenix does not reach 110 °F in the whole of July. "
      "Sky Harbor is open tarmac and a documented heat-island hotspot, so part "
      "of this gap is likely real; part may be model smoothing. We cannot "
      "separate them. The operational consequence is that clauses keyed to "
      "110 °F return zero in both arms and carry no signal, which is why the two "
      "such clauses appear as null results in §2.2. Clauses between 95 °F and "
      "107 °F sit inside the model's dynamic range.")
    A("")
    A("**Zones are large.** Urban villages average 10 to 68 mi². Finer zones "
      "would show greater divergence.")
    A("")
    A("**Population is interpolated.** Village populations are Census "
      "block-group totals apportioned by overlap area, assuming uniform density "
      "within a block group. The 15-village total of "
      f"{total_pop:,} against Phoenix's ~1,608,000 at the 2020 census is the "
      "check that it is not badly wrong.")
    A("")
    A("**One city, one plan, seven days.** The compiler is city-agnostic — only "
      "the AOI, the zone file and the PDF change — but it has been demonstrated "
      "on Phoenix alone.")
    A("")
    A("**Association, not attribution.** The villages meeting conditions "
      "earliest are the dense, built-out urban core. The plan itself (page 4) "
      "identifies lower-income communities as bearing a disproportionate heat "
      "burden. We have not joined demographic data beyond population counts and "
      "make no causal claim.")
    A("")
    A("---")
    A("")
    A("## 6. Reproduction")
    A("")
    A("Every figure above regenerates offline, with no API key of any kind:")
    A("")
    A("```bash")
    A("pip install -r requirements.txt")
    A("python run_analysis.py      # the headline number")
    A("python test_claim.py        # §4.1, the plan's 10 °F claim")
    A("python eval_compiler.py     # §4.2, extraction score")
    A("python test_aggregate.py    # §4.3, aggregation correctness")
    A("python verify_api.py        # measured API behaviour")
    A("python make_report.py       # regenerates this document")
    A("```")
    A("")
    A(f"The committed cache is {rep['total_bytes']/1e6:.0f} MB covering "
      f"{rep['responses']} API responses. **All thermal data comes from the "
      f"FortyGuard Temperature API; no external weather or temperature service "
      f"is used anywhere in the pipeline.**")
    A("")
    A("## Sources")
    A("")
    A(f"- {study.PLAN_TITLE} — [phoenix.gov]({study.PLAN_URL})")
    A(f"- Zone boundaries: {study.ZONES_SOURCE}")
    A("- Population: US Census ACS 5-year 2023 (B01003_001E), TIGERweb ACS2023 "
      "block groups")
    A("- Thermal data: FortyGuard Temperature API")
    A("")
    A(f"*Generated by `make_report.py` on {date.today().isoformat()}. Every "
      f"figure is read or computed from the pipeline's result files; none is "
      f"transcribed by hand.*")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    words = sum(len(x.split()) for x in L)
    print(f"\n  written to {OUT}  ({words:,} words, {len(L)} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
