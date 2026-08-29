"""Shared interface furniture: one stylesheet, one masthead, one set of loaders.

Every page imports from here so the styling cannot drift between pages, and so a
change to the palette or the masthead happens once rather than five times.
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

REPO = Path(__file__).resolve().parent.parent

CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600&display=swap');

  html, body, [class*="css"] { font-family:'Inter',-apple-system,sans-serif; }
  .block-container { padding-top:2rem; padding-bottom:4rem; max-width:1440px; }
  #MainMenu, footer, header { visibility:hidden; }

  h1 { font-weight:900 !important; letter-spacing:-0.035em; }
  h2 { font-weight:800 !important; letter-spacing:-0.025em; }
  h3 { font-weight:700 !important; letter-spacing:-0.02em; }

  /* ---------- masthead ---------- */
  .tg-mast { display:flex; align-items:center; gap:.7rem; flex-wrap:wrap;
    padding-bottom:.7rem; border-bottom:1px solid #e4e4e7; margin-bottom:1.5rem; }
  .tg-brand { font-size:1.45rem; font-weight:900; letter-spacing:-.04em; }
  .tg-tag { color:#71717a; font-size:.98rem; }
  .tg-pill { font-size:.68rem; font-weight:700; letter-spacing:.09em;
    text-transform:uppercase; padding:.28rem .7rem; border-radius:999px;
    background:rgba(255,255,255,.95); color:#27272a; white-space:nowrap;
    border:1px solid rgba(255,255,255,.6); }
  .tg-pill.ghost { background:rgba(0,0,0,.22); color:#fff;
    border:1px solid rgba(255,255,255,.35); }
  .tg-pill.warn { background:#fef3c7; color:#92400e; border:1px solid #fde68a; }

  /* ---------- hero ---------- */
  .tg-hero { text-align:center; padding:2.6rem 1.2rem 2rem; position:relative;
    overflow:hidden;
    background: radial-gradient(ellipse 70% 120% at 50% -10%, #ffe4e1 0%, transparent 65%),
                linear-gradient(180deg,#fffdfd,#fff);
    border:1px solid #f3dcda; border-radius:20px; margin-bottom:1rem;
    box-shadow:0 2px 4px rgba(178,24,43,.05), 0 18px 40px -24px rgba(178,24,43,.35); }
  .tg-hero::before { content:""; position:absolute; inset:0 0 auto 0; height:4px;
    background:linear-gradient(90deg,#7f1220,#b2182b,#e0644b,#f0a58e); }
  .tg-num { font-size:clamp(2.8rem,8.5vw,5.6rem); line-height:.95; font-weight:900;
    letter-spacing:-.05em; color:#b2182b; font-variant-numeric:tabular-nums; }
  .tg-sub { font-size:clamp(.95rem,1.5vw,1.12rem); color:#3f3f46;
    margin-top:.85rem; line-height:1.65; }
  .tg-sub b { color:#18181b; }
  .tg-kicker { font-size:.7rem; font-weight:800; letter-spacing:.17em;
    text-transform:uppercase; color:#b2182b; margin-bottom:.8rem; }

  /* ---------- cards & metrics ---------- */
  /* Depth is carried by a layered shadow and a top hairline, not by a heavy
     border. A single flat 1px box on a white page reads as a wireframe; two
     soft shadows at different radii read as a surface sitting above the page. */
  [data-testid="stMetric"] { background:#fff; border:1px solid #ececef;
    border-radius:14px; padding:1.05rem 1.15rem; position:relative;
    overflow:hidden;
    box-shadow:0 1px 2px rgba(24,24,27,.05), 0 6px 16px -8px rgba(24,24,27,.10); }
  [data-testid="stMetric"]::before { content:""; position:absolute; inset:0 0 auto 0;
    height:3px; background:linear-gradient(90deg,#b2182b,#e0644b); opacity:.85; }
  [data-testid="stMetricValue"] { font-size:clamp(1.15rem,1.8vw,1.85rem) !important;
    font-weight:800; letter-spacing:-.025em; font-variant-numeric:tabular-nums;
    white-space:nowrap; color:#18181b; }
  [data-testid="stMetricLabel"] { font-size:.7rem !important; font-weight:700;
    letter-spacing:.08em; text-transform:uppercase; color:#8a8a93; }
  [data-testid="stMetricDelta"] { font-size:.78rem !important; color:#71717a; }

  .tg-grid { display:grid; gap:1rem;
    grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); margin:.4rem 0 1.2rem; }
  .tg-card { background:#fff; border:1px solid #ececef; border-radius:14px;
    padding:1.1rem 1.2rem;
    box-shadow:0 1px 2px rgba(24,24,27,.05), 0 6px 16px -8px rgba(24,24,27,.10); }
  .tg-card h4 { margin:0 0 .4rem; font-size:1rem; font-weight:700;
    letter-spacing:-.01em; color:#18181b; }
  .tg-card p { margin:0; font-size:.89rem; color:#52525b; line-height:1.62; }
  .tg-step-n { font-size:.66rem; font-weight:800; letter-spacing:.1em; color:#fff;
    background:#b2182b; border-radius:6px; padding:.2rem .42rem; margin-right:.5rem; }

  /* Charts get the same surface treatment as cards, so a figure reads as an
     object on the page rather than ink floating on the background. */
  [data-testid="stVegaLiteChart"], .stVegaLiteChart {
    background:#fff; border:1px solid #ececef; border-radius:14px;
    padding:1rem .85rem .4rem;
    box-shadow:0 1px 2px rgba(24,24,27,.05), 0 6px 16px -8px rgba(24,24,27,.10); }

  /* Vertical rhythm: sections need air between them or everything reads as one
     undifferentiated column. */
  hr, [data-testid="stDivider"] { margin:2.1rem 0 1.7rem !important; }

  /* ---------- the navbar ---------- */
  /* One coloured bar carrying the brand and the page links. Previously this was
     a white masthead above a row of white boxes on a white page -- three
     surfaces of the same colour, so it read as nothing at all. */
  .tg-mast { display:flex; align-items:center; gap:.7rem; flex-wrap:wrap;
    padding:.9rem 1.25rem .75rem; margin:0;
    background:linear-gradient(100deg, var(--tg-nav-a) 0%, var(--tg-nav-b) 100%);
    border-radius:16px 16px 0 0; }
  .tg-brand { font-size:1.4rem; font-weight:900; letter-spacing:-.04em;
    color:#fff; }
  .tg-tag { color:rgba(255,255,255,.78); font-size:.97rem; }

  .tg-navwrap { background:linear-gradient(100deg, var(--tg-nav-a) 0%, var(--tg-nav-b) 100%);
    border-radius:0 0 16px 16px; padding:0 .75rem .7rem; margin-bottom:1.7rem;
    box-shadow:0 10px 30px -18px var(--tg-nav-a); }

  [data-testid="stHorizontalBlock"]:has([data-testid="stPageLink"]) {
    gap:.35rem !important; }
  [data-testid="stPageLink"] a { border:1px solid rgba(255,255,255,.30);
    border-radius:9px; padding:.5rem .55rem; background:rgba(0,0,0,.20);
    justify-content:center; transition:all .15s; }
  [data-testid="stPageLink"] a p, [data-testid="stPageLink"] a span {
    color:#fff !important; font-weight:700 !important;
    font-size:.82rem !important; text-shadow:0 1px 2px rgba(0,0,0,.35); }
  [data-testid="stPageLink"] a:hover { background:rgba(0,0,0,.34);
    border-color:rgba(255,255,255,.6); }

  /* ---------- pipeline ---------- */
  .tg-flow { display:flex; gap:.4rem; flex-wrap:wrap; justify-content:center;
    padding:.9rem; background:#fafafa; border:1px solid #e4e4e7;
    border-radius:13px; margin-bottom:1.3rem; }
  .tg-node { background:#fff; border:1px solid #d4d4d8; border-radius:9px;
    padding:.5rem .8rem; font-size:.82rem; font-weight:600; text-align:center; }
  .tg-node small { display:block; font-weight:400; font-size:.69rem;
    color:#71717a; margin-top:.12rem; }
  .tg-node-api { border-color:#b2182b; background:#fff5f5; color:#b2182b; }
  .tg-node-out { background:#18181b; color:#fff; border-color:#18181b; }
  .tg-arr { align-self:center; color:#a1a1aa; font-weight:700; }

  /* ---------- misc ---------- */
  .tg-legend { display:flex; gap:1.3rem; flex-wrap:wrap; align-items:center;
    font-size:.85rem; color:#52525b; padding:.75rem 1rem; background:#fafafa;
    border:1px solid #e4e4e7; border-radius:10px; margin-top:.6rem; }
  .tg-sw { display:inline-block; width:14px; height:14px; border-radius:4px;
    margin-right:.42rem; vertical-align:-2px; }
  .tg-quote { border-left:3px solid #b2182b; padding:.85rem 1.15rem;
    background:#fafafa; border-radius:0 10px 10px 0; font-style:italic;
    color:#27272a; line-height:1.7; }
  .tg-rank { display:inline-block; background:#b2182b; color:#fff; font-weight:800;
    font-size:.82rem; border-radius:6px; padding:.08rem .48rem; margin-right:.5rem; }

  .stTabs [data-baseweb="tab-list"] { gap:.3rem; border-bottom:1px solid #e4e4e7; }
  .stTabs [data-baseweb="tab"] { height:42px; padding:0 1rem; font-weight:600;
    font-size:.9rem; border-radius:8px 8px 0 0; }
  .stTabs [aria-selected="true"] { background:#fff5f5; color:#b2182b; }

  section[data-testid="stSidebar"] { background:#fafafa;
    border-right:1px solid #e4e4e7; }
  code, .stCode { font-family:'JetBrains Mono',monospace !important; }
  iframe { border-radius:13px; }

  /* ---------- page background ---------- */
  /* Applied as background LAYERS on the app container, not as an injected
     element. An earlier version put a fixed, scrimmed div in the DOM and raised
     the content above it with z-index; Streamlit's own wrappers create their
     own stacking contexts, so the white scrim ended up over the page and blanked
     it. Background layers cannot do that -- content is always painted on top of
     its own container's background, with no stacking to get wrong. */

  /* ---------- responsive ---------- */
  @media (max-width: 900px) {
    .block-container { padding-left:1rem; padding-right:1rem; }
    .tg-mast { gap:.45rem; }
    .tg-brand { font-size:1.2rem; }
    .tg-tag { display:none; }
    .tg-hero { padding:1.6rem .8rem 1.2rem; border-radius:14px; }
    .tg-flow { padding:.65rem; }
    .tg-arr { display:none; }
    .tg-node { flex:1 1 44%; }
  }
  @media (max-width: 640px) {
    .tg-pill { font-size:.6rem; padding:.2rem .5rem; }
    .tg-legend { gap:.7rem; font-size:.79rem; }
  }
</style>
"""


def style() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def masthead(page: str, pills: list[str] | None = None,
             warn: str | None = None) -> None:
    chips = "".join(f'<span class="tg-pill ghost">{p}</span>' for p in (pills or []))
    if warn:
        chips += f'<span class="tg-pill warn">{warn}</span>'
    st.markdown(
        f'<div class="tg-mast"><span class="tg-brand">TRIGGER</span>'
        f'<span class="tg-tag">{page}</span>'
        f'<span style="flex:1"></span>{chips}</div>',
        unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load(path_str: str) -> dict:
    f = Path(path_str)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def results(name: str) -> dict:
    return load(str(REPO / "data" / "results" / name))


def missing(what: str, how: str) -> None:
    st.info(f"**{what}** has not been generated in this checkout.\n\n"
            f"Run `{how}` to produce it. Every other page works without it.",
            icon="ℹ️")


# --------------------------------------------------------------------- cities
# The pipeline is city-agnostic, so the interface is too. This lives here rather
# than in any one page so every page offers the same cities from one definition.

CITIES = {
    "Phoenix, Arizona": {
        "results": REPO / "data" / "results" / "divergence.json",
        "zones":   REPO / "data" / "zones" / "phoenix_villages_raw.geojson",
        "pop":     REPO / "data" / "zones" / "phoenix_villages_population.json",
        "unit": "urban village", "short": "Phoenix",
        "trigger": "90 °F overnight low",
        "plan_url": "https://www.phoenix.gov/content/dam/phoenix/heatsite/documents/2026%20Heat%20Response%20Plan.pdf",
        "plan": "City of Phoenix 2026 Heat Response Plan",
        "centre": [33.55, -112.09], "tiles": "272,917", "aoi": "1,053",
        "note": "Arid. Heat index sits BELOW air temperature here, so Phoenix "
                "triggers on dry-bulb — the right choice for its climate.",
    },
    "New York City": {
        "results": REPO / "data" / "results" / "nyc" / "divergence_2025-06-22_2025-06-28.json",
        "zones":   REPO / "data" / "zones" / "nyc_cd.geojson",
        "pop":     REPO / "data" / "zones" / "nyc_cd_population.json",
        "unit": "community district", "short": "New York",
        "trigger": "100 °F heat index",
        "plan_url": "https://home3.nyc.gov/site/em/ready/extreme-heat.page",
        "plan": "NYC Heat Emergency Plan (NYCEM / DOHMH)",
        "centre": [40.75, -73.95], "tiles": "71,988", "aoi": "346",
        "note": "Humid. Heat index sits ABOVE air temperature here, so New York "
                "triggers on heat index — also the right choice for its climate.",
    },
}


def city_picker(key: str = "city") -> tuple[str, dict]:
    """Sidebar city selector, identical on every page that offers one."""
    with st.sidebar:
        st.markdown("### City")
        name = st.radio("City", list(CITIES), label_visibility="collapsed",
                        key=key)
        st.caption(CITIES[name]["note"])
    return name, CITIES[name]




#: The pages, in reading order. One list, so nav and any page index agree.
PAGES = [
    ("app.py", "Who does the plan miss?", "🏠"),
    ("pages/1_Heat_Waves.py", "Heat waves", "🌡"),
    ("pages/2_Data_Centre_Siting.py", "Data centre siting", "🏢"),
    ("pages/3_Urban_Planning.py", "Urban planning", "🌳"),
    ("pages/4_Methods_and_Evidence.py", "Methods & evidence", "🔬"),
]


def topnav() -> None:
    """Page navigation IN THE PAGE, not only in the sidebar.

    Streamlit puts multipage navigation in the sidebar, and the sidebar can be
    collapsed -- at which point a reader who has closed it has no way to reach
    another page short of knowing about the small reopen arrow. Navigation that
    can be hidden by a control unrelated to navigation is not navigation, so it
    also lives here, always visible, directly under the masthead.

    st.page_link needs real page context and raises under the test harness when
    a page file is executed on its own, so a failure falls back to nothing
    rather than taking the page down with it.
    """
    st.markdown('<div class="tg-navwrap">', unsafe_allow_html=True)
    try:
        cols = st.columns(len(PAGES))
        for col, (path, label, icon) in zip(cols, PAGES):
            with col:
                st.page_link(path, label=label, icon=icon,
                             use_container_width=True)
    except Exception:  # noqa: BLE001 - navigation is chrome, never fatal
        pass
    st.markdown('</div>', unsafe_allow_html=True)


def guidance() -> dict:
    return load(str(REPO / "data" / "heat_guidance.json"))


def tier_for(overnight_low_f: float | None, daily_high_f: float | None = None) -> dict:
    """The danger tier a measurement falls in.

    Overnight low governs where the two disagree, because the epidemiological
    literature ties mortality to the failure to cool at night rather than to the
    daytime peak -- the reason that rule exists is recorded in the data file.
    """
    levels = guidance().get("levels", [])
    if not levels:
        return {}
    chosen = levels[0]
    for lv in levels:
        lo_ok = (overnight_low_f is not None
                 and lv["overnight_low_f"][0] <= overnight_low_f < lv["overnight_low_f"][1])
        hi_ok = (overnight_low_f is None and daily_high_f is not None
                 and lv["daily_high_f"][0] <= daily_high_f < lv["daily_high_f"][1])
        if lo_ok or hi_ok:
            chosen = lv
    return chosen


# --------------------------------------------------------------- page themes
# Each page carries its own accent so a reader always knows where they are
# without reading the title. This is CHROME ONLY. Chart colour comes from
# src/charts.py, where the palette is validated against CVD and contrast floors,
# and a page tint must never leak into a data encoding -- otherwise the same hue
# would mean "you are on the siting page" in one place and a measured value in
# another, which is the fastest way to make a chart lie.
PAGE_THEME = {
    "home":     {"accent": "#b2182b", "nav_a": "#8c1220", "nav_b": "#c9455a",
                 "glow": "#ffe6e3", "file": "app", "hue": "hue-rotate(0deg)"},
    "heat":     {"accent": "#c2410c", "nav_a": "#9a3412", "nav_b": "#ea7317",
                 "glow": "#ffeadf", "file": "1_Heat_Waves", "hue": "hue-rotate(-12deg)"},
    "siting":   {"accent": "#1d6a96", "nav_a": "#14506f", "nav_b": "#3d8cb8",
                 "glow": "#e3f1f9", "file": "2_Data_Centre_Siting", "hue": "hue-rotate(175deg) saturate(.7)"},
    "planning": {"accent": "#2d6a4f", "nav_a": "#1f4f3a", "nav_b": "#4f9b73",
                 "glow": "#e4f2ea", "file": "3_Urban_Planning", "hue": "hue-rotate(105deg) saturate(.65)"},
    "methods":  {"accent": "#4a4458", "nav_a": "#39344a", "nav_b": "#6d6484",
                 "glow": "#eeedf3", "file": "4_Methods_and_Evidence", "hue": "hue-rotate(225deg) saturate(.45)"},
}


def theme(page: str) -> None:
    """Tint this page's chrome and lay a moving background behind it.

    Two jobs. First, the navbar and accents take the page's own colour so a
    reader knows where they are without reading the title. Second, three
    slow-drifting blurred shapes sit BEHIND the content -- the page was flat
    white, and flat white against flat white is what made it read as
    unfinished.

    The background is deliberately weak. Every card, chart and table above it
    keeps its own opaque surface, so nothing decorative ever lands underneath
    text. Decoration that costs legibility is a net loss, especially in front of
    engineer judges.
    """
    t = PAGE_THEME.get(page, PAGE_THEME["home"])
    css = """
<style>
  :root { --tg-accent:%(a)s; --tg-glow:%(g)s;
          --tg-nav-a:%(na)s; --tg-nav-b:%(nb)s;
          --tg-hue:%(hue)s; }
  /* Two layers: a white scrim first, the measured field beneath it. The scrim
     is what guarantees text contrast, so it is part of the background rather
     than a separate element that could ever land on the wrong side. */
  .stApp {
    background-image:
      linear-gradient(180deg, rgba(252,252,253,.955) 0%%,
                              rgba(252,252,253,.930) 40%%,
                              rgba(252,252,253,.965) 100%%),
      url(app/static/backdrop.jpg);
    background-size: cover, cover;
    background-position: center, center;
    background-attachment: fixed, fixed;
    background-repeat: no-repeat, no-repeat; }
  .tg-q, .tg-kicker { color:%(a)s !important; }
  .tg-step-n, .tg-rank { background:%(a)s !important; }
  [data-testid="stMetric"]::before {
      background:linear-gradient(90deg,%(na)s,%(nb)s) !important; }
  .tg-quote { border-left-color:%(a)s !important; }
  .tg-vs-mid { color:%(a)s !important; }
  .stTabs [aria-selected="true"] { color:%(a)s !important; background:%(g)s !important; }
  .tg-next .tg-card:hover { border-color:%(a)s !important; }
  /* The headline sits on the satellite image itself: a dark panel where the
     rest of the page is light, so the eye lands on the number first. The
     gradient over the photograph is what guarantees contrast for the white
     type -- part of the background, so it can never end up on the wrong side
     of the text it is protecting. */
  .tg-hero { background:
      linear-gradient(180deg, rgba(9,12,26,.86) 0%%, rgba(9,12,26,.78) 45%%,
                              rgba(9,12,26,.90) 100%%),
      url(app/static/backdrop.jpg) center/cover !important;
      border:1px solid rgba(255,255,255,.10) !important;
      box-shadow:0 20px 50px -28px rgba(9,12,26,.75) !important; }
  .tg-hero .tg-kicker { color:%(nb)s !important; }
  .tg-hero .tg-sub { color:rgba(255,255,255,.86) !important; }
  .tg-hero .tg-sub b { color:#fff !important; }
  .tg-hero::before { background:linear-gradient(90deg,%(na)s,%(nb)s) !important; }
  .tg-num { color:#fff !important;
      text-shadow:0 2px 26px %(a)s, 0 1px 3px rgba(0,0,0,.5) !important; }
  /* the page you are on, filled solid on the bar */
  a[href$="/%(f)s"] { background:#fff !important;
      border-color:#fff !important; }
  a[href$="/%(f)s"] p, a[href$="/%(f)s"] span { color:%(na)s !important; }
</style>
""" % {"a": t["accent"], "g": t["glow"], "na": t["nav_a"], "nb": t["nav_b"],
       "f": t["file"], "hue": t["hue"]}
    st.markdown(css, unsafe_allow_html=True)
