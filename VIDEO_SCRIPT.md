# Video script — 2:30

Record with the app **already loaded** and a terminal ready. **Never call the
API live** — polling takes minutes and will look broken.

Two windows to have open before you start:
- Browser: `streamlit run app.py`, Mission 1 selected, day slider on 2025-08-08
- Terminal: sitting at the repo root, ready to run `python run_demo.py`

---

## 0:00 – 0:20 · The number, on the map

**Screen:** the app, Mission 1. The red banner and the map are both visible.

> "Phoenix has a Heat Response Plan. It's a legal document — twenty-three
> actions, named departments, numeric temperature thresholds."
>
> "On the eighth of August last year, the citywide reading was eighty-nine point
> nine degrees. The City's own benchmark is ninety. So nothing fired."
>
> **[point at the map]**
>
> "Ten of Phoenix's fifteen urban villages were above it. **One point one eight
> million people — seventy-two percent of the city.**"

---

## 0:20 – 0:50 · The problem — one station, a whole city

**Screen:** zoom the map so the Sky Harbor plane marker is visible.

> "That single reading comes from one weather station, here, at the airport. One
> number for five hundred square miles."
>
> "And the City knows heat isn't one number. Page four of their own plan says
> neighbourhoods differ by **ten degrees or more**. We measured twenty-one
> degrees overnight."
>
> "Page nine says **sixty-three percent of heat deaths happen on days no warning
> fires.** The plan is good. The sensor is in the wrong place."

---

## 0:50 – 1:30 · Compiling a clause

**Screen:** Mission 4, the clause inventory. Then click into a clause to show
the verbatim quote and page link.

> "We didn't hardcode those rules. We compiled them out of the published PDF."
>
> **[point at a source quote]**
>
> "Every clause carries a word-for-word quote and a page number. And here's the
> part that matters — if that quote isn't found on that page, **the clause is
> thrown away automatically.** A model that invents a citation produces nothing,
> not a wrong answer."
>
> "On the free Gemini tier that scores an F1 of **0.962**, with a hundred percent
> quote verification rate."
>
> "Compiling the whole document also found something we weren't looking for.
> **Twenty of the twenty-three actions aren't conditioned on heat at all** —
> they run on the calendar. Of the two that do respond to temperature, both fire
> citywide."

---

## 1:30 – 2:10 · The divergence, and one named action

**Screen:** Mission 1 table, then Mission 2's firing grid.

> "So we re-ran every clause on FortyGuard's two-metre data — two hundred and
> seventy thousand tiles a day — once per village, and once against a citywide
> average."
>
> **[Mission 2 grid]**
>
> "The bottom row is the citywide number saying no. The rows above it are
> neighbourhoods saying yes. Median lead time: **four days.**"
>
> **[back to Mission 1, point at Maryvale]**
>
> "Concretely: Maryvale, two hundred and twenty-seven thousand residents, met
> the ninety-degree condition on four of seven nights. The citywide trigger
> fired on two. That's a specific gap, on a specific clause, page six, and the
> plan names the Office of Heat Response and Mitigation as responsible."

---

## 2:10 – 2:30 · Limitations, and what it generalises to

**Screen:** switch to the terminal. Run `python run_demo.py` and let it print.

> "Three things we're careful about. Our comparator is the true city mean — a
> **perfect** sensor, better than any real station. So every number here is a
> **lower bound.** Second, FortyGuard's model reads cooler than the airport, so
> clauses keyed to a hundred and ten degrees show nothing, and we report that as
> a null result. Third, our own compiler missed the very clause this headline
> rests on, so the published analysis runs on a hand-checked set — and we say
> so."
>
> **[demo output on screen, replication table visible]**
>
> "And it isn't one lucky week. We re-ran it on live data from last week, a year
> later: same pattern, nine villages, nine hundred and fifty-eight thousand
> people."
>
> "Everything reproduces offline, no API key, one command. The plan is fine.
> It's being executed with the wrong sensor — and now that gap has a number."

---

## Recording notes

- **The number must land inside the first twenty seconds.** Non-negotiable.
- Say **"proxy"** every time the baseline comes up. An engineer judge who spots
  an overclaim discounts everything else you said.
- The strongest single shot is the terminal printing the headline with no key
  set. Hold on it.
- Rehearse three times, record the fourth.
- Under three minutes. If you're over, cut from 0:50–1:30, not from the number.

## Numbers to get right

| | |
|---|---|
| People in silent zones | 1,184,971 (72% of Phoenix) |
| Silent zones | 10 of 15 urban villages |
| Worst day | 8 Aug 2025 — proxy 89.9 °F vs 90 °F threshold |
| Villages above it that day | 10, hottest 93.9 °F |
| Median lead time | 4 days |
| False-calm days | 3 of 7 |
| Calendar-activated actions | 20 of 23 |
| Compiler F1 | 0.962, free Gemini tier, 100% quote verification |
| Plan's own claim vs measured | 10 °F stated, 21.2 °F measured overnight |
| Replication (live 2026) | 9 villages, 958,205 people, same 3 of 7 |
