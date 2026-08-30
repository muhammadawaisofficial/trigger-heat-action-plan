# How this was built, and what broke

`BUILD_PLAN.md` records the order the work was done in and the gate each phase
had to pass. This document covers what that plan does not: why the project
exists, why the pieces are shaped the way they are, and the things that went
wrong badly enough to change the design.

Most of what follows is failure. That is deliberate. A system that has never
been wrong in a way its authors can describe has usually not been checked.

---

## Why we built it

The starting point was reading Phoenix's 2026 Heat Response Plan properly, all
the way through, instead of skimming it for a statistic.

It is a good document. Twenty-three numbered actions, each with a named
department attached: the Office of Heat Response and Mitigation, the Police
Department, the Human Services Department. Real budgets behind them. Page 4
states that "historical development patterns and varying topography across
Phoenix lead to neighborhood-to-neighborhood air temperature differences of 10°F
or more on summer days."

So the city already knows heat is not one number. It says so in its own plan.
And then every conditional clause in that plan is switched on and off by a
single reading, from a single station, at the airport.

That gap is the whole project. Not that the plan is bad, but that a good plan is
being executed through an instrument that cannot see what the plan itself says is
there. Nobody had put a number on what that costs, and the FortyGuard API made
the number measurable, so we measured it.

---

## Why Gemini, and why the model matters less than it looks

The compiler turns a PDF into structured rules. That is an extraction problem
with a hard correctness requirement, and there were three ways to approach it.

Hand-coding regexes over the document would work for Phoenix and break on the
next city, which defeats the point. Fine-tuning something would need training
data we do not have for a corpus of one document. So the clause compiler calls a
model, and the model is Gemini through Google AI Studio.

The reason is unglamorous: the free tier is enough. `src/llm.py` defaults to
`gemini-3.5-flash` and carries a fallback chain of `3.5-flash`, `3.7-flash`,
`2.5-flash`, `3.6-flash`, `2.5-flash-lite`. Every one of those is a free-tier
model. The pro and preview tiers return `429 RESOURCE_EXHAUSTED` without
billing attached, so none of them appear in the chain: an account with no
billing degrades to a smaller model instead of failing or quietly charging
someone. Model names are discovered by listing what the SDK offers rather than
hardcoded from memory, because a hardcoded name is a time bomb that goes off
when the vendor deprecates it.

The provider is swappable through `TRIGGER_LLM_PROVIDER` and
`TRIGGER_LLM_MODEL`, and a local Ollama model works too.

Here is the part that matters more than the choice of vendor. **Model quality
is not what makes the output trustworthy.** Every clause the compiler returns
must carry the verbatim sentence it came from and the page number it appeared
on, and `src/compile.py` then asserts that the quoted sentence appears, character
for character, in the extracted text of that page. A clause that fails is
rejected and logged.

A model that invents a citation therefore produces nothing rather than something
wrong. That check is mechanical, so it does not depend on the model behaving,
and it is why a free flash-tier model is an acceptable component here. A weaker
model scores lower on a measurement we publish (F1 0.962 against a hand-built
golden set, `python eval_compiler.py`) rather than silently poisoning the
result.

The same discipline applies to the action brief. `src/brief.py` passes the
computed results as JSON and post-validates the generated prose against them, so
a sentence containing a number the pipeline did not compute is rejected and
regenerated. `test_brief_guard.py` exists to prove the rejection path fires,
because a guarantee nobody has watched fail is not a guarantee.

The language model extracts and narrates. It never decides. Every fired-or-not
call in this system is a numeric comparison in Python.

---

## What broke

### Two unit errors, either of which would have been invisible

The FortyGuard `tcm` analytic returns Celsius. The plan is written in
Fahrenheit. Sending 95 to the API when the clause says 95 °F asks for hours
above 95 °C, which returns all zeros, with no error and no warning. It looks
exactly like a quiet night.

The fix is structural rather than careful: `fahrenheit_to_celsius` exists in
`src/schema.py` and nowhere else, the `Clause` validator refuses to construct a
clause whose `threshold_c` does not equal `round((threshold_source - 32) * 5/9, 2)`,
and `tests/test_units.py` greps the codebase to assert the conversion arithmetic
appears exactly once. Not because we are tidy, but because the second place it
appears is where it will eventually be wrong.

The second unit error was ours and lived in `src/heatwave.py`: a comparison
between an hours value and a Fahrenheit threshold. Both are floats. Both are
plausible magnitudes. Python was perfectly happy. It produced heat-wave counts
that looked reasonable and were meaningless.

Around the same time, the population lookup read one level too high in a nested
dictionary and returned 0 instead of 1,184,971. That one at least announced
itself, because a headline of "0 people" is hard to miss. The hours-versus-
degrees bug is the one worth remembering: wrong answers that look right are the
expensive kind, and the only defence is checking a number against something
computed a different way.

### The API does three things its documentation does not mention

All of this is in `docs/api_findings.md` with the reproductions attached.

`persistence` saturates at 8.0 under `filter_type=4`, across three consecutive
Julys. The documented area cap is far below what the endpoint actually accepts:
the docs describe 50 mi², and our Phoenix AOI of 1,053 mi² and 272,917 tiles is
served without complaint. Credits are flat per call regardless of area, which is
the single most consequential thing we learned, because it inverts how you
should structure requests.

That last one is why the pipeline batches by threshold rather than by zone. One
call per unique combination of threshold, direction, and analytic type covers
every urban village at once, and the zones are separated afterwards by
intersecting geometry locally. Calling per zone would have cost fifteen times as
much for identical data. The logged call count tracks the number of distinct
thresholds in the plan, not clauses times zones.

### The retraction

This is the failure we are least comfortable with and the one most worth
reading.

An earlier draft of this project measured trigger behaviour on a 2 km downtown
box, 420 tiles, and reported that a threshold outside the day's range collapses
discrimination from 394 distinct values to 1. The measurement was real. The
conclusion drawn from it was not, because it described the box rather than the
mechanism.

Over 4 km², the spatial spread in overnight low is 0.08 to 0.47 °C. Almost any
threshold falls outside a range that narrow, and the API returns a single
quantised value. Over the full 1,053 mi² AOI the same nights carry a spread of
10.85 to 13.49 °C and between 43,497 and 74,365 distinct values. We had measured
our own sampling window and mistaken it for a property of the world.

Two things came out of it. The measure was replaced with one that does not
depend on area: a trigger emits one bit per tile, fire or don't, so the binary
entropy of the firing share is comparable across days and cities in a way a
distinct-value count never is. And a claim that had passed review was withdrawn.

The retracted derivation is still in the repository. `sweep_dwell.py` and
`data/results/dwell_grid.json` remain, the script exits non-zero, and
`verify_all.py` asserts that it keeps failing. A retraction that quietly
disappears is not a retraction.

It forced a correction upstream, too. Section 2 of `docs/api_findings.md` had
concluded that at `filter_type=3`, "persistence tracks exceedance and behaves
exactly as documented." On the small box the two analytics agreed and we read
agreement as corroboration. The better explanation is that they are not
independent: they largely return the same field, including the same physically
impossible −2.51 °C minimum. The agreement was the problem, not the evidence.

### What porting to New York exposed

Adding a second city is the cheapest test of whether a pipeline is actually
city-agnostic or merely has not been asked yet. Ours had three defects that
Phoenix alone would never have surfaced.

A hardcoded cache label meant every city's stored responses claimed to be
Phoenix's. Harmless to correctness, since the cache key hashes the request
payload, but actively misleading to anyone auditing the cache, which is the one
thing that cache exists to allow.

A hardcoded population path meant running a second city overwrote the first
city's population file. We ran New York once, got 51 community districts at zero
population, and destroyed Phoenix's denominator in the same command.
`build_population.py` now refuses to write a total of zero, at line 206, with the
reason recorded next to the guard.

And the Census query took a single county. New York spans five. It returned
nothing, which is why `census_counties` is a list.

There was also a constraint we could not engineer around. The heatmap endpoint
rejects an AOI dominated by water. New York's full five-borough box, 840 mi², is
refused while Phoenix's larger 1,053 mi² box is accepted, because the New York
box spans the Atlantic, New York Harbor and Long Island Sound. New York is
therefore analysed over a reduced 346 mi² land-heavy box, and the districts
falling outside it are reported as excluded rather than silently averaged in at
zero coverage.

The failure mode taught us something about the API as well. Two attempts at the
rejected AOI hung for 2,400 seconds and emitted 40 transient status errors
before timing out. A third, polling with a shorter deadline, returned a clean
`FortyGuardError` in 105 seconds. The same rejected request presents either as a
fast error or as a forty-minute hang depending on how you poll it, which is why
our first two attempts looked like an outage rather than a rejection.

### The interface fought back

A full-city fetch in the browser was designed, built, and abandoned. A
citywide call is 118 seconds best case, the response is around 130 MB, and peak
memory during parse is roughly 540 MB against Streamlit Community Cloud's
container limit of about 1 GB. Add the documented forty-minute failure mode and
it does not belong anywhere near a judge's first thirty seconds. It was replaced
by the custom-window picker, which runs the same pipeline offline, and by a
small live probe: a 2 km box, one analytic, one day, day-cached so ten people
pressing it spend 4,220 credits once rather than ten times.

Three rendering failures cost more time than any of the analysis:

A page-background overlay was implemented as a fixed scrim `div` with content
raised above it by `z-index`. Streamlit's own wrappers create their own stacking
contexts, so the white scrim landed on top and blanked the page. It is now
painted as background layers on the app container, where content is always drawn
above its own container's background and there is no stacking order to get wrong.

The headline chart rendered blank, and it took four attempts to find out why.
Altair was hoisting layer data into a top-level `datasets` block with the layers
referencing it by name, and Streamlit re-injects chart data, so the spec arrived
with nothing to draw. One line fixes it, at `src/charts.py:70`:
`alt.data_transformers.enable("default", consolidate_datasets=False)`. Three of
the four diagnoses before it were wrong, and one of them, pinning `altair<6`,
took every page down because Altair 5 will not import on Python 3.14.

And the sidebar. Hiding Streamlit's header to remove its toolbar also hid the
control that reopens a collapsed sidebar, and Streamlit carries collapsed state
from page to page. One click could strand the city and study-window pickers for
an entire session with no way back. The pickers now live in the page body under
the navigation, for the same reason navigation does: a control that decides what
every number on the page refers to should not sit behind a panel the reader can
close.

---

## What we would do differently

Measure the mechanism at the scale you intend to claim it at, not at the scale
that is convenient to fetch. The retraction came from a 2 km box chosen because
it was fast.

Port to the second city earlier. Three real bugs were sitting in code that had
passed its tests for days, and every one of them needed a second city to become
visible.

Check surprising results against something computed a different way before
building on them. The aggregation is verified against a brute-force
recomputation with no spatial index, agreeing to 7.8 × 10⁻¹⁴
(`python test_aggregate.py`), and that habit should have been applied to the
dwell derivation before it was written up.
