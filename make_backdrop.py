"""Render the measured temperature field of Phoenix as the site backdrop.

    python make_backdrop.py

Every other option for a page background was decoration: drifting shapes, stock
satellite imagery, a fluid simulation. This one is the project's own data.

It rasterises 272,917 cached FortyGuard tiles -- the exact tiles the headline
number is computed from -- into a single image. So the thing behind every page
is not an illustration OF the measurement; it IS the measurement, at the
resolution the whole argument turns on. A reader who zooms in is looking at real
2 m temperature over Phoenix.

Output is a small, softly blurred PNG. It has to disappear behind text: the
backdrop is evidence that happens to be beautiful, never something competing
with a chart.
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

REPO = Path(__file__).parent
OUT = REPO / "static" / "phoenix_field.png"

#: The cached citywide tcm response and its tile grid. Committed, so this runs
#: offline like everything else here.
RESPONSE = REPO / "data" / "cache" / "responses" / "d9fb9fe5044685699d97.json.gz"

#: Output raster size. Small on purpose -- it is blurred to nothing anyway, and
#: first paint on Streamlit Cloud is the slowest moment of the demo.
W, H = 820, 560


def load(path: Path) -> dict:
    return json.loads(gzip.open(path, "rt", encoding="utf-8").read())


def main() -> int:
    try:
        import numpy as np
        from PIL import Image, ImageFilter
    except ImportError:
        print("needs numpy and pillow:  pip install numpy pillow")
        return 2

    if not RESPONSE.exists():
        print(f"cached response missing: {RESPONSE}")
        return 2

    resp = load(RESPONSE)
    grid = load(REPO / "data" / "cache" / "grids" / f"{resp['grid_key']}.json.gz")
    vals = resp["compact"]["columns"]["average_temperature"]
    geoms = grid["geometries"]
    print(f"  {len(vals):,} tiles  ·  {resp['label']}")

    # Tile centroids. Every tile is a small quad, so the first ring's mean is
    # its centre to well within a pixel at this raster size.
    lon = np.empty(len(geoms), dtype=np.float64)
    lat = np.empty(len(geoms), dtype=np.float64)
    for i, g in enumerate(geoms):
        ring = g["coordinates"][0]
        lon[i] = sum(p[0] for p in ring) / len(ring)
        lat[i] = sum(p[1] for p in ring) / len(ring)
    v = np.asarray(vals, dtype=np.float64)

    ok = np.isfinite(v)
    lon, lat, v = lon[ok], lat[ok], v[ok]
    print(f"  {v.min():.1f} to {v.max():.1f} degC across the AOI")

    # Bin to the raster. Mean per cell, so denser tiles do not out-vote sparse
    # ones -- a sum would draw the sampling pattern rather than the temperature.
    xi = np.clip(((lon - lon.min()) / (lon.max() - lon.min()) * (W - 1)).astype(int),
                 0, W - 1)
    yi = np.clip(((lat.max() - lat) / (lat.max() - lat.min()) * (H - 1)).astype(int),
                 0, H - 1)
    flat = yi * W + xi
    total = np.bincount(flat, weights=v, minlength=W * H)
    count = np.bincount(flat, minlength=W * H)
    field = np.where(count > 0, total / np.maximum(count, 1), np.nan).reshape(H, W)

    # Fill gaps with the field mean so the blur has nothing hard to smear.
    field = np.where(np.isnan(field), np.nanmean(field), field)

    # Rank transform, not a linear stretch. Phoenix is genuinely near-uniform
    # across this AOI -- our own measurement puts the spread at 14.4 degF -- so
    # a linear map paints almost the whole city one colour and the structure
    # that exists is invisible.
    #
    # Ranking is MONOTONIC: hotter ground is still darker everywhere, and no
    # two pixels swap order. Only the spacing between them changes. That makes
    # it honest as a picture of where the heat is, and useless as a lookup for
    # how hot -- which is exactly right for a backdrop, and why the temperature
    # scale is never printed on it.
    flat_f = field.ravel()
    order = np.argsort(np.argsort(flat_f))
    norm = (order / (len(flat_f) - 1)).reshape(field.shape)

    # The same sequential heat ramp the charts use, so the backdrop and the
    # figures speak one visual language rather than two.
    stops = [(0.00, (254, 229, 217)), (0.25, (252, 187, 161)),
             (0.50, (252, 146, 114)), (0.72, (251, 106, 74)),
             (0.88, (222, 45, 38)), (1.00, (165, 15, 21))]
    rgb = np.zeros((H, W, 3), dtype=np.float64)
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        m = (norm >= p0) & (norm <= p1)
        t = np.zeros_like(norm)
        t[m] = (norm[m] - p0) / (p1 - p0)
        for ch in range(3):
            rgb[..., ch][m] = c0[ch] + (c1[ch] - c0[ch]) * t[m]

    img = Image.fromarray(rgb.astype(np.uint8), "RGB")
    img = img.filter(ImageFilter.GaussianBlur(radius=3.0))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, optimize=True)
    print(f"  -> {OUT.relative_to(REPO)}  ({OUT.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
