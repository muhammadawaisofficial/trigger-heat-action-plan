"""Multi-factor data-centre siting, with the water-energy tradeoff made explicit.

Cooling is not the first thing a site selector looks at. Published surveys put
POWER AVAILABILITY top -- 84% rank it in their top three -- and the 2025 framing
of the problem is "power, water and permits", with the binding constraint usually
being interconnection timeline rather than land. A model that ranked sites on
temperature alone would be answering a question nobody asks.

But cooling is the factor that is measured worst. Every published free-cooling
figure is a CITY-level number: Phoenix "1,000-2,000 hours a year", Minneapolis
"4,000-6,000". Nobody sites a building on a city average, and the whole premise
of this project is that city averages hide the variation that matters. So this
model contributes precision where precision is missing, and treats the rest
honestly.

    MEASURED BY US, at 100 m, from FortyGuard
        free-cooling hours          hours below the economiser setpoint
        wet-bulb temperature        whether evaporative cooling will work
        overnight low               how much the site recovers at night

    REFERENCE CONSTANTS, from published sources, at STATE resolution
        electricity price           EIA commercial average
        water stress                WRI Aqueduct / USGS band
        disaster risk               FEMA National Risk Index band
        grid headroom               interconnection-queue reporting
        renewables proximity        published generation mix

The asymmetry is deliberate and is stated wherever the model surfaces: our
thermal term resolves within a metro, and every other term does not. That is the
same criticism this project levels at heat plans, pointed at our own model.

THE WATER-ENERGY TRADEOFF

The industry's core dilemma is that saving electricity often means wasting water
and vice versa. Evaporative cooling is far more energy-efficient than mechanical
chilling, but consumes water -- and its effectiveness is set by WET-BULB
temperature, not dry-bulb. A hot ARID site has a low wet-bulb, so evaporative
cooling works beautifully there; it is also exactly where water is scarcest.
Microsoft's reported WUE is 1.52 L/kWh in Arizona against 0.02 in Singapore.

This model therefore does not emit a single score. It emits a RECOMMENDED COOLING
STRATEGY per site, because the right answer in Phoenix (air-cooled, high energy,
near-zero water) is different from the right answer in Minneapolis (free cooling
most of the year) and different again from Houston (high wet-bulb: evaporative
works poorly AND free cooling is rare, the genuinely worst case).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
FACTORS = json.loads((REPO / "data" / "siting_factors.json").read_text(encoding="utf-8"))

#: Ordinal bands -> 0..1 where 1 is always BETTER for a data centre.
_BAND = {
    "water_stress":   {"extreme": 0.0, "high": 0.25, "medium": 0.5, "low": 0.8, "very low": 1.0},
    "disaster_risk":  {"very high": 0.0, "high": 0.25, "medium": 0.55, "low": 0.85, "very low": 1.0},
    "grid_headroom":  {"very tight": 0.0, "tight": 0.25, "moderate": 0.55, "good": 0.8, "excellent": 1.0},
    "renewables":     {"poor": 0.0, "limited": 0.25, "moderate": 0.55, "good": 0.8, "excellent": 1.0},
}

#: Default weights. Power first, because the industry ranks it first. Exposed
#: rather than buried so a user can weigh the problem their own way.
DEFAULT_WEIGHTS = {
    "power":     0.30,   # price + grid headroom
    "cooling":   0.25,   # free-cooling hours -- the term we measure
    "water":     0.20,   # water stress
    "risk":      0.15,   # natural disaster exposure
    "renewable": 0.10,   # green capacity access
}

#: Wet-bulb above this makes evaporative cooling largely ineffective.
WETBULB_LIMIT_C = 24.0


def _norm(values: list[float], higher_is_better: bool = True) -> list[float]:
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [0.5] * len(values)
    out = [(v - lo) / (hi - lo) for v in values]
    return out if higher_is_better else [1.0 - x for x in out]


@dataclass
class SiteScore:
    metro_id: str
    name: str
    state: str
    free_hours: float
    daily_high_f: float | None
    overnight_low_f: float | None
    wet_bulb_c: float | None
    electricity: float
    water_stress: str
    disaster_risk: str
    grid_headroom: str
    renewables: str
    note: str = ""
    sub: dict[str, float] = field(default_factory=dict)
    score: float = 0.0

    @property
    def cooling_strategy(self) -> dict[str, str]:
        """Which cooling technology this site's climate actually calls for.

        Not a preference -- a consequence of wet-bulb and water stress together.
        """
        arid_ok = (self.wet_bulb_c is not None and self.wet_bulb_c < WETBULB_LIMIT_C)
        scarce = self.water_stress in ("high", "extreme")

        if self.free_hours >= 100:
            return {"strategy": "Air-side economiser",
                    "why": ("Enough hours below the setpoint that outside air "
                            "carries most of the load. Lowest energy AND lowest "
                            "water: no tradeoff to make here.")}
        if arid_ok and not scarce:
            return {"strategy": "Evaporative / adiabatic",
                    "why": ("Low wet-bulb makes evaporative cooling highly "
                            "effective, and water is not constrained here, so "
                            "the energy saving is available without a water "
                            "penalty.")}
        if arid_ok and scarce:
            return {"strategy": "Air-cooled chillers — water-constrained",
                    "why": ("Low wet-bulb means evaporative cooling WOULD work "
                            "well, but this is a water-stressed region where it "
                            "is a documented flashpoint for community "
                            "opposition. Trading energy efficiency away to "
                            "protect water is the defensible choice.")}
        return {"strategy": "Mechanical chillers — worst case",
                "why": ("High wet-bulb blunts evaporative cooling and there are "
                        "few free-cooling hours, so mechanical cooling runs "
                        "nearly always. This is the expensive quadrant.")}

    def to_dict(self) -> dict[str, Any]:
        d = {
            "metro_id": self.metro_id, "name": self.name, "state": self.state,
            "score": round(self.score, 4),
            "free_cooling_hours": round(self.free_hours, 1),
            "daily_high_f": self.daily_high_f,
            "overnight_low_f": self.overnight_low_f,
            "wet_bulb_c": self.wet_bulb_c,
            "electricity_cents_kwh": self.electricity,
            "water_stress": self.water_stress,
            "disaster_risk": self.disaster_risk,
            "grid_headroom": self.grid_headroom,
            "renewables": self.renewables,
            "sub_scores": {k: round(v, 4) for k, v in self.sub.items()},
            "note": self.note,
        }
        d.update(self.cooling_strategy)
        return d


def score_metros(national: dict, weights: dict[str, float] | None = None,
                 wet_bulb: dict[str, float] | None = None) -> list[SiteScore]:
    """Rank the national panel. Returns best-first.

    ``national`` is the output of fetch_national.py. ``wet_bulb`` optionally maps
    metro_id -> mean wet-bulb degC from env_params; without it the evaporative
    branch of the strategy logic is skipped rather than guessed.
    """
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    total_w = sum(weights.values()) or 1.0
    wet_bulb = wet_bulb or {}

    metros = [m for m in national.get("metros", [])
              if m.get("free_hours_24") is not None]
    if not metros:
        return []

    st_of = FACTORS["metro_state"]
    st = FACTORS["states"]

    free = _norm([m["free_hours_24"] for m in metros], True)
    price = _norm([st[st_of[m["id"]]]["electricity_cents_kwh"] for m in metros], False)

    out: list[SiteScore] = []
    for i, m in enumerate(metros):
        s = st[st_of[m["id"]]]
        grid = _BAND["grid_headroom"][s["grid_headroom"]]
        sub = {
            "power": 0.5 * price[i] + 0.5 * grid,
            "cooling": free[i],
            "water": _BAND["water_stress"][s["water_stress"]],
            "risk": _BAND["disaster_risk"][s["disaster_risk"]],
            "renewable": _BAND["renewables"][s["renewables"]],
        }
        sc = SiteScore(
            metro_id=m["id"], name=m["name"], state=st_of[m["id"]],
            free_hours=m["free_hours_24"],
            daily_high_f=m.get("mean_daily_high_f"),
            overnight_low_f=m.get("mean_overnight_low_f"),
            wet_bulb_c=wet_bulb.get(m["id"]),
            electricity=s["electricity_cents_kwh"],
            water_stress=s["water_stress"], disaster_risk=s["disaster_risk"],
            grid_headroom=s["grid_headroom"], renewables=s["renewables"],
            note=s.get("note", ""), sub=sub,
        )
        sc.score = sum(sub[k] * weights[k] for k in weights) / total_w
        out.append(sc)

    out.sort(key=lambda x: -x.score)
    return out


def tradeoff_table(scores: list[SiteScore]) -> list[dict[str, Any]]:
    """The water-energy tradeoff, made visible.

    Sites that are energy-cheap but water-expensive are the ones that get built
    and then fought over, so they are worth naming explicitly rather than
    letting a single composite score hide them.
    """
    rows = []
    for s in scores:
        energy_good = s.sub.get("cooling", 0) >= 0.5 or s.free_hours >= 60
        water_good = s.sub.get("water", 0) >= 0.5
        if energy_good and water_good:
            quad = "win-win — cool and water-secure"
        elif energy_good and not water_good:
            quad = "energy-cheap, water-constrained"
        elif not energy_good and water_good:
            quad = "water-secure, cooling-expensive"
        else:
            quad = "worst quadrant — hot and dry-stressed"
        rows.append({
            "name": s.name, "state": s.state, "quadrant": quad,
            "free_cooling_hours": round(s.free_hours, 1),
            "water_stress": s.water_stress,
            "strategy": s.cooling_strategy["strategy"],
        })
    return rows
