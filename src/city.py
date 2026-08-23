"""City profiles: everything that changes when you point TRIGGER at a new city.

TRIGGER compiles heat plans, not Phoenix's heat plan. Making that claim true
rather than aspirational means every city-specific value lives in one JSON
profile, and nothing city-specific is baked into the pipeline.

A profile supplies:

    identity        name, timezone offset, whether DST applies
    the plan        PDF path, title, source URL, clause-id prefix
    the geography   AOI bounding box, zone file, zone name field
    the vocabulary  the department key the plan itself prints

Add a city by adding ``data/cities/<slug>.json`` plus its plan PDF and zone
boundaries, then set ``TRIGGER_CITY=<slug>``. No code changes.

Hard constraint worth stating up front: the FortyGuard API covers the **United
States only** (documented under Known Limitations, and the reason this project
studies Phoenix rather than a South Asian city, where heat action plans are
most developed). A profile for a non-US city would compile its plan correctly
and then fail at evaluation.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CITIES_DIR = REPO_ROOT / "data" / "cities"

DEFAULT_CITY = os.getenv("TRIGGER_CITY", "phoenix")


@dataclass
class City:
    """One city's complete configuration."""

    slug: str
    name: str

    # ---- plan
    plan_pdf: str
    plan_title: str
    plan_url: str
    clause_prefix: str            # e.g. "PHX-2026"
    golden_clauses: str

    # ---- geography
    aoi_west: float
    aoi_south: float
    aoi_east: float
    aoi_north: float
    zones_path: str
    zone_name_field: str
    zone_unit: str
    zones_source: str

    # ---- time
    utc_offset_h: int
    observes_dst: bool
    timezone_note: str

    # ---- vocabulary
    department_key: dict[str, str] = field(default_factory=dict)
    strategies: dict[str, str] = field(default_factory=dict)

    # ---- optional
    population_path: str | None = None
    granularity_m: int = 100
    default_start: str | None = None
    default_end: str | None = None

    # -------------------------------------------------------------- derived

    @property
    def plan_pdf_path(self) -> Path:
        return REPO_ROOT / self.plan_pdf

    @property
    def zones_full_path(self) -> Path:
        return REPO_ROOT / self.zones_path

    @property
    def golden_path(self) -> Path:
        return REPO_ROOT / self.golden_clauses

    @property
    def population_full_path(self) -> Path | None:
        return REPO_ROOT / self.population_path if self.population_path else None

    @property
    def centre_lat(self) -> float:
        """Latitude used for the local equal-area projection."""
        return (self.aoi_south + self.aoi_north) / 2.0

    @property
    def zone_weight_key(self) -> str:
        """Cache key for tile->zone overlap weights.

        Includes the AOI and granularity so a changed boundary or resolution
        can never silently reuse stale weights.
        """
        box = f"{self.aoi_west:.4f}_{self.aoi_south:.4f}_{self.aoi_east:.4f}_{self.aoi_north:.4f}"
        return f"{self.slug}_{box}_g{self.granularity_m}"

    def aoi(self) -> dict:
        from geo import bbox_aoi

        return bbox_aoi(self.aoi_west, self.aoi_south, self.aoi_east, self.aoi_north)

    def aoi_sq_mi(self) -> float:
        from geo import aoi_area_sq_km, sq_km_to_sq_mi

        return sq_km_to_sq_mi(aoi_area_sq_km(self.aoi()))

    def utc_hour_to_local(self, utc_hour: float) -> float:
        """time_of_measure is UTC; convert to this city's local clock."""
        return (utc_hour + self.utc_offset_h) % 24


def available() -> list[str]:
    if not CITIES_DIR.exists():
        return []
    return sorted(p.stem for p in CITIES_DIR.glob("*.json"))


def load(slug: str | None = None) -> City:
    slug = slug or DEFAULT_CITY
    path = CITIES_DIR / f"{slug}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No city profile {slug!r}. Available: {available() or 'none'}\n"
            f"  Expected {path.relative_to(REPO_ROOT)}")
    d = json.loads(path.read_text(encoding="utf-8"))
    known = {k: v for k, v in d.items() if k in City.__dataclass_fields__}
    return City(slug=slug, **{k: v for k, v in known.items() if k != "slug"})
