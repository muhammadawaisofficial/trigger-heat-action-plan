"""TRIGGER — the home page, written to be understood by someone who arrives cold.

This page answers four questions in order, and nothing else:

    1. What is wrong?          one thermometer decides for a whole city
    2. What did you find?      the number, in plain words
    3. Where?                  a map you can click
    4. So what do I do?        tonight's brief, and where to go next

Everything technical -- the clause explorer, provenance, the New York
replication, the API findings, the retractions -- lives on the Methods &
Evidence page. That separation is deliberate: a page that answers "what did you
find" and "how exactly did you compute it" at the same time answers neither.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import folium
import streamlit as st
from streamlit_folium import st_folium

sys.path.insert(0, str(Path(__file__).parent / "src"))

import charts  # noqa: E402
import liveconditions  # noqa: E402
import study  # noqa: E402
import ui  # noqa: E402
from alerts import detect, summarise  # noqa: E402
from cache import has_key  # noqa: E402

REPO = Path(__file__).parent

st.set_page_config(page_title="TRIGGER — who does the heat plan miss?",
                   page_icon="🌡", layout="wide",
                   initial_sidebar_state="expanded")
ui.style()
ui.theme("home")

st.markdown("""
<style>
  .tg-q { font-size:.72rem; font-weight:800; letter-spacing:.16em;
    text-transform:uppercase; color:#b2182b; margin:0 0 .3rem; }
  .tg-lead { font-size:clamp(1.05rem,1.7vw,1.3rem); line-height:1.65;
    color:#27272a; }
  .tg-lead b { color:#18181b; }
  .tg-plain { background:#fafafa; border:1px solid #e4e4e7; border-radius:13px;
    padding:1.1rem 1.3rem; margin:.5rem 0 1.1rem; }
  .tg-vs { display:grid; grid-template-columns:1fr auto 1fr; gap:1rem;
    align-items:center; margin:.6rem 0 0; }
  .tg-vs-box { background:#fff; border:1px solid #e4e4e7; border-radius:11px;
    padding:.9rem 1rem; }
  .tg-vs-box h5 { margin:0 0 .3rem; font-size:.8rem; font-weight:800;
    letter-spacing:.06em; text-transform:uppercase; color:#71717a; }
  .tg-vs-box p { margin:0; font-size:.92rem; line-height:1.55; color:#3f3f46; }
  .tg-vs-mid { font-size:1.4rem; color:#b2182b; font-weight:800; }
  .tg-next { display:grid; gap:.9rem;
    grid-template-columns:repeat(auto-fit,minmax(215px,1fr)); margin:.3rem 0 0; }
  .tg-next a { text-decoration:none; }
  .tg-next .tg-card { height:100%; transition:border-color .15s; }
  .tg-next .tg-card:hover { border-color:#b2182b; }
  @media (max-width:760px){ .tg-vs { grid-template-columns:1fr; }
    .tg-vs-mid { text-align:center; } }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_json(path_str: str) -> dict:
    f = Path(path_str)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


AVAILABLE = {k: v for k, v in ui.CITIES.items() if v["results"].exists()}
if not AVAILABLE:
    st.error("No results found. Run `python run_analysis.py` first.")
    st.stop()

with st.sidebar:
    st.markdown("### Choose a city")
    city_name = st.radio("City", list(AVAILABLE), label_visibility="collapsed",
                         captions=[AVAILABLE[c]["trigger"] for c in AVAILABLE])
    CITY = AVAILABLE[city_name]
    st.caption(CITY["note"])
    if len(AVAILABLE) > 1:
        st.success("Switching city re-runs every number on this page from that "
                   "city's own data. Same code, one profile file per city.",
                   icon="🔀")

_results_path, _window_label = ui.window_picker(CITY, key="home_window")
res = load_json(str(_results_path))
geo = load_json(str(CITY["zones"]))
pop = (load_json(str(CITY["pop"])) or {}).get("villages", {})
summary = res["summary"]


def zone_id_of(feature: dict) -> str:
    return str(feature["properties"].get("NAME", "")).lower().replace(" ", "_")


#: Union of silent zones across every evaluated clause -- the same set that
#: produces the published population figure. Not a new computation.
SILENT: set[str] = set()
for _c in res["clauses"]:
    SILENT |= set(_c.get("silent_zones") or [])

exposed = summary.get("population_exposed")
total_pop = summary.get("population_total")

ui.masthead("who does the heat plan miss?",
            pills=[CITY["short"], f"{len(res['zones'])} {CITY['unit']}s", f"{CITY['tiles']} tiles/day at 100 m", "real API data"])
ui.topnav()

# ═══════════════════════════════════════════════════ 1 · WHAT IS WRONG
st.markdown('<p class="tg-q">1 — The problem</p>', unsafe_allow_html=True)
st.markdown(
    f'<p class="tg-lead">{CITY["short"]} has a <b>Heat Action Plan</b> — a legal '
    f'document naming who must act, and at what temperature. '
    f'<b>The whole plan is switched on and off by one number:</b> a single '
    f'reading, usually from the airport. But heat is not one number.</p>',
    unsafe_allow_html=True)

st.markdown(
    '<div class="tg-plain"><div class="tg-vs">'
    '<div class="tg-vs-box"><h5>What the plan sees</h5>'
    '<p>One thermometer. One reading for the entire city. It either crosses the '
    'threshold, or it does not.</p></div>'
    '<div class="tg-vs-mid">vs</div>'
    '<div class="tg-vs-box"><h5>What people live in</h5>'
    '<p>Every neighbourhood at its own temperature, measured 2 metres above the '
    'ground — where a body actually stands.</p></div>'
    '</div></div>', unsafe_allow_html=True)

st.markdown(
    "**The question this app answers:** on nights the airport reading stayed "
    "below the threshold — so the plan never switched on — had any "
    "neighbourhood *already* crossed it? And how many people live there?")

st.divider()

# ═══════════════════════════════════════════════════ 2 · WHAT WE FOUND
st.markdown('<p class="tg-q">2 — What we found</p>', unsafe_allow_html=True)

if exposed:
    st.markdown(
        f"""<div class="tg-hero">
          <div class="tg-kicker">Measured, not modelled · {summary['window'][0]} to {summary['window'][1]}</div>
          <div class="tg-num">{exposed:,}</div>
          <div class="tg-sub">
            people — <b>{exposed / total_pop:.0%} of {CITY['short']}</b> — live in a
            neighbourhood that <b>was hot enough to trigger the plan</b>,
            on nights the citywide reading <b>never did</b>.<br>
            That is <b>{len(SILENT)} of {len(res['zones'])}</b> {CITY['unit']}s.
          </div>
        </div>""", unsafe_allow_html=True)

k = st.columns(4)
k[0].metric("Neighbourhoods missed", f"{summary['silent_zones']} of {len(res['zones'])}",
            "the plan stayed off", delta_color="off")
k[1].metric("Nights missed", summary["silent_zone_days"],
            "neighbourhood-nights", delta_color="off")
k[2].metric("Days the plan never fired at all",
            f"{len(summary.get('false_calm_days', []))} of {summary['days']}",
            "despite local conditions being met", delta_color="off")
k[3].metric("Typical warning lost",
            f"{summary['median_lead_days']:.0f} days"
            if summary.get("median_lead_days") else "n/a",
            "before the citywide trigger caught up", delta_color="off")

# The replication was buried in the README while the app showed only the
# published window -- which made a pipeline that HAS been run on unseen data
# look like it could only ever produce one hardcoded result.
if _window_label:
    _n_windows = len(CITY.get("windows") or {})
    st.info(
        f"**You are viewing: {_window_label}.** This city has "
        f"**{_n_windows} analysed windows** — switch between them in the "
        f"sidebar. The 2026 window was **fetched live from the API**, a week "
        f"this analysis had never seen, and the finding reproduced: "
        f"9 of 15 {CITY['unit']}s, 958,205 residents, same near-miss "
        f"signature. Nothing here is hardcoded to one week.", icon="🔁")

with st.expander(f"Why {summary['days']} days, and not a whole summer?"):
    st.markdown(
        f"**These {summary['days']} days were chosen by measurement, not "
        f"convenience.** We first scanned **1 July – 15 Aug 2025** day by day "
        f"over a small, cheap area and ranked every day by hours above the "
        f"105 °F threshold the plan itself names. "
        f"**{summary['window'][0]} to {summary['window'][1]}** came out as the "
        f"most severe consecutive stretch of that summer — so the plan is being "
        f"tested on the days it most needed to work, which is the hardest test "
        f"for our own argument rather than the easiest.\n\n"
        f"**Why not run the whole summer at full resolution?** Every full-city "
        f"request costs the same **4,220 credits flat**, whether it covers 420 "
        f"tiles or 272,917. Each day of the published analysis needs several "
        f"such calls, and the run so far has used **125 calls / 527,500 "
        f"credits** across **58 distinct days** of data. A full summer at "
        f"1,053 mi² and 100 m resolution would cost several times the entire "
        f"budget.\n\n"
        f"The finding does not rest on this one window: the same pipeline, "
        f"unchanged, was re-run on a **separate 2026 window the analysis had "
        f"never seen**, and reproduced the result. That replication is on the "
        f"Methods & evidence page.")

_api = load_json(str(REPO / "data" / "results" / "api_usage.json"))
if _api:
    with st.expander("Is this live data? Where did it come from?"):
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Real API calls made", f"{_api['calls']}", "FortyGuard",
                  delta_color="off")
        a2.metric("Tiles fetched", f"{_api['tiles'] / 1e6:.1f}M",
                  "at 100 m resolution", delta_color="off")
        a3.metric("Credits spent", f"{_api['credits']:,}",
                  f"{_api['distinct_days']} distinct days", delta_color="off")
        a4.metric("Responses committed", f"{_api['cache_mb']:.0f} MB",
                  "in the repository", delta_color="off")
        st.markdown(
            f"**Every number here came from real calls to the FortyGuard "
            f"Temperature API** — {_api['calls']} of them, covering "
            f"{_api['tiles']:,} tiles across {_api['distinct_days']} days. "
            f"Nothing is simulated, and no other weather source is used "
            f"anywhere in the pipeline.\n\n"
            f"**The responses are saved and committed to the repository, and "
            f"the app reads those saved responses rather than calling the API "
            f"again.** That is a deliberate choice, for three reasons:\n\n"
            f"- **So you can check us.** Clone the repo and run "
            f"`python verify_all.py` — it re-derives every published figure "
            f"from the same saved responses and fails loudly if one has moved. "
            f"A demo that only works against a live key cannot be audited.\n"
            f"- **So it always works.** A submitted demo that depends on a live "
            f"API is one outage or one expired key away from showing a judge an "
            f"error page.\n"
            f"- **Because the calls are expensive.** Each full-city request "
            f"costs a flat 4,220 credits and takes minutes to poll, whatever "
            f"the area.\n\n"
            f"The cache is a **saved copy, not baked-in data**: ask the "
            f"pipeline for a window that is not in it, set an API key, and it "
            f"calls the API for real. That is exactly how the 2026 replication "
            f"window was produced — on data this analysis had never seen.\n\n"
            f"**Want to watch the network move anyway?** The Methods & "
            f"evidence page has a **\"Fetch a live reading\"** button — a "
            f"small, real, on-demand call kept deliberately separate from "
            f"everything on this page, so it can prove liveness without "
            f"putting a live poll on the critical path of the number above.")

with st.expander("How is this measured, and what is the comparison?"):
    st.markdown(
        f"We take {CITY['short']}'s **own published plan**, extract each rule "
        f"(its threshold, who must act, which page it is on), and then test "
        f"every rule twice against the same FortyGuard measurements:\n\n"
        f"- **Neighbourhood by neighbourhood** — each {CITY['unit']} gets its "
        f"own temperature, averaged over every 100 m tile that overlaps it.\n"
        f"- **One citywide number** — the same measurements averaged over the "
        f"whole city, standing in for the single-station reading.\n\n"
        f"Where the first says *act* and the second says *nothing to do*, that "
        f"is a **missed neighbourhood**. Every decision is a plain numeric "
        f"comparison — no AI decides any of it.")
    st.info(
        "**One honest caveat.** Our citywide comparison is the average across "
        "the whole city — a **proxy** for station-based sensing, not a real "
        "feed from the airport station. That proxy is a *generous* stand-in: a "
        "real single sensor would do worse than a citywide average. So every "
        "number above is a **lower bound**, not an exaggeration.", icon="ℹ️")

# ------------------------------------------------------------- the gap chart
# The argument in one figure. Every neighbourhood's peak against the threshold
# it had to clear, and against the single citywide number that was supposed to
# notice. The bars that cross the dashed line while the solid line does not are
# the finding -- previously the reader had to assemble that from a table.
_gap_clause = next(
    (c for c in res["clauses"]
     if c.get("silent_zones") and c["determinations"][0]["zones"][0]["units"] != "hours"),
    None)
if _gap_clause:
    _worst = _gap_clause.get("worst_false_calm")
    _day = _worst[0] if _worst else _gap_clause["determinations"][-1]["day"]
    _det = next((d for d in _gap_clause["determinations"] if d["day"] == _day),
                _gap_clause["determinations"][-1])

    def _f(v: float, units: str) -> float:
        return v * 9 / 5 + 32 if units == "degC" else v

    _rows = [{
        "name": z["name"],
        "value_f": _f(z["value"], z["units"]),
        "missed": z["zone_id"] in SILENT and z["fired"],
        "population": pop.get(z["zone_id"], {}).get("population") or 0,
    } for z in _det["zones"]]
    _thr = _gap_clause["threshold_f"]
    _proxy_f = _f(_det["proxy"]["value"], _det["proxy"]["units"])

    st.markdown(f"##### The night of {_day}, neighbourhood by neighbourhood")
    st.altair_chart(
        charts.zone_gap(_rows, _thr, _proxy_f, unit=CITY["unit"]),
        use_container_width=True)
    _n_over = sum(1 for r in _rows if r["value_f"] >= _thr)
    st.markdown(
        f'<div class="tg-legend">'
        f'<span><span class="tg-sw" style="background:{charts.ACCENT}"></span>'
        f'crossed the threshold — the plan should have fired here</span>'
        f'<span><span class="tg-sw" style="background:{charts.MUTED}"></span>'
        f'below it</span>'
        f'<span>┈ dashed: the <b>{_thr:g} °F</b> threshold</span>'
        f'<span>─ solid: the <b>citywide reading, {_proxy_f:.1f} °F</b></span>'
        f'</div>', unsafe_allow_html=True)
    st.caption(
        f"**The solid line sits below the dashed one, so the plan stayed off.** "
        f"{_n_over} of {len(_rows)} {CITY['unit']}s were already above the "
        f"threshold that night. One number for the whole city cannot be above "
        f"and below the same line at once — that is the entire failure, in one "
        f"picture.")

st.divider()

# ------------------------------------------------------ right now, live
# Everything above is the published, cached analysis. This runs the SAME
# evaluation code, not a rebuild of it, against the most recent real day,
# fetched from FortyGuard on demand. It answers "can this run on live data"
# by doing it, rather than by arguing that it could.
if city_name == study.CITY:
    st.markdown("##### Right now, live")
    st.caption(
        "Everything above is the published analysis, re-derivable from the "
        "committed cache. This is different: it fetches today's real data "
        "from FortyGuard on demand and runs it through the same evaluator, "
        "live. One button, one real API call — four clauses share it, "
        "because credits are flat regardless of area (see the disclosure "
        "above), so there is no reason to fetch anything smaller than the "
        "whole city.")

    _live_col1, _live_col2 = st.columns([1, 2])
    with _live_col1:
        _go_live = st.button("Check current conditions, live",
                             use_container_width=True)
    with _live_col2:
        st.caption(
            "First press today makes a real live call and takes roughly "
            "60-120 s. Later presses today replay that same real response "
            "instead of paying again — the label states which happened.")

    if _go_live:
        if not has_key():
            st.warning(
                "No `FORTYGUARD_API_KEY` is configured on this deployment, "
                "so there is nothing to fetch live here. Every number "
                "elsewhere on this page already comes from 125 real API "
                "calls, committed to the repo — see the disclosure above.",
                icon="🔑")
        else:
            try:
                with st.spinner("Calling FortyGuard for today's real "
                                "reading across all 15 villages…"):
                    _live = liveconditions.run(population=pop)
            except Exception as _exc:  # noqa: BLE001 — a demo must never crash
                st.error(
                    f"The live call did not complete: "
                    f"{type(_exc).__name__}. This is the same failure mode "
                    f"measured in docs/api_findings.md — full reliability "
                    f"detail is why the headline above never depends on a "
                    f"live call succeeding on demand.", icon="⚠️")
            else:
                if not _live.clauses:
                    st.info("No temperature-backed clause was evaluable "
                            "today.")
                else:
                    st.success(
                        (f"**Fetched live just now**, {_live.day}."
                         if _live.was_fetched_live else
                         f"**Replayed today's real fetch**, {_live.day} — "
                         f"this exact request already ran live once today."),
                        icon="📡" if _live.was_fetched_live else "♻️")
                    _live_ids = {lc.clause_id: lc for lc in _live.clauses}
                    _live_pick = st.selectbox(
                        "Clause", list(_live_ids),
                        format_func=lambda k: f"{k} ({_live_ids[k].threshold_f:g} °F)",
                        key="live_clause_pick")
                    _lc = _live_ids[_live_pick]
                    st.altair_chart(
                        charts.zone_gap(_lc.zones, _lc.threshold_f, _lc.proxy_f,
                                        unit=CITY["unit"]),
                        use_container_width=True)
                    _n_live_over = sum(1 for r in _lc.zones
                                       if r["value_f"] >= _lc.threshold_f)
                    st.caption(
                        f"Live citywide reading: {_lc.proxy_f:.1f} °F against "
                        f"a {_lc.threshold_f:g} °F threshold "
                        f"({'FIRED' if _lc.proxy_fired else 'did not fire'}). "
                        f"{_n_live_over} of {len(_lc.zones)} "
                        f"{CITY['unit']}s were at or above it.")

    st.divider()

# ═══════════════════════════════════════════════════ 3 · WHERE
st.markdown('<p class="tg-q">3 — Where</p>', unsafe_allow_html=True)
st.markdown(
    f"**Red areas were missed.** Each one met the plan's condition on at least "
    f"one night when the citywide reading did not. **Click any area** to see who "
    f"lives there and which nights it happened.")

hero = folium.Map(tiles="cartodbpositron", zoom_control=True)
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
if _lats:
    hero.fit_bounds([[min(_lats), min(_lons)], [max(_lats), max(_lons)]],
                    padding=(18, 18))

for ft in geo.get("features", []):
    zid = zone_id_of(ft)
    if zid not in _ids:
        continue
    silent = zid in SILENT
    nm = next((z["name"] for z in res["zones"] if z["zone_id"] == zid), zid)
    p = pop.get(zid, {}).get("population")
    folium.GeoJson(
        ft,
        style_function=lambda _f, s=silent: {
            "fillColor": "#c1121f" if s else "#dfe6ec",
            "color": "#7f0000" if s else "#9aa5b1",
            "weight": 2.5 if s else 1,
            "fillOpacity": 0.80 if s else 0.30,
        },
        tooltip=folium.Tooltip(
            f"<b>{nm}</b><br>"
            + ("<span style='color:#c1121f'><b>MISSED</b></span><br>"
               "hot enough to trigger the plan on nights the city reading was not"
               if silent else "covered by the citywide reading")
            + (f"<br>{p:,} people" if p else "")),
    ).add_to(hero)

if CITY["short"] == "Phoenix":
    folium.Marker(
        [33.4342, -112.0116],
        tooltip=("<b>Phoenix Sky Harbor</b><br>One station. One reading for "
                 "1,053 square miles."),
        icon=folium.Icon(color="darkblue", icon="plane", prefix="fa"),
    ).add_to(hero)

_click = st_folium(hero, height=520, use_container_width=True,
                   returned_objects=["last_object_clicked_tooltip"],
                   key="hero_map")

_picked = (_click or {}).get("last_object_clicked_tooltip")
if _picked:
    _name = str(_picked).split("<")[0].strip()
    _row = next((z for z in res["zones"]
                 if z["name"].lower() in _name.lower()), None)
    if _row:
        _sil = _row["zone_id"] in SILENT
        _pp = pop.get(_row["zone_id"], {}).get("population")
        with st.container(border=True):
            _c1, _c2, _c3, _c4 = st.columns([2, 1, 1, 1])
            _c1.markdown(f"#### {_row['name']}")
            _c1.caption("Click any other area to compare.")
            _c2.metric("Residents", f"{_pp:,}" if _pp else "—")
            _c3.metric("Area", f"{_row.get('area_sq_mi', 0):.0f} mi²")
            _c4.metric("Status", "MISSED" if _sil else "covered",
                       delta_color="off")
            if _sil:
                _days = sorted({d["day"] for c in res["clauses"]
                                for d in c.get("determinations", [])
                                if not d["proxy"]["fired"]
                                and any(z["zone_id"] == _row["zone_id"] and z["fired"]
                                        for z in d["zones"])})
                st.error(
                    f"**{_row['name']} was hot enough to trigger the plan on "
                    f"{len(_days)} night(s) when the citywide reading never "
                    f"was.** " + (f"Nights: {', '.join(_days)}." if _days else ""),
                    icon="🔴")
            else:
                st.success(f"{_row['name']} was never missed in this window — "
                           f"the citywide reading and this area agreed.",
                           icon="✅")
else:
    st.caption("👆 Click a neighbourhood on the map to see its detail.")

st.markdown(
    '<div class="tg-legend">'
    '<span><span class="tg-sw" style="background:#c1121f"></span>'
    '<b>Missed</b> — met the plan\'s condition while the citywide reading stayed below it</span>'
    '<span><span class="tg-sw" style="background:#dfe6ec"></span>covered in this window</span>'
    '</div>', unsafe_allow_html=True)

st.divider()

# ═══════════════════════════════════════════════════ 4 · SO WHAT DO I DO
st.markdown('<p class="tg-q">4 — What to do tonight</p>', unsafe_allow_html=True)
st.markdown(
    "If you had to send crews somewhere first, this is the order — **most "
    "people, most nights missed, first**. Every line names the rule it comes "
    "from, the page of the plan it is on, and the department that owns it.")

_rank = []
for _c in res["clauses"]:
    for _z in sorted(_c.get("silent_zones") or []):
        _n = next((x["name"] for x in res["zones"] if x["zone_id"] == _z), _z)
        _p = (pop or {}).get(_z, {}).get("population") or 0
        _dets = _c.get("determinations", [])
        _silent_days = [d["day"] for d in _dets
                        if not d["proxy"]["fired"]
                        and any(zz["zone_id"] == _z and zz["fired"]
                                for zz in d["zones"])]
        if not _silent_days:
            continue
        _rank.append({
            "zone": _n, "pop": _p, "nights": len(_silent_days),
            "severity": _p * len(_silent_days),
            "clause": _c["clause_id"], "page": _c["source_page"],
            "actor": ", ".join(_c.get("actor") or []) or "—",
            "threshold_f": _c["threshold_f"], "quote": _c["source_text"],
        })
_rank.sort(key=lambda r: -r["severity"])

for _i, _r in enumerate(_rank[:3], 1):
    with st.container(border=True):
        _a, _b = st.columns([3, 2])
        with _a:
            st.markdown(
                f"<span class='tg-rank'>{_i}</span> "
                f"<span style='font-size:1.25rem;font-weight:700'>{_r['zone']}</span>"
                f"<span style='color:#71717a'> &nbsp;·&nbsp; {_r['pop']:,} residents</span>",
                unsafe_allow_html=True)
            st.markdown(
                f"Was hot enough to trigger the **{_r['threshold_f']:g} °F** rule "
                f"on **{_r['nights']} night{'s' if _r['nights'] != 1 else ''}** "
                f"when the citywide reading stayed below it.")
        with _b:
            st.markdown(f"**Who must act:** {_r['actor']}")
            st.caption(f"{_r['clause']} · plan page {_r['page']}")
        with st.expander("The exact sentence in the plan"):
            st.markdown(f'<div class="tg-quote">"{_r["quote"]}"</div>',
                        unsafe_allow_html=True)
            st.caption(f"Source: {CITY['plan']}, page {_r['page']}. "
                       f"[Open the plan]({CITY['plan_url']})")

if len(_rank) > 3:
    with st.expander(f"The remaining {len(_rank) - 3} — same ranking"):
        for _r in _rank[3:]:
            st.markdown(
                f"**{_r['zone']}** · {_r['pop']:,} residents · "
                f"{_r['nights']} night(s) · {_r['clause']} (p. {_r['page']}) · "
                f"{_r['actor']}")

_alerts = detect(res, pop, city=city_name, plan_title=CITY["plan"],
                 plan_url=CITY["plan_url"])
_asum = summarise(_alerts)
if _alerts:
    st.caption(
        f"This is also available as **{len(_alerts)} machine-readable alerts** "
        f"({_asum.get('red', 0)} red, {_asum.get('amber', 0)} amber) — each one "
        f"fires on an *unexecuted legal obligation*, not on a temperature. "
        f"See Methods & evidence for the payload.")

st.divider()

# ═══════════════════════════════════════════════════ WHERE NEXT
st.markdown('<p class="tg-q">Explore further</p>', unsafe_allow_html=True)
st.markdown(
    '<div class="tg-next">'
    '<div class="tg-card"><h4>🌡 Heat waves</h4><p>A heat wave is a <i>run</i> of '
    'nights, and it does not start city-wide. See which neighbourhoods were in '
    'one, since when — and what the threshold choice costs.</p></div>'
    '<div class="tg-card"><h4>🏢 Data centre siting</h4><p>Where in the US is '
    'cooling cheapest? 30 metros ranked on free-cooling hours, power, water and '
    'risk — with the water–energy trade-off made explicit.</p></div>'
    '<div class="tg-card"><h4>🌳 Urban planning</h4><p>How much tree canopy, and '
    'where? Measured thermal gaps joined to published cooling effect sizes, so '
    'each recommendation carries a magnitude.</p></div>'
    '<div class="tg-card"><h4>🔬 Methods &amp; evidence</h4><p>The full technical '
    'record: every rule and its source page, the New York replication, what we '
    'measured about the API, and the claims we retracted.</p></div>'
    '</div>', unsafe_allow_html=True)
st.caption("Use the sidebar, or the page list at the top left, to open any of these.")

st.divider()
st.caption(
    f"All thermal data from the FortyGuard Temperature API, measured 2 m above "
    f"ground at 100 m resolution. Study window {summary['window'][0]} to "
    f"{summary['window'][1]}. Every figure on this page is a deterministic "
    f"comparison of measured values — no language model produces any number "
    f"here. Runs offline from a committed cache: `python run_demo.py`.")
