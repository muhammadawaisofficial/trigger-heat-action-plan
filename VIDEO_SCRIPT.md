# Video script — 2:40

Rewritten to lead with the finding and to make the FortyGuard API's role explicit throughout, rather than mentioning it once and moving on.

Every figure below comes from `python run_demo.py` and `python verify_all.py`. Check them the morning you record; if one has moved, change the script, not the number.

## Before you hit record

Two windows, both prepared:

- **Browser** — the deployed app, or `streamlit run app.py`. Open every page once first so nothing renders cold on camera. Start on the home page, scrolled to top.
- **Terminal** — at the repo root, cleared, ready to run `python run_demo.py`.

Close the sidebar before recording. The in-page nav strip is enough, and a closed sidebar gives the charts more width.

Move between pages using the coloured nav strip, not the address bar. Each page carries its own accent on that bar — red, orange, blue, green, violet — so clicking across it reads as one structured app with five rooms. That transition is free production value; use it every time the script says "screen: switch to."

---

## 0:00 – 0:25 · The number first

**Screen:** home page, top. Scroll immediately to the big red number.

> "One-point-one-eight million people. Seventy-two percent of Phoenix.
>
> Those are the residents who live in a neighbourhood that got hot enough to trigger the city's Heat Action Plan — on nights the city's own reading never did. So the plan stayed off."

**Pause on the number for a full beat before moving.** This is the 40% of the score; do not rush past it to get to the architecture.

---

## 0:25 – 0:50 · Why it happens

**Screen:** scroll up to the "What the plan sees / What people live in" panel.

> "A Heat Action Plan is a legal document. Twenty-three actions, named departments, numeric thresholds. Open cooling centres at ninety degrees overnight.
>
> The whole thing is switched on and off by **one number** — one reading, from one weather station at the airport. But heat isn't one number, and FortyGuard's data is what let us prove that at the resolution people actually live at."

---

## 0:50 – 1:15 · The proof, in one chart

**Screen:** the gap chart. Let it fill the frame.

> "Here is that night, neighbourhood by neighbourhood — every bar measured through the FortyGuard Temperature API, two metres above the ground, at hundred-metre resolution.
>
> The dashed line is the threshold the plan names. The solid line is the single citywide reading. **The solid line sits below the dashed one — so the plan stayed off.**
>
> And these ten bars are already above it."

**[trace the red bars crossing the dashed line with the cursor]**

> "One number cannot be above and below the same line at once. That is the entire failure of the trigger, in one picture."

---

## 1:15 – 1:45 · Built on the API, and auditable because of it

**Screen:** home page, open the "Is this live data? Where did it come from?" expander — four metric tiles: real API calls, tiles fetched, credits spent, MB committed.

> "A hundred and twenty-five calls to the FortyGuard API. Eleven million tiles. Fifty-eight distinct days. Half a million credits. Nothing simulated, and no other weather source anywhere in this pipeline.
>
> And because a single call covers the whole city — a thousand square miles, two hundred and seventy thousand tiles, for one flat credit cost — we measure Phoenix in one request per day instead of fifteen."

**Screen:** switch to Methods & evidence via the nav strip, clause provenance panel with a quote visible.

> "Every rule the plan is built from carries the verbatim sentence and the page it came from. The language model extracts and narrates. It never decides — every fired-or-not call is a plain numeric comparison in Python, against FortyGuard measurements."

**Screen:** switch to the terminal. Run `python run_demo.py`.

> "And we kept every response. So you can re-derive that number yourself, in one command, and check us instead of taking my word for it."

**Let the output land on screen.** Reproducibility is the 35%.

---

## 1:45 – 2:10 · Not one week, and not one city

**Screen:** home page, the Study window selector in the sidebar. Switch to the 2026 window and let the numbers change.

> "This isn't one hardcoded week. We re-ran the identical pipeline on August 2026 — fetched live from the API, a week the analysis had never seen — and the finding reproduced. Nine of fifteen villages. Nine hundred and fifty-eight thousand people. The same near-miss signature."

**Screen:** Methods & evidence, the date-range picker.

> "And you can point it anywhere. Any dates the API serves, back to 2019. Pick a window, and it runs the whole analysis on it."

**Screen:** switch the city selector to New York.

> "Same pipeline, unchanged, on New York's plan and New York's districts. New York triggers on heat index; Phoenix triggers on dry-bulb. Opposite choices, same failure."

---

## 2:10 – 2:30 · What else the same measurement answers

**Screen:** the siting page tradeoff scatter, then the urban planning dumbbell. Move quickly — these are breadth, not the argument.

> "The same hyperlocal layer answers two more questions. Where a data centre should go — free-cooling hours and wet-bulb measured across thirty US metros, where the places evaporative cooling works best are exactly the places that can least spare the water.
>
> And how much tree canopy, and where — a measured thermal gap joined to published cooling effect sizes, so a recommendation carries a magnitude."

---

## 2:30 – 2:40 · The honest close

**Screen:** back to the home page, open "How is this measured, and what is the comparison?"

> "One thing we put in the interface, not the footnotes. Our citywide comparator is the average across the whole city — a **proxy** for a station feed. It's a *generous* stand-in: a single real sensor would do worse.
>
> So 1.18 million is a **lower bound**."

**End on the number.**

---

## Figures to re-check the morning you record

| Claim | Source |
|---|---|
| 1,184,971 · 72% of Phoenix | `run_demo.py` |
| 10 of 15 urban villages | `run_demo.py` |
| 125 calls · 11.19M tiles · 527,500 credits · 58 days | `data/results/api_usage.json`, or the home page expander |
| 2026 replication: 9 of 15, 958,205 | Study window selector, or the README |
| 90 °F → 10 waves / 110 °F → 0 | Heat waves page, threshold ladder |
| 30 metros, wet-bulb measured | `data/results/wetbulb.json` |

## Things to keep straight on camera

- The citywide comparator is a **proxy**, always. Never call it a station feed.
- The app **detects** heat waves in measured data and ranks metros climatologically. The API serves history and about twelve hours ahead, so do not describe it as a multi-day forecast.
- The national work is a **30-metro panel**, sampled identically. Say "panel," not "grid."
- Say "125 real API calls" in the same breath as anything about the stored responses. The data is real and was fetched through the API; the responses are kept so the result can be audited.
- The headline is a **lower bound**. That is a strength, and it is worth saying out loud.
