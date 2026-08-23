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
class TileStats:
    """Over-trigger diagnostics, computed on raw tiles BEFORE aggregation.

    The under-trigger metrics ask "who did the citywide number miss?". These
    ask the opposite question: when the clause does fire, does it fire
    *selectively* enough to act on? A trigger that fires everywhere is as
    useless for allocating finite resources as one that fires nowhere -- an
    emergency manager cannot send crews to the whole city.

    Aggregating to zones first would hide this: 15 zone means say nothing about
    whether the underlying field had any structure. So this is measured on all
    272,917 tiles.
    """

    n_tiles: int
    n_fired: int
    distinct_values: int
    min_value: float
    max_value: float
    mean_value: float
    units: str

    @property
    def saturation_index(self) -> float:
        """Share of tiles where the clause fires. 1.0 = no targeting value."""
        return self.n_fired / self.n_tiles if self.n_tiles else 0.0

    @property
    def spread(self) -> float:
        return self.max_value - self.min_value

    @property
    def discrimination(self) -> float:
        """Distinct values as a share of tiles.

        Weak at city scale: 272,917 tiles of floating-point data always carry
        tens of thousands of distinct values, so this never approaches zero
        however useless the trigger is. Kept because it is the natural measure
        over a small AOI, where quantisation does collapse it to 1. Use
        ``targeting_bits`` to compare days.
        """
        return self.distinct_values / self.n_tiles if self.n_tiles else 0.0

    @property
    def targeting_bits(self) -> float:
        """Information in the trigger's own output, in bits. 0 to 1.

        A trigger emits one bit per tile: fire or don't. The information that
        carries is the binary entropy of the firing share --

            H(p) = -p log2 p - (1-p) log2 (1-p)

        -- which is 1 bit when the trigger splits the city evenly and 0 bits
        when it says the same thing everywhere, whether that is "everywhere" or
        "nowhere". This is the quantity that collapses at BOTH ends of severity,
        and unlike a count of distinct values it does not depend on tile count,
        floating-point noise, or AOI size, so days and cities are comparable.

        It measures the trigger's output, not the underlying heat: the city can
        be highly differentiated while a badly placed threshold still reports
        0 bits.
        """
        from math import log2
        p = self.saturation_index
        if p <= 0.0 or p >= 1.0:
            return 0.0
        return -(p * log2(p) + (1 - p) * log2(1 - p))

    @property
    def actionable(self) -> bool:
        """Is there a basis here for choosing where to send resources?

        Both bounds matter. Below 5% the clause is effectively silent; above
        95% it is effectively always-on. In between, and with more than a
        handful of distinct values, the field can be ranked.
        """
        return 0.05 < self.saturation_index < 0.95 and self.distinct_values > 10

    @property
    def failure_mode(self) -> str:
        if self.actionable:
            return "actionable"
        if self.saturation_index >= 0.95:
            return "over_trigger"      # fires everywhere: no targeting
        if self.saturation_index <= 0.05:
            return "under_trigger"     # fires nowhere: no coverage
        return "low_discrimination"    # right share, too few distinct values

    def to_dict(self) -> dict:
        return {
            "n_tiles": self.n_tiles,
            "n_fired": self.n_fired,
            "saturation_index": round(self.saturation_index, 6),
            "distinct_values": self.distinct_values,
            "discrimination": round(self.discrimination, 6),
            "targeting_bits": round(self.targeting_bits, 6),
            "spread": round(self.spread, 4),
            "min_value": round(self.min_value, 4),
            "max_value": round(self.max_value, 4),
            "mean_value": round(self.mean_value, 4),
            "units": self.units,
            "actionable": self.actionable,
            "failure_mode": self.failure_mode,
        }


@dataclass
class ClauseDayResult:
    """Both arms for one clause on one day."""

    clause_id: str
    day: str
    zones: list[Determination] = field(default_factory=list)
    proxy: Determination | None = None
    #: Tile-level over-trigger diagnostics for this clause on this day.
    tiles: TileStats | None = None
    #: Mean tile temperature that day, degC -- the severity axis of the sweep.
    #: Read from tcm regardless of which product the clause itself uses, so
    #: every clause is placed on the same severity scale.
    severity_c: float | None = None

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
        self._severity_cache: dict[str, float | None] = {}

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

    def _tile_stats(self, clause: Clause, hm: Heatmap,
                    tcm_field: str | None) -> TileStats | None:
        """Apply the clause to every tile, without aggregating first."""
        if tcm_field:
            vals = [t.props[tcm_field] for t in hm.tiles if tcm_field in t.props]
        else:
            vals = [t.value for t in hm.tiles if t.value is not None]
        if not vals:
            return None
        fired = sum(1 for v in vals if self._fires(clause, v)[0])
        return TileStats(
            n_tiles=len(vals), n_fired=fired, distinct_values=len(set(vals)),
            min_value=min(vals), max_value=max(vals),
            mean_value=sum(vals) / len(vals),
            units="hours" if clause.metric == "air_temperature" else "degC",
        )

    def severity(self, day: str) -> float | None:
        """Mean tile temperature over the AOI that day, in degC.

        The severity axis for the sweep. Always read from tcm
        ``average_temperature`` so clauses using different products land on one
        comparable scale. Cached per day: this is one pass over 272,917 tiles.
        """
        if day in self._severity_cache:
            return self._severity_cache[day]
        try:
            hm = parse_heatmap(self.fg.heatmap(
                polygon_aoi=self.aoi, start_date=day, filter_type=3,
                granularity=self.granularity, analytic_type="tcm",
                label=f"phx-city tcm {day}")["result"], "tcm")
        except Exception:  # noqa: BLE001 -- severity is diagnostic, never fatal
            self._severity_cache[day] = None
            return None
        vals = [t.props["average_temperature"] for t in hm.tiles
                if "average_temperature" in t.props]
        out = (sum(vals) / len(vals)) if vals else None
        self._severity_cache[day] = out
        return out

    def evaluate(self, clause: Clause, day: str) -> ClauseDayResult:
        hm, tcm_field = self._heatmap(clause, day)
        out = ClauseDayResult(clause_id=clause.clause_id, day=day)
        out.tiles = self._tile_stats(clause, hm, tcm_field)
        out.severity_c = self.severity(day)

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
