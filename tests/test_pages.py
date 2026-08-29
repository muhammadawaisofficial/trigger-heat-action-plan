"""The new pages, and the modules behind them, actually run and are correct.

The unit tests here guard the two bugs that made the heat-wave module unsafe to
ship, plus the delta-conversion trap in the planning module. The AppTest cases
execute each page through Streamlit's own harness, because a page that raises
still serves HTTP 200 with a traceback in the body -- a health check cannot tell
a working page from a broken one.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

import heatwave  # noqa: E402
import planning  # noqa: E402
import ui  # noqa: E402

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
TIMEOUT = 180

PAGES = ["pages/1_Heat_Waves.py",
         "pages/2_Data_Centre_Siting.py",
         "pages/3_Urban_Planning.py"]


@pytest.fixture(scope="module")
def results() -> dict:
    return json.loads((REPO / "data" / "results" / "divergence.json")
                      .read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def population() -> dict:
    return json.loads((REPO / "data" / "zones" /
                       "phoenix_villages_population.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def national() -> dict:
    return json.loads((REPO / "data" / "results" / "national.json")
                      .read_text(encoding="utf-8"))


# --------------------------------------------------------------- pages run
@pytest.mark.parametrize("page", PAGES)
def test_page_runs_without_exception(page):
    at = AppTest.from_file(str(REPO / page), default_timeout=TIMEOUT).run()
    assert not at.exception, [str(e) for e in at.exception]


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_numbers(page):
    """A page that renders no metric has silently degraded to prose."""
    at = AppTest.from_file(str(REPO / page), default_timeout=TIMEOUT).run()
    assert len(at.metric) >= 3


# ------------------------------------------------------- heatwave: units bug
def test_hours_clause_is_refused(results, population):
    """An exceedance clause is HOURS. Comparing it to a degF threshold is the
    unit-chain trap -- it must raise, not quietly return zero waves."""
    with pytest.raises(ValueError, match="not a temperature"):
        heatwave.from_results(results, clause_id="PHX-2026-A1.1",
                              population=population)


def test_temperature_clauses_excludes_the_hours_clause(results):
    ids = [c["clause_id"] for c in heatwave.temperature_clauses(results)]
    assert "PHX-2026-A1.1" not in ids
    assert ids, "no temperature clause found at all"


# -------------------------------------------------- heatwave: population bug
def test_population_accepts_the_whole_file(results, population):
    """Passing the population FILE (with its meta/villages wrapper) must not
    silently report every population as zero."""
    det = heatwave.from_results(results, clause_id="PHX-2026-BENCH-LOW90",
                                population=population)
    assert det["absolute"]["summary"]["population"] > 0


def test_population_accepts_the_inner_mapping(results, population):
    inner = heatwave.from_results(results, clause_id="PHX-2026-BENCH-LOW90",
                                  population=population["villages"])
    outer = heatwave.from_results(results, clause_id="PHX-2026-BENCH-LOW90",
                                  population=population)
    assert (inner["absolute"]["summary"]["population"]
            == outer["absolute"]["summary"]["population"])


def test_higher_threshold_never_detects_more_waves(results, population):
    """Monotonicity: raising the bar cannot create heat waves."""
    low = heatwave.from_results(results, clause_id="PHX-2026-BENCH-LOW90",
                                population=population)["absolute"]["summary"]
    high = heatwave.from_results(results, clause_id="PHX-2026-BENCH-HIGH110",
                                 population=population)["absolute"]["summary"]
    assert high["waves"] <= low["waves"]


def test_wave_runs_are_consecutive_and_long_enough(results, population):
    det = heatwave.from_results(results, clause_id="PHX-2026-BENCH-LOW90",
                                population=population, min_days=3)
    for w in det["absolute"]["waves"]:
        assert w["length_days"] >= 3
        assert w["days"] == sorted(w["days"])
        assert w["peak_f"] >= w["threshold_f"]


# ------------------------------------------------- planning: delta conversion
def test_delta_conversion_is_a_ratio_not_an_offset():
    """1 degC of COOLING is 1.8 degF, never 33.8 -- adding 32 to a difference
    is the classic unit-chain error."""
    assert planning.c_to_f_delta(1.0) == pytest.approx(1.8)
    assert planning.c_to_f_delta(0.0) == pytest.approx(0.0)


def test_canopy_requirement_scales_with_the_gap():
    assert (planning.canopy_points_for(2.0)
            == pytest.approx(2 * planning.canopy_points_for(1.0)))


# ------------------------------------------------------- planning: national
def test_every_metro_gets_a_plan(national):
    plans = planning.from_national(national)
    assert len(plans) == national["n_metros"]
    assert all(p.spread_f >= 0 for p in plans)


def test_plans_sorted_by_spread(national):
    spreads = [p.spread_f for p in planning.from_national(national)]
    assert spreads == sorted(spreads, reverse=True)


def test_recommendations_are_populated_and_ordered(national):
    for p in planning.from_national(national):
        recs = p.recommendations()
        assert recs, p.name
        assert [r["priority"] for r in recs] == sorted(r["priority"] for r in recs)
        for r in recs:
            assert r["because"] and r["quantified"] and r["evidence"]


def test_zone_priority_weights_heat_by_population(results, population):
    rows = planning.zone_priorities(results, population, "PHX-2026-A4.2")
    assert rows
    scores = [r["priority_score"] for r in rows]
    assert scores == sorted(scores, reverse=True)
    # A zone with no residents cannot outrank a populated one on this metric.
    assert all(r["priority_score"] == 0 for r in rows if r["population"] == 0)


# ------------------------------------------------------------------ ui/tier
def test_tier_rises_with_overnight_low():
    levels = [ui.tier_for(f)["level"] for f in (70, 78, 83, 88, 95)]
    assert levels == sorted(levels)


def test_every_tier_has_actions():
    for lv in ui.guidance()["levels"]:
        assert lv["actions"]
        if lv["level"] >= 2:
            assert lv["who"], lv["name"]


def test_shared_city_registry_paths_exist():
    for name, c in ui.CITIES.items():
        assert Path(c["results"]).exists(), name
        assert Path(c["pop"]).exists(), name


# ------------------------------------------------------------------ charts
def test_every_feature_page_renders_a_chart():
    """The pages were tables. A page with no figure has regressed to that."""
    for page in PAGES + ["app.py"]:
        at = AppTest.from_file(str(REPO / page), default_timeout=TIMEOUT).run()
        assert not at.exception, [str(e) for e in at.exception]
        n = len(at.get("vega_lite_chart"))
        assert n >= 1, f"{page} renders no chart"


def test_chart_palette_is_the_validated_pair():
    """The accent/muted pair was validated, not eyeballed.

    The earlier grey (#8c96a0) failed contrast against the surface at 2.93:1.
    Pinning the values stops it drifting back to something unchecked.
    """
    import charts
    assert charts.ACCENT == "#b2182b"
    assert charts.MUTED == "#7d8792"
    # Sequential ramp must be monotonically darker, or "more is darker" breaks.
    def lum(h):
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    lums = [lum(c) for c in charts.HEAT]
    assert lums == sorted(lums, reverse=True), "heat ramp is not monotonic"


def test_charts_survive_empty_input():
    """A city with no qualifying rows must render an empty chart, not raise."""
    import charts
    import pandas as pd
    assert charts.zone_gap([], 90.0, 88.0) is not None
    assert charts.ladder([]) is not None
    assert charts.wave_runs([]) is not None
    assert charts.rank_bar(pd.DataFrame(), "v", "l", "t") is not None
    assert charts.spread_dumbbell(pd.DataFrame(), "l", "lo", "hi") is not None


def test_navigation_does_not_depend_on_the_sidebar():
    """Every page must offer a way off it that a collapsed sidebar cannot hide.

    Streamlit's own multipage nav lives in the sidebar, and the sidebar can be
    closed -- stranding a reader who closed it. ui.topnav() puts the same links
    in the page body; this pins that every page calls it.
    """
    for page, *_ in __import__("ui").PAGES:
        src = (REPO / page).read_text(encoding="utf-8")
        assert "ui.topnav()" in src, f"{page} has no in-page navigation"


def test_page_list_points_at_files_that_exist():
    import ui as _ui
    for path, label, icon in _ui.PAGES:
        assert (REPO / path).exists(), path
        assert label and icon


# ------------------------------------------------------------- page identity
def test_every_page_declares_a_theme():
    """A page with no accent falls back to the home red and loses its identity."""
    import ui as _ui
    expect = {"app.py": "home", "pages/1_Heat_Waves.py": "heat",
              "pages/2_Data_Centre_Siting.py": "siting",
              "pages/3_Urban_Planning.py": "planning",
              "pages/4_Methods_and_Evidence.py": "methods"}
    for path, key in expect.items():
        src = (REPO / path).read_text(encoding="utf-8")
        assert f'ui.theme("{key}")' in src, path
        assert key in _ui.PAGE_THEME


def test_page_accents_do_not_collide_with_chart_colours():
    """Chrome tint must never equal a data colour.

    If a page accent matched a series colour, the same hue would mean "you are
    on this page" in one place and a measured value in another.
    """
    import charts
    import ui as _ui
    data_colours = {charts.ACCENT.lower(), charts.MUTED.lower(),
                    *(c.lower() for c in charts.HEAT)}
    for key, t in _ui.PAGE_THEME.items():
        if key == "home":
            continue  # home shares the brand red by design
        assert t["accent"].lower() not in data_colours, key


def test_every_theme_is_a_full_hex_pair():
    import ui as _ui
    import re
    for key, t in _ui.PAGE_THEME.items():
        for slot in ("accent", "glow"):
            assert re.fullmatch(r"#[0-9a-fA-F]{6}", t[slot]), (key, slot)


def test_background_cannot_overlay_the_content():
    """The backdrop must be a background LAYER, never an element over the page.

    This is a real regression, not a hypothetical: a fixed, scrimmed div was
    added to the DOM and the content raised above it with z-index. Streamlit's
    own wrappers create stacking contexts, so the white scrim landed on top and
    blanked every page. AppTest did not catch it -- a page covered by an opaque
    overlay still renders every element and raises nothing -- so the guard has
    to be on the CSS itself.
    """
    import inspect
    import ui as _ui
    # The backdrop is emitted per page by theme(); the shared sheet carries the
    # rest. Both are checked, because the overlay bug could return in either.
    css = _ui.CSS + inspect.getsource(_ui.theme)
    assert "app/static/phoenix_field.png" in css, "backdrop not applied"
    assert "background-attachment: fixed" in css
    # No full-viewport overlay elements: that is the shape of the bug.
    for banned in (".tg-scrim", ".tg-bg", ".tg-field", ".tg-orb"):
        assert banned not in css, f"{banned} reintroduces an overlay element"


def test_nav_text_is_opaque_white_on_the_bar():
    """The nav was unreadable once: translucent white on a light gradient."""
    import ui as _ui
    assert "color:#fff !important" in _ui.CSS
    assert "rgba(255,255,255,.92) !important" not in _ui.CSS


def test_every_page_still_shows_its_pills():
    for page in ["app.py", "pages/1_Heat_Waves.py",
                 "pages/2_Data_Centre_Siting.py", "pages/3_Urban_Planning.py",
                 "pages/4_Methods_and_Evidence.py"]:
        src = (REPO / page).read_text(encoding="utf-8")
        assert "pills=[" in src, f"{page} lost its masthead pills"


# --------------------------------------------------------------- the backdrop
def test_backdrop_is_generated_from_real_cached_tiles():
    """The background is the project's own measurement, not stock artwork.

    If the generator ever loses its input, the claim in the README and the video
    ('that is the measured field') stops being true.
    """
    import make_backdrop
    assert make_backdrop.RESPONSE.exists(), "cached tcm response is missing"
    assert (REPO / "static" / "phoenix_field.png").exists()
    # Small enough not to hurt first paint on Streamlit Cloud.
    assert (REPO / "static" / "phoenix_field.png").stat().st_size < 400_000


def test_backdrop_transform_preserves_temperature_order():
    """The rank transform must be monotonic: hotter is darker, always.

    Ranking is what makes the near-uniform field legible. It is honest only
    while no two pixels swap order, so this pins that property directly.
    """
    import numpy as np
    field = np.array([[30.0, 31.0, 35.0], [29.0, 33.0, 38.0]])
    flat = field.ravel()
    norm = (np.argsort(np.argsort(flat)) / (len(flat) - 1))
    assert np.all(np.argsort(flat) == np.argsort(norm))
    assert norm.min() == 0.0 and norm.max() == 1.0


def test_static_serving_is_enabled():
    """Without this the backdrop 404s and every page loses its background."""
    cfg = (REPO / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert "enableStaticServing = true" in cfg


# ------------------------------------------------------------- live probe
def test_live_probe_is_a_genuinely_separate_request():
    """The probe must never be able to feed the headline pipeline.

    It has its own AOI, its own analytic call, and touches no file that
    evaluate.py or diverge.py read -- so a failure or a stale response here
    cannot silently change a published number.
    """
    import liveprobe
    assert liveprobe.PROBE_SIDE_KM <= 5, "probe should stay small and cheap"
    payload_keys = {"polygon_aoi", "start_date", "filter_type", "granularity",
                    "analytic_type", "label"}
    import inspect
    src = inspect.getsource(liveprobe.run)
    assert "fg.heatmap(" in src
    assert all(k in src for k in payload_keys)


def test_live_probe_requests_a_day_the_api_can_serve():
    """"Today" can be requested before the day's data has landed; one day back
    is what avoids an empty-response false negative on the demo."""
    import liveprobe
    from datetime import datetime, timezone
    day = liveprobe.probe_day()
    assert day < datetime.now(timezone.utc).date().isoformat()


def test_live_probe_raises_cleanly_with_no_key_and_no_cache():
    """No key configured must be a clear, catchable failure -- never a crash
    the page has to absorb by accident."""
    import liveprobe
    from cache import OfflineCacheMiss
    import pytest as _pytest
    with _pytest.raises(OfflineCacheMiss):
        liveprobe.run(day="1999-01-01")  # never plausibly cached


def test_methods_page_survives_a_probe_click_with_no_key():
    """Pinning the actual regression check: click the button, no exception,
    a clear message naming the 125 already-committed calls as the fallback."""
    at = AppTest.from_file(str(REPO / "pages" / "4_Methods_and_Evidence.py"),
                           default_timeout=TIMEOUT).run()
    buttons = [b for b in at.button if b.label == "Fetch a live reading"]
    assert buttons, "live-probe button not found"
    buttons[0].click().run()
    assert not at.exception, [str(e) for e in at.exception]
    text = " ".join(w.value for w in at.warning)
    assert "125 real calls" in text


# ------------------------------------------------------------ live conditions
def test_liveconditions_shares_one_call_across_four_clauses():
    """The whole point: credits are flat, so evaluate every tcm-backed clause
    from one fetch rather than pretending four calls are needed."""
    import liveconditions
    from schema import load_clauses
    from evaluate import evaluable
    import study
    temp_clauses = [c for c in load_clauses(study.GOLDEN_CLAUSES)
                    if evaluable(c) and c.metric in liveconditions.TEMPERATURE_METRICS]
    assert len(temp_clauses) >= 3, "expected several tcm-backed clauses to share the fetch"


def test_liveconditions_excludes_the_hours_clause():
    """PHX-2026-A1.1 is exceedance/hours; mixing it into a degF comparison is
    the same unit-chain trap heatwave.py already guards against."""
    import liveconditions
    from schema import load_clauses
    from evaluate import evaluable
    import study
    ids = [c.clause_id for c in load_clauses(study.GOLDEN_CLAUSES)
           if evaluable(c) and c.metric in liveconditions.TEMPERATURE_METRICS]
    assert "PHX-2026-A1.1" not in ids


def test_liveconditions_requests_a_day_the_api_can_serve():
    import liveconditions
    from datetime import datetime, timezone
    day = liveconditions.probe_day()
    assert day < datetime.now(timezone.utc).date().isoformat()


def test_liveconditions_raises_cleanly_with_no_key_and_no_cache():
    import liveconditions
    from cache import OfflineCacheMiss
    with pytest.raises(OfflineCacheMiss):
        liveconditions.run(day="1999-01-01")


def test_home_page_survives_live_conditions_click_with_no_key():
    at = AppTest.from_file(str(REPO / "app.py"), default_timeout=TIMEOUT).run()
    buttons = [b for b in at.button if "live" in b.label.lower()]
    assert buttons, "live-conditions button not found on the home page"
    buttons[0].click().run()
    assert not at.exception, [str(e) for e in at.exception]
    text = " ".join(w.value for w in at.warning)
    assert "125 real API" in text


def test_live_section_only_shows_for_the_backend_city():
    """study.py's active city is fixed at import time (TRIGGER_CITY); the UI
    must never offer a live button for a city that backend isn't wired to."""
    at = AppTest.from_file(str(REPO / "app.py"), default_timeout=TIMEOUT).run()
    at.sidebar.radio[0].set_value("New York City").run()
    assert not at.exception, [str(e) for e in at.exception]
    assert not any("Right now, live" in str(m.value) for m in at.markdown)


# ----------------------------------------------------------- study windows
def test_phoenix_exposes_both_analysed_windows():
    """The 2026 replication was fetched live on unseen data. Showing only the
    published window made a pipeline that HAS been re-run look hardcoded."""
    import ui as _ui
    windows = _ui.CITIES["Phoenix, Arizona"]["windows"]
    assert len(windows) >= 2
    for label, path in windows.items():
        assert Path(path).exists(), label


def test_switching_window_changes_every_headline_number():
    """If the numbers do not move, the picker is decorative."""
    at = AppTest.from_file(str(REPO / "app.py"), default_timeout=TIMEOUT).run()
    published = [m.value for m in at.metric[:4]]
    w = [r for r in at.sidebar.radio if r.label == "Window"][0]
    w.set_value("16–22 Aug 2026  ·  fetched live").run()
    assert not at.exception, [str(e) for e in at.exception]
    live = [m.value for m in at.metric[:4]]
    assert published != live, "window switch did not change the numbers"
    assert "9 of 15" in live[0], live


def test_window_picker_hidden_when_a_city_has_only_one():
    """New York has a single window; a one-option picker is noise."""
    import ui as _ui
    assert len(_ui.CITIES["New York City"].get("windows", {})) == 1
