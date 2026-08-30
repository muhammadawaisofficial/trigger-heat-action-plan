# Submission checklist and deployment

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
| Public repository | done | https://github.com/muhammadawaisofficial/trigger-heat-action-plan |
| Live demo, no key needed | done | https://trigger-heat.streamlit.app/ |
| README against the four criteria | done | `README.md` |
| Headline number reproducible offline in one command | done | `python run_demo.py` |
| Fresh-clone test (clean clone, all keys stripped) | done | `run_demo.py` and `verify_all.py` both exit 0 |
| Retraction stays reproducible | done | `verify_all.py` asserts `sweep_dwell.py` keeps failing |
| Compiler accuracy measured, not asserted | done | `python eval_compiler.py` — F1 0.962 |
| Standalone research report | done | `docs/trigger_divergence_report.md` |
| Action brief with clause/page/owner citations | done | `docs/action_brief.md` |
| Measured API findings | done | `docs/api_findings.md` |
| Baseline labelled a proxy everywhere | done | code, README, report, UI |
| Limitations written honestly | done | README §5, report §5 |
| Video under three minutes | done | https://youtu.be/R3xShqbcUdI |

### Track claim — Track 04, Government & Environment

Assessed in Track 04. Tagged Track 03 (Industrial & Enterprise) and Track 05
(Model Designing) as secondary, because each track's own listed example is
answered by a page of this app from the same measurement — Track 03 names "a
data-center siting screener that flags candidate locations with elevated
ambient heat", and Track 05 names packaging "the algorithms that turn raw
temperature into vulnerability scores". They are tags, not claims. The entry is
assessed on 04 alone.

Track 04's own build examples are *Heat Vulnerability Map, Agricultural Stress
Monitor, Climate Resilience Planner*, and its listed technologies are
*Temperature API, Policy AI, GIS, Open Data*. TRIGGER is a heat vulnerability
map driven by policy AI over GIS and open data, and the track's framing —
"support policymakers and city agencies to act on heat intelligence" — is the
sentence this whole submission answers.

Track 07, Data Analysis & Correlation, was considered and dropped. Its own
example is *Heat Equity Analysis*, which expects demographic and socioeconomic
joins this project does not perform: the population figures here are an areal
interpolation used as a denominator, not an equity analysis. Claiming a track
we half-fit would weaken the one we fit completely.

Track 06, Agentic AI, is not claimed either. This system deliberately has no
agent — the decisions are numeric comparisons, and the language model only
extracts and narrates.

---

## 3. Video

The shot-by-shot script lives in [`VIDEO_SCRIPT.md`](../VIDEO_SCRIPT.md) at the
repo root, with its pauses, delivery notes, and spoken-number table. It runs
2:52 at the pace it specifies, against a three-minute cap.

Two rules from it are worth repeating here, because breaking either one costs
more than a retake. Record with every page already loaded, since the gap chart
takes a moment on a cold render. And say "proxy" every time the citywide
baseline appears: a judge who catches an overclaim discounts everything else.

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
