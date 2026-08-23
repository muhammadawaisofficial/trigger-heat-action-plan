# Video script — 2:30

Rewritten after the dwell-time retraction. **The previous version opened on a
framing we withdrew and quoted numbers that no longer stand.** Every figure below
is checked against `verify_all.py` output as of commit `5fa7af3`.

Record with the app **already loaded** and a terminal ready. **Never call the API
live** — polling takes minutes and will look broken on camera.

Two windows open before you start:
- Browser: `streamlit run app.py`, scrolled to the top so the hero number and the
  silent-zones map are both in frame
- Terminal: at the repo root, ready to run `python run_demo.py`

---

## 0:00 – 0:20 · The number, on the map

**Screen:** the app at the top. The big red number and the silent-zones map are
both visible without scrolling.

> "Phoenix has a Heat Response Plan. It's a legal document — twenty-three
> actions, named departments, numeric temperature thresholds."
>
> **[point at the map — the ten red villages]**
>
> "**One point one eight million people. Seventy-two percent of Phoenix.** They
> live in the ten of fifteen urban villages that met the City's own
> overnight-heat benchmark — on nights the citywide reading never fired."

---

## 0:20 – 0:50 · One station, one thousand square miles

**Screen:** zoom the hero map until the Sky Harbor plane marker is centred.

> "That citywide reading comes from one weather station. Here, at the airport.
> **One number for one thousand and fifty-three square miles.**"
>
> "And the City already knows heat isn't one number. Page four of their own plan
> says neighbourhoods differ by **ten degrees or more**. We measured twenty-one
> degrees overnight."
>
> "Page nine says **sixty-three percent of heat deaths happen on days no warning
> fires.** The plan is good. The sensor is in the wrong place."

---

## 0:50 – 1:30 · Compiling a clause, with its receipt

**Screen:** scroll to "Explore the result", Mission 4 — the clause inventory.
Click into a clause so the verbatim quote and the page link are visible.

> "We didn't hardcode those rules. We compiled them out of the published PDF."
>
> **[point at the source quote and the page link]**
>
> "Every clause carries a word-for-word quote and a page number. And here's the
> part that matters — **if that quote isn't found on that page, the clause is
> thrown away automatically.** A model that invents a citation produces nothing,
> not a wrong answer."
>
> "On the free Gemini tier that's an **F1 of 0.962**, with a hundred percent
> quote-verification rate. Though I'll come back to what that score doesn't
> cover."
>
> "Compiling the whole document also found something we weren't looking for.
> **Twenty of the twenty-three actions aren't conditioned on heat at all** —
> they run on the calendar. Of the two that do respond to temperature, both fire
> citywide."

---

## 1:30 – 2:00 · The lead time, and the replication

**Screen:** Mission 1 for the worst day, then Mission 3 for the lead-time view.

> "Across the study week: **twenty zone-days** where a neighbourhood met the
> condition and the city stayed quiet. Median lead time, **four days.**"
>
> "On the eighth of August the citywide average overnight low read **eighty-nine
> point nine.** The City's benchmark is ninety. One tenth of a degree. Nothing
> fired — and ten villages were above it."
>
> **[switch to the terminal, run `python run_demo.py`, let the replication table
> land]**
>
> "And it isn't one lucky week. We re-ran the identical pipeline on **live data
> from August 2026** — a year later, data the analysis had never seen. Same
> pattern: **nine villages, nine hundred and fifty-eight thousand people**, and
> the same near-miss signature — eighty-nine point four against a ninety-degree
> threshold."

---

## 2:00 – 2:20 · What we got wrong

**Screen:** the app's "What we retracted" tab. Hold on it — do not rush this.

> "One more thing, and it's the part I'd want to see in someone else's
> submission."
>
> "We had a second headline. We measured that adding a **duration requirement**
> to the plan's existing hundred-and-five-degree threshold would restore its
> ability to target — and then we retracted it."
>
> "Two reasons. The analytic we used returns a **total** of hot hours, but a
> duration clause describes a **continuous spell** — wrong tool for the
> question. And when we switched to the right one, it returned runs of
> twenty-six hours inside a single day, and negative runs. Impossible values."
>
> "So **FortyGuard has no trustworthy duration analytic at city scale.** We
> published that as a negative finding instead of deleting it — and our
> verification script now asserts that the broken result *stays* broken, so the
> retraction can't quietly go stale."
>
> "That's also why I flagged the F1 score. **Our compiler missed the very clause
> this headline rests on.** The published analysis runs on a hand-checked set. We
> report the compiler's accuracy; we don't rely on it."

---

## 2:20 – 2:30 · Close

**Screen:** the terminal, `run_demo.py` output still on screen.

> "Everything reproduces offline. Clone it, no API key, one command."
>
> "Change the PDF, the boundaries and the bounding box, and it runs on any US
> city. The plan is fine. It's being executed with the wrong sensor — and now
> that gap has a number."

---

## Recording notes

- **The number must land inside the first twenty seconds.** Non-negotiable.
- Say **"proxy"** or **"lower bound"** whenever the baseline comes up. An
  engineer judge who catches an overclaim discounts everything else you said.
- **Give the retraction its full twenty seconds.** It is the strongest
  credibility signal in the video and the thing almost no other entrant will
  have. Do not apologise through it — deliver it as a result.
- The strongest single shot is the terminal printing the headline with no key
  set. Hold on it.
- Rehearse three times, record the fourth.
- Under three minutes. If over, cut from 0:50–1:30 — never from the number and
  never from the retraction.

## Numbers to get right

| | |
|---|---|
| People in silent zones | 1,184,971 (72% of Phoenix) |
| Silent zones | 10 of 15 urban villages |
| Silent zone-days | 20 |
| Median lead time | 4 days |
| Worst day | 8 Aug 2025 — proxy 89.9 °F vs 90 °F threshold |
| False-calm days | 3 of 7 |
| Calendar-activated actions | 20 of 23 |
| Compiler F1 | 0.962, free Gemini tier, 100% quote verification |
| Plan's own claim vs measured | 10 °F stated, 21.2 °F measured overnight |
| Replication (live 2026) | 9 villages, 958,205 people, proxy 89.4 °F |
| AOI | 1,053 mi², 272,917 tiles/day at 100 m |

## Do NOT say — retracted or superseded

| Dead figure | Why |
|---|---|
| ~~0.090 → 0.974 bits~~ | Retracted. Derived from a smoothed field, and from the wrong analytic. |
| ~~"a dwell requirement recovers targeting"~~ | Retracted — no trustworthy duration analytic at city scale. |
| ~~"1 → 251 distinct values"~~ | A 2 km box artefact, not a citywide finding. |
| ~~"comparable to the San Jose sample"~~ | That reference cannot be sourced. Make no comparison. |
| ~~"the plan has 8 strategies"~~ | It has 6. |
| ~~"tcm returns °F"~~ | It returns °C. |
