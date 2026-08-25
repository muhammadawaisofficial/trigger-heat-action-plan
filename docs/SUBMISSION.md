# Submission checklist, deployment, and video script

Everything needed to ship TRIGGER.

## Verified against the live hackathon site, 25 Aug 2026

| | |
|---|---|
| **Submission deadline** | **30 August 2026, 11:59 PM GST (UTC+4)** |
| Build sprint | 18–30 August 2026 |
| Judging | 1–15 September |
| Winners announced | 16 September |
| Prizes | $3,000 / $2,000 / $1,000 — plus internship pathway and partner promotion for 1st |
| Team size | solo or up to 3 |
| Every participant | certificate of completion, partner network access |

**Note on a conflicting source.** Press coverage (Entrepreneur ME) states the
sprint ran 3–17 August with submissions due 17 August. That is a superseded
schedule — the live site shows 18–30 August. Trust the site.

---

## 1. Deploy the live demo (free, ~10 minutes)

The app runs entirely from the committed cache, so **the deployment needs no
secrets of any kind**. That is why it can be hosted free and why a judge can
never hit an authentication wall.

**Pre-flight, already verified:**

| Check | Status |
|---|---|
| Largest tracked file | 10.9 MB — far under GitHub's 100 MB block |
| Repository size | ~61 MB of git history, ~124 MB working tree |
| `.env` tracked? | No. `.gitignore` covers `.env` and `.env.*` |
| API keys anywhere in the tree? | None — grepped for all three before every commit |
| `.python-version` | 3.11 |
| `.streamlit/config.toml` | present, light theme, headless |
| Fresh clone reproduces headline with no key? | Yes — `run_demo.py` and `verify_all.py` both pass |

### Step 1 — create the repository and push

`gh` is not installed on the build machine, so this step needs a human. Either
install it (`winget install GitHub.cli`, then `gh auth login`) or create the repo
in the browser at <https://github.com/new> — public, **no** README, **no**
`.gitignore`, **no** licence, since the repo already has them.

Then, from the repo root:

```bash
git remote add origin https://github.com/<you>/trigger-heat-action-plan.git
git branch -M main
git push -u origin main
```

Confirm before pushing that no key is tracked:

```bash
git ls-files | grep -i "\.env$"     # must return nothing
```

### Step 2 — deploy on Streamlit Community Cloud

This step is browser-OAuth only and cannot be automated.

1. <https://share.streamlit.io> → sign in with GitHub.
2. **New app** → pick the repo, branch `main`, main file `app.py`.
3. Advanced settings → Python 3.11 (also pinned in `.python-version`).
4. **Leave the secrets box empty.** The app needs none.
5. Deploy. First build takes 3–5 minutes while dependencies install.

If the build is slow, the only heavy dependency is `google-genai`, which the app
never imports — it is needed solely to *re*-compile the plan. Commenting it out
of `requirements.txt` for the deployment leaves the app fully working.

### Step 3 — verify the deployment

- The hero number **1,184,971** renders at the top, above the map.
- The silent-zones map shows **10 of 15** villages in alarm red.
- The Sky Harbor marker is present and its tooltip reads.
- The three secondary tabs open, including **What we retracted**.
- Clicking through to the source PDF page works.

## 2. Submission checklist

| Item | Status | Where |
|---|---|---|
| Public repository | ✅ | https://github.com/muhammadawaisofficial/trigger-heat-action-plan |
| Live demo, no key needed | ✅ | https://trigger-heat.streamlit.app/ |
| README against the four criteria | ✅ | `README.md` |
| Headline number reproducible offline in one command | ✅ | `python run_demo.py` |
| Fresh-clone test (clean clone, all keys stripped) | ✅ | `run_demo.py` and `verify_all.py` both exit 0 |
| Retraction stays reproducible | ✅ | `verify_all.py` asserts `sweep_dwell.py` keeps failing |
| Compiler accuracy measured, not asserted | ✅ | `python eval_compiler.py` — F1 0.962 |
| Standalone research report | ✅ | `docs/trigger_divergence_report.md` |
| Action brief with clause/page/owner citations | ✅ | `docs/action_brief.md` |
| Measured API findings | ✅ | `docs/api_findings.md` |
| Baseline labelled a proxy everywhere | ✅ | code, README, report, UI |
| Limitations written honestly | ✅ | README §5, report §5 |
| Video under three minutes | to record | `VIDEO_SCRIPT.md` — rewritten post-retraction |

### Tracks to claim — confirmed, 7 tracks on the live site

**Track 04 — Government & Environment (PRIMARY).** The site's own build examples
for this track are *Heat Vulnerability Map, Agricultural Stress Monitor, Climate
Resilience Planner*, and its listed technologies are *Temperature API, Policy AI,
GIS, Open Data*. TRIGGER is a heat vulnerability map driven by policy AI over GIS
and open data. This is the closest fit of any track to any project we could have
built, and the framing — "support policymakers and city agencies to act on heat
intelligence" — is the sentence our whole submission answers.

**Track 07 — Data Analysis & Correlation (CO-PRIMARY).** Build examples include
*Heat Equity Analysis*. Trigger Divergence is a correlation result between two
sensing regimes over one rule set, with population weighting.

**Track 05 — Model Designing (SUPPORTING).** The clause compiler is an
extraction model with a hand-built golden set and a measured F1 of 0.962.

The site says tracks may be combined, so claim 04 + 07 and mention 05.
**Do not claim Track 06 Agentic AI** — we deliberately do not have an agent, and
it is the most crowded track.

---

## 3. Video script

The shot-by-shot script lives in [`VIDEO_SCRIPT.md`](../VIDEO_SCRIPT.md) at the repo root, timed to 2:30 with the number landing in the first twenty seconds.

### Older 2:50 variant, kept for reference

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
