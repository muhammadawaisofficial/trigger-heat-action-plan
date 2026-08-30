"""Heat waves, detected per neighbourhood and ranked nationally.

A heat wave is a RUN of consecutive qualifying days, and it starts on different
nights in different neighbourhoods of the same city. That is the distinction
this page exists to make.

Everything here is DETECTED IN MEASURED DATA. Nothing is forecast -- see the
closing section, which says plainly what this cannot do.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

import charts  # noqa: E402
import heatwave  # noqa: E402
import ui  # noqa: E402

#: Provenance strip, resolved defensively. A deployed Streamlit container can
#: keep an older copy of a helper module in memory after a partial reload, so a
#: newly added ui function may not exist yet at import time. This strip is
#: chrome; a missing one is a cosmetic loss, while an AttributeError takes down
#: the whole page. Chrome must never be able to do that.
_api_strip = getattr(ui, "api_strip", lambda *a, **k: None)


st.set_page_config(page_title="TRIGGER — Heat Waves", page_icon="🌡",
                   layout="wide", initial_sidebar_state="expanded")
ui.style()
ui.theme("heat")

city_name, city = ui.city_picker("hw_city")
guide = ui.guidance()
national = ui.results("national.json")

ui.masthead("Heat waves",
            pills=[city["short"], "per-neighbourhood detection", "absolute vs percentile basis"])
ui.topnav()

st.title("Which neighbourhoods are in a heat wave — and since when")

# The first question anyone asks of a heat page is whether it predicts. Answer
# it at the top, in one line, rather than leaving it to a caveat at the bottom.
st.info(
    "**What this page does, in one line.** It **detects** heat waves in "
    "measured data — which neighbourhoods were in one, starting which night — "
    "and ranks 30 US metros by how dangerous their nights run. It does **not** "
    "forecast days ahead: the API serves measured history and about twelve "
    "hours forward, so a multi-day prediction is not something this data "
    "supports and none is shown. Full detail in section 6.")
st.markdown(
    "Every operational heat-wave definition has the same three parts: a "
    "**threshold**, a **persistence** requirement, and — in the definitions that "
    "actually predict mortality — a **night-time** condition. City-scale "
    "products answer *is the city in a heat wave*. This answers **which "
    "neighbourhoods are, and since which night**.")

_api_strip(
    [("POST /v1/heatmap · tcm",
      "per-zone daily low and high, the run detection is computed from"),
     ("filter_type 3", "day by day, because a run needs a time axis a "
                       "multi-day aggregate collapses"),
     ("granularity 100 m", "so a run can start in one neighbourhood and "
                           "not another")],
    note="Detection runs on measured FortyGuard values. The absolute and "
         "percentile bases below are two ways of reading the same measurements.")

results = ui.load(str(city["results"]))
population = ui.load(str(city["pop"]))

if not results:
    ui.missing(f"{city['short']} results", "python run_analysis.py")
    st.stop()

# ------------------------------------------------------------------ clause
# Only clauses whose series is a TEMPERATURE can be used. An exceedance clause
# measures HOURS past a threshold; comparing that to a degF heat-wave threshold
# is arithmetic on two different quantities. The module refuses it, and this
# page never offers it.
valid = heatwave.temperature_clauses(results)
if not valid:
    st.warning(
        "No clause in this city's results carries a temperature series. "
        "Heat-wave detection needs a temperature per zone per day; the "
        "clauses here are exceedance counts measured in hours.")
    st.stop()

cc = st.columns([3, 1, 1])
min_days = cc[1].number_input("Consecutive days", 2, 7, 2)
pct = cc[2].number_input("Percentile basis", 50.0, 99.0, 90.0, 1.0)

# ------------------------------------------------------------------- ladder
# Run detection across EVERY temperature clause, not just the selected one.
# Showing one clause invites the question "why that clause"; showing all of them
# answers it, and the collapse in wave count as the threshold rises IS the
# finding rather than an illustration of it.
ladder = []
for c in valid:
    try:
        d = heatwave.from_results(results, clause_id=c["clause_id"],
                                  population=population,
                                  min_days=int(min_days), pct=float(pct))
    except ValueError:
        continue
    if not d:
        continue
    s = d["absolute"]["summary"]
    ladder.append({
        "Clause": c["clause_id"],
        "Threshold °F": d["absolute"]["threshold_f"],
        "Waves": s["waves"],
        f"{city['unit'].title()}s": s["zones_in_heatwave"],
        "Longest run": s["longest_days"],
        "Residents in those zones": s["population"],
        "_id": c["clause_id"], "_waves": s["waves"],
    })
ladder.sort(key=lambda r: r["Threshold °F"])

if ladder:
    st.markdown("### 1 · What the threshold choice costs")
    st.markdown(
        "The same week, the same measurements, the same zones — detected "
        "against each threshold in turn. **Nothing about the weather changes "
        "down this table. Only the number written in the plan changes.**")
    charts.render(charts.ladder([{"label": f"{r['Threshold °F']:g} °F",
                        "people": r["Residents in those zones"],
                        "waves": r["Waves"],
                        "zones": r[f"{city['unit'].title()}s"]} for r in ladder]))
    st.caption("Bar height is residents inside a detected heat wave; the number "
               "above each bar is how many separate waves were detected.")
    with st.expander("The same figures as a table"):
        st.dataframe(pd.DataFrame([{k: v for k, v in r.items()
                                    if not k.startswith("_")} for r in ladder]),
                     hide_index=True, use_container_width=True)
    lo, hi = ladder[0], ladder[-1]
    if lo["_waves"] != hi["_waves"]:
        st.error(
            f"At **{lo['Threshold °F']:.0f} °F** this week is "
            f"**{lo['Waves']} heat waves** covering "
            f"**{lo['Residents in those zones']:,} residents**. At "
            f"**{hi['Threshold °F']:.0f} °F** it is **{hi['Waves']}**. A city "
            f"that writes the higher number into its plan does not experience "
            f"less heat — it just stops being able to see it.")

# Default to a clause that actually produces runs, so the detail view below
# demonstrates the analysis rather than opening on an empty result. The ladder
# above already shows every clause, so this default hides nothing.
labels = {f"{c['clause_id']} — threshold {c.get('threshold_f')} °F": c["clause_id"]
          for c in valid}
_with_waves = [r["_id"] for r in ladder if r["_waves"]]
_default = 0
if _with_waves:
    for i, cid in enumerate(labels.values()):
        if cid == _with_waves[0]:
            _default = i
            break
picked = cc[0].selectbox("Clause / threshold to detect against", list(labels),
                         index=_default)
clause_id = labels[picked]

det = heatwave.from_results(results, clause_id=clause_id,
                            population=population, min_days=int(min_days),
                            pct=float(pct))
if not det:
    st.warning("That clause produced no determinations.")
    st.stop()

absolute, percentile = det["absolute"], det["percentile"]

# ------------------------------------------------------------------ headline
st.markdown("### 2 · Two thresholds, two different answers")
st.markdown(
    "**The absolute threshold is what the plan governs on.** The **percentile** "
    "threshold is what the epidemiological literature uses, because the "
    "temperature at which people begin dying is relative to what they are "
    "acclimatised to — 95 °F is an emergency in Seattle and a Tuesday in "
    "Phoenix. Both are computed on the same zones, same days, same measurements.")

a, p = absolute["summary"], percentile["summary"]
k = st.columns(4)
k[0].metric(f"Absolute — {absolute['threshold_f']:.0f} °F",
            f"{a['waves']} waves",
            f"{a['zones_in_heatwave']}/{a['zones_total']} {city['unit']}s",
            delta_color="off")
k[1].metric("People in those zones", f"{a['population']:,}",
            f"longest run {a['longest_days']} days", delta_color="off")
k[2].metric(f"Percentile p{pct:.0f} — {percentile['threshold_f']:.1f} °F",
            f"{p['waves']} waves",
            f"{p['zones_in_heatwave']}/{p['zones_total']} {city['unit']}s",
            delta_color="off")
k[3].metric("People in those zones", f"{p['population']:,}",
            f"longest run {p['longest_days']} days", delta_color="off")

gap = absolute["threshold_f"] - percentile["threshold_f"]
if abs(gap) >= 0.5:
    higher = "ABOVE" if gap > 0 else "BELOW"
    st.info(
        f"The plan's threshold sits **{abs(gap):.1f} °F {higher}** the p{pct:.0f} "
        f"of this city's own measured distribution. A threshold above the local "
        f"distribution fires rarely and late; one below it fires often enough to "
        f"be ignored. Neither is visible to a city that never compares the two.")

# ------------------------------------------------------------------ the runs
st.markdown("### 3 · The runs")
basis = st.radio("Basis", ["absolute", "percentile"], horizontal=True,
                 format_func=lambda b: (
                     f"Absolute — {absolute['threshold_f']:.0f} °F (what the plan governs on)"
                     if b == "absolute" else
                     f"Percentile p{pct:.0f} — {percentile['threshold_f']:.1f} °F (what the epidemiology uses)"))
waves = det[basis]["waves"]

if not waves:
    st.success(
        f"No run of {int(min_days)}+ consecutive days met the "
        f"{det[basis]['threshold_f']:.1f} °F threshold on this basis. "
        f"**That is a finding, not an absence of one** — the other basis above "
        f"may well show runs over the identical days.")
else:
    wdf = pd.DataFrame([{
        "Severity": w["severity"], city["unit"].title(): w["zone_name"],
        "Start": w["start"], "End": w["end"], "Nights": w["length_days"],
        "Peak °F": w["peak_f"], "Peak day": w["peak_day"],
        "Residents": w["population"],
    } for w in waves])
    charts.render(charts.wave_runs(waves))
    st.caption("Each bar is one continuous run of qualifying nights in one area. "
               "Length is the run; colour reinforces it.")
    st.dataframe(wdf, hide_index=True, use_container_width=True)
    st.download_button("Download detected waves as CSV", wdf.to_csv(index=False),
                       f"trigger_heatwaves_{city['short'].lower()}.csv", "text/csv")
    st.caption(
        "**SEVERE** is 4+ consecutive nights, **SIGNIFICANT** 3, **NOTABLE** 2. "
        "Length is what kills: risk rises sharply across the first three days of "
        "sustained heat because a body that never cools does not recover.")

# ------------------------------------------------------------- danger tier
st.markdown("### 4 · What that means for people, and what to do")
st.caption(guide.get("source_note", ""))

peak = max((w["peak_f"] for w in waves), default=None)
tier = ui.tier_for(peak) if peak is not None else ui.tier_for(None, None)
if peak is not None and tier:
    st.markdown(
        f'<div style="border-left:5px solid {tier["colour"]};background:#fafafa;'
        f'padding:.9rem 1.2rem;border-radius:0 10px 10px 0;margin:.4rem 0 1rem">'
        f'<b style="font-size:1.05rem">Level {tier["level"]} — {tier["name"]}</b>'
        f'<br><span style="color:#3f3f46">{tier["meaning"]}</span></div>',
        unsafe_allow_html=True)
    g1, g2 = st.columns(2)
    with g1:
        st.markdown("**Who is at risk**")
        for who in tier.get("who", []) or ["—"]:
            st.markdown(f"- {who}")
    with g2:
        st.markdown("**What the response is**")
        for act in tier.get("actions", []):
            st.markdown(f"- {act}")

with st.expander("Why overnight low governs, not the daytime high"):
    st.markdown(guide.get("why_overnight", ""))
    st.markdown(f"*{guide.get('consecutive_day_note', '')}*")
    st.caption(guide.get("_README", ""))

# ---------------------------------------------------------------- national
st.markdown("### 5 · The national picture")
if not national:
    ui.missing("The national panel", "python fetch_national.py")
else:
    st.markdown(
        f"The same measurement across **{national.get('n_metros', 0)} US "
        f"metros** on a common design day (**{national.get('design_day')}**), "
        f"tiered by **overnight low** — the variable the epidemiology ties "
        f"mortality to, and the one daytime-high products do not report.")

    rows = []
    for m in national.get("metros", []):
        low, high = m.get("mean_overnight_low_f"), m.get("mean_daily_high_f")
        if low is None:
            continue
        t = ui.tier_for(low, high)
        rows.append({"Metro": m["name"], "Climate": m.get("zone", ""),
                     "Overnight low °F": low, "Daily high °F": high,
                     "Level": t.get("level"), "Danger tier": t.get("name", "—")})
    if rows:
        ndf = pd.DataFrame(rows).sort_values("Overnight low °F", ascending=False)
        top = ndf.iloc[0]
        n1, n2, n3 = st.columns(3)
        n1.metric("Hottest night in the panel", top["Metro"],
                  f"{top['Overnight low °F']:.1f} °F — {top['Danger tier']}",
                  delta_color="off")
        n2.metric("Metros at Major or worse",
                  f"{int((ndf['Level'] >= 3).sum())} of {len(ndf)}",
                  "by overnight low", delta_color="off")
        n3.metric("Coolest night", ndf.iloc[-1]["Metro"],
                  f"{ndf.iloc[-1]['Overnight low °F']:.1f} °F", delta_color="off")
        st.dataframe(ndf, hide_index=True, use_container_width=True, height=360)
        st.caption(national.get("coverage_note", ""))

# ----------------------------------------------------------------- honesty
st.markdown("### 6 · What this does not do")
st.warning(
    "**This does not forecast.** The temperature API serves measured history "
    "and roughly twelve hours ahead — there is no multi-day forecast horizon in "
    "it, so a multi-day heat-wave *prediction* is not something this data can "
    "honestly support, and none is shown. What is shown is detection in "
    "measured data, plus a climatological ranking of how metros compare on a "
    "common day.\n\n"
    "A forecast product would need a numerical weather prediction feed "
    "(NWS/NBM or ECMWF) joined to this hyperlocal layer. That is a real and "
    "buildable design — it is simply not what is running here, and we would "
    "rather say so than show a number we cannot stand behind.")

st.caption(
    "Danger tiers follow the structure of NOAA/NWS **HeatRisk** — five ordinal, "
    "colour-coded levels — and standard NWS/CDC extreme-heat guidance. Because "
    "our levels are keyed to *measured* overnight low and daily high rather than "
    "the forecast, multi-factor product NWS publishes, this is an **analogue of "
    "HeatRisk, not a reproduction of it**, and is not an NWS product.")
