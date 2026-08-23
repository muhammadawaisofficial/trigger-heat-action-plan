# Measured behaviour of the FortyGuard Temperature API

Everything below was measured against the live API and is reproducible offline
from the committed cache:

```
python verify_api.py
```

Three of these findings contradict the published documentation or the official
quickstart. Each one would fail **silently** — returning plausible numbers that
are wrong — so each is stated with the evidence that settles it.

Measurements were taken on the Hackathon plan between 22 and 23 August 2026,
over Phoenix, Arizona.

---

## 1. `tcm` tiles are Celsius, not Fahrenheit

The official quickstart README states that `tcm` tiles are returned in °F. They
are returned in **°C**. The API reference documentation is correct on this
point; the quickstart is not.

Downtown Phoenix, 2 km box, 2025-07-15, granularity 100:

| Field | min | max | spread |
|---|---|---|---|
| `min_temperature` | 32.67 | 33.14 | 0.47 |
| `average_temperature` | 36.91 | 37.02 | 0.12 |
| `max_temperature` | 40.11 | 40.30 | 0.18 |

A daily maximum of 40.3 is 104.5 °F, which is correct for Phoenix in mid-July.
Read as Fahrenheit it would mean the city peaked at 40 °F.

**Consequence for TRIGGER.** The Phoenix plan writes every threshold in °F. The
conversion to °C happens in exactly one function, `schema.f_to_c`, and the
Celsius value is only ever produced by the `Clause.threshold_c` property. No
other module converts anything.

---

## 2. `persistence` saturates at 8.0 under `filter_type=4`

This is the most consequential finding, and it is invisible unless you probe it
with a threshold low enough that you already know the answer.

Downtown Phoenix 2 km box, 2025-07-08 to 2025-07-14 — a 168-hour window —
`filter_type=4`, `direction="above"`:

| Threshold | `exceedance` (median h) | `persistence` (median h) | True longest run |
|---|---|---|---|
| 20 °C | 168.00 | **8.00** | 168 — every hour qualifies |
| 30 °C | 168.00 | **8.00** | 168 — every hour qualifies |
| 35 °C | 137.46 | **8.00** | ~19.6 h/day |
| 40 °C | 49.42 | 8.00 | ~7 h/day |
| 45 °C | 0.00 | 0.00 | 0 |

At a 20 °C threshold, every one of the 168 hours is above threshold, so the
longest continuous run is *definitionally* the whole window. `persistence`
returns 8.0. It returns 8.0 at 30 °C and at 35 °C as well. The value is pinned.

`exceedance` over the same calls is perfectly monotone and saturates correctly
at both ends, so the threshold parameter itself is being applied properly.

### The defect is scoped to range-of-days

Same AOI, single day 2025-07-15, `filter_type=3`:

| Threshold | `exceedance` | `persistence` | Truth |
|---|---|---|---|
| 20 °C | 24.00 | **24.00** ✓ | 24 — every hour qualifies |
| 35 °C | 17.27 | **16.00** ✓ | one unbroken run |
| 40 °C | 2.00 | **2.00** ✓ | short afternoon run |

Under `filter_type=3`, `persistence` tracks `exceedance` and behaves exactly as
documented.

### On the reference sample, and why we do not compare against it

`BUILD_PLAN.md` sets the gate against "FortyGuard's San Jose sample: 2.07 → 8.73
hours across 329 tiles". We can no longer source that figure. It is not in the
vendored client (`fortyguard/samples.py` carries the San Jose *polygon* but no
statistics), and the quoted numbers come with no window, threshold or
granularity — so there is nothing to normalise against. 8.73 − 2.07 = 6.66 h,
and whether that is one day or seven is undetermined, which changes the per-day
figure by a factor of seven.

**We therefore make no comparability claim in either direction.** An earlier
draft of ours said Phoenix was "comparable to the San Jose reference"; that was
unsupported and has been removed. What we report instead is Phoenix's own
measured spread, as an absolute figure:

| Window | Spread across 420 tiles | Per day |
|---|---|---|
| 2025-07-15, one day, t35 | 1.345 h | 1.345 h |
| 2024-07-15, one day, t35 | 1.393 h | 1.393 h |
| 2025-07-08–14, seven days, t35 | 3.932 h | 0.56 h |

Note the weekly spread is far less than seven times the daily one: tile rankings
are stable but daily extremes partly cancel. **These are small numbers.** Over a
2 km box the per-day spatial spread in hours-above-threshold is on the order of
one hour, and nothing in this document should be read as claiming otherwise.

### Reproduced in three consecutive Julys

`python verify_years.py` repeats the whole probe on 8-14 July of 2025, 2024 and
2023. `filter_type=4` returns exactly **8.0 hours, zero variance, all 420
tiles, in every year**.

The cleanest way to state the defect needs no reference temperature at all. For
the week of 8-14 July 2025 it reports a longest unbroken run of **8.0 hours**;
for 15 July 2025, a single day *inside* a comparable window, it reports
**16.0 hours**. A longest run measured over a superset window cannot be shorter
than one measured inside it. The value is not merely wrong, it is inconsistent
with itself.

### Only `persistence` is affected, and it is a clamp rather than a ceiling

`exceedance` over the identical `filter_type=4` requests is well-behaved, which
is what isolates the defect to the one analytic:

| Threshold | `exceedance` (168 h window) | distinct | `persistence` | distinct |
|---|---|---|---|---|
| 20 °C | 168.00 flat | 1 | 8.00 | 1 |
| 30 °C | 168.00 flat | 1 | 8.00 | 1 |
| 35 °C | 135.54–139.47 | **419** | 8.00 | 1 |
| 40 °C | 48.83–50.25 | **409** | 7.82–8.10 | 251 |
| 45 °C | 0.00 | 1 | 0.00 | 1 |

`exceedance` is monotone and saturates correctly at both ends, so the threshold
parameter is being applied properly and the AOI is fine.

"Saturates at 8.0" also undersells it. At 35 °C the true longest run is ~19 h and
it returns 8.0; at 40 °C the true longest run is ~2 h (measured directly at
`filter_type=3`) and it returns ~8.1. It is **clamped to roughly 8 hours
regardless of the truth, erring in both directions** — not clipped at a ceiling.

At `filter_type=3` the same analytic holds up under the same cross-check —
total hours above threshold is never less than the longest unbroken run, and in
two of the three years the two are *identical*, meaning every qualifying hour
was contiguous:

| Day | `exceedance` | `persistence` | |
|---|---|---|---|
| 2025-07-15 | 16.86–18.21 h | 16.00 h | consistent |
| 2024-07-15 | 13.78–15.17 h | 13.78–15.17 h | identical — one unbroken run |
| 2023-07-15 | 24.00 h | 24.00 h | identical — the whole day qualified |

**Consequence for TRIGGER.** Duration clauses are never driven from
`persistence` under `filter_type=4`. TRIGGER evaluates day by day with
`filter_type=3` — which it needs to do regardless, because a single 7-day
aggregate collapses the very time axis the lead-time metric is about. You
cannot recover *when* a condition was first met from one number covering a
whole week.

---

## 3. The AOI area limit is far above the documented cap

Documented: 10 mi² on Basic and Startup, 50 mi² on Premium. Measured on the
Hackathon plan, all accepted without rejection:

| Box | Area | Tiles returned | Wall clock |
|---|---|---|---|
| 5.0 km | 9.7 mi² | 2,452 | — |
| 8.0 km | 24.7 mi² | 6,417 | — |
| 11.5 km | 51.1 mi² | 12,947 | — |
| 18.0 km | 125.1 mi² | 32,474 | — |
| 25.0 km | 241.0 mi² | 62,609 | 46 s |
| 35.0 km | 473.0 mi² | 122,542 | 61 s |
| Phoenix full bbox | **1,053 mi²** | **272,917** | 118 s |

**Consequence for TRIGGER.** The entire City of Phoenix (556 mi² across 15
urban villages, 1,053 mi² bounding box) fits in a single request. The pipeline
makes one call per (day, analytic, threshold) and aggregates all 15 villages
from that one response, rather than one call per village.

---

## 4. Credits are flat per call, regardless of area

| Calls | Credits | Per call |
|---|---|---|
| 8 heatmaps (420 to 122,542 tiles) | 33,760 | **4,220** |

A 420-tile call and a 122,542-tile call cost exactly the same. Combined with
finding 3, this means there is no reason to make small requests: one
city-covering call is 290× more data for the same price.

Failed and rejected requests are not charged, so probing the area limit and the
threshold response cost nothing.

---

## 5. The tile grid is stable, which makes an offline cache practical

For a fixed AOI and granularity, the returned grid is byte-identical across
calls — same `tile_id` sequence, same geometry — verified across calls
differing only in threshold. Measured on the tile payload, **geometry is 87% of
the bytes**.

`src/cache.py` therefore stores geometry once per grid and values columnar per
request. On the probe set this took the cache from **265.7 MB to 11.3 MB, a
23.5× reduction**, with no loss of information: responses are rebuilt into
exactly the shape the API returned.

This is what makes "clone the repo and reproduce the number with no API key"
achievable rather than aspirational.

---

## 6. Calibration: the model reads cooler than the Sky Harbor station

This one is not a defect, but it changes how results must be read, so it is
recorded here rather than buried.

The Phoenix plan reports that Sky Harbor Airport **hit at least 110 °F on 37
days in 2025**, peaking at 118 °F on 9 July and 7 August (plan, page 6).

FortyGuard's 2 m model over a downtown Phoenix 2 km box, July 2025:

| Threshold | Hours in month | % of the month |
|---|---|---|
| 95 °F | 492.5 | 66.2% |
| 100 °F | 286.4 | 38.5% |
| 104 °F | 140.3 | 18.9% |
| 105.8 °F | 57.1 | 7.7% |
| 107.6 °F | 6.0 | 0.8% |
| 110 °F | **0.0** | 0.0% |

The model's ceiling over downtown is near 42 °C (107.6 °F). It does not reach
110 °F anywhere in the month.

Two readings of this are plausible and we cannot distinguish them with the data
available:

1. Sky Harbor is an open airfield of asphalt and concrete, a well-documented
   heat-island hotspot, and genuinely hotter than the shaded, built-up urban
   core at 2 m.
2. The model is smoothed relative to point observations.

**Consequence for TRIGGER, and why the method survives it.** Both arms of the
divergence comparison — per-village and citywide-proxy — are computed from the
*same* FortyGuard data. Any systematic offset against station readings appears
in both arms and cancels in the difference. What the offset does affect is
threshold selection: a clause keyed to 110 °F returns zero everywhere in both
arms and yields no signal. Clauses keyed between 95 °F and 107 °F sit inside
the model's dynamic range and are where the analysis has power.

This is stated in the limitations section of the README, not only here.

---

## 7. Aggregation: area weighting matters less than expected at 100 m

CLAUDE.md warns that nearest-tile lookup "silently discards most of a zone".
That is true in principle. Measured on Phoenix urban villages at 100 m
granularity, the effect is small:

| Village | Area-weighted | Centroid-in-polygon | Difference | Boundary tiles dropped |
|---|---|---|---|---|
| Encanto | 36.862 | 36.862 | 0.0001 °C | 131 |
| Alhambra | 36.711 | 36.711 | 0.0001 °C | 188 |
| Central City | 36.995 | 36.995 | 0.0000 °C | 177 |
| Laveen | 36.549 | 36.549 | 0.0000 °C | 215 |

A 10 mi² village contains ~2,800 tiles at 100 m, so the ~150 boundary tiles a
centroid test drops are a small and roughly unbiased fraction.

TRIGGER uses area weighting anyway, because it is the correct operation and
because the margin would grow at coarser granularity or with smaller zones. But
the honest statement is that **this choice does not materially change our
results**, and claiming otherwise would be overselling a detail.

Verified against a brute-force recomputation with no spatial index:
agreement to 7.8 × 10⁻¹⁴ (`python test_aggregate.py`).

---

---

## 8. PRIMARY FINDING — a fixed trigger loses discriminating power exactly when severity peaks

Not a defect, and not an aside. This is the project's headline result. It is a
property of how the rule is written, and it is measurable.

### The mechanism: a threshold only resolves what it sits inside

Same 420 tiles, same day (2025-07-15), same analytic. Only the threshold moves:

| Threshold | `exceedance` result | Distinct values across 420 tiles |
|---|---|---|
| 20 °C (68 °F) | 24.00 h everywhere | **1** |
| 35 °C (95 °F) | 16.86–18.21 h | **394** |
| 40 °C (104 °F) | 2.00 h everywhere | **1** |

That day ran 32.7–40.3 °C (91–105 °F). A threshold below the whole range is
cleared by every tile for all 24 hours; one at the very top is cleared by every
tile for the same 2 hours. Perfect data at 100 m buys nothing if the rule reading
it sits outside the range.

### The failure: on Phoenix's record day the trigger returns nothing usable

**2023-07-15.** The same 95 °F trigger that resolved 394 distinct values in 2025
returns **24.00 h across all 420 tiles — one distinct value, zero targeting
information.** On the hottest day in the record, the City's rule cannot say which
neighbourhood to reach first.

Two independent measurements explain why, and they compound:

*The trigger fell below the day's floor.* `tcm` for that day:

| | across 420 tiles | |
|---|---|---|
| overnight low | 35.07 – 35.37 °C | 95.1 – 95.7 °F |
| daily mean | 39.38 – 39.46 °C | σ = 0.023 °C |
| daily peak | 42.49 – 42.56 °C | 108.5 – 108.6 °F |

The coolest hour anywhere was 95.1 °F. The 95 °F trigger sits **0.07 °C below
it**, so every tile qualifies for all 24 hours by construction.

*And the spatial variation itself collapsed.* Daily-mean spread across the box
was **0.08 °C** (σ 0.023). Extreme heat is more spatially uniform than ordinary
heat — so there is both less signal to find and a rule positioned to miss what
remains.

### The recovery: discrimination is retrievable from the same data

Re-evaluating that day against the 90th percentile of its own tile distribution
(39.44 °C / 103.0 °F) instead of a fixed number:

| Threshold on 2023-07-15 | `exceedance` | Distinct values |
|---|---|---|
| 35.00 °C — the City's 95 °F trigger | 24.000 h flat | **1** |
| 39.44 °C — p90 of that day | 13.816 – 14.101 h | **251** |

**1 → 251.** The information was present in the data the whole time; the fixed
threshold was discarding it. A rank ordering of neighbourhoods is recoverable on
the record day, which is precisely the day a heat plan most needs one.

### What this result does not license

Three limits, and they matter:

1. **The magnitude is modest.** 0.285 h of spread is about 17 minutes. What is
   recovered is a *rank ordering* — which is what targeting needs — not a large
   difference in absolute exposure. Do not state it as hours.
2. **A same-day percentile is post hoc.** You cannot compute today's p90 before
   today ends. An operational trigger would use a percentile of the local
   *historical climatology*; this probe demonstrates that the signal survives,
   not that the City should adopt this exact rule.
3. **This is a 2 km box, not a city.** A 0.08 °C daily-mean spread is a
   *within-2 km* figure and will be far larger across Phoenix's 15 urban
   villages. Any headline number must be computed on the full-city AOI. Nothing
   here should be generalised to the city from this box.

TRIGGER reports this rather than fixing it. Rewriting a legal threshold is a
policy act, not an engineering one.

---

## Summary of consequences for the pipeline

| Finding | Design consequence |
|---|---|
| `tcm` is °C | One conversion, in `schema.f_to_c`, nowhere else |
| `persistence` saturates at `filter_type=4` (3 of 3 Julys) | Evaluate day by day with `filter_type=3` |
| A threshold outside the day's range resolves nothing | Report it; choosing thresholds is the City's call, not ours |
| Fixed trigger returns 1 distinct value on the record day; p90 returns 251 | The primary finding — see section 8 |
| Per-day evaluation needed for lead time | A week-long aggregate cannot answer "when" |
| 1,053 mi² in one call | One call per (day, threshold), not one per village |
| Flat credit cost | No incentive to shrink requests |
| Stable grid, geometry is 87% of bytes | Split cache: 23.5× smaller, offline demo viable |
| Model ceiling ~107.6 °F | Clause thresholds must sit in 95–107 °F to have power |
| Area weighting ≈ centroid at 100 m | Use it, but do not claim it as a differentiator |
