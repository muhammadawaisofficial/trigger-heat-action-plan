# TRIGGER — the Heat Action Plan Compiler

**Submission summary · FortyGuard Hackathon '26 · Track 4, Government & Environment**

Live demo: https://trigger-heat.streamlit.app/ · Repository: https://github.com/muhammadawaisofficial/trigger-heat-action-plan

---

## The problem

Cities govern extreme heat through Heat Action Plans: legal documents with numeric temperature thresholds and named departments obliged to act when those thresholds are crossed. Phoenix's 2026 Heat Response Plan is one of the best in the United States.

Every conditional clause in it is switched on and off by **one reading, from one weather station at the airport**. The plan itself states, on page 4, that neighbourhood temperatures across Phoenix differ by "10°F or more." The city knows heat is not a citywide quantity. Its trigger cannot act on that knowledge, because a single number has no spatial resolution to give.

## Who it is for

**City heat officers and emergency managers** — the people who decide, on a given afternoon, where to open cooling centres and where to send welfare checks with a finite number of crews. They already have the legal authority and the budget. What they lack is evidence about which neighbourhoods their own trigger is missing, and a defensible order in which to deploy.

Secondary users: **data-centre siting teams** choosing between US metros on cooling cost, and **urban-planning departments** allocating tree-canopy budgets between neighbourhoods.

## FortyGuard usage

The Temperature API is the instrument the entire measurement is made with. **125 calls, 11,189,301 tiles, 527,500 credits, across 58 distinct days.** No other weather, temperature, or climate source is used anywhere in the pipeline.

- **`POST /v1/heatmap` · `tcm`** (23 calls) — per-tile min, mean, max temperature. Produces the overnight-low benchmark carrying the headline, and the severity axis every clause is scored on.
- **`POST /v1/heatmap` · `exceedance`** (84 calls) — hours above a threshold per tile. Drives duration clauses, the 46-day event-selection scan, and free-cooling hours via `direction="below"`.
- **`POST /v1/heatmap` · `persistence`** (18 calls) — longest unbroken run, probed across three consecutive Julys at each `filter_type`.
- **`POST /v1/env_params`** — wet-bulb temperature at 30 US metro centroids, the variable the evaporative-versus-mechanical cooling decision turns on.

Because credits are flat per call regardless of area, the whole 1,053 mi² city is **one request per day at 100 m granularity — 272,917 tiles** — rather than one per neighbourhood.

## The measured result

**1,184,971 people — 72% of Phoenix — live in a neighbourhood that met the city's own overnight-heat benchmark on nights the citywide reading never fired.** Ten of fifteen urban villages, 20 silent zone-days, a median of 4 days' lost warning.

The same trigger also over-fires: on 27 of 35 clause-days it fired either almost everywhere or almost nowhere, giving no basis for choosing where to send anyone.

Re-run unchanged on **New York City**: 2,453,713 people, same failure, opposite metric. Re-run on **August 2026, fetched live**, on data the pipeline had never seen: the finding reproduced.

Every figure is re-derivable offline in one command: `python verify_all.py`.
