# Adding a city

Everything city-specific lives in one JSON profile. Adding a city takes five files and one environment variable, with no code changes.

This has been done once already, for New York, and `data/cities/nyc.json` is the worked example every step below refers to.

---

## What you need

| # | Input | Where it comes from | Notes |
|---|---|---|---|
| 1 | The city's published Heat Action Plan | The city's own website, as a PDF | The document is the specification. Everything else follows from it. |
| 2 | Zone boundaries, GeoJSON | The city's open-data portal | Whatever unit the city governs by: urban villages, community districts, wards, boroughs. |
| 3 | A city profile, JSON | You write it, about 40 lines | `data/cities/<slug>.json`. Copy `nyc.json` and edit. |
| 4 | Compiled clauses | `python compile.py`, then verified | Or hand-compile against the PDF, as we did for the published analysis. |
| 5 | Population per zone | `python build_population.py` | Optional. Without it the result is zones rather than people. |

---

## The steps

### 1. Get the plan and the boundaries

Download the plan PDF into `data/plan/`. Download the zone boundaries into `data/zones/` as GeoJSON, and note which property holds the zone name. Phoenix uses `NAME`, and so does New York, but this is configurable.

### 2. Write the profile

`data/cities/<slug>.json`. The fields that need thought rather than copying:

`aoi_west` / `aoi_south` / `aoi_east` / `aoi_north`: the bounding box the API is asked for. Two constraints apply here, both learned by measurement:

- Clip to land. The heatmap endpoint rejects an AOI dominated by water. New York's full five-borough box, 840 mi², is rejected while Phoenix's larger 1,053 mi² box is accepted, because the New York box spans the Atlantic, New York Harbor and Long Island Sound. New York is therefore analysed over a reduced 346 mi² land-heavy box, and the districts that fall outside it are reported as excluded rather than silently averaged in at zero coverage.
- One box rather than several. Credits are flat per call regardless of area, so a single box covering the whole city costs the same as one small one.

`utc_offset_h` and `observes_dst`. `time_of_measure` is returned in UTC. Arizona is UTC−7 year-round and does not observe DST; New York is UTC−4 through the entire summer heat season but does observe it. Getting this wrong shifts every peak-hour figure.

`department_key`: the abbreviations the plan itself prints, mapped to full department names. This is what lets an alert name the department that owns the clause, and it comes from the plan's own key rather than from us.

`census_state` / `census_counties`: FIPS codes for the population join. A multi-county city needs all of them: New York spans five, and passing one silently returns nothing.

### 3. Compile the plan

```bash
TRIGGER_CITY=<slug> python compile.py
```

Every clause the compiler proposes carries a verbatim quote and a page number, and the quote is checked against the extracted text of the page it cites before the clause can be evaluated. A clause whose quote does not appear verbatim on its stated page is rejected. That check is what makes an unfamiliar plan safe to compile.

For the published analysis we ran on a hand-verified golden set rather than raw compiler output, and reported the compiler's own score separately. For a new city, either path works; `build_golden.py` mechanically re-verifies every quote against the PDF.

### 4. Build the population join, if you want people rather than polygons

```bash
CENSUS_API_KEY=... TRIGGER_CITY=<slug> python build_population.py
```

Areal interpolation of Census block-group population onto the zone boundaries. Static, fetched once, committed.

### 5. Run it

```bash
FORTYGUARD_API_KEY=... TRIGGER_CITY=<slug> python run_analysis.py --start ... --end ...
```

The result lands in `data/results/` and is picked up by the app's study-window selector automatically.

---

## What does not change

The pipeline. `evaluate.py`, `aggregate.py`, `diverge.py`, `charts.py`, and every page of the app read the active profile through `study.py` and never name a city. The New York run tests that: the same code, unmodified, produced 2,453,713 people across 51 community districts.

---

## One hard constraint

The FortyGuard API covers the United States only. A profile for a non-US city will compile its plan correctly and then fail at evaluation, because the heatmap endpoint returns errors or empty results for polygons outside the US. This is the reason this project studies Phoenix rather than a South Asian city, where heat action plans are furthest developed and the need is greatest.

## What porting actually exposed

Adding New York surfaced three defects that Phoenix alone never would have, and each one is now fixed and tested:

- A hardcoded cache label meant every city's responses claimed to be Phoenix's. Harmless to correctness, since the cache key hashes the request payload, but misleading to anyone auditing the cache.
- A hardcoded population path meant running under a second city overwrote the first city's population file. Running it for New York once produced 51 districts at zero population and destroyed Phoenix's denominator. `build_population.py` now refuses to write a total of zero.
- A single-county Census query returned nothing for a five-county city, which is why `census_counties` is a list.

---

## Tips for Contributors

When adding or testing a new city profile:

1. **Verify Coordinate Ordering**: Ensure all spatial polygons and GeoJSON boundary files use strict `[longitude, latitude]` order.
2. **Test Bounding Boxes**: Keep the AOI clipped closely to land to avoid FortyGuard API heatmap rejections on open water bodies.
3. **Run Validation Checks**: Use `python build_golden.py` and `python verify_all.py` to ensure quote verification and analytical pipelines run cleanly for your new city profile.

