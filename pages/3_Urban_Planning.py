"""Urban-planning recommendations: how much intervention, and where.

Generic heat advice -- plant trees, paint roofs white -- is not wrong, it is
unquantified. This page joins a MEASURED thermal gap to PUBLISHED effect sizes so
each recommendation carries a magnitude and the number that produced it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

import charts  # noqa: E402
import planning  # noqa: E402
import ui  # noqa: E402

st.set_page_config(page_title="TRIGGER — Urban Planning", page_icon="🌡",
                   layout="wide")
ui.style()
ui.theme("planning")

city_name, city = ui.city_picker("up_city")
national = ui.results("national.json")

ui.masthead("Urban planning",
            pills=["30 US metros", "measured gap × published effect size"])
ui.topnav()

st.title("How much intervention, and exactly where")

st.info(
    "**Why this exists.** Heat kills more people than any other weather "
    "hazard, and the remedy is physical: shade, tree canopy, reflective "
    "surfaces. Cities know this. What a citywide average cannot tell them is "
    "**how much**, and **in which neighbourhood** — so budgets get spread "
    "evenly across places that are not equally hot, and the hottest blocks "
    "stay hottest.",
    icon="🌳")
st.markdown(
    "**How the FortyGuard API makes this answerable.** Intervention has to be "
    "aimed at a thermal gap, and a gap has to be measured before it can be "
    "closed. We measure it at **100 m** through `tcm`: per neighbourhood "
    "inside a city, and across 30 US metros as the spread between the hottest "
    "and coolest ground inside each sample box. That measured gap is then "
    "joined to published cooling effect sizes, which is what lets a "
    "recommendation carry a magnitude instead of being general advice.")
ui.api_strip(
    [("POST /v1/heatmap · tcm",
      "hottest and coolest ground inside each metro box, at tile resolution"),
     ("POST /v1/heatmap · tcm, per zone",
      "the per-neighbourhood peak the intervention order is ranked on"),
     ("granularity 100 m", "the resolution the whole targeting argument needs")],
    note="The thermal gap is measured. The canopy and albedo effect sizes it "
         "is joined to are published values, and are cited as such.")

# ------------------------------------------------------------------ national
st.markdown("### 1 · The range a single citywide number stands in for")

if not national:
    ui.missing("The national panel", "python fetch_national.py")
else:
    plans = planning.from_national(national)
    if plans:
        pdf = pd.DataFrame([{
            "Metro": p.name, "Climate": p.climate,
            "Coolest °F": p.min_f, "Hottest °F": p.max_f,
            "Spread °F": round(p.spread_f, 1),
            "Overnight low °F": p.overnight_low_f,
            "Instrument": ("Targeted — neighbourhood level"
                           if p.targeted else "Uniform citywide is defensible"),
        } for p in plans])

        w = plans[0]
        m1, m2, m3 = st.columns(3)
        m1.metric("Widest internal range", w.name, f"{w.spread_f:.1f} °F "
                  f"within one sample box", delta_color="off")
        m2.metric("Metros needing targeted policy",
                  f"{sum(p.targeted for p in plans)} of {len(plans)}",
                  f"spread ≥ {planning.SPREAD_TARGETED_F:.0f} °F",
                  delta_color="off")
        m3.metric("Metros with critical nights",
                  f"{sum(p.night_critical for p in plans)} of {len(plans)}",
                  f"overnight low ≥ {planning.NIGHT_CRITICAL_F:.0f} °F",
                  delta_color="off")

        st.altair_chart(
            charts.spread_dumbbell(pdf, "Metro", "Coolest °F", "Hottest °F"),
            use_container_width=True)
        st.caption("Each line runs from the coolest to the hottest ground "
                   "measured inside that metro's sample box. The length of the "
                   "line is the range a single citywide number stands in for.")
        st.dataframe(pdf, hide_index=True, use_container_width=True, height=380)
        st.download_button("Download the national planning table as CSV",
                           pdf.to_csv(index=False),
                           "trigger_urban_planning.csv", "text/csv")

        st.warning(
            "**Read spread carefully.** It is computed over every tile in a "
            "10 km sample box, and that box contains whatever is there — water, "
            "ridgelines, farmland, desert. Seattle's large spread is partly "
            "Puget Sound and hills sitting inside the box, **not** proof of an "
            "unjust heat island. What spread reliably measures is the *range of "
            "thermal conditions a single citywide number is standing in for* — "
            "which is the claim this project actually makes, and it holds "
            "regardless of what causes the range.", icon="⚠️")

        # ------------------------------------------------- per-metro detail
        st.markdown("### 2 · Recommendations for one metro")
        pick = st.selectbox("Metro", [p.name for p in plans])
        plan = next(p for p in plans if p.name == pick)

        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Spread", f"{plan.spread_f:.1f} °F",
                  f"{plan.min_f:.0f} → {plan.max_f:.0f} °F", delta_color="off")
        d2.metric("Mean", f"{plan.mean_f:.1f} °F", plan.climate,
                  delta_color="off")
        d3.metric("Overnight low",
                  f"{plan.overnight_low_f:.1f} °F" if plan.overnight_low_f
                  else "—",
                  "critical" if plan.night_critical else "recovers at night",
                  delta_color="off")
        d4.metric("Instrument", "Targeted" if plan.targeted else "Uniform",
                  "neighbourhood" if plan.targeted else "citywide",
                  delta_color="off")

        for r in plan.recommendations():
            st.markdown(
                f'<div class="tg-card" style="margin-bottom:.7rem">'
                f'<h4><span class="tg-rank">{r["priority"]}</span>'
                f'{r["action"]}</h4>'
                f'<p><b>Because:</b> {r["because"]}</p>'
                f'<p style="margin-top:.45rem"><b>Magnitude:</b> '
                f'{r["quantified"]}</p>'
                f'<p style="margin-top:.45rem;color:#71717a;font-size:.8rem">'
                f'Basis: {r["evidence"]}</p></div>',
                unsafe_allow_html=True)

# -------------------------------------------------------------- city zones
st.markdown(f"### 3 · Intervention order inside {city['short']}")
st.markdown(
    "Temperature alone ranks empty ground above a dense neighbourhood. "
    "Weighting measured heat by **residents** is what turns a thermal map into "
    "a planning order — and it is the step a citywide number cannot take, "
    "because it has no per-neighbourhood value to weight.")

results = ui.load(str(city["results"]))
population = ui.load(str(city["pop"]))

if not results:
    ui.missing(f"{city['short']} results", "python run_analysis.py")
else:
    clauses = [c["clause_id"] for c in results.get("clauses", [])]
    cid = st.selectbox("Clause providing the temperature series", clauses,
                       key="up_clause")
    rows = planning.zone_priorities(results, population, cid)
    if not rows:
        st.info("That clause carries no per-zone series.")
    else:
        zdf = pd.DataFrame([{
            "#": i, city["unit"].title(): r["name"],
            "Peak °F": round(r["peak_f"], 1),
            "Above coolest zone °F": r["above_coolest_f"],
            "Residents": r["population"],
            "Priority score": r["priority_score"],
        } for i, r in enumerate(rows, 1)])
        st.dataframe(zdf, hide_index=True, use_container_width=True, height=320)

        top = rows[0]
        st.info(
            f"**{top['name']}** ranks first: {top['above_coolest_f']:.1f} °F "
            f"above the coolest {city['unit']} with **{top['population']:,} "
            f"residents**. Priority score is normalised heat × residents — "
            f"deterministic arithmetic on measured values, with no model and no "
            f"language layer involved.", icon="📍")

        st.caption(
            "Zone values are **area-weighted means** over every overlapping "
            "tile, so they are deliberately smoother than the tile extremes in "
            "section 1. A zone mean and a single hottest tile are different "
            "quantities and are not compared with each other anywhere here.")

# ---------------------------------------------------------------- evidence
st.markdown("### 4 · The coefficients, and why these ones")
st.markdown(
    f"- **Canopy — {planning.CANOPY_C_PER_10PCT} °C per +10 points of cover.** "
    f"A global meta-analysis figure. Phoenix-specific work found 10% → 25% "
    f"canopy delivered up to **2.0 °C** of daytime cooling, and full canopy "
    f"against treeless ground reaches **5.5 °C**, rising to **8.8 °C** once air "
    f"temperature hits 40 °C. We use the meta-analysis number because it is the "
    f"**most conservative** and the one that generalises across a 30-metro "
    f"panel.\n"
    f"- **Cool roofs — {planning.ALBEDO_C_RESIDENTIAL} °C** in residential "
    f"deployment. Boston modelling gives −0.61 °C per +0.1 albedo in the "
    f"afternoon; again we take the conservative figure.\n"
    f"- **Canopy outperforms cool roofs by ~{planning.CANOPY_VS_ALBEDO:.2f}× on "
    f"temperature**, but cool roofs achieve higher *heat exposure* reduction in "
    f"practice, because they deploy in the dense, vulnerable districts that "
    f"have no room to plant. That trade-off is why nothing here recommends a "
    f"single winner.")

st.caption(
    "Effect sizes are published values applied to our measurements — they are "
    "not outcomes we measured. A degree of modelled cooling is not a degree of "
    "delivered cooling: implementation, maintenance, irrigation and survival "
    "rates all sit between the two. These are planning magnitudes, not "
    "guarantees.")
