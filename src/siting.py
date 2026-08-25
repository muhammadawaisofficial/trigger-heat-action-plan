"""Siting economics: what a thermal difference costs, in kWh and dollars.

Free-cooling hours are the physical quantity. This module turns them into the
number a siting decision is actually made on.

THE MODEL, AND ITS LIMITS

Cooling energy for a facility is approximated as

    kWh_cooling  =  IT_load_kW  x  mechanical_hours  /  COP

where ``mechanical_hours`` is the time the chillers must run because ambient
temperature sat above the economiser setpoint, and COP is the coefficient of
performance of the plant. This is a FIRST-ORDER model and it is stated as one.
It deliberately omits:

  - humidity, which can block economiser operation even when temperature allows
    it, and which matters enormously in humid climates
  - the fact that chiller COP itself degrades as ambient temperature rises, so
    hot hours cost more than the linear term implies
  - part-load behaviour, water-side economisers, evaporative assist, thermal
    storage and every other real plant refinement

Every one of those omissions makes the model CONSERVATIVE -- the true cost gap
between a hot site and a cool one is larger than this computes, not smaller. That
is the right direction for an omission to point, and it is why the output is
framed as a floor.

WHAT IS DEFENSIBLE HERE

The RANKING and the RELATIVE gap. Both sites are evaluated with identical
assumptions on the same days from the same measurements, so the assumptions
cancel and what survives is the thermal difference between two pieces of ground.
The absolute dollar figure depends on tariff and plant efficiency and should be
read as an order of magnitude, not a quotation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: Reference plant. Every figure below scales linearly with these, and they are
#: exposed rather than buried so a reader can substitute their own.
DEFAULT_IT_LOAD_KW = 1_000.0      # a small-to-mid colocation hall
DEFAULT_COP = 3.5                 # typical air-cooled chiller, full load
DEFAULT_TARIFF_USD_KWH = 0.085    # US commercial average, order of magnitude
HOURS_PER_DAY = 24.0


@dataclass
class SiteCost:
    """Cooling cost for one candidate site over the measured window."""

    zone_id: str
    zone_name: str
    free_hours: float
    window_days: int
    it_load_kw: float = DEFAULT_IT_LOAD_KW
    cop: float = DEFAULT_COP
    tariff: float = DEFAULT_TARIFF_USD_KWH

    @property
    def total_hours(self) -> float:
        return self.window_days * HOURS_PER_DAY

    @property
    def mechanical_hours(self) -> float:
        """Hours the chillers must run: everything not free-cooled."""
        return max(0.0, self.total_hours - self.free_hours)

    @property
    def free_share(self) -> float:
        return self.free_hours / self.total_hours if self.total_hours else 0.0

    @property
    def cooling_kwh(self) -> float:
        return self.it_load_kw * self.mechanical_hours / self.cop

    @property
    def cooling_usd(self) -> float:
        return self.cooling_kwh * self.tariff

    def annualised_usd(self) -> float:
        """Scaled to a year at this week's rate. A worst-case bound, not a forecast.

        The measured window is the hottest week of the year, so a full year at
        this rate is an OVERSTATEMENT of annual cost and is labelled as such
        wherever it appears. It is useful only as an upper bound on the gap
        between two sites, never as a budget figure.
        """
        return self.cooling_usd * (365.0 / self.window_days)

    def to_dict(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id, "zone_name": self.zone_name,
            "free_cooling_hours": round(self.free_hours, 1),
            "free_cooling_share": round(self.free_share, 4),
            "mechanical_hours": round(self.mechanical_hours, 1),
            "cooling_kwh_window": round(self.cooling_kwh, 0),
            "cooling_usd_window": round(self.cooling_usd, 0),
            "annualised_usd_upper_bound": round(self.annualised_usd(), 0),
        }


def rank(zones: list[dict], window_days: int,
         setpoint_key: str = "24",
         it_load_kw: float = DEFAULT_IT_LOAD_KW,
         cop: float = DEFAULT_COP,
         tariff: float = DEFAULT_TARIFF_USD_KWH) -> list[SiteCost]:
    """Candidate sites, cheapest cooling first."""
    out = [
        SiteCost(zone_id=z["zone_id"], zone_name=z["name"],
                 free_hours=float(z.get("free_hours", {}).get(setpoint_key, 0.0)),
                 window_days=window_days, it_load_kw=it_load_kw, cop=cop,
                 tariff=tariff)
        for z in zones
    ]
    out.sort(key=lambda s: s.cooling_usd)
    return out


def compare(ranked: list[SiteCost]) -> dict[str, Any]:
    """Best against worst: the number a siting decision turns on."""
    if len(ranked) < 2:
        return {}
    best, worst = ranked[0], ranked[-1]
    return {
        "best": best.to_dict(),
        "worst": worst.to_dict(),
        "free_hour_gap": round(best.free_hours - worst.free_hours, 1),
        "kwh_gap_window": round(worst.cooling_kwh - best.cooling_kwh, 0),
        "usd_gap_window": round(worst.cooling_usd - best.cooling_usd, 0),
        "usd_gap_annualised_upper_bound":
            round(worst.annualised_usd() - best.annualised_usd(), 0),
        "pct_cheaper": round(
            (worst.cooling_usd - best.cooling_usd) / worst.cooling_usd * 100.0, 2)
        if worst.cooling_usd else 0.0,
        "assumptions": {
            "it_load_kw": best.it_load_kw, "cop": best.cop,
            "tariff_usd_per_kwh": best.tariff,
            "note": ("First-order model. Omits humidity blocking economiser "
                     "operation, COP degradation at high ambient, and part-load "
                     "behaviour -- all of which make the true gap LARGER than "
                     "this. Both sites use identical assumptions on the same "
                     "days, so what survives the comparison is the thermal "
                     "difference between two pieces of ground. Absolute dollars "
                     "are an order of magnitude, not a quotation."),
        },
    }
