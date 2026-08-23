"""TRIGGER — the interface.

Runs entirely from committed files. No API key, no network, no live calls:

    streamlit run app.py

Four preset missions rather than an open text box, because the point of this
tool is adjudicating a specific legal document, not answering arbitrary
questions. Every panel traces back to a clause, a page and a verbatim sentence.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

sys.path.insert(0, str(Path(__file__).parent / "src"))

import study  # noqa: E402

REPO = Path(__file__).parent
RESULTS = REPO / "data" / "results" / "divergence.json"
ZONES = REPO / "data" / "zones" / "phoenix_villages_raw.geojson"
POP = REPO / "data" / "zones" / "phoenix_villages_population.json"

PROXY_LABEL = ("Citywide proxy — the area-weighted mean over the whole city AOI, "
               "used as a stand-in for station-based sensing. **It is not a real "
               "station feed.** A real single station is less representative than "
               "this, so every divergence figure here is a lower bound.")

st.set_page_config(page_title="TRIGGER — Heat Action Plan Compiler",
                   page_icon="🌡", layout="wide")


# ------------------------------------------------------------------- loading

@st.cache_data
def load_results() -> dict:
    if not RESULTS.exists():
        return {}
    return json.loads(RESULTS.read_text(encoding="utf-8"))


@st.cache_data
def load_zone_geo() -> dict:
    return json.loads(ZONES.read_text(encoding="utf-8"))


@st.cache_data
def load_pop() -> dict:
    if not POP.exists():
        return {}
    return json.loads(POP.read_text(encoding="utf-8")).get("villages", {})


res = load_results()
if not res:
    st.error("No results found. Run `python run_analysis.py` first.")
    st.stop()

geo = load_zone_geo()
pop = load_pop()
clauses = {c["clause_id"]: c for c in res["clauses"]}
summary = res["summary"]


# --------------------------------------------------------------------- header

st.title("TRIGGER — the Heat Action Plan Compiler")
st.markdown(
    f"**{study.PLAN_TITLE}** compiled into executable rules and re-evaluated "
    f"against FortyGuard 2-metre data across {len(res['zones'])} Phoenix urban "
    f"villages."
)

c1, c2, c3, c4, c5 = st.columns(5)
if summary.get("population_exposed"):
    c1.metric("People in silent zones",
              f"{summary['population_exposed']:,}",
              f"{summary['population_exposed']/summary['population_total']:.0%} of Phoenix")
else:
    c1.metric("People in silent zones", "n/a")
c2.metric("Silent zones", f"{summary['silent_zones']} of {len(res['zones'])}")
c3.metric("Silent zone-days", summary["silent_zone_days"])
c4.metric("False-calm days",
          f"{len(summary.get('false_calm_days', []))} of {summary['days']}")
c5.metric("Median lead time",
          f"{summary['median_lead_days']:.0f} d" if summary.get("median_lead_days")
          else "n/a")

st.caption(f"Study window {summary['window'][0]} to {summary['window'][1]}. "
           f"All decisions are deterministic comparisons; no language model "
           f"produces any number on this page.")


# ------------------------------------------------------------------- missions

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

with st.sidebar:
    st.header("Mission")
    mission = st.radio("Preset mission", list(MISSIONS.keys()),
                       label_visibility="collapsed")
    st.caption(MISSIONS[mission])

    st.divider()
    st.header("Clause")
    # Default to the clause carrying the headline.
    ids = list(clauses.keys())
    default = next((i for i, k in enumerate(ids) if clauses[k]["silent_zone_days"]), 0)
    clause_id = st.selectbox("Evaluable clause", ids, index=default,
                             format_func=lambda k: f"{k} ({clauses[k]['threshold_f']:g}°F)")

    cl = clauses[clause_id]
    days = [d["day"] for d in cl["determinations"]]
    worst = cl.get("worst_false_calm")
    day_default = days.index(worst[0]) if worst and worst[0] in days else len(days) - 1
    day = st.select_slider("Day", options=days, value=days[day_default])

    st.divider()
    st.subheader("Baseline")
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
    st.markdown(f"> *“{cl['source_text']}”*")
    st.caption(f"**{study.PLAN_TITLE}, page {cl['source_page']}** — verbatim, "
               f"verified against that page. "
               f"[Open the source PDF]({study.PLAN_URL}#page={cl['source_page']})")
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


def zone_id_of(feature: dict) -> str:
    return str(feature["properties"].get("NAME", "")).lower().replace(" ", "_")


m = folium.Map(location=[33.55, -112.09], zoom_start=9, tiles="cartodbpositron")

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
    st_folium(m, height=520, use_container_width=True, returned_objects=[])  # st_folium keeps this kwarg
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

st.divider()
st.caption(
    f"Thermal data: FortyGuard Temperature API at {study.GRANULARITY_M} m, "
    f"272,917 tiles per day over {study.city_aoi_sq_mi():,.0f} mi². "
    f"No external weather source is used anywhere in this pipeline. "
    f"Zones: {study.ZONES_SOURCE}. "
    f"Population: US Census ACS 5-year 2023. "
    f"{study.TIMEZONE_NOTE}"
)
