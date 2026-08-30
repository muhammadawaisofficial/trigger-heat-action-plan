# The algorithms

Four things in this project turn temperature into a decision. This document
describes each one precisely enough to argue with.

The rule that governs all four: **the language model never decides anything.**
Gemini extracts clauses from the plan PDF and narrates finished results. Every
determination below is arithmetic in Python, and every one of them is
reproducible from the committed cache with no API key.

---

## 1. From a sentence in a PDF to a fired-or-not determination

This is the core chain and the reason the project exists.

### Compile

`src/compile.py` extracts the plan page by page with page numbers preserved,
chunks by section so a clause keeps its context, and asks Gemini for JSON
matching the `Clause` dataclass. Each clause carries the threshold as written,
the operator, an optional duration, the responsible department, the verbatim
sentence, and the page number.

Then the check the design rests on. The verbatim sentence is asserted to appear,
character for character, in the extracted text of the page the clause cites. A
clause that fails is rejected and logged. Mechanical, not trusted.

Measured accuracy on Phoenix: F1 0.962, and 100% on the classification that
drives the headline, conditional-on-heat against calendar-activated
(`python eval_compiler.py`).

### Convert units, once

The plan is written in Fahrenheit. The API takes Celsius. `fahrenheit_to_celsius`
lives in `src/schema.py` and nowhere else, and the `Clause` validator refuses
any clause where `threshold_c != round((threshold_source - 32) * 5/9, 2)`. Sending
95 to an API that expects Celsius returns all zeros with no error, which is
indistinguishable from a cool night. See `docs/engineering.md`.

### Choose the analytic from the clause's own shape

The clause decides which FortyGuard analytic answers it. Nothing is configured
by hand:

| The clause says | Analytic used | What comes back |
|---|---|---|
| a threshold and a duration in hours | `persistence` | longest unbroken run past the threshold |
| a threshold and no duration | `exceedance` | total hours past the threshold |
| a temperature level to compare against | `tcm` | per-tile min, mean, max |

`threshold_c` and the operator become the `threshold` and `direction`
parameters directly.

### Call once per threshold, not once per zone

One call per unique combination of threshold, direction, and analytic type
covers the whole city. Zones are separated afterwards, locally, by intersecting
geometry.

This is a direct consequence of a measured API property: credits are flat per
call regardless of area. Calling per zone would cost fifteen times as much for
identical tiles. The logged call count tracks distinct thresholds in the plan
rather than clauses times zones, which is how you can tell from the outside that
the batching is real.

### Reduce tiles to zones by area

`src/aggregate.py` computes, for each zone, the area-weighted mean over every
tile whose polygon intersects it, weighted by intersection area. Not
nearest-tile, and not a centroid lookup: both discard most of the measurement.

Verified against a brute-force recomputation with no spatial index, agreeing to
7.8 × 10⁻¹⁴ (`python test_aggregate.py`). Measured against a naive
centroid-in-polygon lookup the difference is about 0.0001 °C at 100 m, so area
weighting is used because it is correct, not because it changes the answer.

Any zone under five intersecting tiles is flagged as under-covered rather than
reported as if it were solid.

### Determine, and compare against the citywide arm

Each `ClauseResult` records `fired`, the value, the margin against what the
clause required, and `first_hour_met` in local time. Phoenix is UTC−7 with no
DST; New York observes it. Getting that wrong shifts every peak-hour figure, so
a test asserts the conversion.

The citywide arm runs the identical clauses against an area-weighted mean over
the entire city AOI. It is labelled `citywide_proxy` in every output structure,
in code, in the report, and in the interface, because it stands in for station
sensing rather than being a station feed. It is deliberately generous: a true
city mean is a best-case single sensor, and a real airport station is worse.
Every divergence figure is therefore a lower bound.

`src/diverge.py` then computes three things:

- **silent zones** — a clause fired locally and the citywide arm never fired at
  all. Joined to population where available.
- **lead time gained** — hours between the local and citywide `first_hour_met`,
  reported as a median and a distribution.
- **false-calm clauses** — never fire citywide, fire in at least one zone.

Phoenix, 2–8 August 2025: 10 of 15 urban villages, 20 silent zone-days,
1,184,971 people, median 4 days of lost warning.

### Measure whether the trigger discriminates at all

A trigger emits one bit per tile: fire or don't. The information in that bit is
the binary entropy of the firing share,

    H(p) = -p·log₂p - (1-p)·log₂(1-p)

which is 1 bit when the rule splits the city evenly and 0 when it says the same
thing everywhere, whether that is everywhere or nowhere.

This replaced a distinct-value count, which is not comparable across areas
because 272,917 floating-point tiles always carry tens of thousands of distinct
values however useless the rule is. Entropy is independent of tile count and AOI
size, so days and cities can be compared. It measures the trigger's output
rather than the underlying heat: a genuinely varied city still yields 0 bits
under a badly placed rule.

Across 35 clause-days, 8 were actionable (firing on 5–95% of tiles), 11
over-triggered, and 16 under-triggered.

---

## 2. Heat-wave detection, per neighbourhood

`src/heatwave.py`. A heat wave is not a hot day. Every operational definition in
use has three parts, and this implements all three at zone resolution:

- a **threshold**, absolute or a percentile of local climatology
- a **persistence** requirement, a minimum number of consecutive days
- a **night** condition, overnight minima that stay elevated

The night condition carries the health signal. Mortality tracks the failure to
cool down at night rather than the daytime peak, which is why overnight low
governs wherever the two disagree.

Both threshold bases are reported. Absolute is what plans are written against,
so it is what governs. Percentile is what the epidemiological literature uses,
because the temperature at which people begin dying is relative to what they are
acclimatised to: 95 °F is an emergency in Seattle and a Tuesday in Phoenix.
Showing both lets a reader see where the plan's own number sits in the local
distribution.

Every city-scale heat-wave product answers "is the city in a heat wave". This
answers "which neighbourhoods are, and since when" — a wave can be running in
Maryvale and not in Ahwatukee on the same night.

Nothing here is forecast. These are runs detected in measured data. The app does
not predict future heat waves and does not claim to.

Run the same week against each threshold in turn and the count moves from ten
waves at 90 °F to zero at 110 °F. The weather is identical down that table. Only
the number written in the plan changes.

---

## 3. Data-centre siting, with the weights exposed

`src/site_model.py`, over 30 US metros.

Cooling is not the first thing a site selector looks at. Published surveys put
power availability top, with 84% ranking it in their top three, and the binding
constraint is usually the interconnection timeline. A model that ranked sites on
temperature alone would answer a question nobody asks.

But cooling is the factor measured worst. Every published free-cooling figure is
a city-level number — Phoenix "1,000–2,000 hours a year", Minneapolis
"4,000–6,000" — and nobody sites a building on a city average. So this model
contributes precision where precision is missing and treats the rest honestly.

**What we measure, at 100 m, from FortyGuard:** free-cooling hours (hours below
the economiser setpoint, via `exceedance` with `direction="below"`), wet-bulb
temperature (via `env_params`), and overnight low.

**What is a published constant, at state resolution:** electricity price (EIA),
water stress (WRI Aqueduct / USGS band), disaster risk (FEMA National Risk
Index), grid headroom, and renewables proximity.

That asymmetry is deliberate and is stated wherever the model appears in the
interface. Our thermal term resolves within a metro; every other term does not.
It is the same criticism this project levels at heat plans, pointed at our own
model.

### The weights

Ordinal bands map to 0–1 where 1 is always better for a data centre. Continuous
values are min-max normalised across the panel. The score is a weighted mean:

| Factor | Default weight | What it covers |
|---|---|---|
| power | 0.30 | electricity price and grid headroom |
| cooling | 0.25 | free-cooling hours — the term we measure |
| water | 0.20 | water stress |
| risk | 0.15 | natural disaster exposure |
| renewable | 0.10 | green capacity access |

Power is first because the industry ranks it first, not because we think heat is
unimportant. The weights are exposed as sliders rather than buried in the code,
so a user who cares more about water than power can say so and watch the ranking
reorder. A single composite number that hides its own weighting is not a
decision aid.

Free-cooling hours are converted to a share of the window before scoring, since
an absolute hour count is meaningless without knowing how many days it spans —
12 hours is excellent over one day and negligible over seven.

### The strategy branch, which is the actual output

The model does not emit one score. It emits a recommended cooling strategy per
site, because the right answer in Phoenix is different from the right answer in
Minneapolis:

- free-cooling share ≥ 40% → **air-side economiser**
- no wet-bulb measured → **needs wet-bulb to decide**, stated rather than guessed
- wet-bulb < 24 °C and water not scarce → **evaporative / adiabatic**
- wet-bulb < 24 °C and water scarce → **air-cooled chillers, water-constrained**
- wet-bulb ≥ 24 °C → **mechanical chillers, worst case**

The 24 °C wet-bulb limit is where evaporative cooling stops being effective.

This encodes the industry's real dilemma: saving electricity often means
spending water. Evaporative cooling is far more energy-efficient than mechanical
chilling and its effectiveness is set by wet-bulb, not dry-bulb. A hot arid site
has a low wet-bulb, so evaporative cooling works beautifully there — and that is
exactly where water is scarcest. Microsoft's reported water-use effectiveness is
1.52 L/kWh in Arizona against 0.02 in Singapore.

Houston is the genuinely worst case: high wet-bulb means evaporative works
poorly and free cooling is rare.

---

## 4. Urban planning: how much canopy, and where

`src/planning.py`. Heat advice is usually unquantified. Plant trees, paint roofs
white — true, but it never says how much canopy, in which neighbourhood, to
close what gap.

This joins the measured thermal gap at 100 m to published effect sizes, so a
recommendation carries a magnitude. Neither half is invented: the gap comes from
FortyGuard tiles, the coefficients come from the peer-reviewed urban-heat
literature and are cited inline next to the numbers they produce.

Both coefficients are deliberately the most conservative available:

**Canopy.** A global meta-analysis finds about 0.3 °C of cooling per +10
percentage points of canopy cover. Phoenix-specific work found 10% → 25% canopy
delivering up to 2.0 °C, and full canopy against treeless ground reaching 5.5 °C,
rising to 8.8 °C once air temperature hits 40 °C. We use the meta-analysis
number because it is the one that generalises across the panel.

**Albedo.** Cool roofs reduce neighbourhood air temperature by about 0.3 °C in
residential deployment; Boston modelling gives −0.61 °C per +0.1 albedo in the
afternoon. We use the residential figure, again the conservative one.

Tree canopy outperforms cool roofs on temperature by roughly 35%.

`canopy_points_for(gap_f)` inverts the coefficient to answer the question a
planning department actually asks: to close this measured gap in this named
neighbourhood, how many percentage points of canopy is that? Ordering is by
residents affected, so the intervention list is a deployment order rather than a
ranking.

---

## Where the model is, and where it is not

| Step | Decided by |
|---|---|
| Extracting clauses from the PDF | Gemini, then verbatim-quote verified |
| Unit conversion | `schema.py`, one function, asserted by test |
| Which analytic to call | the clause's own shape |
| Whether a clause fired | numeric comparison |
| Tile-to-zone aggregation | area-weighted intersection |
| Silent zones, lead time, false calms | arithmetic on those results |
| Heat-wave runs | threshold, persistence, night condition |
| Siting score and strategy | weighted mean, then a branch on wet-bulb |
| Canopy recommendation | measured gap ÷ published coefficient |
| Writing the brief in English | Gemini, post-validated against the numbers |

Two rows involve a language model. Both are wrapped in a mechanical check that
rejects output rather than trusting it.
