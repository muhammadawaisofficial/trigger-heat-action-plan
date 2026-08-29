"""National data-centre siting: where cooling is cheapest, and what it costs elsewhere."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

import charts  # noqa: E402
import ui  # noqa: E402

#: Provenance strip, resolved defensively. A deployed Streamlit container can
#: keep an older copy of a helper module in memory after a partial reload, so a
#: newly added ui function may not exist yet at import time. This strip is
#: chrome; a missing one is a cosmetic loss, while an AttributeError takes down
#: the whole page. Chrome must never be able to do that.
_api_strip = getattr(ui, "api_strip", lambda *a, **k: None)

from site_model import DEFAULT_WEIGHTS, score_metros, tradeoff_table  # noqa: E402
from siting import compare, rank  # noqa: E402

st.set_page_config(page_title="TRIGGER — Data Centre Siting", page_icon="🌡",
                   layout="wide")
ui.style()
ui.theme("siting")

national = ui.results("national.json")
ui.masthead("Data centre siting",
            pills=["30 US metros", "free-cooling measured at 100 m", "ASHRAE 24 °C setpoint"])
ui.topnav()

st.title("Where should a data centre go?")

st.info(
    "**Why this exists.** Data centres are sited on power, water and permits, "
    "and on cooling: the largest controllable operating cost, and the term "
    "measured worst. Every published free-cooling figure is a *city average* — "
    "Phoenix around 1,000 to 2,000 hours a year, Minneapolis 4,000 to 6,000. "
    "Nobody sites a building on a city average.",
    icon="🏢")
st.markdown(
    "**How the FortyGuard API makes this answerable.** Every thermal term "
    "below is measured by us across 30 US metros, at full resolution: "
    "**free-cooling hours** below the ASHRAE setpoint through `exceedance` "
    "with `direction=\"below\"`, **overnight lows and daily highs** through "
    "`tcm`, and **wet-bulb temperature** through `/v1/env_params` at each "
    "metro centroid — the variable the evaporative-versus-mechanical decision "
    "actually turns on. Because credits are flat per call regardless of area, "
    "each metro is a full-resolution request rather than a sample.")
st.markdown(
    "**The weights are yours to set.** Power is weighted highest by default "
    "because published surveys put it first, but a bank, a hyperscaler and a "
    "sovereign-cloud operator weigh these differently. Move the sliders below "
    "and the ranking, the cooling strategy and the cost model all recompute on "
    "your priorities rather than ours.")
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

_api_strip(
    [("POST /v1/heatmap · exceedance · direction=below",
      "free-cooling hours under the ASHRAE setpoint, per metro"),
     ("POST /v1/heatmap · tcm", "overnight lows and daily highs, per metro"),
     ("POST /v1/env_params", "wet-bulb at each metro centroid, the variable "
                             "the evaporative decision turns on")],
    note="30 US metros, each one a full-resolution call, because credits are "
         "flat per call regardless of area. The thermal terms are measured; "
         "electricity price, water stress and disaster risk are published "
         "state-level constants and are labelled as such.")

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
st.altair_chart(
    charts.rank_bar(df.assign(**{"Metro ": df["Metro"]}), "Score", "Metro ",
                    "composite score (higher is better)",
                    highlight=f'{best.name}'),
    use_container_width=True)
st.caption(f"Ranked on the weights above. **{best.name}** leads; every other "
           f"metro is shown in context rather than competing for attention.")
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

_sc = pd.DataFrame([{
    "Metro": s_.name,
    "Free-cooling hours": s_.free_hours,
    "Water security": s_.sub.get("water", 0) * 100,
} for s_ in scores])
st.altair_chart(
    charts.tradeoff(_sc, "Free-cooling hours", "Water security", "Metro",
                    "free-cooling hours (more is cheaper to cool)",
                    "water security (higher is safer)",
                    x_split=float(_sc["Free-cooling hours"].median()),
                    y_split=50.0),
    use_container_width=True)
st.caption("Bottom-left is the quadrant to worry about: little free cooling "
           "**and** constrained water, so neither cooling route is open. Those "
           "metros are named on the chart; the rest are context.")

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
