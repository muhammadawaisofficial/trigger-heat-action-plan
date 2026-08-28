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
