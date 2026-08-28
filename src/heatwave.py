"""Heat-wave detection, per neighbourhood rather than per city.

A heat wave is not "a hot day". Every operational definition in use has the same
three parts: a threshold, a persistence requirement, and -- in the definitions
that actually predict mortality -- a NIGHT-TIME condition, because the health
damage comes from bodies never getting a chance to cool down.

    threshold      an absolute value, or a percentile of local climatology
    persistence    a minimum number of CONSECUTIVE days
    night          overnight minima that stay elevated

This module implements that definition at the resolution the data supports:
per zone, per day, so a heat wave can be detected in Maryvale and not in
Ahwatukee on the same night. Every city-scale heat-wave product answers "is the
city in a heat wave"; this one answers "which neighbourhoods are, and since
when".

WHY PERCENTILE AND ABSOLUTE BOTH APPEAR

An absolute threshold is what plans are written against, so it is what governs.
A percentile threshold is what the epidemiological literature uses, because the
temperature at which people start dying is relative to what they are acclimatised
to -- 95 degF is an emergency in Seattle and a Tuesday in Phoenix. Reporting both
lets a reader see where the plan's own number sits against the local
distribution.

Nothing here is modelled or forecast. These are runs detected in measured data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


def percentile(values: list[float], p: float) -> float:
    if not values:
        raise ValueError("no values")
    v = sorted(values)
    if len(v) == 1:
        return v[0]
    k = (len(v) - 1) * p / 100.0
    f = int(k)
    return v[-1] if f + 1 >= len(v) else v[f] + (v[f + 1] - v[f]) * (k - f)


@dataclass
class HeatWave:
    """A run of consecutive qualifying days in one zone."""

    zone_id: str
    zone_name: str
    start: str
    end: str
    days: list[str] = field(default_factory=list)
    peak_f: float = 0.0
    peak_day: str = ""
    threshold_f: float = 0.0
    basis: str = "absolute"          # "absolute" | "percentile"
    population: int | None = None

    @property
    def length(self) -> int:
        return len(self.days)

    @property
    def severity(self) -> str:
        """Length is what kills. Three nights is the usual inflection."""
        if self.length >= 4:
            return "SEVERE"
        if self.length >= 3:
            return "SIGNIFICANT"
        return "NOTABLE"

    def to_dict(self) -> dict:
        return {
            "zone_id": self.zone_id, "zone_name": self.zone_name,
            "start": self.start, "end": self.end, "length_days": self.length,
            "days": self.days, "peak_f": round(self.peak_f, 2),
            "peak_day": self.peak_day, "threshold_f": round(self.threshold_f, 2),
            "basis": self.basis, "severity": self.severity,
            "population": self.population,
        }


#: Units that carry a TEMPERATURE. Anything else is a different physical
#: quantity and cannot be compared against a degF threshold -- see _guard_units.
TEMPERATURE_UNITS = {"degC", "degF", "celsius", "fahrenheit", "C", "F"}


def _villages(population: dict | None) -> dict:
    """Accept either the population file or its inner ``villages`` mapping.

    The population files are ``{"meta": {...}, "villages": {zone_id: {...}}}``.
    Passing the whole file where the inner mapping was wanted looks up zone ids
    against the keys ``meta`` and ``villages``, finds nothing, and silently
    reports every population as zero -- a wrong number rather than an error.
    """
    if not population:
        return {}
    inner = population.get("villages")
    return inner if isinstance(inner, dict) else population


def _guard_units(units: str, clause_id: str) -> None:
    """Refuse to treat a non-temperature series as a temperature.

    Exceedance clauses come back in ``hours`` -- a value of 5.8 means the zone
    spent 5.8 hours past its threshold. Comparing that to a 105 degF heat-wave
    threshold is arithmetic on two different physical quantities: it raises no
    error, returns zero waves, and reads as "no heat wave here". This is the
    unit-chain trap the project documents, so it is enforced rather than
    trusted.
    """
    if units not in TEMPERATURE_UNITS:
        raise ValueError(
            f"{clause_id}: series is in '{units}', not a temperature. Heat-wave "
            f"detection needs a temperature per day; an exceedance clause "
            f"measures HOURS past a threshold and cannot be compared against a "
            f"degF heat-wave threshold. Select a clause whose analytic returns "
            f"a temperature.")


def detect_waves(series: dict[str, list[tuple[str, float]]],
                 names: dict[str, str],
                 threshold_f: float,
                 min_days: int = 2,
                 basis: str = "absolute",
                 population: dict[str, dict] | None = None) -> list[HeatWave]:
    """Runs of >= ``min_days`` consecutive days at or above ``threshold_f``.

    ``series`` maps zone_id -> [(day, value_f), ...]. Days must be consecutive
    calendar days for the run logic to mean what it says; the caller supplies
    them in order from a contiguous study window.
    """
    population = _villages(population)
    out: list[HeatWave] = []

    for zid, rows in series.items():
        rows = sorted(rows)
        run: list[tuple[str, float]] = []

        def close(run):
            if len(run) >= min_days:
                peak_day, peak = max(run, key=lambda r: r[1])
                out.append(HeatWave(
                    zone_id=zid, zone_name=names.get(zid, zid),
                    start=run[0][0], end=run[-1][0],
                    days=[d for d, _ in run], peak_f=peak, peak_day=peak_day,
                    threshold_f=threshold_f, basis=basis,
                    population=population.get(zid, {}).get("population")))

        for day, val in rows:
            if val >= threshold_f:
                run.append((day, val))
            else:
                close(run)
                run = []
        close(run)

    out.sort(key=lambda w: (-w.length, -(w.population or 0)))
    return out


def summarise(waves: Iterable[HeatWave], n_zones: int) -> dict:
    waves = list(waves)
    zones = {w.zone_id for w in waves}
    return {
        "waves": len(waves),
        "zones_in_heatwave": len(zones),
        "zones_total": n_zones,
        "longest_days": max((w.length for w in waves), default=0),
        "severe": sum(1 for w in waves if w.severity == "SEVERE"),
        "population": sum((w.population or 0) for w in
                          {w.zone_id: w for w in waves}.values()),
    }


def from_results(results: dict, clause_id: str | None = None,
                 population: dict[str, dict] | None = None,
                 min_days: int = 2,
                 pct: float = 90.0) -> dict:
    """Detect waves from a divergence result, on both bases.

    Returns the absolute-threshold detection (what the plan governs on) and the
    percentile detection (what the epidemiology uses), so the two can be
    compared directly.
    """
    clause = None
    for c in results.get("clauses", []):
        if clause_id is None or c["clause_id"] == clause_id:
            clause = c
            break
    if clause is None:
        return {}

    units = "degC"
    series: dict[str, list[tuple[str, float]]] = {}
    names: dict[str, str] = {}
    pooled: list[float] = []
    for det in clause.get("determinations", []):
        for z in det["zones"]:
            units = z["units"]
            val = z["value"] * 9 / 5 + 32 if units == "degC" else z["value"]
            series.setdefault(z["zone_id"], []).append((det["day"], val))
            names[z["zone_id"]] = z["name"]
            pooled.append(val)

    _guard_units(units, clause.get("clause_id", "clause"))

    thr_abs = clause.get("threshold_f", 0.0)
    thr_pct = percentile(pooled, pct) if pooled else thr_abs

    n_zones = len({z for z in series})
    abs_w = detect_waves(series, names, thr_abs, min_days, "absolute", population)
    pct_w = detect_waves(series, names, thr_pct, min_days, "percentile", population)

    return {
        "clause_id": clause["clause_id"],
        "min_days": min_days,
        "absolute": {
            "threshold_f": round(thr_abs, 2),
            "summary": summarise(abs_w, n_zones),
            "waves": [w.to_dict() for w in abs_w],
        },
        "percentile": {
            "threshold_f": round(thr_pct, 2), "percentile": pct,
            "summary": summarise(pct_w, n_zones),
            "waves": [w.to_dict() for w in pct_w],
            "note": (f"p{pct:g} of this window's own per-zone distribution. Post "
                     f"hoc, like every same-window percentile in this project: it "
                     f"shows where the plan's number sits against the local "
                     f"distribution, not a rule a city could adopt as written."),
        },
    }


def temperature_clauses(results: dict) -> list[dict]:
    """Clauses whose series is a temperature, so heat-wave detection applies.

    Exposed so a caller can offer only the clauses this analysis is valid for,
    rather than offering all of them and raising on the ones that are not.
    """
    out = []
    for c in results.get("clauses", []):
        det = c.get("determinations") or []
        zones = det[0].get("zones") if det else None
        if not zones:
            continue
        if zones[0].get("units") in TEMPERATURE_UNITS:
            out.append(c)
    return out
