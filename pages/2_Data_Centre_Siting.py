"""National data-centre siting: where cooling is cheapest, and what it costs elsewhere."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

import ui  # noqa: E402
from site_model import DEFAULT_WEIGHTS, score_metros, tradeoff_table  # noqa: E402
from siting import compare, rank  # noqa: E402

st.set_page_config(page_title="TRIGGER — Data Centre Siting", page_icon="🌡",
                   layout="wide")
ui.style()

national = ui.results("national.json")
ui.masthead("Data centre siting",
            pills=[f"{national.get('n_metros', 0)} US metros",
                   "free-cooling hours measured at 100 m",
                   "ASHRAE 24 °C setpoint"] if national else [],
            warn=None if national else "data not generated")

st.title("Where should a data centre go?")
st.markdown(
    "A facility runs on outside air whenever ambient sits below the economiser "
    "setpoint — **free cooling**. Below that line the chillers idle and the "
    "cooling bill collapses. Published figures give Phoenix roughly "
    "**1,000–2,000 free-cooling hours a year** against **4,000–6,000** for "
    "Minneapolis, which is why climate dominates siting economics.\n\n"
    "**Every one of those published figures is a city-level number.** We measure "
    "the same quantity at **100 m**, because the free-cooling hours on one side "
    "of a metro are not the hours on the other, and nobody sites a building on a "
    "city average.")

if not national:
    ui.missing("The national panel", "python fetch_national.py")
    st.stop()

st.caption(national["coverage_note"])

# ---------------------------------------------------------------- weights
st.markdown("### 1 · How do you weigh the problem?")
st.caption(
    "Cooling is **not** the industry's first question. Published surveys put "
    "power availability top — 84% rank it in their top three — and the 2025 "
    "framing is *power, water and permits*, with interconnection timeline "
    "usually the binding constraint. Defaults reflect that. Move them.")

c = st.columns(5)
w = {}
for col, (k, v) in zip(c, DEFAULT_WEIGHTS.items()):
    w[k] = col.slider(k.capitalize(), 0.0, 1.0, v, 0.05, key=f"w_{k}")

scores = score_metros(national, w)
if not scores:
    st.warning("The panel contains no complete metros yet.")
    st.stop()

# ---------------------------------------------------------------- ranking
st.markdown("### 2 · The ranking")
best, worst = scores[0], scores[-1]
k1, k2, k3, k4 = st.columns(4)
k1.metric("Best site", best.name, f"score {best.score:.3f}", delta_color="off")
k2.metric("Free-cooling hours", f"{best.free_hours:.0f} h",
          f"vs {worst.free_hours:.0f} h at {worst.name}", delta_color="off")
k3.metric("Power", f"{best.electricity:.1f} ¢/kWh",
          best.grid_headroom + " grid", delta_color="off")
k4.metric("Water stress", best.water_stress.title(),
          best.disaster_risk.title() + " disaster risk", delta_color="off")

df = pd.DataFrame([{
    "#": i, "Metro": s.name, "State": s.state, "Score": round(s.score, 3),
    "Free-cool h": round(s.free_hours, 1),
    "Daily high °F": s.daily_high_f, "Overnight low °F": s.overnight_low_f,
    "¢/kWh": s.electricity, "Water": s.water_stress,
    "Disaster": s.disaster_risk, "Grid": s.grid_headroom,
    "Strategy": s.cooling_strategy["strategy"],
} for i, s in enumerate(scores, 1)])
st.dataframe(df, hide_index=True, use_container_width=True, height=430)
st.download_button("Download the ranking as CSV", df.to_csv(index=False),
                   "trigger_siting_ranking.csv", "text/csv")

# ------------------------------------------------------------- tradeoff
st.markdown("### 3 · The water–energy tradeoff")
st.markdown(
    "The industry's core dilemma is that **saving electricity often means "
    "wasting water, and saving water often means wasting electricity**. "
    "Evaporative cooling is far more energy-efficient than mechanical chilling, "
    "but it consumes water — and its effectiveness is set by **wet-bulb** "
    "temperature, not dry-bulb.\n\n"
    "A hot **arid** site has a low wet-bulb, so evaporative cooling works "
    "beautifully there. It is also exactly where water is scarcest. Microsoft "
    "reports a WUE of **1.52 L/kWh in Arizona** against **0.02 in Singapore**.")

tt = pd.DataFrame(tradeoff_table(scores))
q = st.selectbox("Filter by quadrant", ["All"] + sorted(tt["quadrant"].unique()))
st.dataframe(tt if q == "All" else tt[tt["quadrant"] == q],
             hide_index=True, use_container_width=True)

st.info(
    "**Energy-cheap but water-constrained** is the dangerous quadrant. Those "
    "sites get built and then fought over — data-centre water use is a "
    "documented flashpoint for community opposition in Arizona and California. "
    "A single composite score hides them, so they are named here.", icon="💧")

# ------------------------------------------------------------ cost model
st.markdown("### 4 · What the thermal difference costs")
cc = st.columns(3)
it_kw = cc[0].number_input("IT load (kW)", 100, 100_000, 1_000, 100)
cop = cc[1].number_input("Chiller COP", 1.5, 8.0, 3.5, 0.1)
tariff = cc[2].number_input("Tariff ($/kWh)", 0.02, 0.40, 0.085, 0.005,
                            format="%.3f")

zones = [{"zone_id": s.metro_id, "name": s.name,
          "free_hours": {"24": s.free_hours}} for s in scores]
ranked = rank(zones, window_days=national["n_days"], it_load_kw=it_kw,
              cop=cop, tariff=tariff)
cmp = compare(ranked)
if cmp:
    m1, m2, m3 = st.columns(3)
    m1.metric("Cheapest to cool", cmp["best"]["zone_name"],
              f"${cmp['best']['cooling_usd_window']:,.0f} over the window",
              delta_color="off")
    m2.metric("Most expensive", cmp["worst"]["zone_name"],
              f"${cmp['worst']['cooling_usd_window']:,.0f} over the window",
              delta_color="off")
    m3.metric("Gap", f"${cmp['usd_gap_window']:,.0f}",
              f"{cmp['pct_cheaper']:.0f}% cheaper", delta_color="off")
    st.caption(
        f"First-order model: kWh = IT load × mechanical hours ÷ COP. It omits "
        f"humidity blocking economiser operation, COP degradation at high "
        f"ambient, and part-load behaviour — **each of which makes the true gap "
        f"larger, not smaller**. Both sites carry identical assumptions on the "
        f"same days from the same measurements, so what survives the comparison "
        f"is the thermal difference between two pieces of ground. Absolute "
        f"dollars are an order of magnitude, not a quotation.")

# ------------------------------------------------------------- honesty
with st.expander("What is measured here, and what is not"):
    st.markdown(
        "**Measured by us**, at 100 m, from FortyGuard: free-cooling hours, "
        "daily high, overnight low. These resolve *within* a metro.\n\n"
        "**Reference constants**, from published sources, at **state** "
        "resolution: electricity price (EIA), water stress (WRI/USGS), disaster "
        "risk (FEMA National Risk Index), grid headroom (interconnection-queue "
        "reporting), renewables proximity.\n\n"
        "A state constant **cannot** resolve within-metro differences. That is "
        "exactly the criticism this project levels at heat plans, pointed back "
        "at our own model — and it is why the thermal term is the one we claim "
        "precision for and the others are weighted inputs rather than "
        "measurements.\n\n"
        "This is a **30-metro panel, not a national grid**. The API accepts "
        "roughly 1,053 mi² of land per call and the continental US is about "
        "3.1 million mi², so full coverage would need ~3,000 calls against a "
        "472-call budget. Every metro is sampled identically — same box, same "
        "day, same analytics — so the comparison is sound even though the "
        "coverage is a sample.")
