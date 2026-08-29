"""The unit chain: degF as written in the plan, degC as sent to the API.

BUILD_PLAN Phase 1 requires the conversion to exist in exactly one place, and
SPEC.md names this as the first trap that fails silently: sending 95 instead
of 35.0 asks for hours above 95 degC and returns all zeros, with no error.
"""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

from schema import Clause, ClauseValidationError, c_to_f, f_to_c

REPO = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------ the conversion

@pytest.mark.parametrize("f, c", [
    (32.0, 0.0),
    (212.0, 100.0),
    (95.0, 35.0),        # the classic heat-plan threshold
    (90.0, 32.222222),   # Phoenix's overnight benchmark, the headline clause
    (110.0, 43.333333),
    (-40.0, -40.0),      # the crossover, a good sanity anchor
])
def test_f_to_c_known_values(f, c):
    assert f_to_c(f) == pytest.approx(c, abs=1e-6)


@pytest.mark.parametrize("f", [0.0, 32.0, 78.5, 90.0, 95.0, 105.0, 110.0, 118.0])
def test_round_trip(f):
    assert c_to_f(f_to_c(f)) == pytest.approx(f, abs=1e-9)


def test_the_trap_itself():
    """95 degF must never reach the API as 95."""
    assert f_to_c(95.0) == pytest.approx(35.0)
    assert f_to_c(95.0) != 95.0


# ------------------------------------- the conversion exists in ONE place

def test_conversion_defined_exactly_once_in_src():
    """No module may re-implement the arithmetic.

    Phase 1's real requirement is structural, not numeric: a second copy of
    ``(x - 32) * 5 / 9`` anywhere in src/ is a latent divergence, because the
    two copies can drift and nothing will fail loudly. This test greps for the
    shape of the arithmetic rather than the function name, so a hand-inlined
    conversion is caught too.
    """
    offenders = []
    for path in (REPO / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            code = line.split("#")[0]
            if "32" not in code:
                continue
            # The two orderings of the conversion, with or without spaces.
            squashed = code.replace(" ", "")
            if any(pat in squashed for pat in ("-32)*5", "-32.0)*5", "-32)*(5", "*5/9")):
                offenders.append(f"{path.relative_to(REPO)}:{lineno}: {line.strip()}")

    assert len(offenders) == 1, (
        "degF->degC arithmetic must appear exactly once, in schema.f_to_c. Found:\n  "
        + "\n  ".join(offenders))
    assert "schema.py" in offenders[0], f"the one copy should be schema.py, got {offenders[0]}"


def test_threshold_c_is_derived_not_stored():
    """Stronger than the validator Phase 1 asks for.

    Phase 1 specifies a validator asserting ``threshold_c ==
    round((threshold_source - 32) * 5/9, 2)``. That check only exists because a
    *stored* threshold_c can disagree with its source. We make it a computed
    property instead, which removes the failure mode rather than detecting it --
    so the thing worth asserting is that no stored field shadows it.
    """
    assert "threshold_c" not in Clause.__dataclass_fields__
    assert isinstance(getattr(Clause, "threshold_c"), property)


def test_threshold_c_matches_the_spec_formula():
    """The property still has to agree with what Phase 1 specified."""
    c = Clause(clause_id="T", source_text="x", source_page=1,
               kind="operative_trigger", metric="air_temperature", action="a",
               operator="above", threshold_source=95.0)
    assert round(c.threshold_c, 2) == round((95.0 - 32.0) * 5 / 9, 2) == 35.0


def test_celsius_source_is_not_converted_twice():
    """A clause already written in degC must pass through untouched."""
    c = Clause(clause_id="T", source_text="x", source_page=1,
               kind="operative_trigger", metric="air_temperature", action="a",
               operator="above", threshold_source=35.0, threshold_unit_source="C")
    assert c.threshold_c == 35.0


# --------------------------------------------------------- to_api_params

def test_to_api_params_sends_celsius():
    c = Clause(clause_id="T", source_text="x", source_page=1,
               kind="operative_trigger", metric="air_temperature", action="a",
               operator="above", threshold_source=90.0)
    p = c.to_api_params()
    assert p["threshold"] == pytest.approx(32.222222, abs=1e-5)
    assert p["direction"] == "above"
    assert p["analytic_type"] == "exceedance"
    # The degF value must not survive anywhere in the payload.
    assert 90.0 not in p.values()


def test_to_api_params_refuses_a_clause_with_no_threshold():
    """Silence would become the API's default of 30 degC -- a different question."""
    c = Clause(clause_id="T", source_text="x", source_page=1,
               kind="scheduled", metric="none", action="open cooling centres")
    with pytest.raises(ClauseValidationError, match="no threshold"):
        c.to_api_params()
