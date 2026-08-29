"""Prepare the page backdrop: NASA's Earth at Night, framed on North America.

    python make_backdrop.py

WHAT THIS IS

A real satellite composite -- NASA/NOAA VIIRS Day-Night Band aboard Suomi NPP,
the "Black Marble" view of Earth at night. Public domain. Not stock artwork,
not a render, not a simulation.

WHY THIS IMAGE

It is the subject of this project seen from orbit. Every gold point is a city
lit after dark, and the whole finding here concerns what happens in cities AT
NIGHT: overnight lows are what the epidemiological literature ties mortality to,
and what Phoenix's own benchmark is written against. A spinning globe would have
been decoration. This is the phenomenon.

The frame is cropped to North America so Phoenix -- the city under study -- is
actually inside the picture rather than off the edge of a world map.

HOW IT IS TREATED

The source is very dark and the interface is light, so the raster is lifted,
desaturated a little and softened here, then sits under a white scrim in CSS.
What survives is a faint field of city lights. It must read as texture, never as
an image competing with a chart.

CREDIT: NASA Earth Observatory / NOAA, VIIRS Day-Night Band, Suomi NPP.
        NASA material is generally not subject to copyright in the United
        States; attribution is good practice and is carried in the interface.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).parent
SRC = REPO / "data" / "source" / "earth_at_night.jpg"
OUT = REPO / "static" / "backdrop.jpg"

URL = ("https://eoimages.gsfc.nasa.gov/images/imagerecords/79000/79765/"
       "dnb_land_ocean_ice.2012.3600x1800.jpg")

#: The source is equirectangular: x is longitude -180..180, y is latitude
#: 90..-90. These bounds frame North America with Phoenix (-112.07, 33.45)
#: comfortably inside.
WEST, EAST = -128.0, -62.0
NORTH, SOUTH = 52.0, 14.0

#: Wide enough to stay sharp on a large monitor, small enough not to slow first
#: paint on Streamlit Cloud -- the slowest moment of the demo.
OUT_W = 1600


def main() -> int:
    try:
        from PIL import Image, ImageEnhance, ImageFilter
    except ImportError:
        print("needs pillow:  pip install pillow")
        return 2

    if not SRC.exists():
        print(f"source missing: {SRC}\n"
              f"fetch it once:\n  curl -L -o \"{SRC}\" \"{URL}\"")
        return 2

    img = Image.open(SRC).convert("RGB")
    w, h = img.size
    box = (int((WEST + 180.0) / 360.0 * w), int((90.0 - NORTH) / 180.0 * h),
           int((EAST + 180.0) / 360.0 * w), int((90.0 - SOUTH) / 180.0 * h))
    img = img.crop(box)
    print(f"  cropped {img.size[0]}x{img.size[1]} "
          f"({WEST}..{EAST} lon, {SOUTH}..{NORTH} lat)")

    img = img.resize((OUT_W, max(1, int(OUT_W * img.size[1] / img.size[0]))),
                     Image.LANCZOS)

    # Lift the blacks so the image survives a white scrim; drop a little
    # saturation so the city lights read as warm texture rather than a second
    # colour scheme arguing with each page's accent.
    img = ImageEnhance.Brightness(img).enhance(1.55)
    img = ImageEnhance.Color(img).enhance(0.80)
    img = ImageEnhance.Contrast(img).enhance(1.10)
    img = img.filter(ImageFilter.GaussianBlur(radius=0.6))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "JPEG", quality=82, optimize=True, progressive=True)
    print(f"  -> {OUT.relative_to(REPO)}  "
          f"({OUT.stat().st_size / 1024:.0f} KB, {img.size[0]}x{img.size[1]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
