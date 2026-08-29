# Measured behaviour of the FortyGuard Temperature API

Everything below was measured against the live API and is reproducible offline from the committed cache:

```
python verify_api.py
```

Three of these findings contradict the published documentation or the official quickstart. Each one fails silently, returning plausible numbers that are wrong, so each is stated with the evidence that settles it.

Measurements were taken on the Hackathon plan between 22 and 23 August 2026, over Phoenix, Arizona.

---

## 1. `tcm` tiles are Celsius, not Fahrenheit

The official quickstart README states that `tcm` tiles are returned in °F. They are returned in °C. The API reference documentation is correct on this point; the quickstart is not.

Downtown Phoenix, 2 km box, 2025-07-15, granularity 100:

| Field | min | max | spread |
|---|---|---|---|
| `min_temperature` | 32.67 | 33.14 | 0.47 |
| `average_temperature` | 36.91 | 37.02 | 0.12 |
| `max_temperature` | 40.11 | 40.30 | 0.18 |

A daily maximum of 40.3 is 104.5 °F, correct for Phoenix in mid-July. Read as Fahrenheit it would mean the city peaked at 40 °F.

Consequence for TRIGGER. The Phoenix plan writes every threshold in °F. The conversion to °C happens in exactly one function, `schema.f_to_c`, and the Celsius value is only ever produced by the `Clause.threshold_c` property. No other module converts anything.

---

## 2. `persistence` saturates at 8.0 under `filter_type=4`

This is the most consequential finding, and it stays invisible unless you probe it with a threshold low enough that you already know the answer.

Downtown Phoenix 2 km box, 2025-07-08 to 2025-07-14, a 168-hour window, `filter_type=4`, `direction="above"`:

| Threshold | `exceedance` (median h) | `persistence` (median h) | True longest run |
|---|---|---|---|
| 20 °C | 168.00 | 8.00 | 168, every hour qualifies |
| 30 °C | 168.00 | 8.00 | 168, every hour qualifies |
| 35 °C | 137.46 | 8.00 | about 19.6 h/day |
| 40 °C | 49.42 | 8.00 | about 7 h/day |
| 45 °C | 0.00 | 0.00 | 0 |

At a 20 °C threshold, every one of the 168 hours is above threshold, so the longest continuous run is definitionally the whole window. `persistence` returns 8.0. It returns 8.0 at 30 °C and at 35 °C as well. The value is pinned.

`exceedance` over the same calls is perfectly monotone and saturates correctly at both ends, so the threshold parameter itself is being applied properly.

### The defect is scoped to range-of-days

Same AOI, single day 2025-07-15, `filter_type=3`:

| Threshold | `exceedance` | `persistence` | Truth |
|---|---|---|---|
| 20 °C | 24.00 | 24.00 ✓ | 24, every hour qualifies |
| 35 °C | 17.27 | 16.00 ✓ | one unbroken run |
| 40 °C | 2.00 | 2.00 ✓ | short afternoon run |

Under `filter_type=3`, `persistence` tracks `exceedance` on this small box.

Superseded, read section 8 before relying on this. We originally read that agreement as corroboration that `filter_type=3` persistence is sound. At city scale it is not: `persistence` returns values identical to `exceedance` on 93.9 to 100% of tiles depending on threshold, along with negative runs and runs longer than 24 hours. The agreement below is evidence of non-independence, not of correctness. Nothing in the pipeline uses `persistence` for a published number.

### On the reference sample, and why we do not compare against it

`BUILD_PLAN.md` sets the gate against "FortyGuard's San Jose sample: 2.07 to 8.73 hours across 329 tiles." We can no longer source that figure. It is not in the vendored client (`fortyguard/samples.py` carries the San Jose polygon but no statistics), and the quoted numbers come with no window, threshold, or granularity, so there is nothing to normalise against. 8.73 minus 2.07 is 6.66 h, and whether that is one day or seven is undetermined, which changes the per-day figure by a factor of seven.

We make no comparability claim in either direction. An earlier draft of ours said Phoenix was "comparable to the San Jose reference"; that was unsupported and has been removed. What we report instead is Phoenix's own measured spread, as an absolute figure:

| Window | Spread across 420 tiles | Per day |
|---|---|---|
| 2025-07-15, one day, t35 | 1.345 h | 1.345 h |
| 2024-07-15, one day, t35 | 1.393 h | 1.393 h |
| 2025-07-08 to 14, seven days, t35 | 3.932 h | 0.56 h |

The weekly spread is far less than seven times the daily one: tile rankings are stable but daily extremes partly cancel. These are small numbers. Over a 2 km box the per-day spatial spread in hours-above-threshold is on the order of one hour, and nothing in this document should be read as claiming otherwise.

### Reproduced in three consecutive Julys

`python verify_years.py` repeats the whole probe on 8 to 14 July of 2025, 2024, and 2023. `filter_type=4` returns exactly 8.0 hours, zero variance, all 420 tiles, in every year.

The cleanest way to state the defect needs no reference temperature at all. For the week of 8 to 14 July 2025 it reports a longest unbroken run of 8.0 hours; for 15 July 2025, a single day inside a comparable window, it reports 16.0 hours. A longest run measured over a superset window cannot be shorter than one measured inside it, and here it is.

### Only `persistence` is affected, and it is a clamp rather than a ceiling

`exceedance` over the identical `filter_type=4` requests is well-behaved, which is what isolates the defect to the one analytic:

| Threshold | `exceedance` (168 h window) | distinct | `persistence` | distinct |
|---|---|---|---|---|
| 20 °C | 168.00 flat | 1 | 8.00 | 1 |
| 30 °C | 168.00 flat | 1 | 8.00 | 1 |
| 35 °C | 135.54 to 139.47 | 419 | 8.00 | 1 |
| 40 °C | 48.83 to 50.25 | 409 | 7.82 to 8.10 | 251 |
| 45 °C | 0.00 | 1 | 0.00 | 1 |

`exceedance` is monotone and saturates correctly at both ends, so the threshold parameter is being applied properly and the AOI is fine.

Calling this "saturates at 8.0" undersells it. At 35 °C the true longest run is about 19 h and it returns 8.0; at 40 °C the true longest run is about 2 h (measured directly at `filter_type=3`) and it returns about 8.1. It clamps to roughly 8 hours regardless of the truth, erring in both directions, rather than clipping at a ceiling.

At `filter_type=3` the same analytic holds up under the same cross-check: total hours above threshold is never less than the longest unbroken run, and in two of the three years the two are identical, meaning every qualifying hour was contiguous.

| Day | `exceedance` | `persistence` | |
|---|---|---|---|
| 2025-07-15 | 16.86 to 18.21 h | 16.00 h | consistent |
| 2024-07-15 | 13.78 to 15.17 h | 13.78 to 15.17 h | identical, one unbroken run |
| 2023-07-15 | 24.00 h | 24.00 h | identical, the whole day qualified |

Consequence for TRIGGER. Duration clauses are never driven from `persistence` under `filter_type=4`. TRIGGER evaluates day by day with `filter_type=3`, which it needs to do regardless, because a single seven-day aggregate collapses the time axis the lead-time metric is about. You cannot recover when a condition was first met from one number covering a whole week.

---

## 3. The AOI area limit is far above the documented cap

Documented: 10 mi² on Basic and Startup, 50 mi² on Premium. Measured on the Hackathon plan, all accepted without rejection:

| Box | Area | Tiles returned | Wall clock |
|---|---|---|---|
| 5.0 km | 9.7 mi² | 2,452 | — |
| 8.0 km | 24.7 mi² | 6,417 | — |
| 11.5 km | 51.1 mi² | 12,947 | — |
| 18.0 km | 125.1 mi² | 32,474 | — |
| 25.0 km | 241.0 mi² | 62,609 | 46 s |
| 35.0 km | 473.0 mi² | 122,542 | 61 s |
| Phoenix full bbox | 1,053 mi² | 272,917 | 118 s |

Consequence for TRIGGER. The entire City of Phoenix (556 mi² across 15 urban villages, 1,053 mi² bounding box) fits in a single request. The pipeline makes one call per (day, analytic, threshold) and aggregates all 15 villages from that one response, rather than one call per village.

---

## 4. Credits are flat per call, regardless of area

| Calls | Credits | Per call |
|---|---|---|
| 8 heatmaps (420 to 122,542 tiles) | 33,760 | 4,220 |

A 420-tile call and a 122,542-tile call cost exactly the same. Combined with finding 3, there is no reason to make small requests: one city-covering call is 290 times more data for the same price.

Failed and rejected requests are not charged, so probing the area limit and the threshold response costs nothing.

---

## 5. The tile grid is stable, which makes an offline cache practical

For a fixed AOI and granularity, the returned grid is byte-identical across calls, same `tile_id` sequence, same geometry, verified across calls differing only in threshold. Measured on the tile payload, geometry is 87% of the bytes.

`src/cache.py` therefore stores geometry once per grid and values columnar per request. On the probe set this took the cache from 265.7 MB to 11.3 MB, a 23.5x reduction, with no loss of information: responses are rebuilt into exactly the shape the API returned.

This is what makes "clone the repo and reproduce the number with no API key" achievable rather than aspirational.

---

## 6. Calibration: the model reads cooler than the Sky Harbor station

This is not a defect, but it changes how results must be read, so it is recorded here rather than buried.

The Phoenix plan reports that Sky Harbor Airport hit at least 110 °F on 37 days in 2025, peaking at 118 °F on 9 July and 7 August (plan, page 6).

FortyGuard's 2-metre model over a downtown Phoenix 2 km box, July 2025:

| Threshold | Hours in month | % of the month |
|---|---|---|
| 95 °F | 492.5 | 66.2% |
| 100 °F | 286.4 | 38.5% |
| 104 °F | 140.3 | 18.9% |
| 105.8 °F | 57.1 | 7.7% |
| 107.6 °F | 6.0 | 0.8% |
| 110 °F | 0.0 | 0.0% |

The model's ceiling over downtown is near 42 °C (107.6 °F). It does not reach 110 °F anywhere in the month.

Two readings of this are plausible, and we cannot distinguish them with the data available. Sky Harbor is an open airfield of asphalt and concrete, a well-documented heat-island hotspot, and may genuinely run hotter than the shaded, built-up urban core at 2 m. Or the model is smoothed relative to point observations. Both could be true at once.

Consequence for TRIGGER, and why the method survives it. Both arms of the divergence comparison, per-village and citywide-proxy, are computed from the same FortyGuard data. Any systematic offset against station readings appears in both arms and cancels in the difference. What the offset does affect is threshold selection: a clause keyed to 110 °F returns zero everywhere in both arms and yields no signal. Clauses keyed between 95 °F and 107 °F sit inside the model's dynamic range and are where the analysis has power.

This is stated in the limitations section of the README, not only here.

---

## 7. Aggregation: area weighting matters less than expected at 100 m

SPEC.md warns that nearest-tile lookup "silently discards most of a zone." That is true in principle. Measured on Phoenix urban villages at 100 m granularity, the effect is small:

| Village | Area-weighted | Centroid-in-polygon | Difference | Boundary tiles dropped |
|---|---|---|---|---|
| Encanto | 36.862 | 36.862 | 0.0001 °C | 131 |
| Alhambra | 36.711 | 36.711 | 0.0001 °C | 188 |
| Central City | 36.995 | 36.995 | 0.0000 °C | 177 |
| Laveen | 36.549 | 36.549 | 0.0000 °C | 215 |

A 10 mi² village contains about 2,800 tiles at 100 m, so the roughly 150 boundary tiles a centroid test drops are a small and roughly unbiased fraction.

TRIGGER uses area weighting anyway, because it is the correct operation and because the margin would grow at coarser granularity or with smaller zones. But stated plainly: this choice does not materially change our results, and claiming otherwise would oversell a detail.

Verified against a brute-force recomputation with no spatial index: agreement to 7.8 x 10⁻¹⁴ (`python test_aggregate.py`).

---

## 8. Primary finding: a fixed trigger fails in both directions, and the failure is severity-dependent

Not a side note. This is the project's headline result.

### Correction to an earlier draft of this section

An earlier version of this section measured the effect on a 2 km downtown box (420 tiles) and reported that a threshold outside the day's range collapses discrimination from 394 distinct values to 1. That measurement was real, but it described the box, not the mechanism. Over 4 km² the spatial spread in overnight low is 0.08 to 0.47 °C, so almost every threshold falls outside it and the API returns a single quantised integer. Over the full 1,053 mi² AOI:

| | 2 km box (420 tiles) | Citywide (272,917 tiles) |
|---|---|---|
| Flat days at 105 °F, study window | 6 of 7 | 0 of 7 |
| Overnight-low spatial spread | 0.08 to 0.47 °C | 10.85 to 13.49 °C |
| Distinct values per day | 1 | 43,497 to 74,365 |

The mechanism survives; its magnitude is set by the area being sensed. The band of thresholds that can resolve anything is as wide as the spatial temperature range it has to sit inside, wide across a city, nearly nonexistent across a neighbourhood. Every figure below is citywide.

### Measuring it: bits, not distinct values

A count of distinct values does not work at city scale. 272,917 floating-point tiles always carry tens of thousands of distinct values, so the measure never approaches zero however useless the trigger is.

A trigger emits one bit per tile: fire or don't. The information that bit carries is the binary entropy of the firing share,

    H(p) = -p log2 p - (1-p) log2 (1-p)

which is 1 bit when the trigger splits the city evenly and 0 bits when it says the same thing everywhere, whether that is everywhere or nowhere. It collapses at both ends by construction, and unlike a distinct-value count it is independent of tile count and AOI size, so days and cities are comparable. It measures the trigger's output, not the underlying heat: a highly differentiated city can still yield 0 bits under a badly placed rule.

### The result: two failure modes, one flaw

Five clauses over the seven-day published window, evaluated on raw tiles:

| | of 35 clause-days |
|---|---|
| Actionable (fires on 5 to 95% of tiles) | 8 (23%) |
| Over-triggered (more than 95% of tiles) | 11 |
| Under-triggered (fewer than 5% of tiles) | 16 |

`BENCH-LOW90` traverses the whole arc within one week as severity rises:

| mean tile temp | saturation | verdict |
|---|---|---|
| 95.2 °F | 0.002 | under-trigger |
| 96.4 °F | 0.000 | under-trigger |
| 98.2 °F | 0.169 | actionable |
| 98.9 °F | 0.178 | actionable |
| 99.7 °F | 0.491 | actionable |
| 100.3 °F | 0.501 | actionable |
| 101.2 °F | 0.955 | over-trigger |

### Retracted: the threshold-by-dwell grid, and why it could not be salvaged

An earlier version of this section published a threshold-by-dwell grid and a headline claim that adding a duration requirement to Action 1.1's existing 105 °F threshold would restore targeting value, 0.090 to 0.974 bits. That claim is withdrawn. It is recorded here rather than deleted, because the reason it failed is itself a reusable finding.

Attempt 1, `exceedance`, rejected on semantics before data quality. `exceedance` returns a total of qualifying hours. A dwell clause, "above 105 °F for more than nine hours," describes a continuous spell. Three separate three-hour spells total nine hours and pass the exceedance test while failing the clause. The two quantities answer different questions and the clause asks the persistence question, so `exceedance` was disqualified on correctness regardless of its data quality. Section 9 below corroborates this: the field also returns negative values, which additionally made the baseline flatter than it deserved.

Attempt 2, `persistence` at `filter_type=3`, failed validation. This is the analytic that measures longest continuous run, and it is the only other one that carries duration information (`tcm` carries none: min, mean, and max temperature per tile and nothing about time). Citywide on 2025-08-07:

| threshold | min | max | negative | tiles > 24 h | run > own total |
|---|---|---|---|---|---|
| 68 °F | 24.00 | 24.00 | 0 | 0 | 0 |
| 77 °F | 24.00 | 24.00 | 0 | 0 | 0 |
| 86 °F | 15.59 | 25.51 | 0 | 8,758 | 9,242 |
| 95 °F | 10.29 | 25.92 | 0 | 6,820 | 39,329 |
| 105 °F | −2.51 | 11.57 | 3,110 | 0 | 6,805 |
| 113 °F | 0.00 | 0.00 | 0 | 0 | 0 |

Three impossibilities, each sufficient on its own. A continuous run within a single day cannot last 25.92 hours. It cannot be negative. And it cannot exceed the tile's own total qualifying hours, which happens on up to 39,329 tiles.

It is also not an independent measurement. Compared tile by tile against `exceedance` on the same day and threshold:

| threshold | tiles identical to `exceedance` | share |
|---|---|---|
| 68 °F | 272,917 / 272,917 | 100% |
| 77 °F | 272,917 / 272,917 | 100% |
| 86 °F | 257,538 / 272,917 | 94.4% |
| 105 °F | 256,146 / 272,917 | 93.9% |
| 113 °F | 272,917 / 272,917 | 100% |
| 95 °F | 7,315 / 272,917 | 2.7% |

At the threshold the retracted claim rested on, `persistence` returns the same value as `exceedance` for 93.9% of tiles, including the same impossible −2.51 minimum. Whatever it is computing, it is not an independent longest-run.

Conclusion, stated as a finding: FortyGuard exposes no trustworthy duration analytic at city scale. `exceedance` is a smoothed total, `persistence` largely copies it and returns physically impossible values, and `tcm` carries no time information. Any dwell-based trigger design is unmeasurable on this data, which is worth knowing on its own, because a dwell requirement is the most natural fix for a saturating threshold and the first thing a reader will ask about.

The retracted derivation, its validation harness, and the failure output all remain in `sweep_dwell.py` and `data/results/dwell_grid.json`. The script exits non-zero, so the failure is visible rather than inferred.

### A correction this forced upstream

Section 2 of this document previously concluded that at `filter_type=3` "persistence tracks exceedance and behaves exactly as documented." On the 2 km box the two analytics agreed, and we read agreement as corroboration. The better explanation is non-independence: they largely return the same field, and the city-scale figures above make that explicit. `filter_type=3` persistence is not validated by agreeing with `exceedance`; that agreement is the problem.

This changes nothing in the pipeline, which never used `persistence` for any published number, but the earlier wording overstated what had been established.

### What recovery is left

With dwell unmeasurable, the surviving alternative design is a percentile threshold, and it applies only to the three clauses backed by `tcm` temperatures. Replacing a fixed value with the 90th percentile of the day's own distribution restores a rankable ordering in both failure directions, the saturated 100 °F benchmark and the never-firing 110 °F one alike, each moving to a firing share of 0.100.

A same-day percentile is post hoc: today's p90 is not knowable before today ends. It establishes that the signal survives in the data, not that a city should adopt that rule. A deployable version would fit the percentile on historical climatology, which this project has not done.

TRIGGER reports all of this rather than rewriting the plan. Changing a legal threshold is a policy act.

---

## 9. `exceedance` is a smoothed field, not a count of hours

Citywide, `exceedance` returns negative values:

| Day (2025) | min hours above 105 °F |
|---|---|
| 08-02 | −1.05 |
| 08-05 | −1.58 |
| 08-07 | −2.51 |

Hours above a threshold cannot be negative. The field is interpolated or smoothed rather than counted, so a near-zero `exceedance` value is not a literal hour count and should not be reported as one. Any "did it fire" test must be an explicit comparison (`value > 0`), never an assumption that the value is a non-negative integer. Differences of a few tenths of an hour between tiles fall within the smoothing rather than resolved measurement; rankings across many tiles are still informative, individual tile-to-tile gaps are not.

TRIGGER defines firing as `value > duration_hours` (with `duration_hours = 0` where the clause states none), which is well-defined regardless.

---

## 10. The area limit is about land, not square miles

Finding 3 reports an accepted AOI of 1,053 mi² over Phoenix, far above the documented 50 mi² cap. Adding New York City showed that figure is not the real constraint.

A size ladder over NYC on 2025-06-24, `tcm`, 100 m:

| AOI | Coverage | Tiles | Result |
|---|---|---|---|
| 122 mi², Manhattan + Bronx | land | 26,819 | succeeded, 53 s |
| 346 mi², + Brooklyn + Queens | mostly land | 71,988 | succeeded, 57 s |
| 840 mi², full five boroughs | about 40% water | — | rejected, FortyGuardError |

The 840 mi² request is smaller than the 1,053 mi² Phoenix box that succeeds, and returns fewer tiles than Phoenix does, so neither area nor tile count is the binding limit. What distinguishes it is water: the full-borough bounding box spans the Atlantic, New York Harbor, Jamaica Bay, and Long Island Sound, where a 2-metre urban temperature model has nothing to return.

The failure mode is worth noting too. Two earlier attempts at the same AOI hung for 2,400 seconds and emitted 40 transient status errors before timing out; the ladder, which polls with a shorter deadline, got a clean `FortyGuardError` in 105 s. The same rejected request presents either as a fast error or as a 40-minute hang depending on how you poll, which is why our first two attempts looked like an outage rather than a rejection, and why we initially misdiagnosed `time_of_measure` the same way.

Consequence for TRIGGER. A coastal city needs its AOI clipped to land before the first request, not after. NYC is analysed over the 346 mi² box that the API accepts, covering 51 of 59 community districts: all of Manhattan and the Bronx, 15 of 18 in Brooklyn, 12 of 14 in Queens. Staten Island and five coastal districts are excluded and reported as excluded, rather than returned with no tile coverage and silently averaged into the result.

---

## Summary of consequences for the pipeline

| Finding | Design consequence |
|---|---|
| `tcm` is °C | One conversion, in `schema.f_to_c`, nowhere else |
| `persistence` saturates at `filter_type=4` (3 of 3 Julys) | Evaluate day by day with `filter_type=3` |
| A threshold outside the day's range resolves nothing | Report it; choosing thresholds is the city's call, not ours |
| A fixed trigger fails in both directions, severity-dependent | The primary finding, see section 8 |
| The AOI limit is about land, not area | Clip a coastal city's AOI to land before the first call, see section 10 |
| No trustworthy duration analytic at city scale | Dwell-based trigger designs are unmeasurable here; retracted, see section 8 |
| `exceedance` returns negative values | Treat it as smoothed, not counted; test `value > 0` explicitly |
| Per-day evaluation needed for lead time | A week-long aggregate cannot answer "when" |
| 1,053 mi² in one call | One call per (day, threshold), not one per village |
| Flat credit cost | No incentive to shrink requests |
| Stable grid, geometry is 87% of bytes | Split cache: 23.5x smaller, offline demo viable |
| Model ceiling about 107.6 °F | Clause thresholds must sit in 95 to 107 °F to have power |
| Area weighting is close to centroid at 100 m | Use it, but do not claim it as a differentiator |
