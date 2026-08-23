# Trigger Divergence: what one thermometer costs Phoenix

**A measurement of the gap between a Heat Action Plan as written and the Heat Action Plan as sensed.**

City of Phoenix · study window 2025-08-02 to 2025-08-08 · 15 urban villages · FortyGuard 2-metre data at 100 m

---

## Abstract

Phoenix's 2026 Heat Response Plan contains 27 compiled clauses across 23 published actions. Only **2** are conditioned on temperature at all; **20** activate on the calendar. Both conditional clauses are scoped citywide, so a single reading decides for all 1,053 square miles.

We compiled the plan into executable rules and re-evaluated every evaluable clause against FortyGuard's 2-metre data, once per urban village and once against a citywide average, over the most severe seven-day window of the 2025 heat season.

**1,184,971 people — 72% of Phoenix — live in the 10 urban villages that met the City's own overnight-heat benchmark on days the citywide reading never fired.**

On 2025-08-08 the citywide average overnight low read **89.9 °F** — 0.1 °F below the 90 °F benchmark the plan sets for itself. Nothing fired. **10 of 15 villages were above it**, the highest at 93.9 °F.

---

## 1. Method

### 1.1 Two arms, one dataset

Both arms are computed from the same FortyGuard responses. They differ only in spatial resolution:

| Arm | Definition |
|---|---|
| **Hyperlocal** | Each urban village, area-weighted over every tile that overlaps it (2,800–18,000 tiles per village) |
| **Citywide proxy** | One number for the whole AOI, area-weighted over all 272,917 tiles |

Because both arms draw on the same data, any systematic calibration offset against ground observation appears in both and cancels in the difference. The result depends only on the model resolving relative spatial structure, not on its absolute accuracy.

### 1.2 The baseline is a proxy, and it is generous

The comparator is **not a station feed**. It is the area-weighted mean over the entire city — a best-case single sensor: perfectly sited, perfectly representative, with no instrument bias and no siting artefact. A real airport station is strictly less representative than this.

**Every divergence figure in this report is therefore a lower bound** on the gap against actual station-based sensing.

### 1.3 Event selection

The window was chosen by measurement. We scanned every day from 1 July to 15 August 2025 for hours above 105 °F — the threshold Action 1.1 of the plan names — and selected the most severe consecutive seven days.

| Window | Total hours above 105 °F |
|---|---|
| 6–12 July | 46.7 |
| **2025-08-02 – 2025-08-08** | **57.8** (selected) |

This corroborates the plan's own account independently: the document records the seasonal high of 118 °F at Sky Harbor on 7 August and calls August the hottest month of the summer (page 6). Our scan identifies 7 August as August's most severe day from FortyGuard data alone.

### 1.4 Determinations are deterministic

Every FIRED / NOT FIRED result is a threshold comparison in code. No language model produces, ranks or adjusts any number in this report. The model's only role is extracting clause structure from the PDF, and its output is verified mechanically before use (§4.2).

---

## 2. Results

| Metric | Result |
|---|---|
| **Population in silent zones** | **1,184,971 (72% of Phoenix)** |
| **Silent zones** | **10 of 15 urban villages** |
| **Silent zone-days** | **20** |
| **False-calm days** | **3 of 7** |
| **Median lead time** | **4 days** |

Definitions. A **silent zone** is a village that met a clause's condition on a day the citywide proxy did not. A **false-calm day** is a day on which the proxy read below threshold while at least one village read above it. **Lead time** is the gap between a village first meeting a condition and the citywide number first meeting it.

### 2.1 The clause that carries the finding

`PHX-2026-BENCH-LOW90` — the plan's own overnight-heat benchmark, page 6:

> *“Nighttime temperatures failed to drop below 90°F at Sky Harbor on 23 days, including a seasonal high overnight low of 95°F on July 10.”*

Threshold 90 °F (32.22 °C). Overnight low by village, °F. `*` marks the condition met:

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

Silent zones by population:

| Village | Population |
|---|---|
| Maryvale | 226,766 |
| North Mountain | 173,875 |
| Camelback East | 147,669 |
| Alhambra | 143,242 |
| South Mountain | 125,391 |
| Estrella | 101,765 |
| Ahwatukee Foothills | 80,249 |
| Laveen | 68,819 |
| Central City | 59,945 |
| Encanto | 57,250 |
| **Total** | **1,184,971** |

### 2.2 Clauses outside the data's range

Two clauses returned zero in **both** arms and are reported as null results rather than omitted:

- `PHX-2026-A4.2` (110 °F) — the model does not reach this threshold anywhere in Phoenix during the window. See the calibration limitation in §5.
- `PHX-2026-BENCH-HIGH110` (110 °F) — the model does not reach this threshold anywhere in Phoenix during the window. See the calibration limitation in §5.

---

## 3. What the plan actually conditions on

| Clause kind | Count |
|---|---|
| Calendar-activated — runs on a date, not a temperature | **20** |
| Planning benchmark — a temperature with no action attached | 3 |
| Indoor habitability standard | 2 |
| Operative trigger — a temperature that causes an action | **1** |
| External trigger — an advisory issued by another agency | **1** |
| **Total compiled** | **27** |

Of the 2 clauses conditioned on heat, 2 are scoped citywide.

This is not a criticism of Phoenix. Its plan is among the more developed municipal heat plans in the United States and improves annually. It is a measurement of where the instrumentation stops.

---

## 4. Validation

### 4.1 The plan's own claim about spatial variability

Page 4 of the plan states that development patterns and topography produce *“neighborhood-to-neighborhood air temperature differences of 10°F or more on summer days.”* Measured over the study window:

| Metric | Mean tile spread (100 m) | Mean village spread |
|---|---|---|
| **Overnight low** | **21.2 °F** | 7.4 °F |
| Daily mean | **14.4 °F** | 4.0 °F |
| Daily high | **10.2 °F** | 2.2 °F |

The City's claim holds and is conservative. The variability is largest **overnight**, when heat is most lethal and the urban heat island is strongest, and smallest at the daily peak — the metric heat plans usually trigger on.

Village-level spreads are much smaller because a village averages 10 to 68 square miles. That smoothing is a property of using administrative units and is a second reason the headline is a lower bound: finer zones would diverge more, not less.

### 4.2 The compiler, measured

Extraction runs on **gemini-3.5-flash** via the free Google AI Studio tier. Correctness does not depend on model quality: every proposed clause carries a verbatim quote and a page number, and is rejected unless that quote is found verbatim on that page. A model that invents a citation produces nothing, not a wrong answer.

| | Result |
|---|---|
| Quote verification rate | **100%** (25 proposed, 25 verified, 0 rejected) |
| Precision / Recall / F1 | **1.000 / 0.926 / 0.962** |
| Actions (narrative prose) | **24 / 24 — 100% recall** |
| Planning benchmarks (tabular) | 1 / 3 |
| `kind` classification | **100%** |
| Conditional vs calendar | **100%** |

**Stated weakness.** The compiler recovers every published action but misses two of three planning benchmarks, including the one this report's headline rests on. Numbers embedded in tables and season-review prose are materially harder than numbers in action narratives. The analysis above therefore runs on the hand-verified golden set, not on raw compiler output.

### 4.3 Aggregation

Tile-to-zone aggregation is area-weighted over every overlapping tile. Verified against a brute-force recomputation with no spatial index: agreement to 7.8 × 10⁻¹⁴ (`python test_aggregate.py`). Measured against a naive centroid-in-polygon lookup the difference is ~0.0001 °C at 100 m, so we use area weighting because it is correct, not because it changes the result.

---

## 5. Limitations

**The baseline is a proxy.** Stated in §1.2 and repeated here because it is the most important caveat: our comparator is an idealised citywide mean, not a station feed. The direction of the error is known — it makes our result conservative.

**The model reads cooler than the Sky Harbor station.** The plan records 110 °F on 37 days of 2025 and a peak of 118 °F. FortyGuard's 2-metre model over downtown Phoenix does not reach 110 °F in the whole of July. Sky Harbor is open tarmac and a documented heat-island hotspot, so part of this gap is likely real; part may be model smoothing. We cannot separate them. The operational consequence is that clauses keyed to 110 °F return zero in both arms and carry no signal, which is why the two such clauses appear as null results in §2.2. Clauses between 95 °F and 107 °F sit inside the model's dynamic range.

**Zones are large.** Urban villages average 10 to 68 mi². Finer zones would show greater divergence.

**Population is interpolated.** Village populations are Census block-group totals apportioned by overlap area, assuming uniform density within a block group. The 15-village total of 1,639,501 against Phoenix's ~1,608,000 at the 2020 census is the check that it is not badly wrong.

**One city, one plan, seven days.** The compiler is city-agnostic — only the AOI, the zone file and the PDF change — but it has been demonstrated on Phoenix alone.

**Association, not attribution.** The villages meeting conditions earliest are the dense, built-out urban core. The plan itself (page 4) identifies lower-income communities as bearing a disproportionate heat burden. We have not joined demographic data beyond population counts and make no causal claim.

---

## 6. Reproduction

Every figure above regenerates offline, with no API key of any kind:

```bash
pip install -r requirements.txt
python run_analysis.py      # the headline number
python test_claim.py        # §4.1, the plan's 10 °F claim
python eval_compiler.py     # §4.2, extraction score
python test_aggregate.py    # §4.3, aggregation correctness
python verify_api.py        # measured API behaviour
python make_report.py       # regenerates this document
```

The committed cache is 63 MB covering 120 API responses. **All thermal data comes from the FortyGuard Temperature API; no external weather or temperature service is used anywhere in the pipeline.**

## Sources

- City of Phoenix 2026 Heat Response Plan DRAFT (2.13.2026) — [phoenix.gov](https://www.phoenix.gov/content/dam/phoenix/heatsite/documents/2026%20Heat%20Response%20Plan.pdf)
- Zone boundaries: City of Phoenix Open Data, 'Villages' (https://www.phoenixopendata.com/dataset/villages)
- Population: US Census ACS 5-year 2023 (B01003_001E), TIGERweb ACS2023 block groups
- Thermal data: FortyGuard Temperature API

*Generated by `make_report.py` on 2026-08-23. Every figure is read or computed from the pipeline's result files; none is transcribed by hand.*
