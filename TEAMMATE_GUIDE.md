## 1. The one-sentence pitch

Heat Action Plans (legal documents) trigger city response off **one citywide temperature reading**. Heat isn't citywide. TRIGGER compiles a plan's rules into code, re-checks each rule against FortyGuard's 2m-resolution data, and measures how many people the citywide trigger misses.

**Headline number:** in Phoenix, **1,184,971 people (72%)** live in zones where a plan clause's condition was met but the citywide trigger never fired.

## 2. Why this wins (judged 40% impact, 35% execution, 15% innovation, 10% comms)

Most entrants build a heat map + LLM chat layer. We're the only one **compiling actual government policy documents into testable rules**. That's the moat — protect it. Every design choice should serve the headline number and its reproducibility, not the UI.

## 3. The pipeline (this is the whole architecture)

```
Heat Action Plan (PDF)
   │
   [A] COMPILE   src/compile.py    PDF → Clause objects (LLM extracts, never decides)
   │                                each clause: verbatim quote + page number, mandatory
   │
   [B] EVALUATE  src/evaluate.py   clause × zone × day → FIRED/NOT FIRED
   │                                two arms, same logic: hyperlocal (per zone) vs
   │                                citywide_proxy (one area-weighted city number)
   │
   [C] DIVERGE   src/diverge.py    THE NUMBER. lead time gained / silent zones /
   │                                false-calm clauses — hyperlocal vs proxy
   │
   [D] BRIEF     src/brief.py      ranked actions, LLM narrates pre-computed facts only
```

**Golden rule enforced everywhere:** the LLM extracts and writes prose. It never computes a threshold, a FIRED/NOT FIRED decision, or a number. All decision logic is deterministic Python. This is why the demo is defensible in front of engineer judges.

## 4. What "citywide" actually means here

We don't have a real airport-station feed. Our proxy = area-weighted mean over the _entire city polygon_, using FortyGuard's own tiles. It's a fair stand-in for "one number for the whole city," but it is **not** real station data — say so everywhere (UI, README, video). Never let it read as more authoritative than it is.

## 5. Repo map (what's real, what's WIP)

```
src/
  cache.py        disk cache keyed on request hash — demo runs offline, zero network calls on 2nd run
  schema.py       Clause dataclass; °F→°C conversion happens ONCE here, nowhere else
  city.py         city profile system — one JSON per city, nothing city-specific hardcoded elsewhere
  study.py        thin shim so pipeline code says study.city_aoi() without knowing which city is active
  geo.py          AOI/area math, GeoJSON [lon, lat] order (get this backwards → silent wrong answers)
  compile.py      PDF → clauses, LLM extraction with mandatory verbatim quote + page
  parse.py        FortyGuard response → tiles, handles both response schemas (tcm vs exceedance/etc.)
  aggregate.py    tiles → zones, area-weighted (never nearest-tile)
  evaluate.py     clause × zone → FIRED/NOT FIRED + margin, both arms
  diverge.py      the three headline metrics — HARD GATE, this must always produce a number
  brief.py        ranked actions, LLM narrates verified results only
  alerts.py       divergence-based alerting: fires when a clause is met in a zone but proxy never fired
  heatwave.py     per-zone consecutive-hot-night detection (SEVERE/SIGNIFICANT/NOTABLE)
  siting.py       single-city cooling-cost model (kWh, $ from free-cooling hours)
  site_model.py   NATIONAL multi-factor data-centre siting (see §6)
  ui.py           shared CSS/masthead/loaders — every page imports this so styling can't drift

app.py                    home page: city switcher (Phoenix / NYC), clickable map, alerts, brief
pages/2_Data_Centre_Siting.py   national siting page (built, working)

data/
  cache/          committed API responses — judges can run offline
  plan/           source PDFs
  golden/         hand-labelled clauses for eval_compiler.py
  zones/          city admin boundaries
  cities/*.json   per-city profile (AOI, plan URL, department key, population file)
  metros.json     30-metro national panel (data-centre siting)
  siting_factors.json   state-level reference constants (electricity, water, disaster risk) — NOT measured by us, labelled as such
  heat_guidance.json    5-tier danger levels + precautions, NWS-HeatRisk-style analogue
  results/national.json, wetbulb.json   fetched national panel data
```

**Not yet built** (still pending): a dedicated Heat Waves page and Urban Planning page in `pages/`. The underlying modules (`heatwave.py`, `heat_guidance.json`) exist and work — they just aren't wired into their own page yet. `app.py` currently only switches between Phoenix/NYC on the home page.

## 6. The two things beyond the core pipeline

**a) Divergence alerts (`alerts.py`)** — not a generic heat alert. It fires specifically when a _legal obligation_ (a plan clause) is met in a zone but the citywide number that's supposed to trigger it never crosses threshold. Severity by population affected (RED ≥100k, AMBER ≥25k, else YELLOW).

**b) National data-centre siting (`site_model.py` + `pages/2_Data_Centre_Siting.py`)** — "where should a data centre go, nationally" needed real research, not a heat map. Key finding, actually measured: evaporative cooling works best exactly where water is scarcest (Phoenix/Vegas/Reno/SLC: great wet-bulb, extreme water stress) — and Houston is the genuine worst case (zero free-cooling hours **and** bad wet-bulb, both cooling routes closed). The model outputs one of 4 cooling strategies per metro instead of one fake composite score. Honesty split is explicit and shown in the UI:

- **measured by us at 100m** (FortyGuard): free-cooling hours, wet-bulb, overnight low
- **reference constants at state resolution** (published: EIA, WRI, FEMA): electricity price, water stress, disaster risk, grid headroom

This asymmetry is the same criticism the whole project makes of heat plans, pointed back at our own model — say that out loud, judges reward it.

**Why "whole country" ≠ full 100m grid:** the API's flat 4,220-credit/call cost covers 1,053 mi² per call; continental US is ~3.1M mi², needing ~3,000 calls against a ~472-call remaining budget. Solution: 30 real metros (covers every US climate zone + real data-center markets), sampled identically, so comparisons are sound even though coverage is a sample — not fabricated national coverage.

## 7. FortyGuard API — traps that fail silently (see full detail in root SPEC.md §5)

- `threshold` param is **°C**; the plan's thresholds are written in **°F**. Convert once, in `schema.py`.
- `time_of_measure` returns **UTC** hour; Phoenix is UTC−7 year-round (no DST).
- `tcm` response uses `properties.average_temperature`; exceedance/persistence use `properties.value`. One parser handles both (`parse.py`).
- `exceedance` = **count of hours** past threshold, not degree-hours.
- `persistence` is **broken at filter_type=4** (saturates at 8.0) — use filter_type=3.
- Credits are **4,220 flat per call** regardless of tile count — never make small calls.
- Tile aggregation must be **area-weighted over every overlapping tile**, never nearest-tile.

## 8. Rules we're holding ourselves to

- Cache everything, commit the cache — the whole demo must run with **no API key**, offline, one command.
- No feature that isn't real: no faked national grid coverage, no faked multi-day heat-wave forecast (API has no forecast horizon — we built historical detection + climatological ranking + an honest 12-hour outlook instead, not a lie dressed as a forecast).
- Every recommendation must trace to a clause + page + verbatim quote, or a measured number — never unsupported LLM prose.
- Deterministic logic decides; LLM narrates. Never the reverse.

## 9. What's left (in priority order)

1. `pages/1_Heat_Waves.py` — wire up `heatwave.py` + `heat_guidance.json` into the 30-metro national panel, with the honest "no forecast beyond 12h" caveat
2. Urban Planning recommendations page (national)
3. Run the test suite (`test_aggregate.py`, `test_brief_guard.py`, `test_claim.py`) + add AppTest coverage for the new pages
4. Finish the responsive/aesthetic layout pass across all pages (CSS breakpoints exist in `src/ui.py`, not fully applied everywhere yet)
5. Push to GitHub, confirm Streamlit Cloud redeploy
6. Update `README.md` for the new scope; update `VIDEO_SCRIPT.md`; record the 3-minute video (headline number in first 30 seconds)

## 10. If you only read one file before coding

`src/diverge.py` — it's the hard gate, the whole reason this project exists, and everything upstream (compile/parse/aggregate/evaluate) exists only to feed it correct inputs.
