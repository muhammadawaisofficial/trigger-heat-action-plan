"""Methods and evidence: the full technical record behind the headline number.

The home page answers "what did you find". This page answers "how, exactly, and
what would falsify it" -- the clause-by-clause explorer, the provenance of every
extracted rule, the map at clause resolution, the New York replication, the
over-trigger analysis, what we measured about the API, and the claims we
retracted. It is deliberately dense; the home page is deliberately not.
"""


from __future__ import annotations

import json
import sys
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import datetime as _dt  # noqa: E402

import cache as fg_cache  # noqa: E402
import customwindow  # noqa: E402
import liveprobe  # noqa: E402
import study  # noqa: E402
import ui  # noqa: E402
from alerts import detect, summarise  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
RESULTS = REPO / "data" / "results" / "divergence.json"
ZONES = REPO / "data" / "zones" / "phoenix_villages_raw.geojson"
POP = REPO / "data" / "zones" / "phoenix_villages_population.json"

PROXY_LABEL = ("Citywide proxy — the area-weighted mean over the whole city AOI, "
               "used as a stand-in for station-based sensing. **It is not a real "
               "station feed.** A real single station is less representative than "
               "this, so every divergence figure here is a lower bound.")

st.set_page_config(page_title="TRIGGER — Methods & Evidence",
                   page_icon="🌡", layout="wide",
                   initial_sidebar_state="expanded")

# --------------------------------------------------------------------- styling
# One stylesheet for the WHOLE app, defined in src/ui.py and applied here and
# on every page. Defining it per page is how two pages drift into looking like
# two products.
ui.style()
ui.theme("methods")


# ------------------------------------------------------------------- cities
# The pipeline is city-agnostic, so the interface is too. Switching cities here
# re-renders every number on the page from that city's own committed results --
# which is the portability claim demonstrated rather than asserted.

CITIES = ui.CITIES


@st.cache_data
def load_json(path_str: str) -> dict:
    f = Path(path_str)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


@st.cache_data
def load_api_usage() -> dict:
    return load_json(str(REPO / "data" / "results" / "api_usage.json"))


AVAILABLE = {k: v for k, v in CITIES.items() if v["results"].exists()}
if not AVAILABLE:
    st.error("No results found. Run `python run_analysis.py` first.")
    st.stop()

with st.sidebar:
    st.markdown("### City")
    city_name = st.radio(
        "City", list(AVAILABLE.keys()), label_visibility="collapsed",
        key="me_city",
        captions=[AVAILABLE[c]["trigger"] for c in AVAILABLE])
    CITY = AVAILABLE[city_name]
    st.caption(CITY["note"])
    if len(AVAILABLE) > 1:
        st.success("Switch cities to re-run every figure on this page. Same "
                   "pipeline, no code changes — one profile file per city.",
                   icon="🔀")
    st.divider()

res = load_json(str(CITY["results"]))
geo = load_json(str(CITY["zones"]))
pop = (load_json(str(CITY["pop"])) or {}).get("villages", {})
api = load_api_usage()
nyc = load_json(str(CITIES["New York City"]["results"]))
clauses = {c["clause_id"]: c for c in res["clauses"]}
summary = res["summary"]



def zone_id_of(feature: dict) -> str:
    return str(feature["properties"].get("NAME", "")).lower().replace(" ", "_")


#: Union of silent zones across every evaluated clause -- the same set that
#: produces the published population figure. Not a new computation.
SILENT: set[str] = set()
for _c in res["clauses"]:
    SILENT |= set(_c.get("silent_zones") or [])

#: Map bounds, derived from the zones themselves. A fixed zoom_start shows half
#: of Arizona on a wide screen; fitting to the geometry keeps the map useful at
#: any window size.
_lats: list[float] = []
_lons: list[float] = []
_ids = {z["zone_id"] for z in res["zones"]}
for _ft in geo.get("features", []):
    if zone_id_of(_ft) not in _ids:
        continue
    def _walk(c):
        if isinstance(c, (int, float)):
            return
        if len(c) == 2 and isinstance(c[0], (int, float)):
            _lons.append(c[0]); _lats.append(c[1]); return
        for _x in c:
            _walk(_x)
    _walk(_ft["geometry"]["coordinates"])

ui.masthead("Methods & evidence",
            pills=[CITY["short"], "clause-level detail", "replication · retractions"])
ui.topnav()

st.title("How the number was computed, and what would falsify it")

st.info(
    "**What this page is for.** Everything needed to check the headline rather "
    "than trust it: every compiled rule beside the verbatim sentence and page "
    "it came from, the map at clause resolution, the machine-readable alert "
    "payload, the New York replication, what we measured about the FortyGuard "
    "API, and a date picker that runs the full analysis on **any window you "
    "choose**, from 2021 to yesterday.",
    icon="🔬")
st.markdown(
    "The landing page answers *what did you find*. This page answers **how, "
    "exactly** — every rule with the page and sentence it came from, the map at "
    "clause resolution, the New York replication, what we measured about the "
    "API, and the claims we withdrew. It is deliberately dense.")




ui.api_strip(
    [("POST /v1/heatmap · tcm · exceedance · persistence",
      "125 calls, 11,189,301 tiles, 58 distinct days"),
     ("GET /v1/status/{activity_id}", "submit-then-poll, handled by the "
                                      "cached client"),
     ("POST /v1/system/fetch-api-key-usage",
      "the credit figures reported on this page")],
    note="This page exists to let a reader check those calls rather than "
         "trust them. Every response is committed to the repository.")

# Every other heat product alerts on temperature. "It is 108 degrees in your
# neighbourhood" is true, and an emergency manager already knows it. These
# alerts fire on an UNEXECUTED LEGAL OBLIGATION instead: a clause of the city's
# own plan was met locally while the instrument that triggers it stayed quiet.
# That is why each one can name a department, a page and a verbatim sentence,
# which no temperature alert can do.
#
# Severity tiers follow the alerting literature: red alerts are read as credible
# and drive behaviour while yellow draws the weakest response, so a red tier is
# earned by measured exposure and kept rare enough to stay credible.

_alerts = detect(res, pop, city=city_name, plan_title=CITY["plan"],
                 plan_url=CITY["plan_url"])
_asum = summarise(_alerts)

st.markdown("### Divergence alerts")
st.caption(
    "Fired when a clause was met in an area while the citywide reading stayed "
    "below its threshold: an obligation incurred locally that the city's own "
    "trigger never registered. Detection is a deterministic comparison. No "
    "language model decides whether to alert, at what severity, or about whom.")

if not _alerts:
    st.success(f"No divergence alerts for {CITY['short']} in this window.",
               icon="✅")
else:
    _k1, _k2, _k3, _k4 = st.columns(4)
    _k1.metric("Alerts", _asum["alerts"])
    _k2.metric("Red", _asum["red"], "100k+ residents", delta_color="off")
    _k3.metric("Amber", _asum["amber"], "25k+ residents", delta_color="off")
    _k4.metric("People covered", f"{_asum['population_exposed']:,}")

    _pick = st.selectbox("Filter by night", ["All nights"] + _asum["days"],
                         key="alert_day")
    _shown = [a for a in _alerts if _pick == "All nights" or a.day == _pick]

    for _a in _shown[:6]:
        _colour = {"RED": "#b2182b", "AMBER": "#c2711c",
                   "YELLOW": "#8a8a2f"}[_a.severity]
        _who = f" · {_a.population:,} residents" if _a.population else ""
        with st.container(border=True):
            st.markdown(
                f"<span style='background:{_colour};color:#fff;font-weight:800;"
                f"font-size:0.72rem;letter-spacing:0.08em;padding:0.2rem 0.55rem;"
                f"border-radius:5px'>{_a.severity}</span> &nbsp;"
                f"<b style='font-size:1.08rem'>{_a.zone_name}</b>"
                f"<span style='color:#71717a'> · {_a.day}{_who}</span>",
                unsafe_allow_html=True)

            _x, _y = st.columns([3, 2])
            _x.markdown(
                f"Reached **{_a.measured_f:.1f} °F** against the "
                f"**{_a.threshold_f:g} °F** threshold "
                f"(**{_a.margin_f:+.1f} °F** over). The citywide reading was "
                f"**{_a.proxy_f:.1f} °F**, "
                f"{_a.proxy_shortfall_f:.1f} °F *below* the line, so "
                f"**nothing fired**.")
            _y.markdown(
                "**Responsible**  \n"
                + (", ".join(_a.actor) or "—")
                + "  \n\n**Authority**  \n"
                + f"`{_a.clause_id}` · "
                + f"[page {_a.source_page}]({_a.plan_url}#page={_a.source_page})")
            with st.expander("Machine-readable payload"):
                st.json(_a.to_dict())

    if len(_shown) > 6:
        st.caption(f"Showing 6 of {len(_shown)} for this filter.")

    st.download_button(
        "Download every alert as JSON",
        json.dumps([a.to_dict() for a in _alerts], indent=2),
        file_name=f"trigger_alerts_{CITY['short'].lower().replace(' ', '_')}.json",
        mime="application/json")



# ------------------------------------------------------------------- missions

st.subheader("Explore the result")
st.caption("Pick a mission and a clause in the sidebar. The map below is "
           "per-clause and per-day; the hero map above is the whole window.")

MISSIONS = {
    "1. Who did the plan miss last night?":
        "Show the clause with the largest silent-zone population, on its worst day.",
    "2. Which clauses never fire where I live?":
        "Per-village firing record for every evaluable clause.",
    "3. How much warning was lost?":
        "Lead time between each village meeting a condition and the citywide number doing so.",
    "4. What does the plan actually condition on?":
        "The full compiled clause inventory with provenance.",
}

# These controls change only what THIS section shows, so they live next to it.
# In the sidebar they read as global settings and leave the reader unsure which
# part of the page a given knob affects.
_m1, _m2, _m3 = st.columns([2, 2, 3])
with _m1:
    mission = st.radio("Question to ask", list(MISSIONS.keys()))
with _m2:
    ids = list(clauses.keys())
    # Default to the clause carrying the headline.
    default = next((i for i, k in enumerate(ids) if clauses[k]["silent_zone_days"]), 0)
    clause_id = st.selectbox("Rule to test", ids, index=default,
                             format_func=lambda k: f"{k} ({clauses[k]['threshold_f']:g}°F)")
    cl = clauses[clause_id]
    days = [d["day"] for d in cl["determinations"]]
    worst = cl.get("worst_false_calm")
    day_default = days.index(worst[0]) if worst and worst[0] in days else len(days) - 1
with _m3:
    day = st.select_slider("Day", options=days, value=days[day_default])
    st.caption(MISSIONS[mission])

st.info(PROXY_LABEL)

cl = clauses[clause_id]
det = next(d for d in cl["determinations"] if d["day"] == day)
threshold_f = cl["threshold_f"]
is_hours = det["zones"][0]["units"] == "hours"


def to_display(v: float) -> float:
    return v if is_hours else v * 9 / 5 + 32


unit = "h" if is_hours else "°F"


# ------------------------------------------------------------------ provenance

st.subheader(f"{clause_id} — {cl['action']}")
pc1, pc2 = st.columns([3, 2])
with pc1:
    st.markdown(f'<div class="tg-quote">&ldquo;{cl["source_text"]}&rdquo;</div>',
                unsafe_allow_html=True)
    st.caption(f"**{CITY['plan']}, page {cl['source_page']}** — verbatim, "
               f"verified against that page. "
               f"[Open the source PDF]({CITY['plan_url']}#page={cl['source_page']})")
with pc2:
    st.markdown(
        f"**Threshold** {threshold_f:g} °F ({cl['threshold_c']:.2f} °C)  \n"
        f"**Responsible** {', '.join(cl['actor']) or '—'}  \n"
        f"**Citywide proxy fired** {len(cl['proxy_fired_days'])} of "
        f"{summary['days']} days  \n"
        f"**Zone-days met** {cl['zone_fired_day_count']}"
    )

st.divider()


# ------------------------------------------------------------------- mission 1

if mission.startswith("1"):
    if not cl["silent_zone_days"]:
        st.success(f"{clause_id} shows no silent zones in this window — the "
                   f"citywide proxy and the villages agree.")
    else:
        w = cl["worst_false_calm"]
        if w:
            wday, pval, nz, mx = w
            exposed = sum(pop[z]["population"] for z in cl["silent_zones"] if z in pop)
            st.error(
                f"**On {wday} the citywide proxy read "
                f"{to_display(pval):.1f} {unit} — below the {threshold_f:g} °F "
                f"threshold, so nothing fired.** "
                f"{nz} villages met it, the highest at {to_display(mx):.1f} {unit}."
            )
            if exposed:
                st.markdown(
                    f"Across the window, **{exposed:,} people** "
                    f"({exposed/summary['population_total']:.0%} of Phoenix) live in the "
                    f"**{len(cl['silent_zones'])} villages** that met this condition on "
                    f"days the citywide number never did."
                )

    rows = []
    for z in det["zones"]:
        rows.append({
            "Village": z["name"],
            f"Value ({unit})": round(to_display(z["value"]), 2),
            "Met?": "YES" if z["fired"] else "no",
            "Margin": round(z["margin"] * (1 if is_hours else 9 / 5), 2),
            "Population": pop.get(z["zone_id"], {}).get("population"),
            "Silent zone": "yes" if z["zone_id"] in cl["silent_zones"] else "",
        })
    df = pd.DataFrame(rows).sort_values(f"Value ({unit})", ascending=False)
    st.dataframe(df, width='stretch', hide_index=True)


# ------------------------------------------------------------------- mission 2

elif mission.startswith("2"):
    st.markdown("**Firing record per village.** `Y` = condition met that day.")
    grid = {}
    for d in cl["determinations"]:
        for z in d["zones"]:
            grid.setdefault(z["name"], {})[d["day"][5:]] = "Y" if z["fired"] else "·"
    prox = {d["day"][5:]: ("Y" if d["proxy"]["fired"] else "·")
            for d in cl["determinations"]}
    df = pd.DataFrame(grid).T
    df["days met"] = (df == "Y").sum(axis=1)
    df = df.sort_values("days met", ascending=False)
    pr = pd.DataFrame({**prox, "days met": sum(1 for v in prox.values() if v == "Y")},
                      index=["CITYWIDE PROXY"])
    st.dataframe(pd.concat([df, pr]), width='stretch')
    st.caption("The proxy row is the comparator. Villages above it with more "
               "`Y` marks are the ones the single reading misses.")


# ------------------------------------------------------------------- mission 3

elif mission.startswith("3"):
    leads = [z for z in cl["zone_leads"] if z["days_met"]]
    if not leads:
        st.info("No village met this condition in the window.")
    else:
        rows = [{
            "Village": z["zone_name"],
            "First met": z["first_met_day"] or "—",
            "Citywide first met": z["proxy_first_day"] or "never",
            "Lead (days)": z["lead_days"] if z["lead_days"] is not None else "—",
            "Days met": z["days_met"],
            "Population": pop.get(z["zone_id"], {}).get("population"),
        } for z in sorted(leads, key=lambda z: (z["first_met_day"] or "9"))]
        st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)
        if cl.get("median_lead_days") is not None:
            st.markdown(f"**Median lead: {cl['median_lead_days']:.0f} day(s)** "
                        f"ahead of the citywide number.")


# ------------------------------------------------------------------- mission 4

else:
    inv = res["inventory"]
    st.markdown(
        f"The compiler read **{inv['total']} clauses** out of the published plan. "
        f"Only **{inv['conditional']}** are conditioned on temperature at all; "
        f"**{inv['scheduled']}** activate on the calendar."
    )
    k1, k2, k3 = st.columns(3)
    k1.metric("Calendar-activated", inv["scheduled"])
    k2.metric("Conditional on heat", inv["conditional"])
    k3.metric("Of those, citywide-scoped", inv["citywide_scope"])
    st.dataframe(pd.DataFrame([{
        "Clause": c["clause_id"],
        "Action": c["action"],
        "Page": c["source_page"],
        "Threshold °F": c["threshold_f"],
        "Responsible": ", ".join(c["actor"]),
        "Proxy fired (days)": len(c["proxy_fired_days"]),
        "Zone-days met": c["zone_fired_day_count"],
        "Silent zones": len(c["silent_zones"]),
    } for c in res["clauses"]]), width='stretch', hide_index=True)
    st.caption("Only clauses evaluable against 2 m data appear here. The full "
               "27-clause inventory, including the 20 calendar-activated "
               "actions, is in data/golden/phoenix_2026_clauses.json.")


# ----------------------------------------------------------------------- map

st.divider()
st.subheader(f"{day} — {'hours above' if is_hours else 'temperature vs'} "
             f"{threshold_f:g} °F")

vals = {z["zone_id"]: z["value"] for z in det["zones"]}
fired = {z["zone_id"]: z["fired"] for z in det["zones"]}
names = {z["zone_id"]: z["name"] for z in det["zones"]}


m = folium.Map(tiles="cartodbpositron", zoom_control=True)
if _lats:
    m.fit_bounds([[min(_lats), min(_lons)], [max(_lats), max(_lons)]],
                 padding=(18, 18))

for ft in geo["features"]:
    zid = zone_id_of(ft)
    if zid not in vals:
        continue
    met = fired[zid]
    v = to_display(vals[zid])
    is_silent = zid in cl["silent_zones"]
    p = pop.get(zid, {}).get("population")

    tip = (f"<b>{names[zid]}</b><br>"
           f"{v:.1f} {unit} vs {threshold_f:g} °F<br>"
           f"<b>{'CONDITION MET' if met else 'not met'}</b>"
           f"{'<br><i>silent zone</i>' if is_silent else ''}"
           + (f"<br>{p:,} people" if p else ""))

    folium.GeoJson(
        ft,
        style_function=lambda _f, met=met, silent=is_silent: {
            # Red where the condition was met, and outlined where the citywide
            # number stayed quiet anyway.
            "fillColor": "#b2182b" if met else "#c6dbef",
            "color": "#000000" if silent else "#666666",
            "weight": 3 if silent else 1,
            "fillOpacity": 0.72 if met else 0.35,
        },
        tooltip=folium.Tooltip(tip),
    ).add_to(m)

pv = to_display(det["proxy"]["value"])
folium.Marker(
    [33.4342, -112.0116],  # Phoenix Sky Harbor, the station the plan reads
    tooltip=(f"<b>Sky Harbor</b><br>The station the plan is triggered from.<br>"
             f"Citywide proxy this day: {pv:.1f} {unit} "
             f"({'fired' if det['proxy']['fired'] else 'did NOT fire'})"),
    icon=folium.Icon(color="green" if det["proxy"]["fired"] else "gray",
                     icon="plane", prefix="fa"),
).add_to(m)

mc1, mc2 = st.columns([3, 1])
with mc1:
    st_folium(m, height=520, use_container_width=True, returned_objects=[],
              key="explorer_map")
with mc2:
    st.markdown(
        f"**Citywide proxy**  \n### {pv:.1f} {unit}  \n"
        f"{'**FIRED**' if det['proxy']['fired'] else '**DID NOT FIRE**'}  \n"
        f"threshold {threshold_f:g} °F"
    )
    n_met = sum(1 for z in det["zones"] if z["fired"])
    st.markdown(f"**Villages meeting it**  \n### {n_met} of {len(det['zones'])}")
    if pop:
        exp = sum(pop[z["zone_id"]]["population"] for z in det["zones"]
                  if z["fired"] and z["zone_id"] in pop)
        st.markdown(f"**People in them**  \n### {exp:,}")
    st.caption("Red = condition met. Heavy black outline = silent zone: met the "
               "condition on a day the citywide number did not.")


# ======================================================= SECONDARY RESULTS
# Below the fold on purpose. The headline is the coverage failure above.

st.divider()
st.subheader("Secondary results")

tab_nyc, tab_over, tab_rec, tab_api, tab_retract = st.tabs(
    ["Does it generalise? New York City",
     "Over-trigger: the targeting failure",
     "Recovery: a different rule",
     "How we used the FortyGuard API",
     "What we retracted"])

with tab_nyc:
    if not nyc:
        st.info("The New York run is not present in this checkout.")
    else:
        ns = nyc["summary"]
        st.markdown(
            "One city is a case study. We ran the **same pipeline, unchanged**, "
            "on **New York City** — a city that disagrees with Phoenix about "
            "what to measure and is right to.")
        st.markdown(
            "Phoenix is arid, so heat index sits **below** air temperature "
            "there and its plan triggers on **dry-bulb**. New York is humid, so "
            "heat index sits **above** air temperature and its plan triggers on "
            "**heat index**. Opposite choices, both defensible. The question is "
            "whether the failure follows the metric or the *architecture*.")
        _p = summary
        st.dataframe(pd.DataFrame([
            {"": "Trigger", "Phoenix": "90 °F overnight low",
             "New York City": "100 °F heat index"},
            {"": "Zones", "Phoenix": f"{len(res['zones'])} urban villages",
             "New York City": f"{len(nyc['zones'])} community districts"},
            {"": "Citywide proxy, worst day", "Phoenix": "89.9 °F", "New York City": "99.0 °F"},
            {"": "Missed the threshold by", "Phoenix": "0.1 °F", "New York City": "1.0 °F"},
            {"": "Silent zones",
             "Phoenix": f"{_p['silent_zones']} of {len(res['zones'])}",
             "New York City": f"{ns['silent_zones']} of {len(nyc['zones'])}"},
            {"": "People exposed",
             "Phoenix": f"{_p['population_exposed']:,}",
             "New York City": f"{ns.get('population_exposed', 0):,}"},
            {"": "False-calm days",
             "Phoenix": f"{len(_p.get('false_calm_days', []))} of {_p['days']}",
             "New York City": f"{len(ns.get('false_calm_days', []))} of {ns['days']}"},
            {"": "Actionable clause-days",
             "Phoenix": f"{_p['actionable_clause_days']} of {_p['clause_days']}"
                        f" ({_p['actionable_share']:.0%})",
             "New York City": f"{ns['actionable_clause_days']} of {ns['clause_days']}"
                              f" ({ns['actionable_share']:.0%})"},
        ]), hide_index=True, use_container_width=True)
        st.markdown("#### And New York already fixed a version of this")
        st.markdown(
            "From 2001 to 2007 New York activated its heat plan on **national** "
            "criteria: a heat index of **40.6 °C — 105 °F — for one day**. An "
            "evaluation found the system *was not preventing heat-related "
            "mortality*. The City replaced it with locally-derived thresholds, "
            "and the change had a measured health outcome.")
        st.markdown(
            "> *“The 40.6 °C threshold for one day was changed to a forecast "
            "maximum heat index of 37.8 °C for one day or more, or 35 °C for at "
            "least two consecutive days … The lower threshold reduced "
            "heat-related hospitalizations among older adults.”*\n\n"
            "> — Kotharkar & Ghosh, *Effective heat action plans*, "
            "[Environmental Research Letters]"
            "(https://iopscience.iop.org/article/10.1088/1748-9326/ab5ab0)")
        st.warning(
            "**The clauses evaluated above are New York's post-change, "
            "epidemiologically-derived thresholds** — the improved rule, already "
            "validated against hospitalisation data. They still leave "
            f"**{ns['silent_zones']} districts and "
            f"{ns.get('population_exposed', 0):,} people** meeting the condition "
            "on days the citywide reading never fired.\n\n"
            "New York fixed the *between-city* problem: a national threshold did "
            "not describe New York. **Nobody has fixed the *within-city* one, and "
            "it survives the fix.** A better single number is still a single "
            "number.", icon="⚠️")
        st.caption(
            "What we do NOT claim: New York's evidence is that 105 °F was too "
            "high *for New York's climate*. It does not follow that Phoenix's "
            "105 °F trigger is wrong for Phoenix, which is a far hotter city, "
            "and we make no such claim. This finding is about spatial "
            "resolution, not about any particular number.")

        _tot = _p["population_exposed"] + ns.get("population_exposed", 0)
        st.success(
            f"**Same near-miss signature. Near-identical actionable share — "
            f"{_p['actionable_share']:.0%} against {ns['actionable_share']:.0%}.** "
            f"Two cities, opposite climates, opposite trigger metrics, the same "
            f"structural failure. **{_tot:,} people** across both.", icon="🎯")
        st.caption(
            "New York was added with **zero code changes** — one profile JSON, "
            "one boundaries file, one clause file. Its AOI is the 346 mi² box "
            "the API accepts: a full five-borough box spans open ocean and is "
            "rejected outright, so 51 of 59 community districts are covered and "
            "Staten Island plus five coastal districts are excluded and "
            "reported as excluded. NYC triggers on heat index while FortyGuard "
            "returns dry-bulb, which UNDER-counts its firings — so these NYC "
            "figures are a lower bound twice over.")

with tab_over:
    st.markdown(
        f"The same rules, measured on **all 272,917 tiles before any "
        f"aggregation** — fifteen zone averages say nothing about whether the "
        f"underlying field had structure. A clause is **actionable** only if it "
        f"fires on between 5% and 95% of tiles: an emergency manager can send "
        f"crews neither to the whole city nor to nowhere.")
    n = summary.get("clause_days")
    act = summary.get("actionable_clause_days")
    if n:
        o1, o2, o3 = st.columns(3)
        o1.metric("Actionable", f"{act} of {n}", f"{act/n:.0%}",
                  delta_color="off")
        o2.metric("Over-triggered", summary.get("over_triggered_clause_days"),
                  "fired on >95% of tiles", delta_color="off")
        o3.metric("Under-triggered", summary.get("under_triggered_clause_days"),
                  "fired on <5% of tiles", delta_color="off")
        st.info(f"On **{n - act} of {n} clause-days ({(n-act)/n:.0%})** the plan "
                f"gave no basis for choosing where to send anyone.")

    sat = res.get("saturation") or []
    if sat:
        rows = []
        for scl in sat:
            for d in scl.get("per_day", []):
                rows.append({
                    "clause": scl["clause_id"],
                    "day": d["day"],
                    "severity °F": (round(d["severity_c"] * 9 / 5 + 32, 1)
                                    if d.get("severity_c") is not None else None),
                    "saturation": round(d["saturation_index"], 3),
                    "verdict": d["failure_mode"],
                })
        st.dataframe(pd.DataFrame(rows), hide_index=True, height=300)
        st.caption(
            "Saturation is the share of tiles where the clause fires. For the "
            "two clauses measured through `exceedance` it is approximate to "
            "about a percentage point, because that field is smoothed rather "
            "than counted. The verdicts are unaffected — they sit far from the "
            "5% and 95% boundaries.")

with tab_rec:
    st.markdown(
        "Replacing a fixed threshold with the **90th percentile of that day's "
        "own distribution** restores a rankable ordering in both failure "
        "directions — the benchmarks that over-fire and the one that never "
        "fires alike.")
    recs = [r for r in (res.get("recovery") or []) if r.get("percentile")]
    if recs:
        st.dataframe(pd.DataFrame([{
            "clause": r["fixed"]["clause_id"],
            "day": r["fixed"]["day"],
            "as written °F": r["fixed"]["threshold_f"],
            "saturation": round(r["fixed"]["saturation_index"], 3),
            "p90 °F": r["percentile"]["threshold_f"],
            "saturation (p90)": round(r["percentile"]["saturation_index"], 3),
            "villages recovered": r["zones_recovered"],
        } for r in recs]), hide_index=True)
    st.warning(
        "**A same-day percentile is post hoc.** Today's 90th percentile is not "
        "knowable before today ends, so this demonstrates that the signal "
        "survives in the data — not that a city could adopt this rule as "
        "written. A deployable version would fit the percentile on historical "
        "climatology, which this project has not done.")

with tab_api:
    st.markdown(
        "Every temperature on this page comes from the **FortyGuard Temperature "
        "API**. No external weather source is used anywhere in the pipeline — "
        "not NOAA, not Open-Meteo, nothing. That constraint is deliberate: it "
        "makes the comparison between the two sensing regimes internally "
        "consistent, so a systematic model offset cancels instead of "
        "contaminating the result.")
    if api:
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("API calls", f"{api['calls']:,}")
        a2.metric("Tiles retrieved", f"{api['tiles']/1e6:.1f} M")
        a3.metric("Days analysed", api["distinct_days"])
        a4.metric("Credits spent", f"{api['credits']:,}")
        st.markdown("**Which analytics, and what each one was for**")
        st.dataframe(pd.DataFrame([
            {"analytic": "tcm", "calls": api["by_analytic"].get("tcm", 0),
             "what it gave us": "per-tile min / mean / max temperature — the "
             "overnight-low benchmark and the severity axis"},
            {"analytic": "exceedance", "calls": api["by_analytic"].get("exceedance", 0),
             "what it gave us": "hours above a threshold per tile — every "
             "duration-style clause and the event-selection scan"},
            {"analytic": "persistence", "calls": api["by_analytic"].get("persistence", 0),
             "what it gave us": "longest unbroken run — probed thoroughly, then "
             "REJECTED as untrustworthy at city scale (see the retraction tab)"},
            {"analytic": "time_of_measure", "calls": api["by_analytic"].get("time_of_measure", 0),
             "what it gave us": "hour of peak per tile, UTC → Phoenix local — "
             "whether silent zones peak later than the rest of the city"},
            {"analytic": "env_params", "calls": api["by_analytic"].get("env_params", 0),
             "what it gave us": "heat index and humidity at village centroids — "
             "whether dry-bulb is the right thing to trigger on at all"},
        ]), hide_index=True, use_container_width=True)
        st.caption(
            f"Responses are cached to disk and committed to the repository "
            f"({api['cache_mb']} MB, {api['responses']} responses over "
            f"{api['grids']} shared tile grids), which is why this page needs no "
            f"API key and why the entire analysis reproduces offline. The tile "
            f"grid is byte-identical across calls on the same AOI, so it is "
            f"stored once rather than {api['responses']} times.")
        st.info("We also measured the API itself and documented three behaviours "
                "that contradict its docs — `tcm` returns °C not °F, "
                "`persistence` clamps to ~8 h at `filter_type=4`, and the real "
                "area limit is ~1,053 mi² rather than the documented 50. "
                "See `docs/api_findings.md`.", icon="🔬")

    st.markdown("---")
    st.markdown("#### Prove it: fetch one real reading right now")
    st.caption(
        "Everything above runs from the committed cache — that is a "
        "reproducibility choice, not a way of avoiding the API (see why, "
        "below). This button is separate from all of it: a real, on-demand "
        "call to FortyGuard for a 2 km box over downtown Phoenix, one "
        "analytic, one day. It never feeds the headline number.")

    pc1, pc2 = st.columns([1, 2])
    with pc1:
        go = st.button("Fetch a live reading", type="primary",
                       use_container_width=True)
    with pc2:
        st.caption(
            f"First press of the day is a genuine network round trip "
            f"(typically 5–15 s for this size). Credits are a flat 4,220 per "
            f"call regardless of area, so later presses today reuse that same "
            f"real response rather than paying again — the label below states "
            f"which happened.")

    if go:
        if not fg_cache.has_key():
            st.warning(
                "No `FORTYGUARD_API_KEY` is configured on this deployment, so "
                "there is nothing to fetch live here. This does not affect "
                "anything else on the site — every other number reproduces "
                "from the **125 real calls already committed** to the repo "
                "(see the metrics above). Run this locally with a key to see "
                "it fetch live.", icon="🔑")
        else:
            try:
                with st.spinner("Calling FortyGuard — polling until the task "
                                "completes…"):
                    p = liveprobe.run()
                if p.was_already_cached:
                    st.success(
                        f"**Replayed today's real fetch** for {p.day} rather "
                        f"than paying again — this exact request already ran "
                        f"live once today.", icon="♻️")
                else:
                    st.success(
                        f"**Fetched live just now** from FortyGuard, for "
                        f"{p.day} — a genuine network round trip that just "
                        f"completed.", icon="📡")
                m1, m2, m3 = st.columns(3)
                m1.metric("Mean temperature", f"{p.mean_c:.1f} °C")
                m2.metric("Range", f"{p.min_c:.1f} – {p.max_c:.1f} °C")
                m3.metric("Tiles in this box", f"{p.n_tiles:,}")
            except Exception as exc:  # noqa: BLE001 — a demo must never crash
                st.error(
                    f"The live call did not complete: {type(exc).__name__}. "
                    f"This is exactly the failure mode documented in "
                    f"`docs/api_findings.md` — a 2,400 s poll timeout under "
                    f"load — and exactly why the headline number never "
                    f"depends on a live call succeeding on demand.", icon="⚠️")

    # ------------------------------------------------- any window, on demand
    st.markdown("---")
    st.markdown("#### Analyse any window: pick your own dates")
    st.caption(
        "The published result is one week of August 2025. This runs the same "
        "pipeline — the same evaluator, the same aggregation, the same "
        "divergence maths — over any dates the API will serve, from "
        "2021-01-01 to yesterday. Any year, any month, any week. A finished "
        "run is saved and joins the **Study window** selector on the home "
        "page, so it becomes a first-class result rather than a one-off view.")

    _today = customwindow.latest_servable()
    _cw1, _cw2 = st.columns(2)
    _start = _cw1.date_input("From", value=_dt.date(2024, 7, 8),
                             min_value=customwindow.EARLIEST, max_value=_today,
                             key="cw_start")
    _end = _cw2.date_input("To", value=_dt.date(2024, 7, 14),
                           min_value=customwindow.EARLIEST, max_value=_today,
                           key="cw_end")

    if _start > _end:
        st.warning("The start date is after the end date.")
    else:
        _est = customwindow.estimate(_start.isoformat(), _end.isoformat())
        _done = customwindow.already_analysed(_start.isoformat(), _end.isoformat())

        _e1, _e2, _e3, _e4 = st.columns(4)
        _e1.metric("Days", _est["days"])
        _e2.metric("API calls", _est["calls"], "2 per day", delta_color="off")
        _e3.metric("Credits", f"{_est['credits']:,}", "4,220 flat per call",
                   delta_color="off")
        _e4.metric("Estimated time",
                   f"{_est['seconds_low'] // 60}–{_est['seconds_high'] // 60} min",
                   "if every call is healthy", delta_color="off")

        if _done:
            st.success(
                f"**This window is already analysed** — no credits needed. "
                f"Select it on the home page's Study window selector to view "
                f"it.", icon="✅")

        st.caption(
            "Every call is cached as it arrives, so a run that fails partway "
            "is not wasted: press again and the completed days replay "
            "instantly while only the missing ones are fetched. Long windows "
            "are resumable rather than all-or-nothing.")

        if st.button(f"Analyse {_start.isoformat()} to {_end.isoformat()}",
                     type="primary", key="cw_go"):
            if not fg_cache.has_key():
                st.warning(
                    "No `FORTYGUARD_API_KEY` is configured on this "
                    "deployment, so no new window can be fetched here. The "
                    "windows already analysed remain available on the home "
                    "page. To run your own: set the key and use "
                    "`python run_analysis.py --start … --end …`, which is the "
                    "same code path this button calls.", icon="🔑")
            else:
                _bar = st.progress(0.0, text="Starting…")

                def _note(msg, i, total):
                    _bar.progress(min(i / max(total, 1), 1.0), text=msg)

                try:
                    _res = customwindow.analyse(_start.isoformat(),
                                                _end.isoformat(), progress=_note)
                except Exception as exc:  # noqa: BLE001 — never crash the page
                    _bar.empty()
                    st.error(
                        f"That window did not complete: {type(exc).__name__}. "
                        f"Whatever was fetched before the failure is cached, "
                        f"so pressing again resumes rather than restarting. "
                        f"Large windows on a small container are the documented "
                        f"weak point here — see `docs/api_findings.md`.",
                        icon="⚠️")
                else:
                    _bar.empty()
                    _path = customwindow.save(_res, _start.isoformat(),
                                              _end.isoformat())
                    _s = _res["summary"]
                    st.success(
                        f"**Analysed {_est['days']} days.** Saved as "
                        f"`{_path.name}` — it now appears in the Study window "
                        f"selector on the home page.", icon="🎉")
                    _r1, _r2, _r3 = st.columns(3)
                    _r1.metric("Silent zones",
                               f"{_s.get('silent_zones', 0)} of "
                               f"{len(_res.get('zones', []))}")
                    _r2.metric("Silent zone-days", _s.get("silent_zone_days", 0))
                    _r3.metric("People exposed",
                               f"{_s.get('population_exposed', 0):,}")

with tab_retract:
    st.markdown(
        "**We withdrew a result.** We measured, and then retracted, a finding "
        "that adding a duration requirement to Action 1.1's existing 105 °F "
        "threshold would restore targeting value.")
    st.error(
        "**FortyGuard exposes no trustworthy duration analytic at city scale.** "
        "`exceedance` returns a *total* of qualifying hours where a dwell "
        "clause describes a *continuous spell* — wrong analytic for the "
        "question. `persistence` is the right one, but citywide it returns runs "
        "of 25.92 h inside a single day, 3,110 negative runs, and up to 39,329 "
        "tiles whose longest run exceeds that tile's own total. It is also "
        "93.9% identical to `exceedance` at that threshold, so it is not an "
        "independent measurement. `tcm` carries no time information at all.")
    st.markdown(
        "We publish it as a **negative finding** rather than deleting it: a "
        "dwell requirement is the most natural fix for a saturating threshold, "
        "so it is the first thing a reader will propose and worth knowing it "
        "cannot be evaluated here. The failing harness is `sweep_dwell.py`, "
        "which exits non-zero, and `verify_all.py` asserts that it *continues* "
        "to fail — so the retraction cannot quietly go stale.")
    st.caption("Full methodology: docs/api_findings.md §8. "
               "All three corrections: README → \"What we got wrong\".")

st.divider()
st.caption(
    f"Thermal data: FortyGuard Temperature API at {study.GRANULARITY_M} m, "
    f"{CITY['tiles']} tiles per day over {CITY['aoi']} mi². "
    f"No external weather source is used anywhere in this pipeline. "
    f"Zones: {study.ZONES_SOURCE}. "
    f"Population: US Census ACS 5-year 2023. "
    f"{study.TIMEZONE_NOTE}"
)
