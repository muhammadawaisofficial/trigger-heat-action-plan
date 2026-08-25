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
    text-transform:uppercase; padding:.26rem .66rem; border-radius:999px;
    background:#18181b; color:#fff; white-space:nowrap; }
  .tg-pill.ghost { background:#f4f4f5; color:#52525b; border:1px solid #e4e4e7; }
  .tg-pill.warn { background:#fef3c7; color:#92400e; border:1px solid #fde68a; }

  /* ---------- hero ---------- */
  .tg-hero { text-align:center; padding:2.3rem 1rem 1.7rem;
    background: radial-gradient(ellipse 80% 100% at 50% 0%, #fff1f0 0%, transparent 70%),
                linear-gradient(180deg,#fafafa,#fff);
    border:1px solid #f0d9d7; border-radius:18px; margin-bottom:.9rem; }
  .tg-num { font-size:clamp(2.8rem,8.5vw,5.6rem); line-height:.95; font-weight:900;
    letter-spacing:-.05em; color:#b2182b; font-variant-numeric:tabular-nums; }
  .tg-sub { font-size:clamp(.95rem,1.5vw,1.12rem); color:#3f3f46;
    margin-top:.85rem; line-height:1.65; }
  .tg-sub b { color:#18181b; }
  .tg-kicker { font-size:.7rem; font-weight:800; letter-spacing:.17em;
    text-transform:uppercase; color:#b2182b; margin-bottom:.8rem; }

  /* ---------- cards ---------- */
  [data-testid="stMetric"] { background:#fff; border:1px solid #e4e4e7;
    border-radius:13px; padding:.95rem 1.05rem; box-shadow:0 1px 2px rgba(0,0,0,.04); }
  [data-testid="stMetricValue"] { font-size:clamp(1.1rem,1.7vw,1.75rem) !important;
    font-weight:800; letter-spacing:-.02em; font-variant-numeric:tabular-nums;
    white-space:nowrap; }
  [data-testid="stMetricLabel"] { font-size:.72rem !important; font-weight:700;
    letter-spacing:.05em; text-transform:uppercase; color:#71717a; }

  .tg-grid { display:grid; gap:1rem;
    grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); margin:.4rem 0 1.2rem; }
  .tg-card { background:#fff; border:1px solid #e4e4e7; border-radius:13px;
    padding:1.05rem 1.15rem; }
  .tg-card h4 { margin:0 0 .35rem; font-size:1rem; font-weight:700;
    letter-spacing:-.01em; }
  .tg-card p { margin:0; font-size:.89rem; color:#52525b; line-height:1.6; }
  .tg-step-n { font-size:.66rem; font-weight:800; letter-spacing:.1em; color:#fff;
    background:#b2182b; border-radius:6px; padding:.2rem .42rem; margin-right:.5rem; }

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
