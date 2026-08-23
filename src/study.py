"""Study configuration: the city, the AOI, the zones, the window.

Kept in one place so the UI, the analysis runner and the tests cannot drift
apart on what "the study" means.
"""

from __future__ import annotations

from pathlib import Path

from geo import aoi_area_sq_km, bbox_aoi, sq_km_to_sq_mi

REPO_ROOT = Path(__file__).resolve().parent.parent

CITY = "Phoenix, Arizona"
TIMEZONE_NOTE = "Arizona is UTC-7 year-round; the state does not observe DST."
UTC_OFFSET_H = -7

# Bounding box of the 15 Phoenix urban villages, from the city's own boundary
# file. 1,053 mi2 -- comfortably inside the measured single-call limit, so the
# whole city is one request per (day, analytic, threshold).
AOI_WEST, AOI_SOUTH = -112.3241, 33.2904
AOI_EAST, AOI_NORTH = -111.9255, 33.9582

GRANULARITY_M = 100

PLAN_PDF = REPO_ROOT / "data" / "plan" / "phoenix_2026_heat_response_plan.pdf"
PLAN_TITLE = "City of Phoenix 2026 Heat Response Plan DRAFT (2.13.2026)"
PLAN_URL = ("https://www.phoenix.gov/content/dam/phoenix/heatsite/documents/"
            "2026%20Heat%20Response%20Plan.pdf")

ZONES_PATH = REPO_ROOT / "data" / "zones" / "phoenix_villages_raw.geojson"
ZONE_NAME_FIELD = "NAME"
ZONE_UNIT = "urban village"
ZONES_SOURCE = ("City of Phoenix Open Data, 'Villages' "
                "(https://www.phoenixopendata.com/dataset/villages)")

GOLDEN_CLAUSES = REPO_ROOT / "data" / "golden" / "phoenix_2026_clauses.json"
RESULTS_DIR = REPO_ROOT / "data" / "results"


def city_aoi() -> dict:
    """The single AOI every citywide call uses."""
    return bbox_aoi(AOI_WEST, AOI_SOUTH, AOI_EAST, AOI_NORTH)


def city_aoi_sq_mi() -> float:
    return sq_km_to_sq_mi(aoi_area_sq_km(city_aoi()))


#: Cache key for the tile->zone overlap weights. Bumped if either the AOI or
#: the zone file changes, so stale weights can never be silently reused.
ZONE_WEIGHT_KEY = "phx_villages_x_cityaoi_g100_v1"
