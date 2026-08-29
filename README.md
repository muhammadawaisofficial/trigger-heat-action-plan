# TRIGGER — the Heat Action Plan Compiler

### **[▶ Open the live demo](https://trigger-heat.streamlit.app/)** · [Repository](https://github.com/muhammadawaisofficial/trigger-heat-action-plan)  ·  Video: _link pending_

Built on the **FortyGuard Temperature API**, provided by FortyGuard for FortyGuard Hackathon '26. Every temperature in this project was measured through that API: **125 calls, 11,189,301 tiles, 527,500 credits, across 58 distinct days.** No other weather, temperature, or climate source appears anywhere in the pipeline.

---

## 1,184,971 people — 72% of Phoenix

live in a neighbourhood that got hot enough to trigger the city's own Heat Action Plan, on nights the citywide reading never did. The plan stayed off. Ten of fifteen urban villages, across one measured heat event.

We compiled Phoenix's published Heat Response Plan into executable rules and re-ran every rule against FortyGuard's 2-metre data at 100-metre resolution, 272,917 tiles a day, then measured what a single station reading misses.

Verified end to end by `python verify_all.py`. The citywide comparator is a proxy, and a generous one, so this number is a lower bound.

> ## One flaw, two failure modes
>
> A heat trigger keyed to a single fixed number fails in both directions, and which way it fails depends on how severe the day is.
>
> It under-fires where the citywide reading sits below the threshold while neighbourhoods sit above it. 1,184,971 people, 72% of Phoenix, live in urban villages that met the city's own overnight-heat benchmark on days the citywide reading never fired.
>
> It over-fires where severity clears the threshold everywhere at once. On 27 of 35 clause-days, 77%, the plan gave no basis for choosing where to send anyone: it fired either almost everywhere or almost nowhere.
>
> Saturation causes both. A threshold only resolves variation it sits inside. Below that variation it under-fires. Above it, it over-fires.
>
> ---
>
> We ran the same pipeline, unchanged, on New York City. New York triggers on heat index where Phoenix triggers on dry-bulb air temperature, because New York is humid and Phoenix is arid. Each city made the right choice for its own climate, and both fail the same way.
>
> | | Phoenix | New York City |
> |---|---|---|
> | Citywide proxy, worst day | 89.9 °F | 99.0 °F |
> | Its own threshold | 90 °F | 100 °F |
> | Missed by | 0.1 °F | 1.0 °F |
> | Zones above it anyway | 10 of 15 | 13 of 51 |
> | People exposed | 1,184,971 | 2,453,713 |
> | Actionable clause-days | 23% | 24% |
>
> Two cities, opposite metrics, 3.6 million people between them missed the same way. The problem is not which metric a city picks. It is using one number for a whole city.

---

## How this project uses the FortyGuard API

The API is not a data source this project happens to read. It is the instrument the entire measurement is made with, and the analysis is designed around what it can do.

### What we call, and why each call is necessary

| Endpoint | Analytic | Calls | What it gives us |
|---|---|---|---|
| `/v1/heatmap` | `tcm` | 23 | Per-tile min, mean, and max temperature. Supplies the overnight-low benchmark that produces the headline, and the severity axis every clause is placed on. |
| `/v1/heatmap` | `exceedance` | 84 | Hours above a threshold per tile. Drives every duration-style clause and the event-selection scan across 46 candidate days. |
| `/v1/heatmap` | `persistence` | 18 | Longest unbroken run per tile. Probed across three consecutive Julys to establish its behaviour at each `filter_type` before relying on it. |
| `/v1/env_params` | wet-bulb, humidity | per metro | Wet-bulb temperature at 30 US metro centroids, which is what the evaporative-cooling decision in the siting model actually turns on. |

**11,189,301 tiles across 58 distinct days.** A single citywide request returns 272,917 tiles covering 1,053 mi² at 100-metre resolution, so the whole City of Phoenix is one call rather than fifteen.

### Where the API is called from

Four places, each for a different reason:

**The published analysis.** `run_analysis.py` fetches every day in the study window and evaluates all five clauses against it. This is what produced the 1,184,971 figure, and it is the same code path every other entry point below uses.

**Event selection.** `scan_event.py` scanned 1 July to 15 August 2025 day by day, ranking every day by hours above the 105 °F threshold the plan itself names, to choose the study window by measurement rather than assumption.

**The national panel.** `fetch_national.py` and `fetch_wetbulb.py` measure free-cooling hours, wet-bulb, and overnight lows across 30 US metros for the data-centre siting and urban-planning models.

**Any window, from the app.** Methods & Evidence carries a date-range picker spanning **2021-01-01 to yesterday** — any year, any month, any week. It runs the full pipeline over the chosen dates and writes a results file in the same shape as the published one, which then joins the study-window selector on the home page. A seven-day window is 14 calls: one shared `tcm` plus one `exceedance` per day, and the cost is shown before the run starts.

### How the calls are structured

Three measured properties of the API shaped the architecture:

**Credits are flat per call, 4,220, regardless of area.** A 420-tile request and a 272,917-tile request cost exactly the same. There is therefore never a reason to make a small request, and the pipeline makes one call per day covering the entire city rather than one per neighbourhood.

**The accepted area exceeds the documented cap.** The participant handbook gives the heatmap AOI limit as roughly 130 km², 50 mi². We measured **1,053 mi² and 272,917 tiles accepted in a single call**, repeatedly and without rejection, which is what makes citywide-in-one-request possible. The full size ladder is in [`docs/api_findings.md`](docs/api_findings.md); we report it because it is a useful measurement for FortyGuard as well as for us, and because a project built on the documented figure would make twenty calls where one suffices.

**The tile grid is byte-identical across calls sharing an AOI and granularity.** Geometry is 87% of the payload, so responses are stored with geometry once per grid and values columnar per request. On the probe set that is 265.7 MB reduced to 11.3 MB, with every response rebuilt into exactly the shape the API returned.

### Every response is kept

All 125 responses are committed to this repository, 63.5 MB across 126 files over 8 shared tile grids. Two consequences:

**The analysis is auditable.** `python verify_all.py` re-derives every published figure from those same responses and asserts each one, so a reader can confirm the headline rather than take it on trust.

**The analysis is extensible.** The stored responses are a saved copy of real API results, not baked-in data. Point the pipeline at a window it has not seen, with a key, and it calls the API for real — which is exactly how the August 2026 replication below was produced, on data the analysis had never seen.

---

## Who this is for, and how it deploys

### The user

**A city heat officer or emergency manager**, on the afternoon of a hot day, deciding where to open cooling centres and where to send welfare checks with a finite number of crews.

They already hold the legal authority and the budget. The plan already names them: `data/golden/` carries the owning department for every clause, taken from the plan's own department key. What they do not have is evidence about which neighbourhoods their trigger is missing, or a defensible order in which to deploy.

That is the gap this fills. The output is not a temperature map. It is a ranked list of neighbourhoods, each one citing the clause that obliges action, the page it appears on, the verbatim sentence, and the department that owns it.

Two secondary users, each served by a page of the app: **data-centre siting teams** choosing between US metros on cooling cost, and **urban-planning departments** allocating tree-canopy budgets between neighbourhoods rather than evenly across a city.

### What adoption looks like

Nothing here requires a city to change its plan. The three steps below are ordered by how much institutional commitment each needs.

**1. Audit, using what already exists.** Point the compiler at a published plan and the pipeline at last summer. It returns which clauses were missed, where, and for how many residents. No new sensors, no new procurement, no change to the plan. This is the state the repository is in today, for Phoenix and New York.

**2. Operate, in parallel with the existing trigger.** Run the analysis nightly on the previous day. Where a clause was met locally while the citywide trigger stayed quiet, that is a documented gap in an obligation the city already holds. The alert payload is machine-readable JSON and already names the department, so it drops into an existing dispatch or work-order system rather than needing a new one.

**3. Re-specify the trigger.** The percentile analysis shows a threshold fitted to a city's own distribution restores targeting in both failure directions. Changing a legal threshold is a policy act, not an engineering one, so this project measures the case for it and stops there.

### Why a city would pay for it

Cooling-centre operation, outreach, and emergency medical response are already budgeted. This changes where that spend lands, not how much of it there is. A city that can name the ten neighbourhoods its trigger misses can direct existing crews at them, and can defend that decision afterwards by citing its own plan.

The cost side is small: one API call per day per city at 100 m resolution covers 1,053 mi².

---

## Submission — FortyGuard Hackathon '26

Track 04, Government & Environment, primary.
Track 07, Data Analysis & Correlation, co-primary.
Track 05, Model Designing, supporting.

Track 04 names its own build examples as Heat Vulnerability Map and Climate Resilience Planner, and its technologies as Temperature API, Policy AI, GIS, Open Data. TRIGGER produces a heat vulnerability map by compiling published policy and evaluating it over GIS and open data, which answers the track's own brief directly.

We are not claiming Track 06, Agentic AI. There is no agent here, by design: every number is a deterministic comparison, and the language model's only job is to extract quotes and narrate verified results. It decides nothing.

| | |
|---|---|
| Thermal data | FortyGuard Temperature API only, no external weather source anywhere |
| API usage | 125 calls, 527,500 credits, 11,189,301 tiles, 58 distinct days |
| Scale | 272,917 tiles/day at 100 m over 1,053 mi² |
| Reproducibility | every response committed, verifiable in one command |
| Coverage | 2 cities, 3 analysed windows, 30-metro national panel |
| Tests | 117 automated tests, 12 end-to-end checks |

---

## Contents

| | |
|---|---|
| [How this project uses the API](#how-this-project-uses-the-fortyguard-api) | Every call, why it is made, and how the results are kept |
| [Who this is for, and how it deploys](#who-this-is-for-and-how-it-deploys) | The user, the adoption path, and why a city would pay for it |
| [1. Impact & relevance](#1-impact--relevance-40) | What we found and why it matters |
| [2. Technical execution](#2-technical-execution-35) | How it works, and what we measured about the API |
| [3. Innovation](#3-innovation-15) | Why compiling the document is the whole point |
| [4. Communication](#4-communication-10) | Reproducing every number here |
| [The precedent](#the-precedent-new-york-already-fixed-a-version-of-this) | A documented natural experiment: New York changed its threshold and hospitalisations fell |
| [Replication](#replication-on-live-2026-data) | The finding reproduced on data the pipeline had never seen |
| [The five pages](#the-five-pages) | What each page answers and what it is measured from |
| [5. Scope](#5-scope) | What this analysis covers, and what it does not |

---

## 1. Impact & relevance (40%)

### The gap, in the city's own words

Two sentences from the published plan frame the entire problem. Both are verbatim, both are page-anchored, and both are in `data/golden/`.

> "Historical development patterns and varying topography across Phoenix lead to neighborhood-to-neighborhood air temperature differences of 10°F or more on summer days."
> — 2026 Heat Response Plan, page 4

> "In 2025, 37% of heat-related deaths in Maricopa County occurred on days with the HeatRisk … designated … as Major or Extreme, and 63% of deaths occurred on days when the HeatRisk was designated as Moderate, Minor, or None."
> — page 9

The city knows heat is not a citywide quantity, and knows most heat deaths happen on days that never trigger a warning. Then every conditional clause in the plan is triggered by one number.

### What the plan actually conditions on

We compiled all 23 actions plus the plan's own planning benchmarks, 27 clauses in total, every one carrying a verbatim quote and a page number, every quote mechanically verified against that page.

| Clause kind | Count |
|---|---|
| Calendar-activated — runs on a date, not a temperature | 20 |
| Planning benchmark — a temperature with no action attached | 3 |
| Indoor habitability standard | 2 |
| Operative trigger — a temperature that causes an action | 1 |
| External trigger — NWS Extreme Heat Warning | 1 |

Twenty of twenty-three actions are not conditioned on heat at all. Of the two that are, both are scoped citywide: one reading decides for all 1,053 mi².

This is not a criticism of Phoenix's plan, which is one of the better heat plans in the United States and is improving. It is a measurement of where the instrumentation stops.

### Trigger Divergence

Study window 2–8 August 2025, selected by measurement (see [event selection](#event-selection)). Five clauses were evaluable against 2-metre data, across 15 urban villages and 272,917 tiles per day.

| Metric | Result |
|---|---|
| Population in silent zones | 1,184,971 — 72% of Phoenix |
| Silent zones | 10 of 15 urban villages |
| Silent zone-days | 20 |
| False-calm days | 3 of 7 (2, 5 and 8 August) |
| Median lead time | 4 days |

The three largest silent villages are Maryvale (226,766), North Mountain (173,875), and Camelback East (147,669). Population is joined from US Census ACS 5-year 2023 block groups, areally interpolated onto village boundaries. The 15-village total comes to 1,639,502 against Phoenix's approximately 1,608,000 at the 2020 census, which is the sanity check on the join.

The clause that carries the finding is the plan's own overnight-heat benchmark (page 6, "Nighttime temperatures failed to drop below 90°F at Sky Harbor on 23 days"). Overnight low, in Fahrenheit, by village. An asterisk marks the condition met.

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

The villages that meet the condition first and most often, Central City, South Mountain, Maryvale, Alhambra, Encanto, are the dense, built-out urban core. The ones that never do are the low-density northern and western fringe. The plan itself (page 4) identifies lower-income, lower-quality-housing communities as carrying a disproportionate share of the heat burden. The spatial pattern here is consistent with that, though we have not joined demographic data and do not claim to have measured it.

### Saturation, measured on tiles rather than zones

The over-trigger metrics are computed on all 272,917 tiles before any aggregation. Fifteen zone averages say nothing about whether the underlying field had structure, so aggregating first would hide exactly what this measures.

Full per-clause, per-day figures are in `data/results/divergence.json` under `saturation`. The sweep is in `data/results/severity_sweep.json`, and the citywide threshold sweep is in `data/results/threshold_sweep.json`.

### We tested the plan's own 10 °F claim

Page 4 asserts neighbourhood differences of "10°F or more." Measured at 100 m across the study window:

| Metric | Mean tile-level spread | Village-level spread |
|---|---|---|
| Overnight low | 21.2 °F | 7.4 °F |
| Daily mean | 14.4 °F | 4.0 °F |
| Daily high | 10.2 °F | 2.2 °F |

The claim holds and is conservative. The measured spread reaches or exceeds 10 °F on 18 of 21 day-metric combinations. The variability is largest overnight, when heat is most lethal and the urban heat island is strongest, and smallest at the daily peak, the metric heat plans usually trigger on.

```bash
python test_claim.py
```

---

## The precedent: New York already fixed a version of this

There is a documented natural experiment for exactly the kind of change this project argues for.

From 2001 to 2007 New York City activated its heat emergency plan on national National Weather Service criteria: a heat index of 40.6 °C, 105 °F, for one day. An evaluation found the system was not preventing heat-related mortality. The city replaced it with locally derived thresholds, 37.8 °C (100 °F) for one day, or 35 °C (95 °F) for two consecutive days, and the change had a measured health outcome:

> "The 40.6 °C threshold for one day was changed to a forecast maximum heat index of 37.8 °C for one day or more, or 35 °C for at least two consecutive days … The lower threshold reduced heat-related hospitalizations among older adults."
> — Kotharkar & Ghosh, *Effective heat action plans: research to interventions*, [Environmental Research Letters](https://iopscience.iop.org/article/10.1088/1748-9326/ab5ab0)

Three things follow.

First, trigger thresholds are not cosmetic. Changing a number in a document changed a hospitalization rate. That is the mechanism this project measures.

Second, one-size thresholds fail because they ignore local conditions. New York's problem was that a national criterion did not describe New York. The paper's own conclusion is that "one-size-fits-all approaches are less effective than solutions designed … with local stakeholders."

Third, and this is the part that carries the argument forward: New York fixed the between-city problem. Nobody has fixed the within-city one, and it survives the fix. The clauses we evaluate for New York are its post-change, epidemiologically derived thresholds, the improved rule, already validated against health outcomes. They still leave 16 community districts and 2,453,713 people meeting the condition on days the citywide reading never fired.

Lowering a citywide threshold is necessary but not sufficient, because a better single number is still a single number. The same reasoning that took New York from a national threshold to a city threshold, applied one level further down, takes a city threshold to a neighbourhood one. That is the step 2-metre data makes possible.

What we do not claim: New York's evidence is that 105 °F was too high for New York's climate. It does not follow that Phoenix's 105 °F trigger is wrong for Phoenix, a far hotter city, and we make no such claim. Our finding is about spatial resolution, not about any particular number.

---

## Replication on live 2026 data

The published result is one week of 2025. To test whether it is a property of the city or an artefact of that week, we re-ran the identical pipeline on 16–22 August 2026, fetched live from the API, on data the analysis had never seen.

| | 2–8 Aug 2025 (published) | 16–22 Aug 2026 (live) |
|---|---|---|
| Silent zones | 10 of 15 | 9 of 15 |
| Population exposed | 1,184,971 (72%) | 958,205 (58%) |
| Silent zone-days | 20 | 18 |
| False-calm days | 3 of 7 | 3 of 7 |
| Median lead time | 4 days | 5 days |
| Worst day | proxy 89.9 °F vs 90 °F, 10 villages over | proxy 89.4 °F vs 90 °F, 9 villages over |

The same structure appears a year later, including the same near-miss signature: the citywide average landing a fraction of a degree below the city's own threshold while nine or ten neighbourhoods sit above it.

Both windows are selectable in the app. The home page carries a study-window selector, and switching between them re-renders every figure on the page from that window's own data.

```bash
FORTYGUARD_API_KEY=... python run_analysis.py --start 2026-08-16 --end 2026-08-22
```

The API accepts any date from 2021-01-01 to twelve hours ahead of now, so this runs on next season as readily as on last. An independently reproduced finding is a research artefact rather than a demo result, which is why it gets its own section. The over-trigger half replicates too; `verify_all.py` asserts both windows.

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
                  app.py            landing page: the problem, the number, the
        │                           map, tonight's brief
                  pages/            heat waves · siting · urban planning ·
                                    methods & evidence (clause explorer,
                                    provenance, replication, custom windows)
```

The language model decides nothing. It extracts structure from the PDF and narrates finished results. Every FIRED/NOT FIRED determination, every threshold comparison, and every count in this document is deterministic code running over API responses.

### The anti-hallucination guarantee is architectural

Every clause the compiler proposes carries a verbatim quote and a page number. Before a clause can be evaluated, that quote is checked against the extracted text of the page it cites. A clause whose quote does not appear verbatim on its stated page is rejected and never reaches the evaluator.

A model that invents a citation produces nothing, not a wrong answer. The rejection rate is reported as an extraction-quality metric rather than hidden.

### The compiler, measured

The automatic compiler runs on Gemini 3.5 Flash via the free AI Studio tier, chosen deliberately. Because correctness is enforced by mechanical quote verification rather than by trusting the model, the compiler's guarantee does not depend on model quality. A weaker model scores lower on a number we publish. It cannot produce a confidently wrong citation.

Scored against the 27-clause hand-built golden set (`python eval_compiler.py`):

| | Result |
|---|---|
| Quote verification rate | 100% — 25 proposed, 25 verified, 0 rejected |
| Precision | 1.000 |
| Recall | 0.926 |
| F1 | 0.962 |
| Actions (narrative prose) | 24 / 24, 100% recall |
| Planning benchmarks (numbers in tables) | 1 / 3, 33% recall |

Field accuracy over matched clauses, reported strictly and after adjudication:

| Field | Strict | Adjudicated |
|---|---|---|
| `kind` (the five-way classification) | 100% | 100% |
| `source_page` | 100% | 100% |
| `metric` | 96% | 96% |
| `threshold_source` | 96% | 100% |
| `operator` | 88% | 96% |
| `actor` | 96% | 100% |
| `scope` | 72% | 96% |

The classification that drives the headline, conditional on heat versus calendar-activated, is 100% (25/25). The compiler independently reports 2 conditional and 20 calendar-activated actions, matching the hand-built set exactly.

Adjudicated means disagreements where the document genuinely supports both readings, listed individually in the eval output. Two examples, chosen because they cut against us:

For the cooling ordinance ("must be able to safely cool all livable rooms to 86°F"), we encoded the violation direction (above); the compiler encoded the requirement direction (below). Same rule, different convention.

For Action 4.2, the plan states no temperature. The compiler correctly emitted none. Our golden set adds a documented 110 °F proxy so the clause can be evaluated at all. Here the compiler is the more faithful reading, and our reference set is the one making an editorial choice.

The published analysis runs on the hand-verified golden set rather than raw compiler output, and the compiler's own score is reported alongside it rather than implying the pipeline is fully autonomous.

### The golden set, and what F1 0.962 means

The score above is only as good as the set it is measured against, so here is that set in full.

**What it is.** 27 clauses, hand-compiled from the published PDF: the plan's 23 numbered actions (24 clause records, one action splits into two), 3 planning benchmarks, and 2 indoor habitability standards. Every clause carries a verbatim quote and a page number, and `build_golden.py` mechanically asserts that all 29 quotes appear on their cited pages. It is committed at `data/golden/phoenix_2026_clauses.json`.

**How it was selected.** Exhaustively, not by sampling. We took every numbered action in the document plus every numeric temperature stated anywhere in it. There is no held-out split, because the population is the document. 27 clauses is the whole plan, not a sample of it.

**What the F1 supports.** That the compiler extracts narrative action clauses reliably and cites them verifiably: 24 of 24 actions recalled, 0 spurious clauses, 100% quote verification, and the conditional-versus-calendar classification correct on 25 of 25. That last figure is what the headline finding rests on.

**How to read the number.** With n = 27, one clause is worth 3.7 points of recall, so 0.962 is the right order of magnitude rather than a precise figure and should not be compared to scores computed on larger sets. The same two people built the golden set and the extraction prompt, so this is not independent annotation and no inter-annotator agreement is reported; every disagreement is listed individually instead, including those where the compiler is the more faithful reading. The compiler is measured on one document, one city, and one plan format.

### What we measured about the FortyGuard API

Five properties, each measured directly and each of which shaped the architecture. Full evidence in [`docs/api_findings.md`](docs/api_findings.md); reproduce with `python verify_api.py`.

| Property | Evidence | How the pipeline uses it |
|---|---|---|
| `tcm` tiles are returned in °C | Downtown Phoenix peaked at 40.3, i.e. 104.5 °F | One conversion, in `schema.f_to_c`, nowhere else |
| `persistence` is exact under `filter_type=3` | Same AOI, one day: 24.00 at 20 °C, 16.00 at 35 °C, 2.00 at 40 °C | Day-by-day evaluation with `filter_type=3` throughout |
| Accepted AOI reaches 1,053 mi² | 272,917 tiles accepted in a single call | One call per day for the whole city, not one per village |
| Credits are flat per call | 420-tile and 272,917-tile calls both cost 4,220 | Always request the full city; never split a request |
| The tile grid is byte-identical across calls | Same `tile_id` sequence and geometry, verified across calls differing only in threshold | Geometry stored once per grid; 265.7 MB reduced to 11.3 MB |

Day-by-day evaluation is also what the lead-time metric requires: a single multi-day aggregate collapses the time axis, and you cannot recover *when* a condition was first met from one number covering a week.

### Response storage

A 1,053 mi² call is 130 MB of raw JSON. Measured on this data, tile geometry is 87% of the payload, and the grid is byte-identical across every call sharing an AOI and granularity. So the cache stores geometry once per grid and values columnar per request: 265.7 MB becomes 11.3 MB on the probe set, a 23.5× reduction, with responses rebuilt into exactly the shape the API returned. Nothing downstream knows the difference.

That is what makes 125 real API responses committable to a repository, and what makes every published figure independently checkable.

### Verification

| Check | Command | Result |
|---|---|---|
| Aggregation vs brute force (no spatial index) | `python test_aggregate.py` | agree to 7.8 × 10⁻¹⁴ |
| Every golden quote appears verbatim on its page | `python build_golden.py` | 29 / 29 |
| API findings reproduce from stored responses | `python verify_api.py` | 5 of 5 |
| The plan's 10 °F claim | `python test_claim.py` | holds, conservative |
| Compiler vs golden set | `python eval_compiler.py` | P 1.000 / R 0.926 / F1 0.962 |
| Generated prose cannot invent a number | `python test_brief_guard.py` | rejection path demonstrated |
| Full automated suite | `python -m pytest tests/` | 117 passed |

### Event selection

The study window was chosen by measurement, not assumption. We scanned every day from 1 July to 15 August 2025 for hours above 105 °F, the threshold Action 1.1 of the plan actually names, and took the most severe consecutive seven days.

| Window | Total hours above 105 °F |
|---|---|
| 6–12 July | 46.7 |
| 2–8 August (selected) | 57.8 |

This independently corroborates the plan's own account of the season: it records the seasonal high of 118 °F at Sky Harbor on 7 August and calls August "the hottest month of the summer" (page 6). Our scan picks 7 August as August's most severe day from FortyGuard data alone.

```bash
python scan_event.py --start 2025-07-01 --end 2025-08-15
```

---

## 3. Innovation (15%)

Most heat-tech maps where it is hot and alerts someone. TRIGGER does something different: it adjudicates a legal document.

| The usual approach | TRIGGER |
|---|---|
| Map where it is hot | Determine which clauses of a real published plan are in force, where, and for whom |
| Alert when a threshold is crossed | Quantify what the existing official threshold has been missing |
| Rules hardcoded by the team | Rules compiled from the published PDF, page-anchored, with a measured extraction score |
| Rank by peak temperature | Rank by exceedance and overnight minimum, because that is what the clauses specify and where the signal is |

The last row is not a stylistic preference. On the same 420 tiles on the same day, daily-mean temperature spread 0.12 °C while hours-above-threshold spread 1.34 hours across 394 distinct values. Ranking neighbourhoods by peak temperature is ranking noise.

---

## 4. Communication (10%)

### Run it

```bash
pip install -r requirements.txt

python verify_all.py         # runs everything below and asserts the headline
python run_analysis.py       # the headline number
python verify_api.py         # every API property we report
python test_aggregate.py     # aggregation correctness (vs brute force)
python test_claim.py         # the plan's 10 F claim vs measurement
python test_brief_guard.py   # prove generated prose cannot invent a number
python eval_compiler.py      # compiler precision / recall / F1
python build_golden.py       # re-verify all 29 quotes against the PDF
python make_report.py        # regenerate the standalone research report
python make_brief.py         # regenerate the ranked action brief
streamlit run app.py         # the app: 5 pages, sidebar or top-strip nav
```

To analyse a window that is not already stored, set `FORTYGUARD_API_KEY` and pass dates:

```bash
FORTYGUARD_API_KEY=... python run_analysis.py --start 2024-07-08 --end 2024-07-14
```

The same is available inside the app, on Methods & Evidence, for any dates from 2021-01-01 to yesterday.

### Repository

```
src/
  cache.py           response storage, grid/value split, resilient polling
  schema.py          Clause dataclass + validation + the only F->C conversion
  parse.py           both tile schemas on one path
  geo.py             AOI construction, areas, [lon, lat] discipline
  aggregate.py       area-weighted tiles -> zones
  evaluate.py        clause x zone x day -> FIRED / NOT FIRED
  diverge.py         the three metrics
  compile.py         LLM extraction with mechanical quote verification
  study.py           city, AOI, zones, window: one source of truth
  liveconditions.py  the same evaluator, run on today, from the app
  customwindow.py    the same pipeline, run on any window, from the app
  liveprobe.py       one small on-demand call, for a fast liveness check
data/
  plan/          the source PDF
  golden/        27 hand-compiled clauses, every quote verified
  zones/         15 Phoenix urban villages (City of Phoenix Open Data)
  cache/         125 committed API responses
  results/       divergence.json and every analysed window
docs/
  trigger_divergence_report.md   the standalone research result
  action_brief.md                ranked actions, each citing clause/page/owner
  api_findings.md                everything we measured about the API
```

### Timezone

`time_of_measure` is UTC. Arizona is UTC−7 year-round and does not observe DST, so UTC hour 22 is 15:00 local. The conversion lives in `parse.utc_hour_to_phoenix`.

---

## The five pages

This document says "silent zone," the term the code and the schema use. The interface says "missed," because "silent zone" is our vocabulary and means nothing to someone reading the page for the first time. They are the same set, computed the same way: a zone that met a clause's condition on a day the citywide proxy did not fire.

| Page | Question | Measured by us | Taken from published sources |
|---|---|---|---|
| Divergence (home) | Who does the citywide trigger miss? | tiles → zones, per clause, per day | plan thresholds, population |
| Heat waves | Which neighbourhoods are in one, since when? | per-zone temperature per day | danger tiers, structured after NWS HeatRisk |
| Data centre siting | Where is cooling cheapest nationally? | free-cooling hours, wet-bulb, overnight low | electricity price, water stress, disaster risk (state level) |
| Urban planning | How much intervention, and where? | thermal gap, per zone and per metro | canopy and albedo effect sizes |
| Methods & evidence | How exactly was this computed? | clause-level detail, API properties, custom windows | — |

### Heat waves

A heat wave is a run, not a hot day, and it does not start on the same night across a city. The page leads with a threshold ladder: the same week, the same zones, the same measurements, detected against each threshold in turn.

At 90 °F that week is 10 heat waves covering 1,184,971 residents. At 110 °F it is zero. Nothing about the weather changes down that table. Only the number written in the plan changes.

It reports two bases side by side: the absolute threshold, which is what plans govern on, and a percentile of the city's own distribution, which is what the epidemiological literature uses, because the temperature at which people begin dying is relative to what they are acclimatised to. Danger tiers are keyed to overnight low, since mortality tracks the failure to cool at night rather than the daytime peak.

**Detection, not forecast.** The page identifies which neighbourhoods were in a heat wave and from which night, in measured data, and ranks 30 US metros by how dangerous their nights run. The API serves measured history and about twelve hours forward, so a multi-day prediction is not something this data supports and none is shown. A forecast product would need a numerical weather prediction feed joined to the hyperlocal layer, which is a real design and simply not this one.

### Data centre siting

**Why it is needed.** Cooling is the largest controllable operating cost in a data centre and the siting term measured worst. Every published free-cooling figure is a city average: Phoenix around 1,000 to 2,000 hours a year, Minneapolis 4,000 to 6,000. Nobody sites a building on a city average, and the difference between two sites inside the same metro is invisible at that resolution.

**How the API answers it.** Every thermal term is measured by us across 30 US metros at full resolution, one call per metro because credits are flat regardless of area:

| Term | How it is measured |
|---|---|
| Free-cooling hours | `exceedance` with `direction="below"` against the ASHRAE 24 °C setpoint — the first use of the below direction in this project |
| Overnight lows and daily highs | `tcm`, per tile, aggregated per metro |
| Wet-bulb temperature | `/v1/env_params` at each metro centroid |

Wet-bulb is what the evaporative-versus-mechanical decision actually turns on, which is why it is measured rather than assumed. The result is the industry's central trade-off, quantified: the metros where evaporative cooling works best are frequently the ones least able to spare the water.

**The weights are user-controlled.** The model scores each metro on five factors — power, cooling, water, disaster risk, and renewable access — and every weight is a slider on the page. Power is weighted highest by default because published surveys put it first, but a bank, a hyperscaler, and a sovereign-cloud operator weigh these differently. Moving a slider recomputes the ranking, the recommended cooling strategy, and the cost model on the reader's priorities rather than ours.

The model emits a recommended cooling strategy per site rather than a single composite score, because the right answer differs by climate: air-side economiser where there are enough hours below the setpoint, evaporative where wet-bulb is low and water is available, air-cooled where wet-bulb is low but water is constrained.

### Urban planning

**Why it is needed.** Heat kills more people than any other weather hazard, and the remedy is physical: shade, tree canopy, reflective surfaces. Cities already know that. What a citywide average cannot tell them is *how much*, and *in which neighbourhood* — so mitigation budgets get spread evenly across places that are not equally hot, and the hottest blocks stay hottest.

**How the API answers it.** Intervention has to be aimed at a thermal gap, and the gap has to be measured before it can be closed. We measure it through `tcm` at 100 m: per neighbourhood inside a city, and across 30 US metros as the spread between the hottest and coolest ground inside each sample box. That measured gap is then joined to published cooling effect sizes, which is what lets a recommendation carry a magnitude instead of being general advice.

Generic advice, plant trees, raise albedo, is not wrong. It is unquantified: it never says how much, or where. This page joins a measured thermal gap to published effect sizes so every recommendation carries a magnitude: canopy at 0.3 °C per 10 points of added cover, cool roofs at 0.3 °C in residential deployment. Both are the conservative end of the published range, chosen because they generalise across a 30-metro panel; Phoenix-specific work reports up to 2.0 °C for canopy, and full canopy against treeless ground reaches 5.5 °C.

Ranking a city's own zones weights measured heat by residents, since temperature alone ranks empty ground above a dense neighbourhood. That puts Maryvale first, the neighbourhood already identified in the literature as Phoenix's most heat-vulnerable, reached here from measurement rather than assumed.

### Methods & evidence

The page a reader uses to check the headline rather than trust it. It carries every compiled rule beside the verbatim sentence and page number it came from, the map at clause resolution, the machine-readable alert payload, the New York replication, the five properties we measured about the API, and a date picker that runs the full analysis on any window from 2021-01-01 to yesterday.

Intra-metro spread is computed over every tile in a 10 km box, and that box contains whatever is inside it, including water and terrain. What spread measures is the range of thermal conditions a single citywide number is standing in for, which is the claim this project makes.

---

## 5. Scope

Written plainly, because these define how the result should be read.

**The baseline is a proxy for station-based sensing.** Our comparator is the area-weighted mean over the full city AOI: a best-case single-number sensor, perfectly sited and perfectly representative. A real airport station is less representative than this, so the divergence reported here is a lower bound rather than an estimate of the true gap against Sky Harbor. This is labelled everywhere it appears, in the code and in the output.

**Both arms use the same data, so a systematic offset cancels.** The plan records 110 °F on 37 days in 2025 and a peak of 118 °F at Sky Harbor, which is open tarmac and a documented hotspot; FortyGuard's 2-metre model over the built-up downtown reads cooler than that. Because per-village and citywide-proxy arms are computed from the same measurements, any offset appears in both and cancels in the difference. What it does affect is threshold selection: clauses between 95 °F and 107 °F sit inside the model's dynamic range and are where the analysis has power.

**Urban villages are large.** They average 10 to 68 mi², which smooths heavily: village-level overnight spread is 7.4 °F against 21.2 °F at 100 m tile scale. Finer zones would diverge more, not less, which is another reason the headline is a lower bound.

**Area weighting is used because it is correct.** Measured against a naive centroid-in-polygon lookup at 100 m the difference is about 0.0001 °C, so we use it as the correct operation rather than claiming it as a differentiator.

**Population is areally interpolated.** Village populations come from Census block-group totals apportioned by overlap area, which assumes uniform density within a block group. Block groups are small by design (600 to 3,000 people) and Phoenix village boundaries largely follow the same arterial grid. The 15-village total of 1,639,502 against Phoenix's approximately 1,608,000 at the 2020 census is the check on the join.

**Two cities, three analysed windows, one plan format.** The compiler is city-agnostic — only the AOI, the zone file, and the PDF change — and has been demonstrated on Phoenix and New York.

**Action 4.2 uses a proxy threshold.** The plan states no temperature for "when the National Weather Service issues an Extreme Heat Warning." We map it to 110 °F, anchored to the plan's own pairing on page 6 (37 days at or above 110 °F against 31 Extreme Heat Warning days). The clause carries `extraction_conf = 0.70` and its result should be read as indicative.

**A heat-index trigger is the natural next step.** Replacing dry-bulb temperature with `heat_index_celsius` or `apparent_temperature_celsius` from `/v1/env_params` is the obvious extension, and humidity is what makes Phoenix nights lethal. `env_params` is a per-point endpoint, so a gridded comparison is a larger measurement campaign than this window covers.

---

## Data provenance

Every thermal number in this project comes from the FortyGuard Temperature API. No external weather, temperature, or climate service is called anywhere in the pipeline. The Sky Harbor figures quoted in our analysis (110 °F on 37 days, 118 °F peak, 90 °F overnight lows) are quoted from the plan PDF itself, page 6, as the document's own account of the season, not fetched from a meteorological source.

Three non-FortyGuard inputs are used, each because it supplies something outside the API's remit.

| Input | Source | Why it is necessary |
|---|---|---|
| Zone boundaries | City of Phoenix Open Data, "Villages" | Aggregation units and named jurisdictions. Static, downloaded once, committed. |
| Population | US Census ACS 5-year 2023 + TIGERweb geometry | Converts silent zones into people. Static, committed. |
| Clause extraction | Google Gemini (free tier) | Reads the PDF. Output is committed; the published analysis runs from it directly. |

None of these is a temperature source, and none substitutes for any FortyGuard capability.

## Sources

- City of Phoenix 2026 Heat Response Plan DRAFT (2.13.2026), [phoenix.gov](https://www.phoenix.gov/content/dam/phoenix/heatsite/documents/2026%20Heat%20Response%20Plan.pdf)
- Phoenix urban village boundaries, [City of Phoenix Open Data](https://www.phoenixopendata.com/dataset/villages)
- FortyGuard Temperature API, [api.fortyguard.com](https://api.fortyguard.com)
- US Census ACS 5-year 2023 (table B01003_001E) and TIGERweb ACS2023 block groups

## Acknowledgment

Every temperature measurement in this project was made through the FortyGuard Temperature API, provided by FortyGuard (Abu Dhabi) to participants of FortyGuard Hackathon '26. The API is the sole source of thermal data throughout the pipeline, at every stage from event selection to the published headline to the live views in the app. This project exists because that access was made available for it.

Built for the FortyGuard Hackathon '26. Tracks: 04 Government & Environment (primary), 07 Data Analysis & Correlation (co-primary), 05 Model Designing (compiler extraction score).
