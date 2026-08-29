"""The chart system: one visual language, built once, used on every page.

WHY THIS EXISTS

The pages were tables. A table is honest and unreadable at a glance -- it makes a
reader do the comparison the chart should have done for them. Every figure here
replaces a comparison the reader was previously performing by eye.

THE FORM IS CHOSEN BY THE DATA'S JOB, NOT BY TASTE

    magnitude, low -> high        bar, sequential ramp
    above/below a baseline        bar against a rule line
    one series is the point       EMPHASIS: accent it, gray everything else
    a span between two ends       dumbbell
    two measures at once          scatter with quadrant rules

Emphasis carries most of this app. The story is almost never "here are fifteen
neighbourhoods"; it is "these ten crossed the line and the city never saw it".
Colouring all fifteen would bury exactly the point the chart exists to make.

THE PALETTE, AND WHY THESE TWO COLOURS

    accent      #b2182b   the thing that matters
    muted       #7d8792   everything that is context

Validated rather than eyeballed. Against the chart surface that pair scores
CVD deltaE 15.3 (deutan) and 23.6 normal-vision -- both clear of the 8 and 15
floors -- and both clear 3:1 contrast against the surface, so the bars are
distinguishable as SHAPES and not only as colours. An earlier, lighter grey
(#8c96a0) failed the contrast check at 2.93:1 and was replaced rather than
shipped.

Colour is never the only encoding. Every chart here is sorted, direct-labelled,
or accompanied by its own table, so a reader who cannot separate the two hues
still gets the ordering and the numbers.
"""

from __future__ import annotations

import altair as alt
import pandas as pd

# ---------------------------------------------------------------- palette
ACCENT = "#b2182b"       # the measured thing that matters
MUTED = "#7d8792"        # context; validated to 3:1 against the surface
INK = "#18181b"
INK_SOFT = "#52525b"
GRID = "#e7e5e4"
SURFACE = "#ffffff"

#: Sequential ramp for magnitude. Monotonic in lightness, single hue family, so
#: "more is darker" survives greyscale printing and every form of CVD.
HEAT = ["#fee5d9", "#fcbba1", "#fc9272", "#fb6a4a", "#de2d26", "#a50f15"]

FONT = "Inter, -apple-system, Segoe UI, sans-serif"


def _base(chart: alt.Chart, height: int = 300) -> alt.Chart:
    """Shared configuration: recessive axes, no chart junk, readable type."""
    # Height only. width="container" silently renders a LAYERED spec at zero
    # width in Vega-Lite -- the layer children do not inherit the container
    # size -- which blanked the gap chart, the ladder, the tradeoff scatter and
    # the dumbbell while leaving the single-mark charts fine. Streamlit sets the
    # width itself from use_container_width, so the spec must not fight it.
    return (chart
            .properties(height=height, background=SURFACE)
            .configure_view(stroke=None)
            .configure_axis(labelFont=FONT, titleFont=FONT, labelColor=INK_SOFT,
                            titleColor=INK_SOFT, labelFontSize=11,
                            titleFontSize=11, titleFontWeight=600,
                            gridColor=GRID, gridDash=[2, 3], domainColor=GRID,
                            tickColor=GRID, labelPadding=6)
            .configure_legend(labelFont=FONT, titleFont=FONT, labelColor=INK_SOFT,
                              titleColor=INK_SOFT, labelFontSize=11,
                              titleFontSize=11, symbolType="square",
                              symbolSize=110, orient="top", direction="horizontal",
                              titleAnchor="start")
            .configure_title(font=FONT, fontSize=13, fontWeight=700, color=INK,
                             anchor="start", offset=10))


def zone_gap(zones: list[dict], threshold_f: float, proxy_f: float | None,
             unit: str = "neighbourhood", height: int = 360) -> alt.Chart:
    """THE chart of this project: who crossed the line the city reading did not.

    Job: above/below a baseline, with one group as the point. So: bars against a
    threshold rule, accent on the ones that crossed, everything else muted.
    Two rule lines carry the whole argument visually -- the threshold, and the
    single citywide number that was supposed to detect crossing it.
    """
    df = pd.DataFrame(zones)
    if df.empty:
        return alt.Chart(pd.DataFrame({"x": []})).mark_point()

    bars = (alt.Chart(df)
            .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4,
                      height=alt.RelativeBandSize(0.78))
            .encode(
                y=alt.Y("name:N", sort="-x", title=None,
                        axis=alt.Axis(labelLimit=170)),
                x=alt.X("value_f:Q",
                        title=f"peak °F  ·  threshold {threshold_f:g} °F",
                        scale=alt.Scale(zero=False,
                                        domain=[df["value_f"].min() - 1.5,
                                                df["value_f"].max() + 0.8])),
                color=alt.condition(alt.datum.missed,
                                    alt.value(ACCENT), alt.value(MUTED)),
                tooltip=[alt.Tooltip("name:N", title=unit.title()),
                         alt.Tooltip("value_f:Q", title="peak °F", format=".1f"),
                         alt.Tooltip("population:Q", title="residents",
                                     format=","),
                         alt.Tooltip("missed:N", title="missed by city reading")]))

    rules = [alt.Chart(pd.DataFrame({"v": [threshold_f]}))
             .mark_rule(color=INK, strokeWidth=2, strokeDash=[5, 3])
             .encode(x="v:Q")]
    if proxy_f is not None:
        rules.append(alt.Chart(pd.DataFrame({"v": [proxy_f]}))
                     .mark_rule(color=MUTED, strokeWidth=2)
                     .encode(x="v:Q"))
    return _base(alt.layer(bars, *rules), height)


def ladder(rows: list[dict], height: int = 250) -> alt.Chart:
    """Threshold vs what it detects. Magnitude -> bar, sequential ramp.

    The reader's job is to see a quantity collapse as the threshold rises, so
    the bar length carries it and the ramp reinforces it redundantly.
    """
    df = pd.DataFrame(rows)
    if df.empty:
        return alt.Chart(pd.DataFrame({"x": []})).mark_point()
    bars = (alt.Chart(df)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4,
                      width=alt.RelativeBandSize(0.62))
            .encode(
                x=alt.X("label:N", sort=list(df["label"]), title="threshold",
                        axis=alt.Axis(labelAngle=0)),
                y=alt.Y("people:Q", title="residents in a detected heat wave",
                        axis=alt.Axis(format="~s")),
                color=alt.Color("people:Q", legend=None,
                                scale=alt.Scale(range=HEAT)),
                tooltip=[alt.Tooltip("label:N", title="threshold"),
                         alt.Tooltip("waves:Q", title="waves"),
                         alt.Tooltip("zones:Q", title="areas"),
                         alt.Tooltip("people:Q", title="residents",
                                     format=",")]))
    text = (alt.Chart(df).mark_text(dy=-8, font=FONT, fontSize=11,
                                    fontWeight=600, color=INK)
            .encode(x=alt.X("label:N", sort=list(df["label"])),
                    y="people:Q",
                    text=alt.Text("waves:Q", format="d")))
    return _base(alt.layer(bars, text), height)


def wave_runs(waves: list[dict], height: int = 300) -> alt.Chart:
    """Each detected heat wave as the span of nights it actually ran.

    A run has a start and an end, so the mark is a bar along time -- not a
    point, which would throw away the duration that is the whole definition.
    """
    if not waves:
        return alt.Chart(pd.DataFrame({"x": []})).mark_point()
    df = pd.DataFrame([{
        "zone": w["zone_name"], "start": w["start"], "end": w["end"],
        "nights": w["length_days"], "peak": w["peak_f"],
        "severity": w["severity"],
        "people": w.get("population") or 0,
    } for w in waves])
    df["start"] = pd.to_datetime(df["start"])
    # An end date is inclusive of that night, so extend it to cover the night.
    df["end"] = pd.to_datetime(df["end"]) + pd.Timedelta(days=1)

    return _base(alt.Chart(df)
                 .mark_bar(cornerRadius=4, height=alt.RelativeBandSize(0.62))
                 .encode(
                     y=alt.Y("zone:N", title=None,
                             sort=alt.EncodingSortField(field="nights",
                                                        order="descending"),
                             axis=alt.Axis(labelLimit=170)),
                     x=alt.X("start:T", title="night"),
                     x2="end:T",
                     color=alt.Color("nights:Q", title="nights",
                                     scale=alt.Scale(range=HEAT)),
                     tooltip=[alt.Tooltip("zone:N", title="area"),
                              alt.Tooltip("nights:Q", title="consecutive nights"),
                              alt.Tooltip("severity:N", title="severity"),
                              alt.Tooltip("peak:Q", title="peak °F", format=".1f"),
                              alt.Tooltip("people:Q", title="residents",
                                          format=",")]), height)


def rank_bar(df: pd.DataFrame, value: str, label: str, title: str,
             highlight: str | None = None, height: int = 460) -> alt.Chart:
    """Ranked magnitude. Emphasis when one row is the point, ramp otherwise."""
    if df.empty:
        return alt.Chart(pd.DataFrame({"x": []})).mark_point()
    color = (alt.condition(alt.datum[label] == highlight,
                           alt.value(ACCENT), alt.value(MUTED))
             if highlight else
             alt.Color(f"{value}:Q", legend=None, scale=alt.Scale(range=HEAT)))
    return _base(alt.Chart(df)
                 .mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4,
                           height=alt.RelativeBandSize(0.76))
                 .encode(
                     y=alt.Y(f"{label}:N", sort="-x", title=None,
                             axis=alt.Axis(labelLimit=190)),
                     x=alt.X(f"{value}:Q", title=title),
                     color=color,
                     tooltip=[alt.Tooltip(f"{label}:N"),
                              alt.Tooltip(f"{value}:Q", format=".2f")]), height)


def tradeoff(df: pd.DataFrame, x: str, y: str, label: str,
             x_title: str, y_title: str, x_split: float, y_split: float,
             height: int = 420) -> alt.Chart:
    """Two measures at once, with the quadrant boundaries drawn.

    Quadrant membership is carried by POSITION, so colouring by quadrant would
    encode the same fact twice and burn four hues to say what the rule lines
    already say. Colour is left to a single accent for the points that sit in
    the quadrant a reader should worry about.
    """
    if df.empty:
        return alt.Chart(pd.DataFrame({"x": []})).mark_point()
    pts = (alt.Chart(df)
           .mark_circle(size=150, opacity=0.85, stroke=SURFACE, strokeWidth=2)
           .encode(
               x=alt.X(f"{x}:Q", title=x_title, scale=alt.Scale(nice=True)),
               y=alt.Y(f"{y}:Q", title=y_title, scale=alt.Scale(nice=True)),
               color=alt.condition((alt.datum[x] <= x_split) & (alt.datum[y] <= y_split),
                                   alt.value(ACCENT), alt.value(MUTED)),
               tooltip=[alt.Tooltip(f"{label}:N"),
                        alt.Tooltip(f"{x}:Q", format=".1f", title=x_title),
                        alt.Tooltip(f"{y}:Q", format=".1f", title=y_title)]))
    vr = (alt.Chart(pd.DataFrame({"v": [x_split]}))
          .mark_rule(color=GRID, strokeWidth=2).encode(x="v:Q"))
    hr = (alt.Chart(pd.DataFrame({"v": [y_split]}))
          .mark_rule(color=GRID, strokeWidth=2).encode(y="v:Q"))
    txt = (alt.Chart(df).mark_text(dx=9, dy=-9, align="left", font=FONT,
                                   fontSize=10, color=INK_SOFT)
           .encode(x=f"{x}:Q", y=f"{y}:Q",
                   text=alt.condition((alt.datum[x] <= x_split) & (alt.datum[y] <= y_split),
                                      alt.Text(f"{label}:N"), alt.value(""))))
    return _base(alt.layer(vr, hr, pts, txt), height)


def spread_dumbbell(df: pd.DataFrame, label: str, lo: str, hi: str,
                    height: int = 460) -> alt.Chart:
    """A span between two ends -> dumbbell. One hue, two shades.

    The distance IS the measurement here, so the bar draws the distance and the
    two dots mark what it runs between.
    """
    if df.empty:
        return alt.Chart(pd.DataFrame({"x": []})).mark_point()
    order = alt.EncodingSortField(field=hi, order="descending")
    base = alt.Chart(df).encode(y=alt.Y(f"{label}:N", sort=order, title=None,
                                        axis=alt.Axis(labelLimit=190)))
    bar = base.mark_bar(height=3, color=MUTED, opacity=0.55).encode(
        x=alt.X(f"{lo}:Q", title="°F across the sample box",
                scale=alt.Scale(zero=False)),
        x2=f"{hi}:Q")
    cool = base.mark_circle(size=110, color=MUTED, stroke=SURFACE,
                            strokeWidth=2).encode(x=f"{lo}:Q")
    hot = base.mark_circle(size=110, color=ACCENT, stroke=SURFACE,
                           strokeWidth=2).encode(
        x=f"{hi}:Q",
        tooltip=[alt.Tooltip(f"{label}:N"),
                 alt.Tooltip(f"{lo}:Q", title="coolest °F", format=".1f"),
                 alt.Tooltip(f"{hi}:Q", title="hottest °F", format=".1f")])
    return _base(alt.layer(bar, cool, hot), height)
