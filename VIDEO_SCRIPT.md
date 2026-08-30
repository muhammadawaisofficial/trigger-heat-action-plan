# Video script

**Runs 2:50 at the pace below. Hard cap 3:00** — the handbook says max three minutes, and a judge stopping the clock mid-sentence is a bad last impression. Every word here has already been cut once against that clock; if you add a line, take one out.

Every figure below was re-checked against `run_demo.py` on the morning this was written. If one has moved, change the script, not the number.

---

## How to read this script

| Mark        | Meaning                                                 |
| ----------- | ------------------------------------------------------- |
| **bold**    | Stress this word. Land on it, don't rush past.          |
| `[beat]`    | Stop talking for about one second.                      |
| `[hold 2s]` | Silence for two seconds while the screen does the work. |
| ▸           | A screen action, not something you say.                 |

Read the narration out loud once before recording. If a sentence makes you run out of breath, cut a clause rather than speeding up.

---

## Before you press record

▸ Open every page once so nothing renders cold. The gap chart takes a moment on first load — that must happen before recording, not during.

▸ Home page, scrolled to the top. Sidebar **closed** — the nav strip is enough, and it gives the charts more width.

▸ A terminal at the repo root, cleared, with `python run_demo.py` typed but **not run**.

▸ Browser zoom at 100%. Close other tabs so no notification appears mid-take.

**Pace:** roughly 145 words a minute — this script is timed at that speed and has about ten seconds of slack. That feels slow while you're speaking and sounds right on playback. The most common mistake is rushing the first twenty seconds.

**If you fluff a line:** stop, pause two seconds in silence, then say the sentence again from its start. A clean cut is easy in editing; a half-corrected sentence is not.

---

## 0:00 – 0:22 · The number

▸ Home page. The big red number visible.

> "One point one eight **million** people. `[beat]` Seventy-two percent of **Phoenix**.
>
> `[beat]`
>
> Those are the residents who live in a neighbourhood that got hot enough to trigger the city's Heat Action Plan — on nights the city's own reading **never did**. `[beat]` So the plan stayed **off**."

`[hold 2s]` ▸ Do not move the mouse. Let the number sit on screen in silence.

**Delivery:** flat and factual. The number does the work; you do not need to sell it. This is the forty percent of the score.

---

## 0:22 – 0:45 · Why it happens

▸ Scroll up to the "What the plan sees / What people live in" panel.

> "A Heat Action Plan is a **legal document** — named departments, numeric thresholds, real budgets. `[beat]` All of it switched on and off by **one number**: one reading, from one weather station at the airport.
>
> But heat isn't one number."

`[beat]`

---

## 0:45 – 1:12 · The proof

▸ Scroll to the gap chart. Let it fill the frame.

> "Here is that night, neighbourhood by neighbourhood — every bar measured through the **FortyGuard Temperature API**, two metres above the ground.
>
> The **dashed** line is the plan's threshold. The **solid** line is the single citywide reading."

▸ Trace the solid line with the cursor, slowly.

> "The solid line sits **below** the dashed one."

▸ Now trace across the red bars, left to right.

> "And these **ten** bars were already above it. `[beat]` One number cannot be above and below the same line at once."

`[hold 2s]`

**Delivery:** slow down here. This is the most important shot in the video — the argument becomes visible instead of asserted.

---

## 1:12 – 1:40 · Why you can believe it

▸ Home page, open the "Is this live data? Where did it come from?" expander.

> "A hundred and twenty-five **real** calls to the FortyGuard API. Eleven million tiles, fifty-eight days. `[beat]` Nothing simulated, and no other weather source in this pipeline."

▸ Click through the nav strip to **Methods & evidence**. Show a clause with its verbatim quote and page number.

> "Every rule carries the **exact sentence** and the page it came from. The language model extracts and narrates — it never decides."

▸ Switch to the terminal. Run `python run_demo.py`.

> "Every response is stored. You can re-derive that number **yourself**, in one command."

`[hold 2s]` ▸ Let the output finish printing before you speak again.

---

## 1:40 – 2:05 · Not one week, not one city

▸ Home page. Sidebar → **Study window** → switch to the 2026 window. Let the numbers visibly change.

> "This isn't one hardcoded week. We re-ran the identical pipeline on August **2026**, fetched live on data it had never seen. `[beat]` Nine of fifteen villages. The same near-miss."

▸ Switch the city selector to **New York**.

> "Same pipeline, unchanged, on New York — which triggers on heat **index**, where Phoenix uses **dry-bulb**. `[beat]` Opposite choices. Same failure. Two point four million more people."

**Delivery:** "Opposite choices. Same failure." — full stop between them. Two sentences, not one.

---

## 1:58 – 2:12 · Heat waves

▸ Nav strip → **Heat waves**. The threshold ladder.

> "Same week, same measurements, each threshold in turn. At ninety degrees: ten heat waves. At a hundred and ten: **zero**. `[beat]` Only the number in the plan changes."

---

## 2:12 – 2:30 · What else it answers

▸ Nav strip → **Data centre siting**. Move a weight slider and let the ranking reorder on camera.

> "Two more questions. **Where a data centre should go** — thirty US metros, where evaporative cooling works best exactly where **water** is scarcest. The weights are yours."

▸ Nav strip → **Urban planning**.

> "And **how much tree canopy, and where** — a measured gap joined to published effect sizes."

**Delivery:** fastest section in the video. This is breadth; do not linger.

---

## 2:30 – 2:45 · Close

▸ Home page. Open "How is this measured, and what is the comparison?"

> "One thing we put in the interface, not the footnotes. Our comparator is a **proxy** for a station feed — a _generous_ one. A single real sensor would do worse.
>
> `[beat]`
>
> So one point one eight million is a **lower bound**."

`[hold 2s]` ▸ End on the number. Stop recording.

---

## Saying the numbers

Spoken numbers are where takes get ruined. Say them this way:

| On screen             | Say                                      |
| --------------------- | ---------------------------------------- |
| 1,184,971             | "one point one eight **million**"        |
| 272,917 tiles         | "two hundred and seventy thousand tiles" |
| 11,189,301            | "eleven million"                         |
| 527,500 credits       | "half a million credits", or skip it     |
| 958,205               | "nine hundred and fifty-eight thousand"  |
| 2,453,713             | "two point four million"                 |
| 1,053 mi²             | "a thousand square miles"                |
| 89.9 °F against 90 °F | "a tenth of a degree below"              |

Round in speech, keep it exact on screen. The precise figure is visible behind you, so a judge reading 1,184,971 while hearing "one point one eight million" registers both.

---

## Things to keep straight

- The citywide comparator is a **proxy**, always. Never call it a station feed.
- The app **detects** heat waves in measured data and ranks metros. It does not forecast days ahead. Do not say "predicts".
- The national work is a **thirty-metro panel**, sampled identically. Say "panel", not "grid".
- Say "125 real API calls" in the same breath as anything about stored responses.
- The headline is a **lower bound**. That is a strength; say it.

---

## Recheck before recording

| Claim                              | Where                        |
| ---------------------------------- | ---------------------------- |
| 1,184,971 · 72% · 10 of 15         | `python run_demo.py`         |
| 125 calls · 11.19M tiles · 58 days | home page expander           |
| 2026: 9 of 15 · 958,205            | Study window selector        |
| New York: 2,453,713                | city selector                |
| 90 °F → 10 waves / 110 °F → 0      | Heat waves, threshold ladder |

## After recording

1. Check the runtime. If it came out over 3:00, cut from the siting and planning section — that is breadth, not argument. Never cut the opening number or the gap chart.
2. Upload unlisted to YouTube, or to Drive with link-sharing on.
3. Paste the link into `README.md` line 3, replacing `_link pending_`.
4. Watch it once, muted, to check nothing on screen is stale or half-loaded.
