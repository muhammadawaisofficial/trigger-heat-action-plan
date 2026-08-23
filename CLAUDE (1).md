# TRIGGER — Heat Action Plan Compiler

> Read this file fully before writing code. It contains API constraints that are
> not in your training data and that fail **silently** if ignored.

---

## 1. What we are building

Cities have Heat Action Plans: legal documents with numeric temperature
thresholds and named officers responsible for acting when those thresholds are
crossed. They are triggered by **one citywide reading**, usually from an airport
weather station.

Heat is not a citywide quantity. So the plan fires late in some neighbourhoods
and never fires at all in others. Nobody measures this, because measuring it
needs temperature data at the resolution people live at.

**TRIGGER compiles a published Heat Action Plan into machine-readable rules,
re-evaluates every clause against FortyGuard's 2-metre data, and quantifies the
gap.**

Pipeline:

```
Phoenix Heat Response Plan (PDF)
        |
   [A] COMPILE      -> rule objects, page-anchored, confidence-scored
        |            -> human review UI (accept / edit / reject)
   [B] EVALUATE     -> per clause x per zone: FIRED / NOT FIRED
        |            -> persistence + exceedance + time_of_measure + env_params
   [C] DIVERGE      -> hyperlocal result vs citywide-proxy baseline
        |            -> lead time gained | silent zones | false-calm clauses
   [D] BRIEF        -> ranked actions w/ clause citation, zone, window, owner
```

**Demo city:** Phoenix, Arizona (Maricopa County).
**Source document:** City of Phoenix 2026 Heat Response Plan —
`https://www.phoenix.gov/content/dam/phoenix/heatsite/documents/2026%20Heat%20Response%20Plan.pdf`
(23 specific actions across 8 strategies; ships a department key mapping
abbreviations to owning departments — that is our `actor` field, pre-structured.)

---

## 2. Context: this is a hackathon submission

**FortyGuard Hackathon '26. Deadline 30 Aug 2026, 11:59 PM GST.**
Team of two. Judged by FortyGuard engineers.

Scoring weights — optimise against these, in this order:

| Weight | Criterion | What it means for our code |
|--------|-----------|----------------------------|
| **40%** | Impact & Relevance | One quantified headline number beats any feature |
| **35%** | Technical Execution | Correctness and reproducibility over polish |
| 15% | Innovation | Already secured by the concept — do not chase it |
| 10% | Communication | README + video; budget real time for these |

Tracks: **04 Government & Environment** (primary), **07 Data Analysis &
Correlation** (co-primary), **05 Model Designing** (supporting — the compiler's
measured extraction accuracy). We do *not* lead with Track 06 Agentic AI; it is
the most saturated track in the competition.

**Competitive position:** ~70% of the field is building heat maps with an LLM
alert layer. We are the only entrant compiling policy documents. Protect that
distinction in every design decision — when in doubt, invest in the compiler and
the measurement, not the interface.

---

## 3. The headline metric — this is the deliverable

Everything else is scaffolding. Three sub-metrics, computed over one historical
heat event:

| Metric | Definition |
|--------|------------|
| **Lead time gained** | Median hours between when a clause's condition was first met in a zone and when the citywide trigger fired |
| **Silent zones** | Count of zones — and population in them — where the condition was met but the citywide trigger never fired |
| **False-calm clauses** | Clauses that never activated under citywide sensing but would have activated N times under hyperlocal sensing |

**Baseline honesty rule:** our "citywide" comparator is the area-weighted mean
over the full city AOI, used as a *proxy* for station-based sensing. It is not a
real station feed. Label it as a proxy in the UI, the README, and the video.
Never let generated text imply otherwise.

---

## 4. FortyGuard API contract — verified from client source

Base URL `https://api.fortyguard.com`. Auth header is **`api-key`**, not Bearer.

**Import the official client. Do not write an HTTP layer.**
Start from `github.com/FortyGuard-Tech/temperature-api-quickstart`; it already
handles submit-and-poll, retries and validation.

### create_heatmap — POST /v1/heatmap

```python
create_heatmap(
    polygon_aoi, start_date, filter_type,
    granularity=100, start_time=None, end_time=None, end_date=None,
    analytic_type="tcm", threshold=None, direction=None,
)
```

| analytic_type | Returns | Requires |
|---|---|---|
| `tcm` | snapshot temperature, tiles in **°F** | — |
| `time_of_measure` | **UTC** hour-of-day 0–23 of each cell's peak | — |
| `exceedance` | **count of hours** past threshold (NOT degree-hours) | threshold + direction |
| `persistence` | **longest continuous run** of such hours | threshold + direction |

- `threshold` is in **°C** (API default 30). `direction` is `"above"` or `"below"`.
- `filter_type`: 1 = single hour, 2 = range of hours, 3 = single day,
  4 = range of days (needs `end_date`). **We use 4.**
- `granularity`: only **60, 80, or 100** metres. Explore at 100.

### Response shapes — handle both from the first commit

```
analysis types:  properties = {tile_id, value}
                 stats_data = {activity_id, analytic_type, units:"hour",
                               n_cells, min, max, mean}

tcm:             properties = {tile_id, average_temperature,
                               min_temperature, max_temperature}
                 stats_data = {temperature_stats:{...}, ...}

geometry:        Polygon, coordinates in [lon, lat] order (GeoJSON), NOT [lat, lon]
```

### env_params — POST /v1/env_params

Requires `latitude`, `longitude`, `temperature` (passed *in*), `date_time`.
Optional `analysis` list. Exact accepted strings:

```
heat_index_celsius, apparent_temperature_celsius, wet_bulb_temperature_celsius,
relative_humidity_percent, precipitation_mm, cloud_cover_octas,
air_quality:idx, air_quality_no2:idx, air_quality_o3:idx,
air_quality_pm2p5:idx, air_quality_pm10:idx, air_quality_so2:idx,
aqi_us_co, methane_ppb, co2_ppm, elevation, solar_irradiance
```

### Premium-gated (verify our tier before designing around these)

`/v1/satellite`, `/v1/streetview`, `/v1/heat_intelligence`.

---

## 5. Traps that fail silently — read twice

1. **Unit chain.** Phoenix plan states thresholds in **°F**. API `threshold` is
   **°C**. `tcm` tiles come back in **°F**. Convert exactly once, in
   `schema.py`, and nowhere else. Store both `threshold_source` (°F as written,
   for provenance) and `threshold_c` (converted, for the API). Sending 95
   instead of 35.0 computes hours above 95 °C and returns all zeros.

2. **UTC vs local.** `time_of_measure` is **UTC**. Phoenix is **UTC−7 all year
   (Arizona does not observe DST)**. UTC hour 22 = 3 PM local. Convert, and
   note the conversion in the README.

3. **Schema divergence.** Code written against `tcm` finds nothing on an
   exceedance response — the field is `properties.value`, not
   `average_temperature`. One parser, both paths.

4. **Exceedance is a count of hours.** A value of 6.0 means six hours past
   threshold. It is not 6 °C·h and not a temperature.

5. **Status 404s briefly** right after submit (eventual consistency). Retry
   until the deadline; do not treat as failure.

6. **Aggregation.** Tiles do not align to administrative boundaries.
   Nearest-tile lookup silently discards most of a zone. Use **area-weighted
   mean over every overlapping tile**, weighted by overlap area.

7. **Credits.** Failed tasks are free; credits deduct only on Completed. Cheap
   to retry, expensive to succeed carelessly.

---

## 6. Repo structure

```
trigger/
  fortyguard/          # vendored official client — do not modify
  src/
    cache.py           # disk cache, keyed on hash of request payload
    schema.py          # Clause dataclass + validator + °F→°C conversion
    compile.py         # PDF -> clauses (LLM extraction + provenance)
    parse.py           # response -> tiles (handles both schemas)
    aggregate.py       # tiles -> zones (area-weighted)
    evaluate.py        # clause x zone -> FIRED/NOT FIRED + margin
    diverge.py         # the three metrics
    brief.py           # LLM narration over verified results ONLY
  data/
    cache/             # committed — demo must run offline
    plan/              # Phoenix Heat Response Plan PDF
    golden/            # hand-compiled clauses (eval set)
    zones/             # Phoenix administrative boundaries
  app.py               # Streamlit UI
  eval_compiler.py     # precision/recall vs golden set
  README.md
```

### Clause schema

```python
@dataclass
class Clause:
    clause_id: str            # "PHX-2026-S3-A07"
    source_text: str          # verbatim, mandatory
    source_page: int          # mandatory
    metric: str               # "air_temperature" | "heat_index" | ...
    operator: str             # "above" | "below"
    threshold_source: float   # as written, °F
    threshold_c: float        # converted, sent to API
    duration_hours: int | None
    scope: str                # "citywide" | "district" | "site"
    actor: str                # from the plan's department key
    action: str
    lead_time_req_h: int | None
    extraction_conf: float
    extraction_note: str      # e.g. "duration inferred from 'sustained'"
```

---

## 7. Build order and acceptance criteria

Build strictly in this order. Do not start a stage before the previous one
passes its criterion.

| # | Component | Done when |
|---|-----------|-----------|
| 1 | `cache.py` | Every API response written to disk on first call; second run makes zero network calls |
| 2 | `schema.py` | Clause validates; °F→°C round-trips; conversion exists in exactly one place |
| 3 | `parse.py` | Both response schemas parse; geometry read as [lon, lat] |
| 4 | `compile.py` | Extracts clauses with verbatim quote + page for every field |
| 5 | `eval_compiler.py` | Reports precision/recall against the golden set |
| 6 | `aggregate.py` | Area-weighted, verified against a hand-computed zone |
| 7 | `evaluate.py` | Any clause returns FIRED/NOT FIRED per zone with margin |
| 8 | `diverge.py` | **THE NUMBER EXISTS. Hard gate.** |
| 9 | `app.py` | Map + clause table + divergence panel + click-through to source page |
| 10 | `brief.py` | Ranked actions, each citing clause + page + owner |

**Hard gate:** if `diverge.py` is not producing a number by end of 26 August,
stop adding features and ship the measurement.

---

## 8. Rules

**Do:**
- Cache on the first call, always. Commit the cache. The demo must run with no
  API key — judges will clone and run it.
- Keep all decision logic deterministic. The LLM extracts (with mandatory
  verbatim quoting) and narrates. It decides nothing.
- Explore at granularity 100. Spend 60 only on zones appearing in the video.
- Write the limitations section honestly. Engineer judges reward it.

**Do not:**
- Write a new HTTP client. Import theirs.
- Use browser storage APIs.
- Build a 3D globe. 2D map only.
- Build an open-ended natural-language input. Use 3–5 preset missions.
- Call the API live during demo recording — polling takes minutes and will look
  broken.
- Let generated prose state a conclusion that is not in the computed results.

**Cut first if behind:** counterfactual engine, then satellite layer, then the
action brief. Never cut the divergence metric or the offline cache.

---

## 9. Definition of done

- [ ] A judge clones the repo and reproduces the headline number offline, one command
- [ ] Compiler extraction accuracy measured and reported, not asserted
- [ ] Every recommendation traces to a clause, a page, and a verbatim sentence
- [ ] Citywide baseline labelled as a proxy everywhere it appears
- [ ] README structured against the four judging criteria and their weights
- [ ] Video under three minutes, headline number in the first thirty seconds
