# TRIGGER — build plan

The build order this project was developed against, kept for the record. Each
phase had an acceptance criterion that had to pass before the next one started,
and the gates are recorded here as they were written, not as they turned out.

`SPEC.md` in the repo root is the specification every phase refers to.

**Environment:** `FORTYGUARD_API_KEY` and `GEMINI_API_KEY` in `.env`, with
`.env` in `.gitignore`. No key is committed anywhere in this repository.

---

## Phase 0 — Verify · Day 6

Set up the repo from the FortyGuard quickstart template, with their `fortyguard`
client package vendored unmodified, plus `.env.example`, `.gitignore`, and
`requirements.txt`.

Then one verification call, and nothing else: a small downtown Phoenix polygon
of roughly 2 km², `analytic_type="persistence"`, threshold 35.0 with
`direction="above"`, `filter_type=4`, one week of July 2025, granularity 100.
Print the full `stats_data` and the count of tiles above zero, then repeat the
identical window for July 2024 and July 2023.

The point of stopping here was to find out whether the API returns usable
spatial variation before any of the rest was worth building.

**Gate:** `n_cells` in the hundreds or more, with a real spread between `min`
and `max`. The reference was FortyGuard's San Jose sample, 2.07 to 8.73 hours
across 329 tiles. A flatter Phoenix, or an empty year, meant choosing a
different study window before continuing.

---

## Phase 1 — Foundation · Day 6, evening

Three modules and their tests, with no API calls beyond what the cache wraps.

`src/cache.py` — a disk cache under `data/cache/`, keyed on the SHA-256 of the
canonical JSON request payload with sorted keys, wrapping the client's heatmap
and `env_params` calls. A second identical call must make zero network
requests. A `list_cache()` helper and a manifest record what each key holds in
human-readable form.

`src/schema.py` — the `Clause` dataclass exactly as SPEC.md specifies.
`fahrenheit_to_celsius()` lives here and in no other file. The validator
requires `threshold_c` to equal `round((threshold_source - 32) * 5/9, 2)`,
`source_text` and `source_page` to be present and non-empty, `operator` to be
one of `above` or `below`, and `extraction_conf` to fall in [0, 1].
`to_api_params()` returns the exact kwargs for `create_heatmap`.

`src/parse.py` — `parse_heatmap(response)` returns `list[Tile]`, each tile
carrying `tile_id`, `value`, `units`, and a shapely polygon built from
`[lon, lat]` coordinates. It handles both response shapes, `properties.value`
for the analysis types and `properties.average_temperature` for `tcm`, and
raises a clear error when neither field is present rather than returning
silently empty.

The tests cover cache hit and miss, the °F to °C round trip, both parse paths,
and coordinate ordering. That last one asserts a Phoenix tile lands near
longitude −112, latitude 33, which catches a lon/lat swap the moment it happens
instead of three phases later.

**Gate:** all tests green, including the coordinate-order assertion.

---

## Phase 2 — The compiler · Day 7

The part of this project nothing else substitutes for, so it got the most care.

Model selection came first, by listing the available Gemini models through the
SDK rather than hardcoding a name from memory, preferring a fast model with
JSON output support and recording the chosen name in a constant.

`src/compile.py` takes `data/plan/phoenix_2026_heat_response_plan.pdf`,
extracts text page by page with the page numbers preserved, chunks by section
so a clause and its context stay together, and calls Gemini in JSON output mode
against a schema matching the `Clause` dataclass.

Five rules are stated in the system prompt and then validated on the output,
because a rule that lives only in the prompt is a request rather than a
guarantee:

- every clause carries the verbatim source sentence and its page number
- an inferred field sets `extraction_note` explaining the inference and lowers
  `extraction_conf`
- a clause with no numeric threshold returns `threshold_source=None` and is
  flagged for review, never given an invented number
- thresholds stay as written, in °F; conversion happens in `schema.py`
- `actor` comes from the plan's own department key, with the abbreviations it
  prints (OHRM, PD, HSD, OEM, PRD) mapped to full department names

Then the check the whole design rests on: every returned clause is asserted to
have its `source_text` appear verbatim in the text of the page it cites. A
clause that fails is rejected and logged. This is mechanical rather than
trusted, which is what makes an unfamiliar plan safe to compile.

`eval_compiler.py` loads the hand-compiled golden set from
`data/golden/clauses.json`, matches compiled against golden on `clause_id` and
on threshold-plus-actor pairs, and reports precision, recall, F1, and a
field-level accuracy table across threshold, duration, actor, and action. It
writes `data/eval/compiler_report.json` and prints a summary. Compiled output
lands in `data/clauses/compiled.json`.

**Gate:** F1 above roughly 0.7 with zero clauses failing verbatim validation.
Below that the fix was to iterate the prompt rather than proceed, since every
downstream number inherits the compiler's errors.

---

## Phase 3 — Zones and aggregation · Day 8, morning

Phoenix administrative boundaries, preferring the city's 15 official urban
villages — Camelback East, Maryvale, South Mountain, Encanto and the rest.
They are the right unit because they are official, named, few enough to display
on one map, and large enough to contain many tiles. Sourced as GeoJSON from
City of Phoenix open data and committed to
`data/zones/phoenix_villages.geojson`, with census tracts clipped to city
limits as the fallback.

`src/aggregate.py` reduces tiles to zones by area-weighted mean over every tile
whose polygon intersects the zone, weighted by intersection area. Not
nearest-tile, and not a centroid lookup: both of those discard most of the
measurement. It also returns max, min, `tile_count`, and total intersection
area per zone, and warns loudly for any zone under five tiles.

One small zone's weighted mean was then computed by hand from its intersecting
tiles and asserted against the function, and that check stayed in as a test.

**Gate:** every zone has meaningful tile coverage, and the hand verification
passes.

---

## Phase 4 — Evaluation and the number · Day 8 evening to Day 9

The hard gate. Nothing after this matters if this does not land.

`src/evaluate.py` runs each clause against each zone over the study window.
A clause with `duration_hours` uses `analytic_type="persistence"`, the longest
consecutive run; a clause without one uses `exceedance`, total hours past the
threshold. `threshold_c` and `operator` become the threshold and direction
parameters. Each `ClauseResult` carries `clause_id`, `zone_id`, `fired`,
`value`, `margin` against what the clause required, and `first_hour_met` in
local time.

Calls are batched so that one call per unique combination of threshold,
direction, and analytic type covers every zone at once, with aggregation
happening afterwards. Calling per zone would multiply cost by fifteen for
identical data, so the logged call count should track the number of distinct
thresholds in the plan rather than clauses times zones.

`src/diverge.py` builds the citywide baseline as an area-weighted mean over the
full city AOI, evaluated against the same clauses, and labels it
`citywide_proxy` in every output structure, because it stands in for station
sensing rather than being a station feed. From that it computes
`lead_time_gained` per clause and zone as the hours between the local and
citywide `first_hour_met`, reported as a median and a distribution;
`silent_zones`, where a clause fired locally and citywide never did, with
population where available; and `false_calm_clauses`, which never fire citywide
but fire in at least one zone. Results go to `data/results/divergence.json`
alongside a plain-language summary.

Every reported hour is converted to Phoenix local time, UTC−7 with no DST,
before display, and a test asserts it.

**Gate: the number exists.** If it came out weak, the options before abandoning
the framing were a hotter study window, a lower-threshold clause, or finer
granularity in the highest-variance zones. The last resort, had it still been
weak by 26 August, was to pivot to "the plan triggers on the wrong metric"
using `env_params` heat index against air temperature.

---

## Phase 5 — Interface · Day 10

`app.py` in Streamlit, running entirely from cache with no API key required.

The layout as planned, top to bottom: a headline banner carrying the three
divergence numbers, large, because it is what a judge sees first; a 2D map of
the urban villages as a choropleth by lead time gained, with silent zones in a
distinct alarm colour and a legend entry to match, clicking through to the
clauses that fired there; a clause table giving id, threshold rendered as
"95°F (35.0°C)", duration, actor, extraction confidence, and the count of zones
it fired in, with each row opening its verbatim `source_text` and page number;
a divergence panel with the lead-time histogram and the citywide-against-
hyperlocal comparison, carrying the word "proxy" in the interface itself rather
than only in the README; and preset questions as buttons instead of a free-text
box.

That is the layout this phase was built against. The interface was later
rebuilt around four questions — the problem, the number, where, and what to do
— after the original proved hard to follow without someone narrating it. The
provenance path and the proxy labelling survived that rewrite unchanged.

**Gate:** unset the API key environment variable and confirm the app still
works in full.

---

## Phase 6 — Brief and hardening · Day 11

`src/brief.py` has Gemini produce a ranked action brief from
`data/results/divergence.json` and nothing else, with the structured results
passed as JSON in the prompt. Every recommendation cites a `clause_id`, page,
zone, time window, and actor, and post-validation checks each cited id and page
against the compiled clause set, regenerating on a mismatch. The system prompt
forbids introducing any fact absent from the input JSON.

Hardening was the fresh-clone test: clone to a new directory with no `.env`,
run one command, and confirm the headline number reproduces from committed
cache. That command is `python run_demo.py`, and `data/cache/` is committed
rather than gitignored so that it can work.

---

## Phase 7 — Submission · Day 12

`README.md` structured against the four judging criteria, leading with the
number before any explanation, then the problem, the approach, and a section
each for impact and relevance (40%), technical execution (35%), innovation
(15%), and communication (10%). Then the track claim, a limitations section
stating plainly that the citywide baseline is an AOI-mean proxy rather than a
station feed, and the one-command reproduction.

`VIDEO_SCRIPT.md` covers the same ground in under three minutes, opening on the
number.

---

## Standing rules for every phase

- Commit after each phase with a clear message, and never leave the repo broken
  overnight.
- If a phase runs long, cut rather than sprawl. Cut order: counterfactual, then
  satellite layer, then action brief. Never the divergence metric, and never
  the offline cache.
- Report API call counts and remaining credits after any phase that touches the
  network.
- If a result looks surprisingly good, verify it before believing it. Silent
  unit errors produce confident nonsense, and this project hit two of them.
