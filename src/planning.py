"""Urban-planning recommendations, derived from measurement and published effect sizes.

WHAT THIS IS

Heat mitigation advice is usually generic: plant trees, paint roofs white. That
advice is not wrong, it is just unquantified -- it never says HOW MUCH canopy, in
WHICH neighbourhood, to close WHAT gap. This module answers those three
questions by joining two things:

    MEASURED, by us, at 100 m       the thermal gap that needs closing
    PUBLISHED effect sizes          how much intervention closes a degree

Neither half is invented. The measurement comes from FortyGuard tiles; the
coefficients come from the peer-reviewed urban-heat literature and are cited
inline with the numbers they produce.

THE COEFFICIENTS, AND WHY EACH IS CONSERVATIVE

    canopy      A global meta-analysis finds ~0.3 degC of cooling per +10%
                canopy cover. Phoenix-specific work found 10% -> 25% canopy
                delivered up to 2.0 degC of daytime cooling, and full canopy
                against treeless ground reaches 5.5 degC (8.8 degC once air
                temperature hits 40 degC). We use the META-ANALYSIS number, the
                most conservative of these, because it is the one that
                generalises across the panel.

    albedo      Cool roofs reduce neighbourhood air temperature by ~0.3 degC in
                residential deployment; Boston modelling gives -0.61 degC per
                +0.1 albedo in the afternoon. We use the residential figure,
                again the conservative one.

Tree canopy delivers roughly 35% more temperature reduction than cool roofs, but
cool roofs achieve higher HEAT EXPOSURE reduction in practice because they can be
deployed in exactly the dense, vulnerable districts where there is no room to
plant. That trade-off is why this module recommends a mix rather than a winner.

THE HONEST LIMIT ON SPREAD

Intra-metro spread is computed over every tile in a 10 km sample box. That box
contains whatever is there -- water, ridgelines, irrigated farmland, desert. So a
large spread is NOT by itself proof of an unjust heat-island; Seattle's spread is
large partly because Puget Sound and hills sit inside the box. What spread does
measure, reliably, is the RANGE OF THERMAL CONDITIONS A SINGLE CITYWIDE NUMBER IS
STANDING IN FOR -- which is the claim this project actually makes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: degC of air-temperature cooling per +10 percentage points of canopy cover.
#: Global meta-analysis value -- the conservative end of the published range.
CANOPY_C_PER_10PCT = 0.3

#: degC of neighbourhood cooling from residential cool-roof deployment.
ALBEDO_C_RESIDENTIAL = 0.3

#: Tree canopy outperforms cool roofs on temperature by roughly this factor.
CANOPY_VS_ALBEDO = 1.35

#: Spread at or above this (degF, within one sample box) means a single number
#: is standing in for materially different places.
SPREAD_TARGETED_F = 20.0

#: Overnight lows at or above this (degF) are the nights bodies do not recover.
NIGHT_CRITICAL_F = 80.0


def c_to_f_delta(c: float) -> float:
    """Convert a TEMPERATURE DIFFERENCE, not a temperature.

    A delta converts with the ratio alone -- adding 32 here would be the
    classic unit-chain error, turning a 1 degC improvement into a 33.8 degF one.
    """
    return c * 9.0 / 5.0


def canopy_points_for(gap_f: float) -> float:
    """Percentage points of canopy needed to close ``gap_f`` degF."""
    per_point_f = c_to_f_delta(CANOPY_C_PER_10PCT) / 10.0
    return gap_f / per_point_f if per_point_f else float("inf")


@dataclass
class MetroPlan:
    metro_id: str
    name: str
    climate: str
    min_f: float
    max_f: float
    mean_f: float
    overnight_low_f: float | None
    daily_high_f: float | None

    @property
    def spread_f(self) -> float:
        return self.max_f - self.min_f

    @property
    def targeted(self) -> bool:
        """Whether uniform citywide policy is the wrong instrument here."""
        return self.spread_f >= SPREAD_TARGETED_F

    @property
    def night_critical(self) -> bool:
        return (self.overnight_low_f or 0) >= NIGHT_CRITICAL_F

    def recommendations(self) -> list[dict[str, Any]]:
        """Ranked, quantified interventions. Deterministic -- no model involved.

        Each entry carries the measured quantity that triggered it, so a reader
        can check the recommendation against the number rather than trusting it.
        """
        out: list[dict[str, Any]] = []

        if self.targeted:
            gap = self.spread_f
            pts = canopy_points_for(gap)
            out.append({
                "priority": 1,
                "action": "Target the hottest tiles, not the city",
                "because": (
                    f"{gap:.1f} °F separates the hottest and coolest ground "
                    f"inside this metro's sample box. A uniform citywide "
                    f"programme spends the same effort on both ends of that "
                    f"range."),
                "quantified": (
                    f"Closing the full {gap:.1f} °F gap by canopy alone implies "
                    f"~{pts:.0f} percentage points of added cover in the "
                    f"hottest areas — implausible as a single measure, which is "
                    f"itself the finding: no one intervention closes this gap."),
                "evidence": "measured spread, 100 m tiles",
            })
        else:
            out.append({
                "priority": 1,
                "action": "Uniform citywide measures are defensible here",
                "because": (
                    f"Only {self.spread_f:.1f} °F separates hottest from coolest "
                    f"ground. Conditions are close to uniform, so a single "
                    f"citywide standard is not obviously mistargeted."),
                "quantified": (
                    f"A citywide +10 pt canopy programme yields roughly "
                    f"{c_to_f_delta(CANOPY_C_PER_10PCT):.1f} °F everywhere."),
                "evidence": "measured spread, 100 m tiles",
            })

        if self.night_critical:
            out.append({
                "priority": 2,
                "action": "Night-time cooling capacity, and high-albedo surfaces",
                "because": (
                    f"Overnight low of {self.overnight_low_f:.1f} °F. Mortality "
                    f"tracks the failure of temperature to fall at night rather "
                    f"than the daytime peak — a body that never cools does not "
                    f"recover."),
                "quantified": (
                    f"Residential cool-roof deployment gives about "
                    f"{c_to_f_delta(ALBEDO_C_RESIDENTIAL):.1f} °F of "
                    f"neighbourhood cooling and reduces heat stored in fabric "
                    f"during the day, which is what re-radiates after dark."),
                "evidence": "measured overnight low, 100 m tiles",
            })

        dense_route = (self.daily_high_f or 0) >= 95.0
        out.append({
            "priority": 3,
            "action": ("Cool roofs first in dense districts, canopy where there "
                       "is planting room" if dense_route else
                       "Canopy-led programme, cool roofs where planting is "
                       "impossible"),
            "because": (
                "Canopy delivers roughly 35% more temperature reduction than "
                "cool roofs, but cool roofs reach higher HEAT EXPOSURE reduction "
                "in practice because they deploy in the dense, vulnerable "
                "districts that have no room to plant."),
            "quantified": (
                f"+10 pts canopy ≈ {c_to_f_delta(CANOPY_C_PER_10PCT):.1f} °F; "
                f"residential cool roofs ≈ "
                f"{c_to_f_delta(ALBEDO_C_RESIDENTIAL):.1f} °F. Canopy is "
                f"{CANOPY_VS_ALBEDO:.2f}× stronger per unit of temperature, "
                f"weaker per unit of deployability."),
            "evidence": "published effect sizes, applied to measured values",
        })
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "metro_id": self.metro_id, "name": self.name,
            "climate": self.climate,
            "min_f": self.min_f, "max_f": self.max_f, "mean_f": self.mean_f,
            "spread_f": round(self.spread_f, 2),
            "overnight_low_f": self.overnight_low_f,
            "daily_high_f": self.daily_high_f,
            "targeted": self.targeted,
            "night_critical": self.night_critical,
        }


def from_national(national: dict) -> list[MetroPlan]:
    """Build a plan per metro from the national panel. Widest spread first."""
    day = national.get("design_day")
    out: list[MetroPlan] = []
    for m in national.get("metros", []):
        tcm = (m.get("days", {}).get(day) or {}).get("tcm") or {}
        if tcm.get("max_f") is None or tcm.get("min_f") is None:
            continue
        out.append(MetroPlan(
            metro_id=m["id"], name=m["name"], climate=m.get("zone", ""),
            min_f=tcm["min_f"], max_f=tcm["max_f"],
            mean_f=tcm.get("mean_f", 0.0),
            overnight_low_f=m.get("mean_overnight_low_f"),
            daily_high_f=m.get("mean_daily_high_f")))
    out.sort(key=lambda p: -p.spread_f)
    return out


def zone_priorities(results: dict, population: dict,
                    clause_id: str | None = None) -> list[dict[str, Any]]:
    """Rank a city's own zones for intervention: hot AND populated first.

    Temperature alone ranks empty desert above a dense neighbourhood. Weighting
    by residents is what turns a thermal map into a planning order.
    """
    villages = population.get("villages", population) or {}
    clause = None
    for c in results.get("clauses", []):
        if clause_id is None or c["clause_id"] == clause_id:
            clause = c
            break
    if clause is None:
        return []

    peak: dict[str, dict[str, Any]] = {}
    for det in clause.get("determinations", []):
        for z in det["zones"]:
            v = z["value"] * 9 / 5 + 32 if z.get("units") == "degC" else z["value"]
            cur = peak.get(z["zone_id"])
            if cur is None or v > cur["peak_f"]:
                peak[z["zone_id"]] = {"zone_id": z["zone_id"], "name": z["name"],
                                      "peak_f": v, "day": det["day"]}

    if not peak:
        return []
    hottest = max(p["peak_f"] for p in peak.values())
    coolest = min(p["peak_f"] for p in peak.values())
    span = (hottest - coolest) or 1.0

    rows = []
    for zid, p in peak.items():
        pop = (villages.get(zid) or {}).get("population") or 0
        # Normalised heat x residents. Both terms matter: a hot empty zone and a
        # cool dense one are both lower priority than a hot dense one.
        heat_n = (p["peak_f"] - coolest) / span
        rows.append({**p, "population": pop,
                     "above_coolest_f": round(p["peak_f"] - coolest, 2),
                     "priority_score": round(heat_n * pop)})
    rows.sort(key=lambda r: -r["priority_score"])
    return rows
