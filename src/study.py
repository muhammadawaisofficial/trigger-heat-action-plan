"""The active study: whichever city profile is loaded.

This module is a thin shim over ``city.py``. It exists so the rest of the
pipeline can say ``study.city_aoi()`` without knowing which city is active, and
so importing it has the side effect of pointing the shared vocabularies at the
right city:

    * the clause validator's department key and strategy list
    * the equal-area projection latitude
    * the UTC-to-local hour conversion

Those three were the values that made the pipeline Phoenix-only. They are now
set here, once, from the profile.

Select a city with ``TRIGGER_CITY=<slug>``; profiles live in ``data/cities/``.
"""

from __future__ import annotations

from pathlib import Path

import aggregate
import city as _city
import parse
import schema

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The active city. Everything below is derived from it.
CITY_PROFILE = _city.load()

# ------------------------------------------------------------ side effects
# Point the shared modules at this city before anything else imports them.
schema.set_vocabulary(CITY_PROFILE.department_key, CITY_PROFILE.strategies)
aggregate.set_projection(CITY_PROFILE.centre_lat)
parse.set_utc_offset(CITY_PROFILE.utc_offset_h)

# ----------------------------------------------------- flat names, unchanged
CITY = CITY_PROFILE.name
#: Prefix used in cache labels. Read from the profile so Phoenix keeps the
#: "phx-city" labels its committed cache was written with.
CITY_SLUG = getattr(CITY_PROFILE, "label_prefix", None) or (CITY_PROFILE.slug + "-city")
TIMEZONE_NOTE = CITY_PROFILE.timezone_note
UTC_OFFSET_H = CITY_PROFILE.utc_offset_h

AOI_WEST, AOI_SOUTH = CITY_PROFILE.aoi_west, CITY_PROFILE.aoi_south
AOI_EAST, AOI_NORTH = CITY_PROFILE.aoi_east, CITY_PROFILE.aoi_north
GRANULARITY_M = CITY_PROFILE.granularity_m

PLAN_PDF = CITY_PROFILE.plan_pdf_path
PLAN_TITLE = CITY_PROFILE.plan_title
PLAN_URL = CITY_PROFILE.plan_url
CLAUSE_PREFIX = CITY_PROFILE.clause_prefix

ZONES_PATH = CITY_PROFILE.zones_full_path
ZONE_NAME_FIELD = CITY_PROFILE.zone_name_field
ZONE_UNIT = CITY_PROFILE.zone_unit
ZONES_SOURCE = CITY_PROFILE.zones_source

GOLDEN_CLAUSES = CITY_PROFILE.golden_path
POPULATION_PATH = CITY_PROFILE.population_full_path
RESULTS_DIR = REPO_ROOT / "data" / "results"

ZONE_WEIGHT_KEY = CITY_PROFILE.zone_weight_key

DEFAULT_START = CITY_PROFILE.default_start
DEFAULT_END = CITY_PROFILE.default_end


def city_aoi() -> dict:
    """The single AOI every citywide call uses."""
    return CITY_PROFILE.aoi()


def city_aoi_sq_mi() -> float:
    return CITY_PROFILE.aoi_sq_mi()


def results_path(name: str = "divergence.json") -> Path:
    """Per-city results file, so two cities do not overwrite each other."""
    if CITY_PROFILE.slug == "phoenix":
        return RESULTS_DIR / name          # the published path, unchanged
    return RESULTS_DIR / CITY_PROFILE.slug / name
