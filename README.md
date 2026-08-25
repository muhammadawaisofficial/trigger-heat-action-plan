# TRIGGER — the Heat Action Plan Compiler

### **[▶ Open the live demo](https://trigger-heat.streamlit.app/)**  ·  [Repository](https://github.com/muhammadawaisofficial/trigger-heat-action-plan)  ·  Video: _link pending_

The live app needs **no API key and no sign-in**. Everything reproduces offline
too: `python run_demo.py`.


> ## One flaw, two failure modes
>
> A heat trigger keyed to a single fixed number fails in **both** directions,
> and which way it fails depends on how severe the day is.
>
> **It under-fires** where the citywide reading sits below the threshold while
> neighbourhoods sit above it — **1,184,971 people, 72% of Phoenix**, live in
> urban villages that met the City's own overnight-heat benchmark on days the
> citywide reading never fired.
>
> **It over-fires** where severity clears the threshold everywhere at once. On
> **27 of 35 clause-days (77%)** the plan gave no basis for choosing where to
> send anyone: it fired either almost everywhere or almost nowhere.
>
> These are not two findings. **Saturation is the mechanism; lost coverage is the
> consequence.** A threshold can only resolve variation it sits inside.

---

### A. Under-trigger — the coverage failure

On **8 August 2025** the citywide average overnight low read **89.9 °F** — one
tenth of a degree below Phoenix's own 90 °F benchmark. Nothing fired. **Ten of
fifteen urban villages were above it**, the hottest by 3.9 °F.

Across the seven-day window: **20 zone-days of silent exposure** on **3 of 7
days**, with a **median lead of 4 days** between a village meeting the condition
and the citywide number doing so.

### B. Over-trigger — the targeting failure

The same rules, measured on all 272,917 tiles before any aggregation. A clause is
**actionable** only if it fires on between 5% and 95% of tiles — an emergency
manager cannot send crews to the whole city, and cannot send them nowhere.

| | of 35 clause-days |
|---|---|
| Actionable | **8** (23%) |
| Over-triggered — fired on >95% of tiles | **11** |
| Under-triggered — fired on <5% of tiles | **16** |

We measure this in **bits**. A trigger emits one bit per tile — fire or don't —
and the information that bit carries is the binary entropy of the firing share:
1 bit on an even split, **0 bits when it says the same thing everywhere**,
whether that is *everywhere* or *nowhere*. Unlike a count of distinct values it
does not depend on tile count or AOI size, so days and cities are comparable.

On **7 August 2025**, the hottest day of the window, Action 1.1's own rule —
*"above 105 °F"* — fired on **98.9% of the city's tiles and all 15 urban
villages**. That is not a warning, it is a weather report.

> **Precision note.** For the two clauses measured through `exceedance`, the
> underlying field is smoothed rather than counted (it returns small negative
> values — [§9](docs/api_findings.md)), so saturation figures for those clauses
> are approximate to about a percentage point. The **verdicts** are unaffected:
> they are threshold comparisons that sit far from the 5% and 95% boundaries, so
> no reasonable correction moves one. The three `tcm`-backed clauses carry
> per-tile temperatures and are exact.

### C. Recovery — a partial result, and one retraction

**Retracted: the dwell-time result.** We measured, and then withdrew, a finding
that adding a duration requirement to Action 1.1's existing 105 °F threshold
would restore targeting value. It does not survive validation, because
**FortyGuard exposes no trustworthy duration analytic at city scale.** The full
methodology and the failed checks are in
[§8 of `docs/api_findings.md`](docs/api_findings.md) — we publish it as a
negative result rather than deleting it, because the reason it failed is a
reusable finding about the data.

**What does hold** is a percentile trigger, on the clauses backed by `tcm`
temperatures rather than by duration. Replacing a fixed threshold with the 90th
percentile of the day's own distribution restores a rankable ordering in *both*
failure directions:

| clause | as written | p90 of that day | villages recovered |
|---|---|---|---|
| `BENCH-LOW90` | 90 °F, saturation **0.955** — over-fires | 94.3 °F, 0.100 | **3** |
| `BENCH-HIGH100` | 100 °F, saturation **1.000** — over-fires | 109.3 °F, 0.100 | **2** |
| `BENCH-HIGH110` | 110 °F, saturation **0.000** — never fires | 107.6 °F, 0.100 | **2** |

A same-day percentile is **post hoc** — today's p90 is not knowable before today
ends. It demonstrates that the signal survives in the data; it is not a rule a
city could adopt as written. A deployable version would fit the percentile on
historical climatology.

---

Phoenix's Heat Response Plan is a legal instrument with named officers, named
actions and numeric temperature thresholds. It is executed against one reading
from one airport. We compiled the plan into executable rules, re-ran every
clause against FortyGuard's 2-metre data across all 15 urban villages, and
measured what that single reading misses.

Reproduce it in one command, offline, with no API key:

```bash
pip install -r requirements.txt
python run_demo.py         # the headline, in seconds
python verify_all.py       # re-derive everything and assert it — 12 checks
```

---

## Submission — FortyGuard Hackathon '26

**Track 04 · Government & Environment** — primary
**Track 07 · Data Analysis & Correlation** — co-primary
**Track 05 · Model Designing** — supporting

Track 04 names its own build examples as *Heat Vulnerability Map* and *Climate
Resilience Planner*, and its technologies as *Temperature API, Policy AI, GIS,
Open Data*. TRIGGER is a heat vulnerability map produced by compiling policy with
an LLM and evaluating it over GIS and open data — so this is the track's own
brief, answered literally.

We are **not** claiming Track 06 Agentic AI. There is no agent here, by design:
every number is a deterministic comparison, and the language model only extracts
quotes and narrates verified results. It decides nothing.

| | |
|---|---|
| Thermal data | FortyGuard Temperature API only — no external weather source anywhere |
| Scale | 272,917 tiles/day at 100 m over 1,053 mi² |
| Reproducibility | committed cache, **no API key needed**, one command |
| Tests | 59 unit + UI tests, 12 end-to-end checks |

---

## Contents

| | |
|---|---|
| [1. Impact & relevance](#1-impact--relevance-40) | What we found and why it matters |
| [2. Technical execution](#2-technical-execution-35) | How it works, and what we measured about the API |
| [3. Innovation](#3-innovation-15) | Why compiling the document is the whole point |
| [4. Communication](#4-communication-10) | Reproducing every number here |
| [Replication](#replication-on-live-2026-data) | The finding reproduced on data the pipeline had never seen |
| [What we got wrong](#what-we-got-wrong) | Three corrections, and the mechanism that keeps them honest |
| [5. Limitations](#5-limitations) | What this does not show |

---

## 1. Impact & relevance (40%)

### The gap, in the city's own words

Two sentences from the published plan frame the entire problem. Both are
verbatim, both are page-anchored, and both are in `data/golden/`.

> *"Historical development patterns and varying topography across Phoenix lead
> to neighborhood-to-neighborhood air temperature differences of **10°F or
> more** on summer days."*
> — 2026 Heat Response Plan, page 4

> *"In 2025, 37% of heat-related deaths in Maricopa County occurred on days
> with the HeatRisk … designated … as Major or Extreme, and **63% of deaths
> occurred on days when the HeatRisk was designated as Moderate, Minor, or
> None**."*
> — page 9

The City knows heat is not a citywide quantity, and knows most heat deaths
happen on days that never trigger a warning. Then every conditional clause in
the plan is triggered by one number.

### What the plan actually conditions on

We compiled all 23 actions plus the plan's own planning benchmarks — 27 clauses,
every one carrying a verbatim quote and a page number, every quote
mechanically verified against that page.

| Clause kind | Count |
|---|---|
| **Calendar-activated** — runs on a date, not a temperature | **20** |
| Planning benchmark — a temperature with no action attached | 3 |
| Indoor habitability standard | 2 |
| **Operative trigger** — a temperature that causes an action | **1** |
| **External trigger** — NWS Extreme Heat Warning | **1** |

**Twenty of twenty-three actions are not conditioned on heat at all.** Of the
two that are, both are scoped citywide: one reading decides for all 1,053 mi².

This is not a criticism of Phoenix — it is one of the better heat plans in the
United States, and it is improving. It is a measurement of where the
instrumentation stops.

### Trigger Divergence

Study window **2 – 8 August 2025**, selected by measurement (see
[event selection](#event-selection)). Five clauses were evaluable against 2 m
data; 15 urban villages; 272,917 tiles per day.

| Metric | Result |
|---|---|
| **Population in silent zones** | **1,184,971 — 72% of Phoenix** |
| **Silent zones** | **10 of 15 urban villages** |
| **Silent zone-days** | **20** |
| **False-calm days** | **3 of 7** (2, 5 and 8 August) |
| **Median lead time** | **4 days** |

The three largest silent villages are Maryvale (226,766), North Mountain
(173,875) and Camelback East (147,669). Population is joined from US Census ACS
5-year 2023 block groups, areally interpolated onto village boundaries; the
15-village total comes to 1,639,502 against Phoenix's ~1,608,000 at the 2020
census, which is the sanity check on the join.

The clause that carries the finding is the plan's own overnight-heat benchmark
(page 6, *"Nighttime temperatures failed to drop below 90°F at Sky Harbor on 23
days"*). Overnight low, °F, by village — `*` marks the condition met:

```
village                   08-02    08-03    08-04    08-05    08-06    08-07    08-08   days
South Mountain            90.7*    83.0     87.2     92.1*    92.9*    94.9*    92.4*   5/7
Central City              92.3*    84.6     88.0     91.6*    94.2*    94.4*    92.5*   5/7
Ahwatukee Foothills       88.6     81.3     84.0     90.9*    92.3*    94.4*    92.9*   4/7
Laveen                    89.5     83.3     85.6     91.0*    91.3*    92.9*    92.3*   4/7
Camelback East            90.2*    80.7     85.5     89.8     92.1*    92.7*    92.1*   4/7
Maryvale                  90.4*    79.5     86.5     87.4     92.3*    92.4*    93.9*   4/7
Encanto                   91.4*    82.0     86.6     89.9     92.9*    93.3*    92.1*   4/7
Alhambra                  90.3*    78.5     87.0     88.7     91.4*    92.8*    93.5*   4/7
Estrella                  89.7     81.5     86.8     88.5     92.3*    92.5*    93.3*   3/7
North Mountain            88.5     77.2     85.8     87.8     90.1*    92.0*    90.3*   3/7
Paradise Valley           88.2     77.9     83.7     87.9     89.9     92.0*    89.6    1/7
Deer Valley               86.6     74.7     81.2     85.7     88.5     91.7*    87.7    1/7
Desert View               85.6     76.8     81.6     86.5     88.3     91.6*    87.6    1/7
North Gateway             85.7     74.9     78.4     84.7     88.1     92.0*    86.9    1/7
Rio Vista                 84.6     75.1     77.3     85.1     88.6     92.5*    88.6    1/7
--------------------------------------------------------------------------------------------
CITYWIDE PROXY            87.3     78.1     82.4     87.2     90.1*    92.4*    89.9    2/7
```

The villages that meet the condition first and most often — Central City,
South Mountain, Maryvale, Alhambra, Encanto — are the dense, built-out urban
core. The ones that never do are the low-density northern and western fringe.
The plan itself (page 4) identifies lower-income, lower-quality-housing
communities as carrying a disproportionate share of the heat burden; the
spatial pattern here is consistent with that, though we have not joined
demographic data and do not claim to have measured it.

### Saturation, measured on tiles rather than zones

The over-trigger metrics are computed on all **272,917 tiles before any
aggregation**. Fifteen zone averages say nothing about whether the underlying
field had structure, so aggregating first would hide exactly what this measures.

Full per-clause, per-day figures are in `data/results/divergence.json` under
`saturation`, the sweep is in `data/results/severity_sweep.json`, and the
citywide threshold sweep is in `data/results/threshold_sweep.json`.

One limit worth stating plainly: the published window was **selected for
severity**, so it samples only the hot end and spans 3.34 °C of mean temperature.
That is narrow. The sweep file reports its own span so a reader can judge whether
the inverted-U claim is testable on this data, rather than taking our word for it.

### We tested the plan's own 10 °F claim

Page 4 asserts neighbourhood differences of "10°F or more". Measured at 100 m
across the study window:

| Metric | Mean tile-level spread | Village-level spread |
|---|---|---|
| **Overnight low** | **21.2 °F** | 7.4 °F |
| Daily mean | 14.4 °F | 4.0 °F |
| Daily high | 10.2 °F | 2.2 °F |

The claim holds and is conservative — the measured spread reaches or exceeds
10 °F on 18 of 21 day-metric combinations. **The variability is largest
overnight**, which is when heat is most lethal and when the urban heat island
is strongest, and smallest at the daily peak — the metric heat plans usually
trigger on.

```bash
python test_claim.py
```

---

## Replication on live 2026 data

The published result is one week of 2025. To test whether it is a property of
the city or an artefact of that week, we re-ran the identical pipeline on
**16–22 August 2026 — fetched live from the API, data the analysis had never
seen.**

| | 2–8 Aug **2025** (published) | 16–22 Aug **2026** (live) |
|---|---|---|
| Silent zones | 10 of 15 | **9 of 15** |
| Population exposed | 1,184,971 (72%) | **958,205 (58%)** |
| Silent zone-days | 20 | **18** |
| False-calm days | 3 of 7 | **3 of 7** |
| Median lead time | 4 days | **5 days** |
| Worst day | proxy 89.9 °F vs 90 °F, 10 villages over | proxy **89.4 °F** vs 90 °F, **9 villages over** |

The same structure appears a year later, including the same near-miss signature:
the citywide average landing a fraction of a degree below the City's own
threshold while nine or ten neighbourhoods sit above it.

```bash
FORTYGUARD_API_KEY=... python run_analysis.py --start 2026-08-16 --end 2026-08-22
```

This also answers the obvious question about whether anything here is
hardcoded. **The committed cache is a saved copy, not baked-in data** — request
an uncached window and the pipeline calls the API for real. The API accepts any
date from 2019-01-01 to twelve hours ahead of now, so this runs on next season
as readily as on last.

What it is *not* is a continuously running monitor: there is no scheduler and no
alerting loop. It runs on demand over any window.

An independently reproduced finding is a research artefact rather than a demo
result, which is why it gets its own section rather than a footnote. The
over-trigger half replicates too: `verify_all.py` asserts both windows.

---

## 2. Technical execution (35%)

### Pipeline

```
Phoenix 2026 Heat Response Plan (PDF, 23 pages)
        │
   [A] COMPILE    src/compile.py    LLM extraction, verbatim quote + page per field
        │                           every quote verified against its page or REJECTED
        │         data/golden/      hand-compiled reference set (27 clauses)
   [B] EVALUATE   src/evaluate.py   clause × zone × day -> FIRED / NOT FIRED + margin
        │         src/aggregate.py  area-weighted tiles -> 15 urban villages
   [C] DIVERGE    src/diverge.py    lead time | silent zones | false-calm days
        │
   [D] BRIEF      src/brief.py      ranked actions; every number in generated
        │                           prose verified against computed facts
                  app.py            map, clause table, click-through to source page
```

**The language model decides nothing.** It extracts structure from the PDF and
narrates finished results. Every FIRED/NOT FIRED determination, every threshold
comparison and every count in this README is deterministic code over API
responses.

### The anti-hallucination guarantee is architectural

Every clause the compiler proposes carries a verbatim quote and a page number.
Before a clause can be evaluated, that quote is checked against the extracted
text of the page it cites. **A clause whose quote does not appear verbatim on
its stated page is rejected and never reaches the evaluator.**

A model that invents a citation therefore produces *nothing*, not a wrong
answer. The rejection rate is reported as an extraction-quality metric rather
than hidden.

### The compiler, measured

The automatic compiler runs on **Gemini 3.5 Flash via the free AI Studio
tier** — deliberately, not as a compromise. Because correctness is enforced by
mechanical quote verification rather than by trusting the model, the compiler's
guarantee does not depend on model quality. A weaker model scores lower on a
number we publish; it cannot produce a confidently wrong citation.

Scored against the 27-clause hand-built golden set (`python eval_compiler.py`):

| | Result |
|---|---|
| **Quote verification rate** | **100%** — 25 proposed, 25 verified, 0 rejected |
| **Precision** | **1.000** |
| **Recall** | **0.926** |
| **F1** | **0.962** |
| Actions (narrative prose) | **24 / 24 — 100% recall** |
| Planning benchmarks (numbers in tables) | 1 / 3 — 33% recall |

Field accuracy over matched clauses, reported strictly and after adjudication:

| Field | Strict | Adjudicated |
|---|---|---|
| `kind` (the five-way classification) | **100%** | 100% |
| `source_page` | **100%** | 100% |
| `metric` | 96% | 96% |
| `threshold_source` | 96% | **100%** |
| `operator` | 88% | 96% |
| `actor` | 96% | 100% |
| `scope` | 72% | 96% |

**The classification that drives our headline — conditional on heat versus
calendar-activated — is 100% (25/25).** The compiler independently reports 2
conditional and 20 calendar-activated actions, matching the hand-built set
exactly.

"Adjudicated" means disagreements where the document genuinely supports both
readings, listed individually in the eval output. Two examples, because they cut
against us:

- For the cooling ordinance (*"must be able to safely cool all livable rooms to
  86°F"*), we encoded the violation direction (`above`); the compiler encoded
  the requirement direction (`below`). Same rule, different convention.
- For Action 4.2, the plan states **no temperature**. The compiler correctly
  emitted none. Our golden set adds a documented 110 °F proxy so the clause can
  be evaluated at all. **Here the compiler is the more faithful reading and our
  reference set is the one making an editorial choice.**

**The honest weakness:** the compiler found every action but missed two of three
planning benchmarks — including `BENCH-LOW90`, the clause our headline rests on.
Numbers embedded in tables and season-review prose are materially harder than
numbers in action narratives. The published analysis therefore runs on the
hand-verified golden set, not on raw compiler output, and we say so rather than
implying the pipeline is fully autonomous.

### The golden set, and what F1 0.962 does not mean

The score above is only as good as the set it is measured against, so here is
that set in full.

**What it is.** 27 clauses, hand-compiled from the published PDF by us: the
plan's 23 numbered actions (24 clause records — one action splits into two),
3 planning benchmarks, and 2 indoor habitability standards. Every clause carries
a verbatim quote and a page number, and `build_golden.py` mechanically asserts
that all 29 quotes appear on their cited pages. It is committed at
`data/golden/phoenix_2026_clauses.json`.

**How it was selected.** Exhaustively, not by sampling. We took every numbered
action in the document plus every numeric temperature stated anywhere in it.
There is no held-out split, because the population *is* the document — 27 clauses
is the whole plan, not a sample of it.

**What the F1 supports.** That the compiler extracts narrative action clauses
reliably and cites them verifiably: **24 of 24 actions recalled, 0 spurious
clauses, 100% quote verification, and the conditional-versus-calendar
classification correct on 25 of 25.** That last figure is the one that matters
most, because that classification is what the headline finding rests on.

**What it does not support.** Four things, and the first is the serious one:

1. **The compiler missed the clause the headline depends on.** Recall failed on
   exactly 2 of 27 clauses, and both were planning benchmarks: `BENCH-LOW90`
   (page 6) and `BENCH-HIGH100` (page 7). `BENCH-LOW90` is the 90 °F overnight
   benchmark that produces the 1,184,971 figure. **Benchmark recall is 1 of 3
   (33%)** against 24 of 24 for actions — numbers embedded in tables and review
   prose are the compiler's blind spot, and that is where the headline lives.
   **The published analysis therefore runs on the hand-checked golden set, not on
   compiler output.** We report the compiler's accuracy; we do not rely on it.
2. **n = 27.** One clause is worth 3.7 points of recall. Treat 0.962 as "roughly
   the right order of magnitude", not a precise figure, and do not compare it to
   scores computed on larger sets.
3. **The annotators wrote the compiler.** The same two people built the golden
   set and the extraction prompt. That is not independent annotation, and there
   is no second annotator, so we report no inter-annotator agreement. Where the
   two disagree we list every case individually — including the ones where the
   compiler is the more faithful reading and our reference set made the
   editorial choice.
4. **One document, one city, one plan format.** Nothing here establishes that the
   compiler generalises to a differently structured heat plan.

### What we measured about the FortyGuard API

Three findings contradict the documentation, and each fails silently. Full
evidence in [`docs/api_findings.md`](docs/api_findings.md); reproduce with
`python verify_api.py`.

| Finding | Evidence | Consequence |
|---|---|---|
| **`tcm` tiles are °C, not °F** — the quickstart README is wrong | Downtown Phoenix peaked at 40.3, i.e. 104.5 °F. As °F it would be 40 °F. | One conversion, in `schema.f_to_c`, nowhere else |
| **`persistence` saturates at 8.0 under `filter_type=4`** | At a 20 °C threshold every hour of a 168 h week qualifies, so the longest run is 168. It returns **8.0**. Same at 30 °C and 35 °C. | Never used for duration; we evaluate day by day |
| **`persistence` is correct under `filter_type=3`** | Same AOI, one day: 24.00 at 20 °C, 16.00 at 35 °C, 2.00 at 40 °C — all correct | The defect is range-of-days only |
| **AOI cap is far above the documented 50 mi²** | 1,053 mi² / 272,917 tiles accepted in a single call | One call per (day, threshold), not one per village |
| **Credits are flat per call** | 420-tile and 272,917-tile calls both cost 4,220 | No reason ever to make a small request |

The `persistence` finding also forced the right architecture for the wrong-
looking reason: **a single 7-day aggregate collapses the time axis the
lead-time metric is about.** You cannot recover *when* a condition was first
met from one number covering a week. Day-by-day evaluation was necessary
regardless.

### Offline reproducibility

The demo must run with no API key, so the cache is committed. A 1,053 mi² call
is 130 MB of raw JSON, which no repository should carry. Measured on this data,
**tile geometry is 87% of the payload — and the grid is byte-identical across
every call sharing an AOI and granularity.** So the cache stores geometry once
per grid and values columnar per request:

**265.7 MB → 11.3 MB on the probe set, a 23.5× reduction**, with responses
rebuilt into exactly the shape the API returned. Nothing downstream knows the
difference.

### Verification

| Check | Command | Result |
|---|---|---|
| Aggregation vs brute force (no spatial index) | `python test_aggregate.py` | agree to **7.8 × 10⁻¹⁴** |
| Every golden quote appears verbatim on its page | `python build_golden.py` | **29 / 29** |
| API findings reproduce from cache | `python verify_api.py` | offline, no key |
| The plan's 10 °F claim | `python test_claim.py` | holds, conservative |
| Compiler vs golden set | `python eval_compiler.py` | **P 1.000 / R 0.926 / F1 0.962** |
| Generated prose cannot invent a number | `python test_brief_guard.py` | rejection path demonstrated |

### Event selection

The study window was chosen by measurement, not assumption. We scanned every
day from 1 July to 15 August 2025 for hours above 105 °F — the threshold
Action 1.1 of the plan actually names — and took the most severe consecutive
seven days.

| Window | Total hours above 105 °F |
|---|---|
| 6 – 12 July | 46.7 |
| **2 – 8 August** | **57.8** ← selected |

This independently corroborates the plan's own account of the season: it
records the seasonal high of 118 °F at Sky Harbor on **7 August** and calls
August *"the hottest month of the summer"* (page 6). Our scan picks 7 August as
August's most severe day from FortyGuard data alone.

```bash
python scan_event.py --start 2025-07-01 --end 2025-08-15
```

---

## 3. Innovation (15%)

Most heat-tech maps where it is hot and alerts someone. TRIGGER does something
different: it **adjudicates a legal document**.

| The usual approach | TRIGGER |
|---|---|
| Map where it is hot | Determine which clauses of a real published plan are in force, where, and for whom |
| Alert when a threshold is crossed | Quantify what the *existing official* threshold has been missing |
| Rules hardcoded by the team | Rules compiled from the published PDF, page-anchored, with a measured extraction score |
| Rank by peak temperature | Rank by exceedance and overnight minimum — because that is what the clauses specify and where the signal is |

The last row is not a stylistic preference. On the same 420 tiles on the same
day, daily-mean temperature spread **0.12 °C** while hours-above-threshold
spread **1.34 hours across 394 distinct values**. Ranking neighbourhoods by
peak temperature is ranking noise.

---

## 4. Communication (10%)

### Run it

```bash
pip install -r requirements.txt

python verify_all.py         # runs everything below and asserts the headline
python run_analysis.py       # the headline number, offline
python verify_api.py         # every API claim we make, offline
python test_aggregate.py     # aggregation correctness (vs brute force)
python test_claim.py         # the plan's 10 F claim vs measurement
python test_brief_guard.py   # prove generated prose cannot invent a number
python eval_compiler.py      # compiler precision / recall / F1
python build_golden.py       # re-verify all 29 quotes against the PDF
python make_report.py        # regenerate the standalone research report
python make_brief.py         # regenerate the ranked action brief
streamlit run app.py         # map, clause table, provenance
```

No API key is needed for any of these. To re-fetch from the API instead, set
`FORTYGUARD_API_KEY` and run `python prefetch.py` first.

### Repository

```
src/
  cache.py       disk cache, grid/value split, resilient polling
  schema.py      Clause dataclass + validation + the ONLY F->C conversion
  parse.py       both tile schemas on one path
  geo.py         AOI construction, areas, [lon, lat] discipline
  aggregate.py   area-weighted tiles -> zones
  evaluate.py    clause x zone x day -> FIRED / NOT FIRED
  diverge.py     the three metrics
  compile.py     LLM extraction with mechanical quote verification
  study.py       city, AOI, zones, window — one source of truth
data/
  plan/          the source PDF
  golden/        27 hand-compiled clauses, every quote verified
  zones/         15 Phoenix urban villages (City of Phoenix Open Data)
  cache/         committed API responses — the demo runs offline
  results/       divergence.json
docs/
  trigger_divergence_report.md   the standalone research result
  action_brief.md                ranked actions, each citing clause/page/owner
  api_findings.md                everything we measured about the API
  SUBMISSION.md                  deployment, checklist, video script
```

### Timezone

`time_of_measure` is UTC. **Arizona is UTC−7 year-round and does not observe
DST**, so UTC hour 22 is 15:00 local. The conversion lives in
`parse.utc_hour_to_phoenix`.

---

## What we got wrong

Three corrections, in the order they happened. Each is recorded rather than
edited away, because in every case the *reason* it was wrong turned out to be a
reusable finding about the data.

### 1. A comparability claim with no source behind it

**Claimed.** That Phoenix's measured spatial spread was "comparable to the San
Jose reference sample" of 2.07–8.73 h across 329 tiles.

**Wrong because.** That reference cannot be sourced. It is not in the vendored
client — which ships the San Jose *polygon* but no statistics — and it carries no
window, threshold or granularity, so there is nothing to normalise against.
8.73 − 2.07 = 6.66 h, and whether that spans one day or seven changes the
per-day figure sevenfold.

**Caught by.** Being asked to state the comparison per-day, which surfaced that
the denominator was unknown.

**Now.** No comparability claim in either direction. Phoenix's spreads are
reported as absolute figures — around **one hour per day over a 2 km box** — with
the explicit note that these are small numbers.

### 2. Publishing a 2 km box result as a citywide finding

**Claimed.** That a threshold outside the day's range collapses discrimination
from 394 distinct values to 1, offered as the project's primary finding.

**Wrong because.** It measured the *box*, not the mechanism. Over 4 km² the
spatial spread in overnight low is 0.08–0.47 °C, so almost any threshold falls
outside it and the API returns a single quantised integer. Citywide, the same
days show **10.85–13.49 °C** of spread and **43,497–74,365** distinct values,
with **zero** flat days against 6 of 7 on the box.

**Caught by.** Running the same measurement on the full AOI before writing the
headline, prompted by a request to justify the magnitude.

**Now.** The mechanism survives — a threshold resolves only variation it sits
inside — but its magnitude is set by **the area being sensed**, and every figure
in [§8](docs/api_findings.md) is citywide. `verify_years.py` carries an explicit
*"do not quote these as the headline"* scope limit, since it is the file most
likely to be read out of context.

### 3. A hero result built on an analytic that cannot support it

**Claimed.** That adding a dwell requirement to Action 1.1's existing 105 °F
threshold restores targeting value, 0.090 → 0.974 bits — same threshold, same
data, a clause edit.

**Wrong because.** Two independent reasons, and the first is decisive on its own:

- **Semantics.** The grid was derived from `exceedance`, which returns a
  **total** of qualifying hours. A dwell clause describes a **continuous spell**.
  Three separate three-hour spells total nine hours, pass the exceedance test,
  and fail the clause. Wrong analytic for the question, regardless of data
  quality.
- **Data quality.** `exceedance` returns negative values citywide (to −2.51 h),
  so it is smoothed rather than counted. This also inflated the baseline: a
  saturation of 0.989 at `dwell>0h` implies 1.1% of tiles recorded ≤ 0 hours
  above 105 °F on a day that peaked at 109.6 °F.

**Then the replacement failed too.** `persistence` is the correct analytic and
the only other one carrying duration information. Citywide it returns runs of
**25.92 h** inside a single day, **3,110 negative** runs, and up to **39,329
tiles** whose "longest run" exceeds that tile's own total qualifying hours. It is
also not independent: **93.9% of tiles identical to `exceedance`** at 105 °F, and
100% at four of six thresholds. `tcm` carries no time information at all.

**Caught by.** Being asked to state the provenance of the hero number explicitly,
then a validation harness written before the replacement numbers were trusted.

**Now.** Retracted and published as a **negative finding**: FortyGuard exposes no
trustworthy duration analytic at city scale. That is worth knowing, because a
dwell requirement is the most natural fix for a saturating threshold and the
first thing a reader will propose. Full methodology in
[§8](docs/api_findings.md); the failing harness is `sweep_dwell.py`.

It also forced a correction upstream: §2 had concluded that `filter_type=3`
persistence "behaves exactly as documented" because it agreed with `exceedance`
on the small box. **We read agreement as corroboration when it was evidence of
non-independence.** No published number moved — the pipeline never used
`persistence` — but the wording overstated what had been established.

### How the retraction is kept from going stale

`sweep_dwell.py` **exits non-zero on purpose**, and `verify_all.py` asserts that
it *continues to fail*:

```python
ok_dwell, secs, _ = run("sweep_dwell.py", env)
if ok_dwell:
    drift.append("sweep_dwell.py PASSED validation; the retraction in "
                 "api_findings.md section 8 may no longer hold")
```

The assertion is deliberately inverted. If FortyGuard fixes `persistence`, or if
our validation harness breaks, the check reports drift and demands a human look —
rather than a retracted claim quietly sitting in the repository as though it were
still true.

---

## 5. Limitations

Written plainly, because these change how the result should be read.

**The baseline is a proxy, not a station feed.** Our comparator is the
area-weighted mean over the full city AOI. That is a *best-case* single-number
sensor: perfectly sited, perfectly representative. A real airport station is
worse than this. **Our divergence is therefore a lower bound**, not an
estimate of the true gap against Sky Harbor. This is labelled everywhere it
appears, in the code and in the output.

**The model reads cooler than the Sky Harbor station.** The plan records 110 °F
on 37 days in 2025 and a peak of 118 °F. FortyGuard's 2 m model over downtown
Phoenix does not reach 110 °F in the whole of July. Sky Harbor is open tarmac
and a documented hotspot, so some of this gap is real; some may be model
smoothing. We cannot separate the two. The consequence is concrete: **clauses
keyed to 110 °F return zero in both arms and carry no signal** — which is why
the two 110 °F clauses in our results show nothing. Clauses between 95 °F and
107 °F sit inside the model's dynamic range and are where the analysis has
power.

**Because both arms use the same data, a systematic offset cancels.** The
divergence result does not depend on the model being correctly calibrated
against station observations — only on it resolving relative spatial structure,
which is exactly what it is built to do.

**Urban villages are large.** They average 10 to 68 mi², which smooths heavily:
village-level overnight spread is 7.4 °F against 21.2 °F at 100 m tile scale.
Finer zones would diverge *more*, not less. This is another reason the headline
is a lower bound.

**Area weighting barely matters at this granularity.** We use it because it is
the correct operation, but measured against a naive centroid-in-polygon lookup
the difference is ~0.0001 °C. We are not claiming it as a differentiator.

**Seven days, one city, one plan.** The compiler is city-agnostic — only the
AOI, the zone file and the PDF change — but we have demonstrated it on Phoenix
only.

**Population is areally interpolated, not counted.** Village populations come
from Census block-group totals apportioned by overlap area, which assumes
uniform density within a block group. Block groups are small by design
(600–3,000 people) and Phoenix village boundaries largely follow the same
arterial grid, so the error is modest — but the figure is an estimate. The
15-village total of 1,639,502 against Phoenix's ~1,608,000 at the 2020 census
is the check that it is not badly wrong.

**We did not test a heat-index trigger.** Replacing dry-bulb temperature with
`heat_index_celsius` or `apparent_temperature_celsius` from `/v1/env_params` is
the obvious third recovery design, and humidity is what makes Phoenix nights
lethal. We did not do it: `env_params` is a per-point endpoint, so a gridded
comparison means thousands of calls rather than one, and its credit cost is not
documented. Left as future work rather than half-done.

**Action 4.2 uses a proxy threshold.** The plan states no temperature for
"when the National Weather Service issues an Extreme Heat Warning". We map it
to 110 °F, anchored to the plan's own pairing on page 6 (37 days at or above
110 °F against 31 Extreme Heat Warning days). 37 ≠ 31, so the mapping is close
but inexact; the clause carries `extraction_conf = 0.70` and its result should
be read as indicative.

---

## Data provenance

**Every thermal number in this project comes from the FortyGuard Temperature
API.** No external weather, temperature or climate service is called anywhere in
the pipeline. The Sky Harbor figures that appear in our analysis (110 °F on 37
days, 118 °F peak, 90 °F overnight lows) are quoted *from the plan PDF itself*,
page 6, as the document's own account of the season — not fetched from a
meteorological source.

Three non-FortyGuard inputs are used, each because it supplies something
FortyGuard does not and cannot:

| Input | Source | Why it is necessary |
|---|---|---|
| Zone boundaries | City of Phoenix Open Data, "Villages" | Aggregation units and named jurisdictions. Static, downloaded once, committed. |
| Population | US Census ACS 5-year 2023 + TIGERweb geometry | Converts silent zones into people. Static, committed. |
| Clause extraction | Google Gemini (free tier) | Reads the PDF. Output is cached and committed; no key needed to reproduce. |

None of these is a temperature source, and none substitutes for any FortyGuard
capability.

## Sources

- City of Phoenix 2026 Heat Response Plan DRAFT (2.13.2026) —
  [phoenix.gov](https://www.phoenix.gov/content/dam/phoenix/heatsite/documents/2026%20Heat%20Response%20Plan.pdf)
- Phoenix urban village boundaries —
  [City of Phoenix Open Data](https://www.phoenixopendata.com/dataset/villages)
- FortyGuard Temperature API — [api.fortyguard.com](https://api.fortyguard.com)
- US Census ACS 5-year 2023 (table B01003_001E) and TIGERweb ACS2023 block groups

Built for the FortyGuard Hackathon '26.
Tracks: **04 Government & Environment** (primary), **07 Data Analysis &
Correlation** (co-primary), **05 Model Designing** (compiler extraction score).
