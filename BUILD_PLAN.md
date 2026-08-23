# TRIGGER — Build Plan

Paste **one phase at a time** into Claude Code. Wait for its stop signal, verify
the acceptance criterion yourself, then paste the next.

`CLAUDE.md` must be in the repo root first — every phase assumes it has been read.

**Environment:** `FORTYGUARD_API_KEY`, `GEMINI_API_KEY` in `.env`. `.env` in
`.gitignore`. Never commit keys.

---

## Phase 0 — Verify (30 min) · Day 6

```
Read CLAUDE.md.

Set up the repo from the FortyGuard quickstart template. Vendor their
`fortyguard` client package unmodified. Create .env.example, .gitignore,
requirements.txt.

Then run ONE verification call and stop:
- small downtown Phoenix polygon (~2 km²)
- analytic_type="persistence", threshold=35.0, direction="above"
- filter_type=4, start_date/end_date covering one week of July 2025
- granularity=100

Print the full stats_data plus the count of tiles with value > 0.
Then try the same window for July 2024 and July 2023.

STOP. Report all three. Do not build anything else.
```

**Gate:** `n_cells` in the hundreds+, and a real spread between `min` and `max`.
Reference: FortyGuard's San Jose sample spans 2.07 → 8.73 hours across 329
tiles. If Phoenix is flatter than that, or a year returns empty, decide the
study window before continuing.

---

## Phase 1 — Foundation (Day 6, evening)

```
Build the foundation layer. No API calls beyond what the cache wraps.

1. src/cache.py
   - Disk cache at data/cache/, key = sha256 of the canonical JSON request
     payload (sorted keys).
   - Decorator or wrapper around the client's heatmap and env_params calls.
   - Second identical call must make ZERO network requests.
   - Include a `list_cache()` helper and a manifest file recording what each
     key represents in human-readable form.

2. src/schema.py
   - Clause dataclass exactly as specified in CLAUDE.md.
   - fahrenheit_to_celsius() lives here and NOWHERE else in the codebase.
   - Validator: threshold_c must equal round((threshold_source - 32) * 5/9, 2);
     source_text and source_page mandatory and non-empty; operator in
     {above, below}; extraction_conf in [0,1].
   - to_api_params() returning the exact kwargs for create_heatmap.

3. src/parse.py
   - parse_heatmap(response) -> list[Tile], where Tile has
     tile_id, value, units, polygon (shapely, built from [lon, lat] coords).
   - MUST handle both shapes: properties.value for analysis types,
     properties.average_temperature for tcm.
   - Raise a clear error if neither field is present — never return silently
     empty.

4. tests/ — pytest covering: cache hit/miss, the °F→°C round trip, both parse
   paths, and [lon, lat] ordering (a Phoenix tile must land near
   lon -112, lat 33 — assert this, it catches coordinate swaps immediately).

Run the tests. STOP and report results.
```

**Gate:** all tests green, including the coordinate-order assertion.

---

## Phase 2 — The compiler (Day 7)

This is the innovation. Give it the most care.

```
Build the clause compiler using the Gemini API (GEMINI_API_KEY in .env).

First: check which Gemini model names are currently valid by listing available
models via the SDK. Do not hardcode a model name from memory. Prefer a fast
model with JSON output support; record the chosen name in a constant.

1. src/compile.py
   - Input: data/plan/phoenix_2026_heat_response_plan.pdf
   - Extract text page by page, preserving page numbers.
   - Chunk by section so a clause and its context stay together.
   - For each chunk, call Gemini with JSON output mode and a schema matching
     the Clause dataclass.

   Prompt rules (enforce these in the system prompt AND validate the output):
   - Every clause MUST include the verbatim source sentence and its page number.
   - If a field is inferred rather than stated, set extraction_note explaining
     the inference and lower extraction_conf.
   - If no numeric threshold is present, do NOT invent one — return the clause
     with threshold_source=None and flag it for review.
   - Thresholds as written (°F). Conversion happens in schema.py, not here.
   - actor must come from the plan's own department key. Map abbreviations
     (OHRM, PD, HSD, OEM, PRD, etc.) to full department names.

   - Post-validate every returned clause: assert source_text appears verbatim
     in the source page text. Reject and log any clause that fails — this is
     the anti-hallucination guarantee and it must be mechanical, not trusted.

2. eval_compiler.py
   - Load data/golden/clauses.json (hand-compiled by teammate).
   - Match compiled vs golden on clause_id and on threshold+actor pairs.
   - Report precision, recall, F1, plus a field-level accuracy table
     (threshold, duration, actor, action).
   - Write results to data/eval/compiler_report.json AND print a summary.

3. Save compiled output to data/clauses/compiled.json.

Run eval_compiler.py. STOP and report precision/recall and any clauses that
failed verbatim validation.
```

**Gate:** F1 above ~0.7 and zero clauses failing verbatim validation. Below
that, iterate the prompt — do not proceed on a weak compiler, everything
downstream inherits its errors.

---

## Phase 3 — Zones and aggregation (Day 8, morning)

```
1. Acquire Phoenix administrative boundaries.
   - Preferred: City of Phoenix **urban villages** (15 official named units —
     Camelback East, Maryvale, South Mountain, Encanto, etc.). Ideal
     granularity: official, named, few enough to display, large enough to
     contain many tiles.
   - Source from City of Phoenix open data / ArcGIS as GeoJSON.
   - Fallback: census tracts clipped to city limits.
   - Save to data/zones/phoenix_villages.geojson. Commit it.

2. src/aggregate.py
   - aggregate_tiles_to_zones(tiles, zones) -> per-zone stats.
   - AREA-WEIGHTED mean over every tile whose polygon intersects the zone,
     weighted by intersection area. Not nearest-tile, not centroid lookup.
   - Also return max, min, tile_count, and total_intersection_area per zone.
   - Warn loudly if any zone has tile_count < 5 (under-covered).

3. Verify: pick one small zone, compute its weighted mean by hand from the
   intersecting tiles, assert the function matches. Include as a test.

STOP. Report per-zone tile counts and flag any under-covered zones.
```

**Gate:** every zone has meaningful tile coverage; hand-verification passes.

---

## Phase 4 — Evaluation and the number (Day 8 evening → Day 9)

**This is the hard gate. Nothing after this matters if this doesn't land.**

```
1. src/evaluate.py
   - For each clause x each zone, over the chosen study window:
     * duration_hours present  -> use analytic_type="persistence"
                                  (longest CONSECUTIVE run)
     * duration_hours absent   -> use analytic_type="exceedance"
                                  (total hours past threshold)
     * threshold_c and operator -> threshold and direction params
   - Return ClauseResult: clause_id, zone_id, fired (bool),
     value, margin (value - required), first_hour_met (local time).
   - Batch API calls: one call per unique (threshold, direction, analytic_type)
     covers ALL zones at once — aggregate afterwards. Do NOT call per zone.
     Log the number of API calls made; it should be roughly the number of
     distinct thresholds in the plan, not clauses x zones.

2. src/diverge.py
   - Citywide baseline: area-weighted mean over the FULL city AOI, evaluated
     against the same clauses. Label it `citywide_proxy` in every output
     structure — it is a proxy for station sensing, not a station feed.
   - Compute:
     * lead_time_gained: per clause+zone, hours between first_hour_met locally
       and first_hour_met citywide. Report median and distribution.
     * silent_zones: zones where fired=True locally but citywide never fired.
       Include population if available.
     * false_calm_clauses: clauses never firing citywide but firing in >=1 zone.
   - Write data/results/divergence.json.
   - Print a plain-language summary block.

3. Convert all reported hours to Phoenix local time (UTC-7, no DST) before
   display. Assert this in a test.

Run the full pipeline end to end from cache. STOP and report the three metrics.
```

**Gate: THE NUMBER EXISTS.** If it's weak, before abandoning — try a hotter
study window, a lower-threshold clause, or finer granularity in the highest-
variance zones. If it's still weak by end of 26 Aug, pivot the framing to "the
plan triggers on the wrong metric" using env_params heat_index vs air
temperature, and ship that instead.

---

## Phase 5 — Interface (Day 10)

```
Build app.py with Streamlit. Runs entirely from cache; no API key required.

Layout, in this order top to bottom:

1. HEADLINE BANNER — the three divergence numbers, large. This is what a judge
   sees first. Format: "N zones met the trigger H hours before the city
   declared it. M zones met it and the city never did. K clauses never fired."

2. MAP (folium or pydeck, 2D — no globe)
   - Phoenix urban villages, choropleth by lead time gained.
   - SILENT ZONES in a distinct alarm colour with a clear legend entry. This is
     the hero visual — make it unmistakable.
   - Click a zone -> side panel of clauses that fired there.

3. CLAUSE TABLE
   - Every compiled clause: id, threshold as "95°F (35.0°C)", duration, actor,
     extraction confidence, fired-in-N-zones.
   - Click a clause -> shows verbatim source_text and page number.
     This provenance path must work; it is a scored differentiator.

4. DIVERGENCE PANEL
   - Lead time distribution histogram.
   - Citywide vs hyperlocal comparison, with "citywide (proxy)" labelled
     visibly in the UI, not just the README.

5. Preset missions as buttons (NOT free-text input):
   - "Which clauses fired during the July heat event?"
   - "Which zones did the plan miss?"
   - "What should OHRM do first tomorrow?"
   - "Which clauses never fire at all?"

Use Tailwind-free plain Streamlit; do not over-style. Correctness over polish.

STOP. Report that it runs offline with no API key set.
```

**Gate:** unset the API key env var and confirm the app still fully works.

---

## Phase 6 — Brief and hardening (Day 11)

```
1. src/brief.py
   - Gemini generates a ranked action brief FROM data/results/divergence.json
     ONLY. Pass the structured results as JSON in the prompt.
   - Every recommendation must cite clause_id, page, zone, time window, actor.
   - Post-validate: every clause_id and page number in the output must exist
     in the compiled clause set. Reject and regenerate on mismatch.
   - System prompt must forbid introducing any fact not present in the input
     JSON.

2. Hardening:
   - Fresh-clone test: clone to a new directory, no .env, run one command,
     confirm the headline number reproduces from committed cache.
   - Add `make demo` or `python run_demo.py` as that one command.
   - Confirm data/cache/ is committed and not gitignored.

STOP and report the fresh-clone result.
```

---

## Phase 7 — Submission (Day 12)

```
Write README.md structured against the judging criteria:

## The number (first thing on the page, before any explanation)
## Problem — plans trigger on one citywide reading
## Approach — compile the plan, re-evaluate on 2m data
## Impact & Relevance (40%) — who acts differently, and on what evidence
## Technical Execution (35%) — architecture, the unit chain, area-weighted
   aggregation, batched API calls, compiler F1 score
## Innovation (15%) — policy-document compilation; nobody else does this
## Communication (10%) — demo link, video, one-command reproduction
## Tracks — 04 primary, 07 co-primary, 05 supporting
## Limitations and honesty
   - citywide baseline is an AOI-mean proxy, not a station feed
   - compiler F1 is X; N clauses required human correction
   - single city, single study window
   - what we would validate next: Maricopa County heat-death records
## Reproduce in one command

Also write VIDEO_SCRIPT.md: 2.5 minutes.
  0:00-0:20  the number, on the silent-zones map
  0:20-0:50  the problem — one station, a whole city
  0:50-1:30  compile a clause live: PDF sentence -> rule -> evaluated per zone
  1:30-2:10  the divergence result and one named action for a named department
  2:10-2:30  limitations, stated plainly, and what it generalises to

STOP.
```

---

## Standing rules for every phase

- After each phase: commit with a clear message. Never leave the repo broken
  overnight.
- If a phase runs long, say so and cut rather than sprawl. Cut order:
  counterfactual → satellite layer → action brief. Never the divergence metric
  or the offline cache.
- Report API call counts and remaining credits after any phase that hits the
  network.
- If a result looks surprisingly good, verify it before celebrating — silent
  unit errors produce confident nonsense.
