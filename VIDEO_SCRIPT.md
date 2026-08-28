# Video script — 2:40

Rewritten for the five-page app. **The previous version described a single-page
layout that no longer exists** and opened by scrolling to a hero number that is
now the *second* thing on the page, after the problem it answers.

Every figure below is produced by `python run_demo.py` and `python verify_all.py`.
Check them the morning you record; if one has moved, change the script, not the
number.

## Before you hit record

Two windows, both prepared:

- **Browser** — the deployed app, or `streamlit run app.py`. Open every page once
  first so nothing renders cold on camera. Start on the home page, scrolled to top.
- **Terminal** — at the repo root, cleared, ready to run `python run_demo.py`.

**Never call the API live.** Polling takes minutes and will look broken.

Close the sidebar before recording — the in-page nav strip is enough, and a
closed sidebar gives the charts more width.

---

## 0:00 – 0:25 · The number first

**Screen:** home page, top. Scroll immediately to the big red number.

> "One-point-one-eight million people. Seventy-two percent of Phoenix.
>
> Those are the residents who live in a neighbourhood that got hot enough to
> trigger the city's Heat Action Plan — on nights the city's own reading never
> did. So the plan stayed off."

**Pause on the number for a full beat before moving.** This is the 40% of the
score; do not rush past it to get to the architecture.

---

## 0:25 – 0:50 · Why it happens

**Screen:** scroll up to the "What the plan sees / What people live in" panel.

> "A Heat Action Plan is a legal document. Twenty-three actions, named
> departments, numeric thresholds. Open cooling centres at ninety degrees
> overnight.
>
> The whole thing is switched on and off by **one number** — one reading, from
> one weather station at the airport. But heat isn't one number."

---

## 0:50 – 1:15 · The proof, in one chart

**Screen:** the gap chart. Let it fill the frame.

> "Here is that night, neighbourhood by neighbourhood.
>
> The dashed line is the threshold the plan names. The solid line is the single
> citywide reading. **The solid line sits below the dashed one — so the plan
> stayed off.**
>
> And these ten bars are already above it."

**[trace the red bars crossing the dashed line with the cursor]**

> "One number cannot be above and below the same line at once. That is the
> entire failure, in one picture."

---

## 1:15 – 1:40 · Why you can believe it

**Screen:** Methods & evidence page, clause provenance panel with a quote visible.

> "We don't paraphrase the plan. We compile it. Every rule carries the verbatim
> sentence and the page it came from, so any number here walks back to the
> document.
>
> The language model extracts and narrates. It never decides. Every
> fired/not-fired call is a plain numeric comparison in Python."

**Screen:** switch to the terminal. Run `python run_demo.py`.

> "No API key. Runs offline from a committed cache. One command, and you get the
> same number I just showed you."

**Let the output land on screen.** Reproducibility is the 35%.

---

## 1:40 – 2:05 · It is not one clause, and not one city

**Screen:** Heat waves page, the threshold ladder chart.

> "Same week, same measurements, same neighbourhoods — detected against each
> threshold in turn. At ninety degrees this week is ten heat waves covering
> 1.18 million residents. At a hundred and ten, it's zero.
>
> Nothing about the weather changes down that table. Only the number written in
> the plan changes."

**Screen:** switch the city selector to New York.

> "Same pipeline, unchanged, on New York's plan and New York's districts. The
> finding reproduces."

---

## 2:05 – 2:25 · What else the same measurement answers

**Screen:** the siting page tradeoff scatter, then the urban planning dumbbell.
Move quickly — these are breadth, not the argument.

> "The same hyperlocal layer answers two more questions. Where a data centre
> should go — measured free-cooling hours and wet-bulb across thirty US metros,
> where the places evaporative cooling works best are exactly the places that
> can least spare the water.
>
> And how much tree canopy, and where — a measured thermal gap joined to
> published cooling effect sizes, so a recommendation carries a magnitude."

---

## 2:25 – 2:40 · The honest close

**Screen:** back to the home page, the caveat expander open.

> "One caveat we put in the interface, not the footnotes. Our citywide
> comparator is the average across the whole city — a **proxy** for a station
> feed, not a real one. It's a *generous* stand-in: a single real sensor would
> do worse.
>
> So 1.18 million is a **lower bound**."

**End on the number.**

---

## Figures to re-check the morning you record

| Claim | Source |
|---|---|
| 1,184,971 · 72% of Phoenix | `run_demo.py` |
| 10 of 15 urban villages | `run_demo.py` |
| 90 °F → 10 waves / 110 °F → 0 | Heat waves page, threshold ladder |
| New York replication | `data/results/nyc/` |
| 30 metros, wet-bulb measured | `data/results/wetbulb.json` |

## Things not to say

- Do not call the citywide comparator a station feed. It is a proxy, always.
- Do not say the app predicts heat waves. It detects them in measured data;
  there is no forecast horizon in the API beyond about twelve hours.
- Do not claim the national panel is national coverage. It is 30 metros,
  sampled identically — say "panel", not "grid".
- Do not mention the dwell-time figures. They were retracted.
