"""The constructive half: can a different trigger design recover targeting?

Everything else in TRIGGER measures what the plan's fixed numeric thresholds
cost. This module asks whether the loss is recoverable from the same data, which
is the only part of the analysis that suggests a remedy rather than a deficit.

Two alternative designs, both evaluated on the same tiles, same day, same
analytic as the clause they replace:

    percentile      Instead of "above 90 degF", "above the 90th percentile of
                    today's own distribution". Free: it is a recomputation over
                    tiles already cached, with no new API call, because the
                    tcm-backed metrics carry per-tile temperatures.

    heat_index      Instead of dry-bulb air temperature, the heat index or
                    apparent temperature from /v1/env_params. Costs one call per
                    sample point, so it is sampled rather than gridded.

WHAT A PERCENTILE TRIGGER IS NOT

A percentile of *today's* distribution cannot be computed before today ends, so
this is a post-hoc diagnostic, not a deployable rule. An operational version
would use a percentile of the local historical climatology -- the same shape,
fitted on years rather than on the day being judged. What this module
establishes is that the SIGNAL SURVIVES: the information needed to rank
neighbourhoods is present in the data on days when the fixed threshold reports
nothing. It does not establish that the City should adopt this exact rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from parse import Heatmap
from schema import Clause, c_to_f


def percentile(values: list[float], p: float) -> float:
    """Linear-interpolated percentile. p in [0, 100]."""
    if not values:
        raise ValueError("no values")
    v = sorted(values)
    if len(v) == 1:
        return v[0]
    k = (len(v) - 1) * p / 100.0
    f = int(k)
    if f + 1 >= len(v):
        return v[-1]
    return v[f] + (v[f + 1] - v[f]) * (k - f)


@dataclass
class RecoveryResult:
    """One alternative trigger design, on one clause, on one day."""

    clause_id: str
    day: str
    design: str                     # "fixed" | "percentile" | "heat_index"
    threshold_c: float | None
    threshold_f: float | None
    n_tiles: int
    n_fired: int
    distinct_values: int
    spread: float
    zones_fired: int = 0
    zone_names_fired: list[str] = field(default_factory=list)
    note: str = ""

    @property
    def saturation_index(self) -> float:
        return self.n_fired / self.n_tiles if self.n_tiles else 0.0

    @property
    def targeting_bits(self) -> float:
        """Binary entropy of the firing share. See evaluate.TileStats."""
        from math import log2
        p = self.saturation_index
        if p <= 0.0 or p >= 1.0:
            return 0.0
        return -(p * log2(p) + (1 - p) * log2(1 - p))

    @property
    def actionable(self) -> bool:
        return 0.05 < self.saturation_index < 0.95 and self.distinct_values > 10

    def to_dict(self) -> dict[str, Any]:
        return {
            "clause_id": self.clause_id,
            "day": self.day,
            "design": self.design,
            "threshold_c": (round(self.threshold_c, 4)
                            if self.threshold_c is not None else None),
            "threshold_f": (round(self.threshold_f, 2)
                            if self.threshold_f is not None else None),
            "n_tiles": self.n_tiles,
            "n_fired": self.n_fired,
            "saturation_index": round(self.saturation_index, 6),
            "targeting_bits": round(self.targeting_bits, 6),
            "distinct_values": self.distinct_values,
            "spread": round(self.spread, 4),
            "zones_fired": self.zones_fired,
            "zone_names_fired": self.zone_names_fired,
            "actionable": self.actionable,
            "note": self.note,
        }


def _tile_values(hm: Heatmap, tcm_field: str | None) -> list[float]:
    if tcm_field:
        return [t.props[tcm_field] for t in hm.tiles if tcm_field in t.props]
    return [t.value for t in hm.tiles if t.value is not None]


def evaluate_at_threshold(clause: Clause, hm: Heatmap, tcm_field: str | None,
                          threshold_c: float, day: str, design: str,
                          zone_values: list[tuple[str, float]] | None = None,
                          note: str = "") -> RecoveryResult:
    """Apply an arbitrary threshold to cached tiles. No API call.

    ``zone_values`` is [(zone_name, area_weighted_value), ...] if the caller
    has already aggregated; used to report which zones the design would flag.
    """
    vals = _tile_values(hm, tcm_field)
    below = (clause.operator == "below")
    fired = sum(1 for v in vals if (v < threshold_c if below else v > threshold_c))

    zf, znames = 0, []
    for name, zv in (zone_values or []):
        if (zv < threshold_c) if below else (zv > threshold_c):
            zf += 1
            znames.append(name)

    return RecoveryResult(
        clause_id=clause.clause_id, day=day, design=design,
        threshold_c=threshold_c, threshold_f=c_to_f(threshold_c),
        n_tiles=len(vals), n_fired=fired, distinct_values=len(set(vals)),
        spread=(max(vals) - min(vals)) if vals else 0.0,
        zones_fired=zf, zone_names_fired=znames, note=note,
    )


class NotRecomputable(ValueError):
    """This clause's threshold cannot be changed without a new API call."""


def percentile_recovery(clause: Clause, hm: Heatmap, tcm_field: str | None,
                        day: str, p: float = 90.0,
                        zone_values: list[tuple[str, float]] | None = None
                        ) -> tuple[RecoveryResult, RecoveryResult]:
    """(fixed, percentile) for the same clause on the same tiles.

    Free -- both arms are recomputations over one cached response -- but ONLY
    for tcm-backed metrics, where each tile carries a temperature that a new
    threshold can be compared against locally.

    An ``exceedance`` clause cannot be re-thresholded this way. Its threshold is
    applied server-side before the response is built, so the tiles carry HOURS
    ABOVE THE OLD THRESHOLD, not temperatures. Comparing those hours to a new
    temperature is exactly the schema-divergence trap CLAUDE.md warns about: it
    returns a confident, meaningless number rather than an error. So we raise.
    Recovering an exceedance clause costs one API call per candidate threshold.
    """
    if not tcm_field:
        raise NotRecomputable(
            f"{clause.clause_id} is measured by exceedance, whose tiles carry "
            f"hours above {clause.threshold_source:g} degF rather than "
            f"temperatures. Re-thresholding it needs a new API call "
            f"(4,220 credits), not a recomputation.")

    vals = _tile_values(hm, tcm_field)
    if not vals:
        raise ValueError(f"{clause.clause_id} on {day}: no tile values")

    assert clause.threshold_c is not None
    fixed = evaluate_at_threshold(
        clause, hm, tcm_field, clause.threshold_c, day, "fixed",
        zone_values, note=f"the plan as written: {clause.threshold_source:g} degF")

    # For a "below" clause the tail of interest is the low end, so the
    # complementary percentile is the comparable one.
    q = (100.0 - p) if clause.operator == "below" else p
    thr = percentile(vals, q)
    pct = evaluate_at_threshold(
        clause, hm, tcm_field, thr, day, "percentile", zone_values,
        note=(f"p{q:g} of that day's own tile distribution. Post hoc: a "
              f"deployable version would use a percentile of historical "
              f"climatology, not of the day being judged."))
    return fixed, pct


def dwell_recovery(clause: Clause, hm: Heatmap, day: str,
                   dwell_hours: tuple[int, ...] = (0, 1, 3, 6, 9, 12, 18),
                   zone_values: list[tuple[str, float]] | None = None
                   ) -> list[RecoveryResult]:
    """Keep the clause's threshold; require it to be exceeded for longer.

    Only meaningful for exceedance-backed clauses, where each tile already
    carries hours-above-threshold. The threshold does not move, so nothing new
    is fetched -- this is the cheapest of the three designs and the only one
    that is deployable as written, because it needs no percentile and no new
    instrument. It is a clause edit.

    "Above 105 degF" fires wherever the temperature touches 105 degF for even an
    instant, which on a severe day is everywhere. "Above 105 degF for more than
    nine hours" asks about dwell time, and dwell time still varies across the
    city when peak temperature no longer does.
    """
    vals = [t.value for t in hm.tiles if t.value is not None]
    if not vals:
        raise ValueError(f"{clause.clause_id} on {day}: no tile values")

    out: list[RecoveryResult] = []
    for d in dwell_hours:
        fired = sum(1 for v in vals if v > d)
        zf, znames = 0, []
        for name, zv in (zone_values or []):
            if zv > d:
                zf += 1
                znames.append(name)
        out.append(RecoveryResult(
            clause_id=clause.clause_id, day=day,
            design=f"dwell>{d}h",
            threshold_c=clause.threshold_c,
            threshold_f=(c_to_f(clause.threshold_c)
                         if clause.threshold_c is not None else None),
            n_tiles=len(vals), n_fired=fired, distinct_values=len(set(vals)),
            spread=max(vals) - min(vals),
            zones_fired=zf, zone_names_fired=znames,
            note=(f"same {clause.threshold_source:g} degF threshold, sustained "
                  f"for more than {d} h. No new data: the hours are already in "
                  f"the cached response."),
        ))
    return out


def zones_recovered(fixed: RecoveryResult, alt: RecoveryResult) -> int:
    """Zones the alternative design can single out that the fixed one cannot.

    Zero when the fixed design was already actionable -- there is nothing to
    recover. Otherwise the count of zones the alternative flags, which is the
    number of places an emergency manager could be sent on evidence that the
    fixed rule discarded.
    """
    if fixed.actionable:
        return 0
    return alt.zones_fired if alt.actionable else 0
