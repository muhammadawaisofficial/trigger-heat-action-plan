"""Evaluate compiled clauses against FortyGuard data, per zone and per day.

Two arms, identical logic, different spatial resolution:

  hyperlocal      each urban village, area-weighted over every tile that
                  overlaps it
  citywide_proxy  one number for the entire AOI, area-weighted over all
                  272,917 tiles

The proxy is a STAND-IN for station-based sensing, not a station feed. It is
the best-case single-number sensor: a perfectly sited, perfectly representative
instrument reporting the true city mean. Real single-station sensing is worse
than this, so divergence measured against the proxy is a LOWER BOUND on the
divergence against an actual airport station.

All decisions here are deterministic comparisons. No model is consulted.

Clause metric -> data product:

    air_temperature   exceedance at the clause threshold, filter_type=3.
                      Value is hours above threshold that day; FIRED when
                      hours > 0 (or >= duration_hours when the clause states
                      a duration).
    daily_high        tcm max_temperature, filter_type=3.
    daily_low         tcm min_temperature, filter_type=3.

persistence is deliberately unused: it saturates at 8.0 under filter_type=4
and TRIGGER evaluates day by day anyway. See docs/api_findings.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from aggregate import ZoneAggregator, area_weighted_mean, tile_areas
from cache import CachedFortyGuard
from parse import Heatmap, parse_heatmap
from schema import Clause

Arm = Literal["hyperlocal", "citywide_proxy"]

#: How each clause metric is measured from the API.
METRIC_PRODUCT = {
    "air_temperature": ("exceedance", None),
    "daily_high": ("tcm", "max_temperature"),
    "daily_low": ("tcm", "min_temperature"),
    "external_warning": ("tcm", "max_temperature"),  # proxied, see below
}


@dataclass
class Determination:
    """One clause, one zone (or the proxy), one day."""

    clause_id: str
    day: str
    arm: Arm
    zone_id: str
    zone_name: str
    fired: bool
    value: float              # measured quantity in its own units
    units: str                # "degC" or "hours"
    threshold_c: float | None
    margin: float             # value - threshold; positive means over
    note: str = ""


@dataclass
class ClauseDayResult:
    """Both arms for one clause on one day."""

    clause_id: str
    day: str
    zones: list[Determination] = field(default_factory=list)
    proxy: Determination | None = None

    @property
    def fired_zones(self) -> list[Determination]:
        return [d for d in self.zones if d.fired]

    @property
    def proxy_fired(self) -> bool:
        return bool(self.proxy and self.proxy.fired)

    @property
    def silent_zones(self) -> list[Determination]:
        """Zones meeting the condition on a day the proxy did not."""
        return [] if self.proxy_fired else self.fired_zones


class Evaluator:
    """Deterministic clause evaluation over a fixed AOI and zone set."""

    def __init__(self, fg: CachedFortyGuard, aggregator: ZoneAggregator,
                 aoi: dict, granularity: int = 100) -> None:
        self.fg = fg
        self.agg = aggregator
        self.aoi = aoi
        self.granularity = granularity
        self._proxy_cache: dict[tuple[str, str, str], float] = {}
        self._areas: list[float] | None = None  # tile areas, computed once

    # ------------------------------------------------------------- fetching

    def _heatmap(self, clause: Clause, day: str) -> tuple[Heatmap, str | None]:
        product, tcm_field = METRIC_PRODUCT[clause.metric]

        if product == "tcm":
            raw = self.fg.heatmap(
                polygon_aoi=self.aoi, start_date=day, filter_type=3,
                granularity=self.granularity, analytic_type="tcm",
                label=f"phx-city tcm {day}",
            )["result"]
            return parse_heatmap(raw, "tcm"), tcm_field

        thr_c = round(clause.threshold_c, 4)
        raw = self.fg.heatmap(
            polygon_aoi=self.aoi, start_date=day, filter_type=3,
            granularity=self.granularity, analytic_type="exceedance",
            threshold=thr_c, direction=clause.operator or "above",
            label=f"phx-city exceedance {day} t{thr_c:.4f}",
        )["result"]
        return parse_heatmap(raw, "exceedance"), None

    # ----------------------------------------------------------- evaluation

    def _fires(self, clause: Clause, value: float) -> tuple[bool, float, str]:
        """Deterministic comparison. Returns (fired, margin, units)."""
        if clause.metric == "air_temperature":
            # exceedance returns hours above the threshold that day.
            need = float(clause.duration_hours or 0)
            # A clause with no stated duration fires on any exceedance at all.
            return (value > need if need else value > 0.0), value - need, "hours"

        thr = clause.threshold_c
        assert thr is not None  # guaranteed by Clause.validate for these kinds
        if clause.operator == "below":
            return value < thr, thr - value, "degC"
        return value > thr, value - thr, "degC"

    def evaluate(self, clause: Clause, day: str) -> ClauseDayResult:
        hm, tcm_field = self._heatmap(clause, day)
        out = ClauseDayResult(clause_id=clause.clause_id, day=day)

        rows = (self.agg.aggregate_field(hm, tcm_field) if tcm_field
                else self.agg.aggregate(hm))
        for r in rows:
            fired, margin, units = self._fires(clause, r.value)
            out.zones.append(Determination(
                clause_id=clause.clause_id, day=day, arm="hyperlocal",
                zone_id=r.zone_id, zone_name=r.name, fired=fired,
                value=r.value, units=units, threshold_c=clause.threshold_c,
                margin=margin,
            ))

        # Keyed on the DATA identity, not the clause, so two clauses reading the
        # same field on the same day share one pass over 272,917 tiles.
        thr = "" if tcm_field else f"{clause.threshold_c:.4f}"
        key = (day, tcm_field or f"exceedance@{thr}", "")
        if key not in self._proxy_cache:
            if self._areas is None:
                self._areas = tile_areas(hm.tiles)
            self._proxy_cache[key] = area_weighted_mean(hm, tcm_field, self._areas)
        pval = self._proxy_cache[key]
        pfired, pmargin, punits = self._fires(clause, pval)
        out.proxy = Determination(
            clause_id=clause.clause_id, day=day, arm="citywide_proxy",
            zone_id="__proxy__", zone_name="Citywide proxy (AOI mean)",
            fired=pfired, value=pval, units=punits,
            threshold_c=clause.threshold_c, margin=pmargin,
            note="Area-weighted mean over the full AOI. A proxy for "
                 "station-based sensing, not a station feed.",
        )
        return out

    def evaluate_window(self, clause: Clause, days: list[str]) -> list[ClauseDayResult]:
        return [self.evaluate(clause, d) for d in days]


def evaluable(clause: Clause) -> bool:
    """Can this clause be measured with the products we have?"""
    return (clause.evaluable
            and clause.metric in METRIC_PRODUCT
            and (clause.threshold_c is not None or clause.metric == "external_warning"))
