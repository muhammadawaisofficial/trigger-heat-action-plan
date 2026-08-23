# Submission checklist, deployment, and video script

Everything needed to ship TRIGGER. Deadline **30 August 2026, 11:59 PM GST**.

---

## 1. Deploy the live demo (free, ~10 minutes)

The app runs entirely from the committed cache, so **the deployment needs no
secrets of any kind**. That is the whole reason it can be hosted for free and
why a judge can never hit an authentication wall.

### Push to GitHub

```bash
git remote add origin https://github.com/<you>/trigger-heat-action-plan.git
git branch -M main
git push -u origin main
```

The repository is ~46 MB, well inside GitHub's limits. Confirm before pushing
that `.env` is absent and `.gitignore` covers it:

```bash
git ls-files | grep -i "\.env$"    # must return nothing
```

### Deploy on Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. **New app** → pick the repo, branch `main`, main file `app.py`.
3. Advanced settings → Python 3.11 (also pinned in `.python-version`).
4. **Leave the secrets box empty.** The app needs none.
5. Deploy. First build takes 3–5 minutes while dependencies install.

If the build is slow, the only heavy dependency is `google-genai`, which the app
itself does not import — it is needed solely to *re-*compile the plan. You can
comment it out of `requirements.txt` for the deployment and the app still runs.

### Verify the deployment

- The five headline metrics render at the top.
- Mission 1 shows the 8 August false-calm banner.
- The map draws 15 villages with heavy outlines on silent zones.
- Clicking through to the source PDF page works.

---

## 2. Submission checklist

| Item | Status | Where |
|---|---|---|
| Public repository | push required | GitHub |
| Live demo, no key needed | deploy required | Streamlit Cloud |
| README against the four criteria | ✅ | `README.md` |
| Headline number reproducible offline in one command | ✅ | `python run_analysis.py` |
| Compiler accuracy measured, not asserted | ✅ | `python eval_compiler.py` — F1 0.962 |
| Standalone research report | ✅ | `docs/trigger_divergence_report.md` |
| Action brief with clause/page/owner citations | ✅ | `docs/action_brief.md` |
| Measured API findings | ✅ | `docs/api_findings.md` |
| Baseline labelled a proxy everywhere | ✅ | code, README, report, UI |
| Limitations written honestly | ✅ | README §5, report §5 |
| Video under three minutes | to record | see §3 |

### Tracks to claim

- **04 Government & Environment** (primary) — the user is a city heat officer
  executing a legal instrument.
- **07 Data Analysis & Correlation** (co-primary) — Trigger Divergence is a
  divergence result between two sensing regimes over the same rule set.
- **05 Model Designing** (supporting) — the clause compiler is an extraction
  model with a hand-built golden set and a reported F1.

If the portal's tracks are the four named in press coverage (AI Agents,
Predictive Models, Dashboards, Interactive Maps), map to **Predictive Models**
primary and **Interactive Maps** secondary — the compiler is the model, the app
is the map. Confirm the live track list before submitting.

---

## 3. Video script — 2 min 50 s

Record the app already loaded. **Never call the API live**: polling takes
minutes and will look broken.

### 0:00–0:30 — the number, first

> *"Phoenix has a Heat Response Plan. It's a legal document — 23 actions, named
> departments, numeric temperature thresholds. It is triggered by one
> thermometer at the airport."*
>
> *"On the eighth of August last year, that citywide reading was 89.9 degrees —
> one tenth of a degree below the City's own 90-degree overnight benchmark. So
> nothing fired."*
>
> **[on screen: the false-calm banner]**
>
> *"Ten of Phoenix's fifteen urban villages were above it. One point one eight
> million people — seventy-two percent of the city — live in neighbourhoods that
> met the City's own benchmark on nights the city never called."*

### 0:30–1:10 — the plan is already a program

> *"We didn't hardcode those rules. We compiled them out of the published PDF."*
>
> **[on screen: mission 4, the clause inventory]**
>
> *"Every clause carries a verbatim quote and a page number — and here's the
> part that matters: if that quote isn't found on that page, the clause is
> thrown away automatically. A model that invents a citation produces nothing,
> not a wrong answer."*
>
> *"On the free Gemini tier that scores an F1 of 0.962, with a hundred percent
> quote verification rate."*
>
> *"And compiling the whole document surfaced something we didn't expect.
> Twenty of the twenty-three actions aren't conditioned on heat at all. They run
> on the calendar. Of the two that do respond to temperature, both fire
> citywide."*

### 1:10–2:00 — the measurement

> **[on screen: mission 1 table, then the map]**
>
> *"So we re-ran every clause against FortyGuard's two-metre data — 272,000
> tiles a day across the whole city — once per urban village, and once against
> a citywide average."*
>
> *"Red is where the condition was met. The heavy outlines are silent zones:
> they met it on days the citywide number didn't."*
>
> *"Median lead time, four days. Three of seven days were false calms."*
>
> *"Our comparator is deliberately generous — it's the true city mean, a
> perfect sensor. A real airport station is worse than that. So every number
> here is a lower bound."*

### 2:00–2:35 — validation

> **[on screen: README §4.1 table]**
>
> *"The plan says neighbourhoods differ by ten degrees or more. We measured
> twenty-one degrees overnight."*
>
> *"And the variation is biggest overnight — twenty-one degrees — and smallest
> at the afternoon peak, ten degrees. Peak temperature is the metric heat plans
> usually trigger on. It's the least informative one they could pick."*

### 2:35–2:50 — close

> *"Everything reproduces offline. Clone the repo, no API key, one command."*
>
> **[on screen: `python run_analysis.py` printing the headline]**
>
> *"We're not telling Phoenix its plan is wrong. The plan is good. It's being
> executed with the wrong sensor — and now that gap has a number."*

### Recording notes

- Headline number **in the first thirty seconds** — non-negotiable.
- Say "proxy" every time the baseline appears. An engineer judge who spots an
  overclaim discounts everything else.
- Show the terminal reproducing the number; it is the strongest single shot.
- Rehearse three times, record the fourth.

---

## 4. One-paragraph submission blurb

> Cities enforce heat law with a thermometer at the airport. TRIGGER compiles a
> published Heat Action Plan into executable rules — every clause anchored to a
> verbatim sentence and a page, with citations verified mechanically rather than
> trusted — then re-runs all 23 of Phoenix's actions against FortyGuard's
> 2-metre data across 15 urban villages. The result: 20 of 23 actions aren't
> conditioned on heat at all, and of the ones that are, 1,184,971 people — 72%
> of Phoenix — live in neighbourhoods that met the City's own overnight-heat
> benchmark on nights the citywide reading never fired. Median lead time lost:
> four days. Extraction accuracy is measured (F1 0.962, free tier), the citywide
> baseline is labelled a proxy throughout, and the entire headline reproduces
> offline from a committed cache with no API key.
