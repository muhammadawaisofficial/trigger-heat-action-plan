# TRIGGER — the Heat Action Plan Compiler

**Phoenix's Heat Response Plan is a legal instrument with named officers, named
actions and numeric temperature thresholds. It is executed against one reading
from one airport. We compiled the plan into executable rules, re-ran every
clause against FortyGuard's 2-metre data across all 15 urban villages, and
measured what that single reading misses.**

> ### The number
>
> **1,184,971 people — 72% of Phoenix — live in urban villages that met the
> City's own overnight-heat benchmark on days the citywide reading never
> fired.**
>
> On **8 August 2025** the citywide average overnight low read **89.9 °F** —
> one tenth of a degree below the City's own 90 °F benchmark. Nothing fired.
> **Ten of Phoenix's fifteen urban villages were above it**, the hottest by
> **3.9 °F**.
>
> Across the seven-day window: **20 zone-days of silent exposure** on **3 of 7
> days**, with a **median lead of 4 days** between when a village first met the
> condition and when the citywide number did.

Reproduce it in one command, offline, with no API key:

```bash
pip install -r requirements.txt
python run_analysis.py
```

---

## Contents

| | |
|---|---|
| [1. Impact & relevance](#1-impact--relevance-40) | What we found and why it matters |
| [2. Technical execution](#2-technical-execution-35) | How it works, and what we measured about the API |
| [3. Innovation](#3-innovation-15) | Why compiling the document is the whole point |
| [4. Communication](#4-communication-10) | Reproducing every number here |
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
   [D] BRIEF      app.py            map, clause table, click-through to source page
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

python run_analysis.py     # the headline number, offline, ~1 minute
python verify_api.py       # every API claim we make, offline
python test_aggregate.py   # aggregation correctness
python test_claim.py       # the plan's 10 F claim vs measurement
python build_golden.py     # re-verify all 29 quotes against the PDF
streamlit run app.py       # map, clause table, provenance
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
  api_findings.md   everything we measured about the API
```

### Timezone

`time_of_measure` is UTC. **Arizona is UTC−7 year-round and does not observe
DST**, so UTC hour 22 is 15:00 local. The conversion lives in
`parse.utc_hour_to_phoenix`.

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
