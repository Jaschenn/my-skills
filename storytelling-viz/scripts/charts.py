"""storytelling-viz charts: data-driven, production-grade chart functions.

Every function takes a tidy DataFrame + column names and returns a Chart. Nothing about the
layout is hard-coded: label space, axis ranges, tick positions, font size (when rows get
tight), value-label placement (inside / outside a bar), truncation of long labels and
"Other" merging are all computed from the data AND the final panel size, which is only
known when the chart is placed with viz_common.figure() / save().

    from charts import bar_rank
    from viz_common import figure, titled, set_lang
    set_lang("en")
    c = bar_rank(df, "channel", "gmv", highlight="POS", fmt="num")
    figure([[(titled(c, title="POS is the only channel that shrank"), 1)]],
           spec="journal-1col", name="fig1")

All marks are drawn in data coordinates on a blank canvas (theme_canvas): axes, ticks and
gridlines are drawn by the chart itself, so every chart controls its own margins exactly
and panels in a multi-panel figure line up. Add extra plotnine layers with `chart + layer`.
"""
import math

import numpy as np
import pandas as pd

import viz_common as vc
from viz_common import (PAL, INK, MUTED, GRID, mix, zh, text_width, fmt_value, dodge,
                        SizedPanel, readable, ink_on, T, font_for, check_contrast)

SF = 1.7725    # plotnine size unit -> points (sqrt(pi))
GREY = "#b8bec7"          # de-emphasised marks
GREY_LT = "#d9dde3"       # very light marks / "Other"


# ====================================================================== basics
def _base():
    return vc.cur()["base"]


def _pt_lw(points):
    """Line width in points (scaled by the spec) -> plotnine size units."""
    return points * vc.cur().get("lw", 1.0) / SF


def _dot_size(diam_pt, stroke=0.0):
    """plotnine geom_point size for a marker of `diam_pt` points diameter."""
    return max(diam_pt * vc.cur().get("lw", 1.0) ** 0.5 / 2 - stroke, 0.3)


def _tw(s, size, bold=False):
    """Width in inches of the widest line of `s`."""
    return max(text_width(line, size, bold) for line in zh(str(s)).split("\n"))


def _fit_label(s, max_in, size, bold=False):
    """Truncate with an ellipsis so the label fits max_in inches."""
    s = zh(str(s))
    if _tw(s, size, bold) <= max_in:
        return s
    while len(s) > 1 and _tw(s + "…", size, bold) > max_in:
        s = s[:-1]
    return s.rstrip() + "…"


def _match(values, highlight):
    """Boolean list: which items are highlighted. highlight = None | value | list | callable."""
    if highlight is None:
        return [False] * len(values)
    if callable(highlight):
        return [bool(highlight(v)) for v in values]
    hl = set(highlight) if isinstance(highlight, (list, tuple, set)) else {highlight}
    return [v in hl for v in values]


def nice_breaks(lo, hi, n=4):
    """'Nice' tick positions covering [lo, hi] with about n intervals. Returns (ticks, step)."""
    if not np.isfinite(lo) or not np.isfinite(hi):
        return [0.0], 1.0
    if hi == lo:
        hi, lo = hi + (abs(hi) or 1) * 0.5, lo - (abs(lo) or 1) * 0.5
    span = hi - lo
    raw = span / max(n, 1)
    mag = 10 ** math.floor(math.log10(raw))
    step = min((m * mag for m in (0.5, 1, 2, 2.5, 5, 10)),
               key=lambda st: (abs(span / st - n), -span / st))      # closest to n intervals
    start = math.floor(lo / step + 1e-9) * step
    ticks, v = [], start
    while v <= hi + step * 0.999:
        ticks.append(round(v, 12))
        v += step
    return ticks, step


def axis_range(lo, hi, n=4, snap=0.12, pad=0.03):
    """Ticks + axis limits for data in [lo, hi] without wasting space: the axis extends to the
    nearest outer tick only when that tick is within `snap` × span of the data; otherwise it
    stops `pad` × span past the data and the outer tick is dropped (no 61 -> 80 overshoot).
    A limit at exactly 0 stays 0. Returns (ticks, step, lo, hi)."""
    ticks, step = nice_breaks(lo, hi, n)
    span = (hi - lo) or abs(hi) or 1.0
    new_lo = lo if lo == 0 else (ticks[0] if lo - ticks[0] <= snap * span else lo - pad * span)
    new_hi = hi if hi == 0 else (ticks[-1] if ticks[-1] - hi <= snap * span else hi + pad * span)
    ticks = [t for t in ticks if new_lo - 1e-9 <= t <= new_hi + 1e-9]
    return ticks, step, new_lo, new_hi


def _rel_change(a, b):
    """(b - a) / |a|: the sign follows the direction of the change, also when a < 0."""
    return (b - a) / abs(a) if a else np.nan


def tick_label(v, fmt, step):
    """Axis tick text with just enough decimals for the step."""
    if callable(fmt):
        return fmt(v)
    if fmt == "pct":
        nd = 0 if step * 100 >= 1 - 1e-9 else (1 if step * 100 >= 0.1 - 1e-12 else 2)
        return vc.pct(v, nd=nd)
    if fmt == "pp":
        nd = 0 if step * 100 >= 1 - 1e-9 else 1
        return vc.pp(v, signed=v != 0, nd=nd)
    big = max(abs(v), abs(step))
    if fmt == "num" and big >= 1e4:
        u = vc.num(big, style=None)                        # pick the unit from the magnitude
        unit = u[-1] if u[-1] in "亿万BMK" else None
        div = {"亿": 1e8, "万": 1e4, "B": 1e9, "M": 1e6, "K": 1e3}.get(unit, 1)
        nd = 0 if step / div >= 1 - 1e-9 else (1 if step / div >= 0.1 - 1e-12 else 2)
        return vc.num(v, unit=unit, nd=nd)
    nd = 0 if step >= 1 - 1e-9 else (1 if step >= 0.1 - 1e-12 else 2)
    return vc._signed(f"{v:,.{nd}f}", v, False)


class Chart(SizedPanel):
    """A chart whose layout is computed when its final size is known.
    chart.at(w, h) -> plotnine ggplot.  chart + layer -> adds plotnine layers/themes.
    chart.legend: a markup legend line ("[A](brand) | [B](focus)") for titled(...)."""
    def __init__(self, build, legend=None):
        self._build, self.extra, self.legend = build, [], legend

    def __add__(self, other):
        c = Chart(self._build, self.legend)
        c.extra = self.extra + [other]
        return c

    def at(self, w, h):
        p = self._build(w, h)
        for e in self.extra:
            p = p + e
        return p


class Frame:
    """Maps the data rectangle xr × yr onto the panel, leaving `left/right/top/bottom` inches
    outside it for labels. dx/dy convert inches to data units."""
    def __init__(self, w, h, xr, yr, left=0.0, right=0.0, top=0.0, bottom=0.0, name="chart",
                 quiet=False):
        dw, dh = w - left - right, h - top - bottom
        if (dw < 0.25 * w or dh < 0.25 * h) and not quiet:
            print(f"WARNING {name}: labels take most of the panel ({dw:.2f} x {dh:.2f} in left "
                  "for data); give the panel more room or shorten labels.")
        dw, dh = max(dw, 0.15 * w), max(dh, 0.15 * h)
        x0, x1 = xr
        y0, y1 = yr
        if x1 == x0:
            x0, x1 = x0 - 0.5, x1 + 0.5
        if y1 == y0:
            y0, y1 = y0 - 0.5, y1 + 0.5
        self.kx, self.ky = (x1 - x0) / dw, (y1 - y0) / dh
        self.xr, self.yr = (x0, x1), (y0, y1)
        self.xlim = (x0 - left * self.kx, x1 + right * self.kx)
        self.ylim = (y0 - bottom * self.ky, y1 + top * self.ky)

    def dx(self, inches):
        return inches * self.kx

    def dy(self, inches):
        return inches * self.ky


class Canvas:
    """Collects marks in data coordinates and emits a few vectorised plotnine layers."""
    def __init__(self):
        self.R, self.S, self.P, self.Tx, self.L, self.B = [], [], [], [], [], []

    def rect(self, x0, x1, y0, y1, fill, color=None, lw_pt=0.0, lt="solid"):
        self.R.append(dict(xmin=min(x0, x1), xmax=max(x0, x1), ymin=min(y0, y1),
                           ymax=max(y0, y1), fill=fill, color=color or fill,
                           size=_pt_lw(lw_pt) if color else 0.0, lt=lt))

    def seg(self, x0, x1, y0, y1, color, lw_pt=0.75, lt="solid", end="butt"):
        self.S.append(dict(x=x0, xend=x1, y=y0, yend=y1, color=color, size=_pt_lw(lw_pt),
                           lt=lt, end=end))

    def pt(self, x, y, color, fill=None, diam_pt=6.0, stroke_pt=0.0):
        st = stroke_pt / SF
        self.P.append(dict(x=x, y=y, color=color, fill=fill or color,
                           size=_dot_size(diam_pt, st), stroke=st))

    def text(self, x, y, s, color=INK, size=None, bold=False, ha="left", va="center",
             italic=False, check=True, angle=0):
        s = zh(str(s))
        size = size or _base()
        if check:
            check_contrast(color, size, bold, s)
        self.Tx.append(dict(x=x, y=y, label=s, color=color, size=size, bold=bold, ha=ha, va=va,
                            italic=italic, family=font_for(s), angle=angle))

    def line(self, xs, ys, color, lw_pt=1.5, lt="solid"):
        gid = len(self.L)
        for x, y in zip(xs, ys):
            self.L.append(dict(x=x, y=y, g=gid, color=color, size=_pt_lw(lw_pt), lt=lt))

    def band(self, xs, lo, hi, fill):
        gid = len(self.B)
        for x, a, b in zip(xs, lo, hi):
            self.B.append(dict(x=x, ymin=a, ymax=b, g=gid, fill=fill))

    def layers(self):
        from plotnine import (aes, geom_rect, geom_segment, geom_point, geom_path, geom_ribbon,
                              geom_text, geom_blank, scale_color_identity, scale_fill_identity,
                              scale_size_identity)
        out = [geom_blank(aes(x="x", y="y"), data=pd.DataFrame({"x": [0.0], "y": [0.0]}),
                          inherit_aes=False)]
        if self.B:
            d = pd.DataFrame(self.B)
            out.append(geom_ribbon(aes(x="x", ymin="ymin", ymax="ymax", group="g", fill="fill"),
                                   data=d, inherit_aes=False, color="none"))
        if self.R:
            d = pd.DataFrame(self.R)
            for lt, g in d.groupby("lt", sort=False):
                out.append(geom_rect(aes(xmin="xmin", xmax="xmax", ymin="ymin", ymax="ymax",
                                         fill="fill", color="color", size="size"),
                                     data=g, inherit_aes=False, linetype=lt))
        if self.S:
            d = pd.DataFrame(self.S)
            for (lt, end), g in d.groupby(["lt", "end"], sort=False):
                out.append(geom_segment(aes(x="x", xend="xend", y="y", yend="yend",
                                            color="color", size="size"),
                                        data=g, inherit_aes=False, linetype=lt, lineend=end))
        if self.L:
            d = pd.DataFrame(self.L)
            for lt, g in d.groupby("lt", sort=False):
                out.append(geom_path(aes(x="x", y="y", group="g", color="color", size="size"),
                                     data=g, inherit_aes=False, linetype=lt,
                                     lineend="round", linejoin="round"))
        if self.P:
            d = pd.DataFrame(self.P)
            for st, g in d.groupby("stroke", sort=False):
                out.append(geom_point(aes(x="x", y="y", color="color", fill="fill", size="size"),
                                      data=g, inherit_aes=False, shape="o", stroke=st))
        if self.Tx:
            d = pd.DataFrame(self.Tx)
            keys = ["family", "bold", "italic", "ha", "va", "size", "angle"]
            for (fam, bold, ital, ha, va, size, ang), g in d.groupby(keys, sort=False):
                kw = dict(fontstyle="italic") if ital else {}
                if ang:
                    kw["angle"] = ang
                out.append(geom_text(aes(x="x", y="y", label="label", color="color"), data=g,
                                     inherit_aes=False, family=fam, size=size, ha=ha, va=va,
                                     fontweight="bold" if bold else "normal", lineheight=1.15,
                                     **kw))
        out += [scale_color_identity(), scale_fill_identity(), scale_size_identity()]
        return out

    def plot(self, fr):
        from plotnine import ggplot, scale_x_continuous, scale_y_continuous
        p = ggplot()
        for layer in self.layers():
            p = p + layer
        return (p + scale_x_continuous(limits=fr.xlim, expand=(0, 0))
                + scale_y_continuous(limits=fr.ylim, expand=(0, 0))
                + vc.theme_canvas(_base()))


def _row_font(h_in, n, name, rel=1.0, gap=1.55):
    """Font size for one text row per category; shrink (to 70%) when rows are tight."""
    s = _base() * rel
    fit = h_in / max(n, 1) * 72 / gap
    if fit < s:
        if fit < _base() * 0.7:
            print(f"WARNING {name}: {n} rows do not fit in {h_in:.2f} in at a readable size; "
                  "use top_n=, a taller panel, or fewer categories.")
        s = max(fit, _base() * 0.7)
    return s


def _y_axis(cv, fr, ticks, labels, size, grid=True, x_text=None):
    x_text = fr.xr[0] - fr.dx(0.06) if x_text is None else x_text
    for t, lab in zip(ticks, labels):
        if fr.yr[0] - 1e-9 <= t <= fr.yr[1] + 1e-9:
            if grid:
                cv.seg(fr.xr[0], fr.xr[1], t, t, GRID, 0.5)
            cv.text(x_text, t, lab, MUTED, size, ha="right")


def _x_axis(cv, fr, ticks, labels, size, baseline=True, edge_align=False):
    """edge_align=True: a label sitting on the left / right edge of the data area is aligned
    left / right instead of centred, so it can't collide with the lowest y tick label."""
    span = (fr.xr[1] - fr.xr[0]) or 1.0
    for t, lab in zip(ticks, labels):
        if fr.xr[0] - 1e-9 <= t <= fr.xr[1] + 1e-9:
            ha = "center"
            if edge_align and abs(t - fr.xr[0]) < 1e-9 * span + 1e-12:
                ha = "left"
            elif edge_align and abs(t - fr.xr[1]) < 1e-9 * span + 1e-12:
                ha = "right"
            cv.text(t, fr.yr[0] - fr.dy(0.05), lab, MUTED, size, ha=ha, va="top")
    if baseline:
        cv.seg(fr.xr[0], fr.xr[1], fr.yr[0], fr.yr[0], MUTED, 0.6)


def _spread(vals, gap, lo, hi):
    """dodge() + keep the labels inside [lo, hi]; returns (positions, new_lo, new_hi) where
    the range is widened only if the labels cannot fit otherwise."""
    pos = dodge(vals, gap)
    if not pos:
        return pos, lo, hi
    need_lo, need_hi = min(pos) - gap / 2, max(pos) + gap / 2
    if need_hi - need_lo > hi - lo:                 # cannot fit: widen symmetrically
        return pos, min(lo, need_lo), max(hi, need_hi)
    shift = max(0.0, lo - need_lo) - max(0.0, need_hi - hi)
    return [p + shift for p in pos], lo, hi


def _max_w(labels, size, bold=False):
    return max((_tw(l, size, bold) for l in labels), default=0.0)


def _lines(s):
    return str(s).count("\n") + 1


def _colors_for(names, highlight, color, n_cat_ok=5, name="chart"):
    """Mark colour per item: highlighted -> color/focus, others grey; no highlight -> brand
    (one series) or categorical (<= 5)."""
    hl = _match(names, highlight)
    if any(hl):
        return [(color or PAL.focus) if h else GREY for h in hl], hl
    if len(names) == 1:
        return [color or PAL.brand], hl
    if len(names) <= n_cat_ok:
        return PAL.categorical(len(names)), hl
    print(f"WARNING {name}: {len(names)} series without highlight= -> all grey; "
          "pass highlight= or use small_multiples().")
    return [mix(MUTED, "#ffffff", 0.3)] * len(names), hl


# ====================================================================== bar_rank
def bar_rank(df, cat, value, highlight=None, color=None, top_n=None, other=None, fmt="num",
             nd=None, sort=True, show_values=True, bar=0.68):
    """Horizontal ranked bars (ranking, composition at one point in time, any signed value).
    highlight: category / list / callable -> focus colour (others grey). top_n: keep the
    largest top_n-1 and merge the rest into `other` ("Other"/"其他"), drawn last in light grey.
    Value labels go inside the bar end when they fit, else just outside."""
    d0 = df[[cat, value]].dropna().groupby(cat, sort=False, as_index=False)[value].sum()
    if sort:
        d0 = d0.sort_values(value, ascending=False, kind="stable")
    other = other or T("其他", "Other")
    is_other = [False] * len(d0)
    if top_n and len(d0) > top_n:
        head, tail = d0.iloc[:top_n - 1], d0.iloc[top_n - 1:]
        d0 = pd.concat([head, pd.DataFrame({cat: [other], value: [tail[value].sum()]})])
        is_other = [False] * len(head) + [True]
    names, vals = [str(c) for c in d0[cat]], [float(v) for v in d0[value]]

    def build(w, h):
        n = len(vals)
        s = _row_font(h, n, "bar_rank")
        sv = s * 0.92
        hl = _match(names, highlight)
        any_hl = any(hl)
        labs = [_fit_label(nm, 0.38 * w, s, b) for nm, b in zip(names, hl)]
        vlabs = [fmt_value(v, fmt, nd) for v in vals]
        lab_w = _max_w(labs, s, True) + 0.1
        val_w = (_max_w(vlabs, sv, True) + 0.08) if show_values else 0.04
        vmin, vmax = min(0.0, min(vals)), max(0.0, max(vals))
        neg_w = val_w if vmin < 0 else 0.0
        fr = Frame(w, h, (vmin, vmax), (-0.5, n - 0.5), left=lab_w + neg_w,
                   right=val_w if vmax > 0 else 0.05, name="bar_rank")
        cv = Canvas()
        for i, (nm, v, lab, vl, h_i, oth) in enumerate(zip(names, vals, labs, vlabs, hl, is_other)):
            y = n - 1 - i
            fill = (GREY_LT if oth else (color or PAL.focus) if h_i
                    else GREY if any_hl else (color or PAL.brand))
            cv.rect(0, v, y - bar / 2, y + bar / 2, fill)
            cv.text(fr.xr[0] - fr.dx(neg_w + 0.08), y, lab,
                    readable(fill) if h_i else (MUTED if any_hl or oth else INK), s,
                    bold=h_i, ha="right")
            if not show_values:
                continue
            sign = 1 if v >= 0 else -1
            inside = abs(v) / fr.kx > _tw(vl, sv, h_i) + 0.14
            if inside:
                cv.text(v - sign * fr.dx(0.06), y, vl, ink_on(fill), sv, bold=h_i,
                        ha="right" if sign > 0 else "left", check=False)
            else:
                cv.text(v + sign * fr.dx(0.05), y, vl, readable(fill) if h_i else MUTED, sv,
                        bold=h_i, ha="left" if sign > 0 else "right")
        if vmin < 0:
            cv.seg(0, 0, -0.5, n - 0.5, MUTED, 0.6)
        return cv.plot(fr)
    return Chart(build)


# ====================================================================== line_trend
def _x_positions(xs):
    """Map an x column to numeric positions + tick labels. Datetimes -> monthly labels when
    the data is monthly, else dates; strings/categories -> 0..n-1 in order of appearance."""
    s = pd.Series(xs)
    if pd.api.types.is_datetime64_any_dtype(s):
        u = sorted(s.dropna().unique())
        u = pd.to_datetime(pd.Series(u))
        monthly = len(u) > 1 and (u.dt.day.nunique() == 1)
        pos = {v: i for i, v in enumerate(u)}
        if monthly:
            per = [(d.year, d.month) for d in u]
            labs = _MonthLabels(per)
        else:
            labs = [d.strftime("%m/%d") if vc.LANG == "zh" else d.strftime("%b %d") for d in u]
        return [pos[v] for v in pd.to_datetime(s)], list(range(len(u))), labs
    if pd.api.types.is_numeric_dtype(s):
        return list(s.astype(float)), None, None
    cats = list(s.cat.categories) if hasattr(s, "cat") else list(dict.fromkeys(s))
    pos = {c: i for i, c in enumerate(cats)}
    return [pos[v] for v in s], list(range(len(cats))), [str(c) for c in cats]


class _MonthLabels(list):
    """Month tick labels that re-derive the two-tier year marks after thinning."""
    def __init__(self, periods):
        super().__init__(vc.month_labels(periods))
        self.periods = periods

    def subset(self, idx):
        return vc.month_labels([self.periods[i] for i in idx])


def _thin(ticks, labels, max_n):
    if len(ticks) <= max_n:
        return list(ticks), list(labels)
    k = math.ceil(len(ticks) / max_n)
    keep = list(range(len(ticks) - 1, -1, -k))[::-1]       # always keep the last tick
    labs = labels.subset(keep) if isinstance(labels, _MonthLabels) else [labels[i] for i in keep]
    return [ticks[i] for i in keep], labs


def _runs(g, xcol, step):
    """Split a sorted series where an x step is missing (NaN rows were dropped), so gaps
    show as breaks instead of being silently bridged."""
    xs = g[xcol].values
    cut = np.where(np.diff(xs) > step * 1.5)[0] + 1
    return [g.iloc[a:b] for a, b in zip(np.r_[0, cut], np.r_[cut, len(g)])]


def _y_range(vals, zero="auto", pad=0.06):
    lo, hi = float(np.nanmin(vals)), float(np.nanmax(vals))
    if zero is True or (zero == "auto" and lo >= 0 and lo < 0.35 * hi):
        lo = 0.0
    if zero == "auto" and hi <= 0 and hi > 0.35 * lo:
        hi = 0.0
    span = (hi - lo) or abs(hi) or 1.0
    return lo - (pad * span if lo != 0 else 0), hi + pad * span


def line_trend(df, x, y, group=None, highlight=None, colors=None, band=None, fmt="num",
               nd=None, label_ends=True, end_values=True, ref=None, zero="auto",
               mark_last=True, x_labels=None, gaps=True):
    """Time series / ordered x. One or more lines with direct end labels (no legend).
    group: series column. highlight: series to emphasise (others become grey context).
    band: (low_col, high_col) -> uncertainty ribbon. ref: y value or (y, label) reference.
    zero: 'auto' (snap the axis to 0 when the data starts near it) | True | False.
    x may be datetime (monthly data gets month labels), numeric or ordered categories.
    gaps=True: a missing period (NaN / absent row) breaks the line instead of bridging it;
    set gaps=False for data that legitimately skips periods (e.g. business days only)."""
    d = df.copy()
    gcol = group or "__g"
    if group is None:
        d[gcol] = str(y)
    d = d.dropna(subset=[y])
    xpos, tks, tlabs = _x_positions(d[x])
    d["__x"] = xpos
    names = list(dict.fromkeys(d[gcol]))
    base_cols, hl = _colors_for(names, highlight, None, name="line_trend")
    cmap = dict(zip(names, base_cols))
    if colors:
        cmap.update(colors)
    any_hl = any(hl)
    vals = list(d[y])
    if band:
        vals += list(d[band[0]].dropna()) + list(d[band[1]].dropna())
    if ref is not None:
        vals.append(ref[0] if isinstance(ref, tuple) else ref)

    def build(w, h):
        s = _base()
        sv = s * 0.88
        ylo, yhi = _y_range(vals, zero)
        yt, ystep = nice_breaks(ylo, yhi, 4 if h > 2.2 else 3)
        yt = [t for t in yt if ylo - 1e-9 <= t <= yhi + 1e-9]
        ylabs = [tick_label(t, fmt, ystep) for t in yt]
        xmin, xmax = float(d["__x"].min()), float(d["__x"].max())
        if tks is None:
            xt, xstep = nice_breaks(xmin, xmax, 5)
            xt = [t for t in xt if xmin - 1e-9 <= t <= xmax + 1e-9]
            xl = [tick_label(t, "num", xstep) for t in xt]
        else:
            xt, xl = list(tks), (x_labels or tlabs)
        y_w = _max_w(ylabs, sv) + 0.1
        n_lab = len(names) if (len(names) <= 6 or not any_hl) else sum(hl)
        last = d.sort_values("__x").groupby(gcol, sort=False).tail(1).set_index(gcol)
        labelled = [nm for nm, h_i in zip(names, hl) if label_ends and (len(names) <= 6 or h_i)]
        end_txt = {nm: (zh(nm) + ("  " + fmt_value(last.loc[nm, y], fmt, nd) if end_values else "")
                        if len(names) > 1 or not end_values
                        else fmt_value(last.loc[nm, y], fmt, nd)) for nm in labelled}
        right = (_max_w(end_txt.values(), s, True) + 0.14) if labelled else 0.1
        if xl:
            right = max(right, _tw(xl[-1], sv) / 2 + 0.04)
            y_w = max(y_w, _tw(xl[0], sv) / 2 + 0.04)
        x_lines = max((_lines(l) for l in xl), default=1)
        bottom = x_lines * sv * 1.25 / 72 + 0.08
        avail_w = w - y_w - right
        max_ticks = max(2, int(avail_w / (_max_w(xl, sv) + 0.15)))
        xt, xl = _thin(xt, xl, max_ticks)
        fr = Frame(w, h, (xmin, xmax), (ylo, yhi), left=y_w, right=right, top=0.06,
                   bottom=bottom, name="line_trend")
        cv = Canvas()
        _y_axis(cv, fr, yt, ylabs, sv)
        _x_axis(cv, fr, xt, xl, sv, baseline=ylo < 0 < yhi or ylo == 0)
        if ylo < 0 < yhi:
            cv.seg(fr.xr[0], fr.xr[1], 0, 0, MUTED, 0.6)
        if ref is not None:
            rv, rl = ref if isinstance(ref, tuple) else (ref, None)
            cv.seg(fr.xr[0], fr.xr[1], rv, rv, MUTED, 0.8, lt="dashed")
            if rl:
                cv.text(fr.xr[0] + fr.dx(0.04), rv + fr.dy(0.03), rl, MUTED, sv * 0.95, va="bottom")
        ux = np.unique(d["__x"].values)
        step_x = float(np.min(np.diff(ux))) if len(ux) > 1 else 1.0
        order = [nm for nm, h_i in zip(names, hl) if not h_i] + [nm for nm, h_i in zip(names, hl) if h_i]
        for nm in order:
            g = d[d[gcol] == nm].sort_values("__x")
            col = cmap[nm]
            emph = (nm in [n for n, h_i in zip(names, hl) if h_i]) or not any_hl
            lw = 2.2 if (any_hl and emph) else (1.7 if emph else 1.0)
            if band:
                gb = g.dropna(subset=list(band))
                cv.band(gb["__x"], gb[band[0]], gb[band[1]], mix(col, "#ffffff", 0.78))
            if len(g) == 1:
                cv.pt(g["__x"].iloc[0], g[y].iloc[0], col, diam_pt=5)
            else:
                for part in (_runs(g, "__x", step_x) if gaps else [g]):   # missing periods break the line
                    if len(part) == 1:
                        cv.pt(part["__x"].iloc[0], part[y].iloc[0], col, diam_pt=3.5)
                    else:
                        cv.line(part["__x"], part[y], col, lw)
            if mark_last and nm in labelled:
                cv.pt(g["__x"].iloc[-1], g[y].iloc[-1], col, diam_pt=5.5 if emph else 4)
        if labelled:
            ys = [float(last.loc[nm, y]) for nm in labelled]
            gap = s * 1.25 / 72 * fr.ky
            ly, _, _ = _spread(ys, gap, fr.ylim[0], fr.ylim[1])
            for nm, yy in zip(labelled, ly):
                col = cmap[nm]
                emph = not any_hl or nm in [n for n, h_i in zip(names, hl) if h_i]
                cv.text(xmax + fr.dx(0.1), yy, end_txt[nm], readable(col) if emph else MUTED,
                        s, bold=emph and len(names) > 1)
        return cv.plot(fr)
    legend = None
    return Chart(build, legend)


# ====================================================================== dumbbell
def dumbbell(df, cat, start, end, labels=None, highlight=None, color=None,
             fmt="num", nd=None, sort=True, show_change="pct"):
    """Two values per category: hollow grey dot = start, filled dot = end, joined by a line.
    Sorted by the end value. Highlighted rows get `color` (default focus) and a change label.
    labels: (start, end) names for the legend (default 之前/之后 · Before/After).
    show_change: 'pct' | 'abs' | None -> appended to the value label of every row."""
    d = df[[cat, start, end]].dropna()
    if sort:
        d = d.sort_values(end, ascending=False, kind="stable")
    names = [str(c) for c in d[cat]]
    v0, v1 = list(d[start].astype(float)), list(d[end].astype(float))
    hl_col = color or PAL.focus
    labels = labels or (T("之前", "Before"), T("之后", "After"))
    # the filled dot is focus on highlighted rows (grey elsewhere), brand when nothing is
    # highlighted; named colours resolve at render time, so the legend follows set_palette()
    end_c = (color or "focus") if any(_match(names, highlight)) else "brand"
    legend = f"[{labels[1]} ●]({end_c}) | {labels[0]} ○"

    def build(w, h):
        n = len(names)
        s = _row_font(h, n, "dumbbell")
        sv = s * 0.9
        hl = _match(names, highlight)
        any_hl = any(hl)

        def vlab(a, b):
            t = fmt_value(b, fmt, nd)
            if show_change == "pct" and a:
                t += f" ({vc.pct(_rel_change(a, b), True, 0)})"
            elif show_change == "abs":
                t += f" ({fmt_value(b - a, fmt, nd) if b - a < 0 else '+' + fmt_value(b - a, fmt, nd)})"
            return t
        vl = [vlab(a, b) for a, b in zip(v0, v1)]
        labs = [_fit_label(nm, 0.36 * w, s, h_i) for nm, h_i in zip(names, hl)]
        lo, hi = min(v0 + v1), max(v0 + v1)
        if lo >= 0 and lo < 0.3 * hi:
            lo = 0.0
        xt, xs, lo, hi = axis_range(lo, hi, 4)
        top = sv * 1.3 / 72 + 0.05
        fr = Frame(w, h, (lo, hi), (-0.5, n - 0.5), left=_max_w(labs, s, True) + 0.12,
                   right=_max_w(vl, sv, True) + 0.14, top=top, name="dumbbell")
        cv = Canvas()
        for t in xt:
            cv.text(t, n - 0.5 + fr.dy(0.04), tick_label(t, fmt, xs), MUTED, sv * 0.92,
                    ha="center", va="bottom")
            cv.seg(t, t, -0.5, n - 0.5, GRID, 0.4)
        for i, (nm, a, b, lab, txt_, h_i) in enumerate(zip(names, v0, v1, labs, vl, hl)):
            y = n - 1 - i
            c1 = hl_col if h_i else (GREY if any_hl else PAL.brand)
            cv.seg(a, b, y, y, mix(c1, "#ffffff", 0.55) if h_i else GRID, 2.6 if h_i else 2.0,
                   end="round")
            cv.pt(a, y, MUTED, "#ffffff", diam_pt=6, stroke_pt=1.0)
            cv.pt(b, y, c1, diam_pt=7)
            cv.text(fr.xr[0] - fr.dx(0.08), y, lab, readable(c1) if h_i else (MUTED if any_hl else INK),
                    s, bold=h_i, ha="right")
            cv.text(max(a, b) + fr.dx(0.09), y, txt_, readable(c1) if h_i else MUTED, sv, bold=h_i)
        return cv.plot(fr)
    return Chart(build, legend)


# ====================================================================== slope
def slope(df, cat, start, end, labels=("Before", "After"), highlight=None, groups=None,
          group_colors=None, fmt="num", nd=None, mode="value"):
    """Slope chart for two time points. mode='value' plots the raw values; mode='change'
    plots % change from start (every line starts at 0) -- use when sizes differ a lot.
    groups: column whose values colour the lines (<= 5 groups); highlight: rows to emphasise."""
    d = df[[cat, start, end] + ([groups] if groups else [])].dropna()
    names = [str(c) for c in d[cat]]
    a = list(d[start].astype(float))
    b = list(d[end].astype(float))
    if mode == "change":
        zero = [nm for nm, x in zip(names, a) if not x]
        if zero:
            print(f"WARNING slope: % change undefined for start = 0, rows dropped: "
                  f"{', '.join(zero[:5])}{' …' if len(zero) > 5 else ''}; use mode='value'.")
            keep = [i for i, x in enumerate(a) if x]
            names, a, b = [names[i] for i in keep], [a[i] for i in keep], [b[i] for i in keep]
            d = d.iloc[keep]
        b = [_rel_change(x, y) for x, y in zip(a, b)]
        a = [0.0] * len(a)
        vfmt = lambda v: vc.pct(v, True, 0)
    else:
        vfmt = lambda v: fmt_value(v, fmt, nd)
    if groups:
        gnames = list(dict.fromkeys(d[groups]))
        gcol = dict(zip(gnames, PAL.categorical(len(gnames))))
        if group_colors:
            gcol.update(group_colors)
        cols = [gcol[g] for g in d[groups]]
        legend = " | ".join(f"[{g}]({gcol[g]})" for g in gnames)
    else:
        cols, legend = None, None

    def build(w, h):
        n = len(names)
        s = _row_font(h * 0.8, n, "slope", rel=0.92)
        hl = _match(names, highlight)
        any_hl = any(hl)
        colr = [(c if c else (PAL.focus if h_i else (GREY if any_hl else PAL.brand)))
                for c, h_i in zip(cols or [None] * n, hl)]
        if cols and any_hl:
            colr = [c if h_i else GREY for c, h_i in zip(colr, hl)]
        left_t = [f"{zh(nm)}  {vfmt(v)}" if mode == "value" else "" for nm, v in zip(names, a)]
        right_t = [f"{vfmt(v)}  {zh(nm)}" for nm, v in zip(names, b)]
        lw_ = (_max_w(left_t, s, True) + 0.12) if mode == "value" else (_tw("0%", s) + 0.12)
        rw_ = _max_w(right_t, s, True) + 0.12
        lo, hi = min(a + b), max(a + b)
        span = (hi - lo) or (abs(hi) * 0.1 or 1.0)
        top = s * 1.4 / 72 + 0.06
        yr = (lo - 0.04 * span, hi + 0.04 * span)
        for _ in range(3):                          # widen the y range until the labels fit
            fr = Frame(w, h, (0, 1), yr, left=lw_, right=rw_, top=top, bottom=0.04, name="slope")
            gap = s * 1.2 / 72 * fr.ky
            _, l0, l1 = _spread(a, gap, *yr)
            _, r0, r1 = _spread(b, gap, *yr)
            new = (min(l0, r0), max(l1, r1))
            if new == yr:
                break
            yr = new
        cv = Canvas()
        yh = fr.yr[1] + fr.dy(0.05)
        cv.text(0, yh, labels[0], MUTED, s * 0.95, ha="center", va="bottom", bold=True)
        cv.text(1, yh, labels[1], MUTED, s * 0.95, ha="center", va="bottom", bold=True)
        gap = s * 1.2 / 72 * fr.ky
        lys = _spread(a, gap, *fr.yr)[0]
        rys = _spread(b, gap, *fr.yr)[0]
        idx = sorted(range(n), key=lambda i: hl[i])            # highlighted drawn last
        for i in idx:
            emph = hl[i] or not any_hl
            cv.line([0, 1], [a[i], b[i]], colr[i], 2.2 if (hl[i]) else (1.5 if emph else 1.0))
            cv.pt(0, a[i], colr[i], diam_pt=4.5)
            cv.pt(1, b[i], colr[i], diam_pt=4.5)
        if mode == "change":
            cv.text(-fr.dx(0.08), 0, "0%", MUTED, s, ha="right")
        for i in range(n):
            emph = hl[i] or not any_hl
            tc = readable(colr[i]) if emph else MUTED
            if mode == "value":
                cv.text(-fr.dx(0.08), lys[i], left_t[i], tc, s, bold=hl[i], ha="right")
            cv.text(1 + fr.dx(0.08), rys[i], right_t[i], tc, s, bold=hl[i])
        return cv.plot(fr)
    return Chart(build, legend)


# ====================================================================== range_dot
def range_dot(df, cat, low, high, value, flag="outside", bench=None, fmt="num", nd=None,
              sort=True, color=None):
    """Actual value vs an expected range (forecast band, target range, peer range).
    flag: 'outside' | 'below' | 'above' | None -> flagged rows: solid focus dot + tinted range
    + bold name; others: hollow dot, grey range. bench: name of a benchmark row (drawn dark)."""
    d = df[[cat, low, high, value]].dropna()
    if sort:
        d = d.sort_values(value, ascending=False, kind="stable")
    names = [str(c) for c in d[cat]]
    lo_, hi_, v_ = (list(d[c].astype(float)) for c in (low, high, value))
    fc = color or PAL.focus

    def is_flag(l, h_, v):
        return {"outside": v < l or v > h_, "below": v < l, "above": v > h_}.get(flag, False)

    def build(w, h):
        n = len(names)
        s = _row_font(h, n, "range_dot")
        sv = s * 0.9
        flags = [is_flag(l, h_, v) for l, h_, v in zip(lo_, hi_, v_)]
        labs = [_fit_label(nm, 0.36 * w, s, f) for nm, f in zip(names, flags)]
        vls = [fmt_value(v, fmt, nd) for v in v_]
        lo, hi = min(lo_ + v_), max(hi_ + v_)
        xt, xs, lo, hi = axis_range(lo, hi, 5)
        lab_w = _max_w(labs, s, True) + 0.12
        val_w = _max_w(vls, sv, True) + 0.1
        top = sv * 1.3 / 72 + 0.05
        fr = Frame(w, h, (lo, hi), (-0.5, n - 0.5), left=lab_w + val_w, right=0.1, top=top,
                   name="range_dot")
        thick = min(h / n * 72 * 0.42, 9.0)
        cv = Canvas()
        for t in xt:
            cv.text(t, n - 0.5 + fr.dy(0.04), tick_label(t, fmt, xs), MUTED, sv * 0.92,
                    ha="center", va="bottom")
        for i, (nm, l, h_, v, lab, vl, f) in enumerate(zip(names, lo_, hi_, v_, labs, vls, flags)):
            y = n - 1 - i
            is_b = bench is not None and nm == str(bench)
            band_c = mix(fc, "#ffffff", 0.6) if f else (INK if is_b else GREY_LT)
            cv.seg(l, h_, y, y, band_c, thick, end="round")
            if f:
                cv.pt(v, y, fc, diam_pt=thick * 0.95)
                cv.text(min(v, l) - fr.dx(0.08), y, vl, readable(fc), sv, bold=True, ha="right")
            else:
                cv.pt(v, y, INK if is_b else MUTED, "#ffffff", diam_pt=thick * 0.8,
                      stroke_pt=1.0)
            tc = readable(fc) if f else (INK if is_b else MUTED)
            cv.text(fr.xr[0] - fr.dx(val_w + 0.04), y, lab, tc, s, bold=f or is_b, ha="right")
        return cv.plot(fr)
    lt = mix(fc, "#ffffff", 0.3)
    legend = T(f"[实际值](focus) ● | [区间]({lt})", f"[actual](focus) ● | [range]({lt})")
    return Chart(build, legend)


# ====================================================================== stacked_100
def stacked_100(df, cat, part, value, order=None, focus_cat=None, focus_parts=None,
                sort_by=None, min_label=0.06, colors=None):
    """100% horizontal stacked bars: composition of several groups. `order` = natural order of
    the parts (funnel stages, risk grades). Parts get a single-hue ramp (or `colors`).
    focus_cat: row moved to the top at full colour, others desaturated. focus_parts: parts kept
    in colour (others grey). sort_by: a part name -> rows sorted by that part's share.
    chart.legend holds the coloured-word legend for titled()."""
    d = df[[cat, part, value]].dropna()
    parts = list(order or dict.fromkeys(d[part]))
    tab = d.pivot_table(index=cat, columns=part, values=value, aggfunc="sum", sort=False).reindex(
        columns=parts).fillna(0)
    share = tab.div(tab.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
    if sort_by is not None:
        share = share.sort_values(sort_by, ascending=False)
    rows = [str(r) for r in share.index]
    if focus_cat is not None and str(focus_cat) in rows:
        rows = [str(focus_cat)] + [r for r in rows if r != str(focus_cat)]
        share.index = share.index.map(str)
        share = share.loc[rows]
    ramp = colors or PAL.sequential(len(parts))
    pcol = dict(zip(parts, ramp))
    fp = set(focus_parts or parts)
    legend = " | ".join(f"[{p}]({readable(pcol[p])})" if p in fp else str(p) for p in parts)

    def build(w, h):
        n = len(rows)
        s = _row_font(h, n, "stacked_100")
        sv = s * 0.85
        labs = [_fit_label(r, 0.3 * w, s, r == str(focus_cat)) for r in rows]
        top = sv * 1.3 / 72 + 0.05
        fr = Frame(w, h, (0, 1), (-0.5, n - 0.5), left=_max_w(labs, s, True) + 0.12,
                   right=0.08, top=top, name="stacked_100")
        cv = Canvas()
        for t in (0, 0.25, 0.5, 0.75, 1):
            cv.text(t, n - 0.5 + fr.dy(0.04), vc.pct(t, nd=0), MUTED, sv,
                    ha="center" if 0 < t < 1 else ("left" if t == 0 else "right"), va="bottom")
        for i, r in enumerate(rows):
            y = n - 1 - i
            x0 = 0.0
            is_f = focus_cat is not None and r == str(focus_cat)
            dim = focus_cat is not None and not is_f
            for p in parts:
                v = float(share.loc[share.index[i], p])
                base_c = pcol[p] if p in fp else mix(MUTED, "#ffffff", 0.35 + 0.1 * parts.index(p) / len(parts))
                fill = mix(base_c, "#ffffff", 0.55) if dim else base_c
                cv.rect(x0, x0 + v, y - 0.34, y + 0.34, fill, "#ffffff", 0.8)
                lab = vc.pct(v, nd=0)
                if v >= min_label and v / fr.kx > _tw(lab, sv) + 0.06 and (not dim or p in fp):
                    cv.text(x0 + v / 2, y, lab, ink_on(fill), sv, ha="center", check=False,
                            bold=is_f)
                x0 += v
            cv.text(-fr.dx(0.08), y, labs[i], INK if (is_f or focus_cat is None) else MUTED, s,
                    bold=is_f, ha="right")
        return cv.plot(fr)
    return Chart(build, legend)


# ====================================================================== heatmap
def heatmap(df, x, y, value, fmt="num", nd=None, x_order=None, y_order=None,
            sort_x="mean", low="#ffffff", high=None, vmin=None, vmax=None, show_values=True):
    """Table-like heatmap with a single-hue scale (white -> `high`, default focus).
    Colour limits default to the 2nd-98th percentile so one outlier doesn't wash out the rest.
    sort_x: 'mean' (columns by mean, high first) | None. Cell text switches to white on dark
    cells and is dropped (with a WARNING) when cells are too small."""
    d = df[[x, y, value]].dropna()
    tab = d.pivot_table(index=y, columns=x, values=value, aggfunc="mean", sort=False)
    if x_order:
        tab = tab.reindex(columns=x_order)
    elif sort_x == "mean":
        tab = tab[tab.mean().sort_values(ascending=False).index]
    if y_order:
        tab = tab.reindex(y_order)
    arr = tab.values.astype(float)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        raise ValueError(f"heatmap: no non-missing values in '{value}' -- nothing to draw.")
    lo = vmin if vmin is not None else float(np.percentile(finite, 2))
    hi = vmax if vmax is not None else float(np.percentile(finite, 98))
    high = high or PAL.focus
    legend = T(f"颜色越深 = 越高(色阶 {fmt_value(lo, fmt, nd)}–{fmt_value(hi, fmt, nd)})",
               f"darker = higher (scale {fmt_value(lo, fmt, nd)}–{fmt_value(hi, fmt, nd)})")

    def build(w, h):
        nr, nc = arr.shape
        s = _base() * 0.92
        rl = [str(r) for r in tab.index]
        cl = [str(c) for c in tab.columns]
        left = _max_w([_fit_label(r, 0.28 * w, s) for r in rl], s) + 0.12
        cw = (w - left - 0.05) / nc
        rot = _max_w(cl, s * 0.92) > cw * 0.95
        cls = [_fit_label(c, 1.2 if rot else cw * 0.95, s * 0.92) for c in cl]
        top = (_max_w(cls, s * 0.92) + 0.08) if rot else s * 1.35 / 72 + 0.06
        fr = Frame(w, h, (-0.5, nc - 0.5), (-0.5, nr - 0.5), left=left, right=0.05, top=top,
                   name="heatmap")
        ch = (h - top) / nr
        vs = min(s * 0.92, ch * 72 * 0.5)
        labs = [[fmt_value(v, fmt, nd) for v in row] for row in arr]
        fits = show_values and vs >= _base() * 0.6 and all(
            _tw(l, vs) < cw * 0.92 for row in labs for l in row)
        if show_values and not fits:
            print("WARNING heatmap: cells too small for values -> numbers hidden; widen the "
                  "panel, reduce columns or set show_values=False.")
        cv = Canvas()
        for j, c in enumerate(cls):
            if rot:
                cv.text(j, nr - 0.5 + fr.dy(0.05), c, INK, s * 0.92, ha="center", va="bottom",
                        angle=90)
            else:
                cv.text(j, nr - 0.5 + fr.dy(0.05), c, INK, s * 0.92, ha="center", va="bottom")
        for i, r in enumerate(rl):
            yy = nr - 1 - i
            cv.text(-0.5 - fr.dx(0.08), yy, _fit_label(r, 0.28 * w, s), INK, s, ha="right")
            for j in range(nc):
                v = arr[i, j]
                if not np.isfinite(v):
                    cv.rect(j - 0.47, j + 0.47, yy - 0.45, yy + 0.45, "#f3f4f6")
                    continue
                t = min(max((v - lo) / (hi - lo) if hi > lo else 0.5, 0), 1)
                fill = mix(low, high, t)
                cv.rect(j - 0.47, j + 0.47, yy - 0.45, yy + 0.45, fill)
                if fits:
                    cv.text(j, yy, labs[i][j], ink_on(fill), vs, ha="center", check=False)
        return cv.plot(fr)
    return Chart(build, legend)


# ====================================================================== waterfall
def waterfall(df, cat, delta, start=None, end_label=None, fmt="num", nd=None,
              up=None, down=None, total_color=None):
    """Bridge from a start total to an end total through signed contributions.
    start: (label, value) for the first total bar (omit to start at 0). end_label: label of
    the final total bar. up/down: colours for increases / decreases. Default: neutral (brand
    tint / grey) with +/− labels -- the focus colour is NOT used for "decrease" (it means
    "look here", not "bad"). Pass PAL.good / PAL.bad when direction has business meaning."""
    d = df[[cat, delta]].dropna()
    cats, dl = [str(c) for c in d[cat]], list(d[delta].astype(float))
    up, down = up or mix(PAL.brand, "#ffffff", 0.25), down or GREY
    total_color = total_color or PAL.brand
    end_label = end_label or T("合计", "Total")

    def build(w, h):
        bars = []
        run = 0.0
        if start:
            bars.append((start[0], 0.0, start[1], total_color, fmt_value(start[1], fmt, nd)))
            run = start[1]
        for c, v in zip(cats, dl):
            lab = ("+" if v > 0 else "") + fmt_value(v, fmt, nd)
            bars.append((c, run, run + v, up if v >= 0 else down, lab))
            run += v
        bars.append((end_label, 0.0, run, total_color, fmt_value(run, fmt, nd)))
        n = len(bars)
        s = _base() * 0.9
        cw = w / n
        xl = [_fit_label(b[0], cw * 0.95, s) for b in bars]
        lo = min(0.0, min(min(b[1], b[2]) for b in bars))
        hi = max(max(b[1], b[2]) for b in bars)
        bottom = s * 1.35 / 72 + 0.08
        top = s * 1.4 / 72 + 0.04
        fr = Frame(w, h, (-0.5, n - 0.5), (lo, hi), top=top, bottom=bottom, left=0.02,
                   right=0.02, name="waterfall")
        cv = Canvas()
        cv.seg(-0.5, n - 0.5, 0, 0, MUTED, 0.6)
        for i, (c, a, b, col, lab) in enumerate(bars):
            cv.rect(i - 0.36, i + 0.36, a, b, col)
            if i < n - 1:
                cv.seg(i + 0.36, i + 1 - 0.36, b, b, MUTED, 0.5, lt="dashed")
            yl = max(a, b) + fr.dy(0.04) if b >= a else min(a, b) - fr.dy(0.04)
            cv.text(i, yl, lab, readable(col) if col != total_color else INK, s,
                    bold=col == total_color, ha="center", va="bottom" if b >= a else "top")
            cv.text(i, fr.yr[0] - fr.dy(0.06), xl[i], MUTED, s, ha="center", va="top")
        return cv.plot(fr)
    return Chart(build)


# ====================================================================== distribution
def _box_stats(v):
    v = np.sort(np.asarray(v, float))
    q1, med, q3 = np.percentile(v, [25, 50, 75])
    iqr = q3 - q1
    lo_w = v[v >= q1 - 1.5 * iqr].min()
    hi_w = v[v <= q3 + 1.5 * iqr].max()
    out = v[(v < lo_w) | (v > hi_w)]
    return q1, med, q3, lo_w, hi_w, out


def distribution(df, value, group=None, kind="box", highlight=None, bins="auto", fmt="num",
                 nd=None, show_n=True, sort=True, max_points=400, seed=0):
    """Distributions. kind='box' (horizontal boxes per group, sorted by median, 1.5×IQR
    whiskers, outliers as hollow dots), 'strip' (jittered points + box; ≤ max_points per group
    are drawn, sampled with `seed`), 'hist' (one histogram per group, shared x, stacked rows)."""
    d = df[[value] + ([group] if group else [])].dropna()
    gcol = group or "__g"
    if group is None:
        d = d.assign(__g=str(value))
    groups = list(dict.fromkeys(d[gcol]))
    data = {g: d.loc[d[gcol] == g, value].astype(float).values for g in groups}
    if sort and kind != "hist":
        groups = sorted(groups, key=lambda g: -np.median(data[g]) if len(data[g]) else 0)
    allv = d[value].astype(float).values

    def build(w, h):
        n = len(groups)
        s = _row_font(h * 0.85, n, "distribution", gap=2.2 if kind == "hist" else 1.6)
        sv = s * 0.88
        hl = _match(groups, highlight)
        any_hl = any(hl)
        lo, hi = float(np.min(allv)), float(np.max(allv))
        xt, xs, lo, hi = axis_range(lo, hi, 5)
        labs = [_fit_label(g, 0.3 * w, s, h_i) for g, h_i in zip(groups, hl)] if group else [""] * n
        nlab = [f"n={len(data[g]):,}" for g in groups] if show_n else [""] * n
        left = (_max_w(labs, s, True) + 0.12) if group else 0.05
        right = (_max_w(nlab, sv) + 0.12) if show_n else 0.05
        bottom = sv * 1.3 / 72 + 0.08
        xl0 = tick_label(xt[0], fmt, xs)
        xl1 = tick_label(xt[-1], fmt, xs)
        left = max(left, _tw(xl0, sv) / 2 + 0.03)
        right = max(right, _tw(xl1, sv) / 2 + 0.03)
        fr = Frame(w, h, (lo, hi), (-0.5, n - 0.5), left=left, right=right, bottom=bottom,
                   top=0.04, name="distribution")
        cv = Canvas()
        for t in xt:
            cv.seg(t, t, -0.5, n - 0.5, GRID, 0.4)
        _x_axis(cv, fr, xt, [tick_label(t, fmt, xs) for t in xt], sv, baseline=False)
        rng = np.random.default_rng(seed)
        for i, g in enumerate(groups):
            y = n - 1 - i
            v = data[g]
            col = (PAL.focus if hl[i] else (GREY if any_hl else PAL.brand))
            if len(v) == 0:
                continue
            if kind == "hist":
                edges = np.histogram_bin_edges(allv, bins=bins)
                cnt, _ = np.histogram(v, bins=edges)
                top_c = cnt.max() or 1
                for c, a, b in zip(cnt, edges[:-1], edges[1:]):
                    if c:
                        cv.rect(a, b, y - 0.42, y - 0.42 + 0.84 * c / top_c, col, "#ffffff", 0.4)
            else:
                q1, med, q3, lw_, hw_, out = _box_stats(v)
                if kind == "strip":
                    pv = v if len(v) <= max_points else rng.choice(v, max_points, replace=False)
                    jy = y + rng.uniform(-0.28, 0.28, len(pv))
                    for xv, yv in zip(pv, jy):
                        cv.pt(xv, yv, mix(col, "#ffffff", 0.45), diam_pt=3)
                cv.seg(lw_, q1, y, y, MUTED, 1.0)
                cv.seg(q3, hw_, y, y, MUTED, 1.0)
                cv.rect(q1, q3, y - 0.26, y + 0.26, "none" if kind == "strip" else mix(col, "#ffffff", 0.35),
                        col, 1.0)
                cv.seg(med, med, y - 0.26, y + 0.26, readable(col) if kind != "strip" else col, 2.2)
                if kind == "box":
                    for o in out[:200]:
                        cv.pt(o, y, MUTED, "#ffffff", diam_pt=4, stroke_pt=0.7)
            if group:
                cv.text(fr.xr[0] - fr.dx(0.08), y, labs[i], readable(col) if hl[i] else INK, s,
                        bold=hl[i], ha="right")
            if show_n:
                cv.text(fr.xr[1] + fr.dx(0.08), y, nlab[i], MUTED, sv)
        return cv.plot(fr)
    return Chart(build)


# ====================================================================== scatter
def _ols(x, y, level=0.95):
    x, y = np.asarray(x, float), np.asarray(y, float)
    n = len(x)
    X = np.column_stack([np.ones(n), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = max(n - 2, 1)
    s2 = resid @ resid / dof
    xtx_inv = np.linalg.inv(X.T @ X)
    # t quantile: normal quantile with a small-sample correction (Cornish-Fisher, 1st order)
    z = {0.9: 1.6449, 0.95: 1.96, 0.99: 2.5758}.get(level, 1.96)
    t = z + (z ** 3 + z) / (4 * dof)
    gx = np.linspace(x.min(), x.max(), 60)
    G = np.column_stack([np.ones_like(gx), gx])
    fit = G @ beta
    se = np.sqrt(np.einsum("ij,jk,ik->i", G, xtx_inv, G) * s2)
    r2 = 1 - (resid @ resid) / (((y - y.mean()) ** 2).sum() or 1)
    return gx, fit, fit - t * se, fit + t * se, beta, r2


def scatter(df, x, y, label=None, highlight=None, fit=None, level=0.95, groups=None,
            fmt_x="num", fmt_y="num", x_title=None, y_title=None, ref_lines=None,
            label_points="highlight", show_r2=True):
    """Scatter with optional linear fit + confidence band (numpy OLS, no extra deps).
    label: column with point names; label_points: 'highlight' | 'all' | None.
    groups: colour by a column (<= 5); chart.legend holds the coloured key. ref_lines: 'mean' -> dashed mean lines (quadrants).
    x_title / y_title: axis titles (recommended: say what and the unit)."""
    cols = [x, y] + [c for c in (label, groups) if c]
    d = df[cols].dropna()
    legend = None
    if groups:
        gn = list(dict.fromkeys(d[groups]))
        gc = dict(zip(gn, PAL.categorical(len(gn))))
        legend = " | ".join(f"[{zh(str(g))} ●]({gc[g]})" for g in gn)

    def build(w, h):
        s = _base()
        sv = s * 0.88
        xs, ys = d[x].astype(float).values, d[y].astype(float).values
        names = [str(v) for v in (d[label] if label else range(len(d)))]
        hl = _match(names, highlight)
        any_hl = any(hl)
        if groups:
            col = [gc[g] for g in d[groups]]
        else:
            col = [PAL.focus if h_i else (mix(MUTED, "#ffffff", 0.25) if any_hl else PAL.brand) for h_i in hl]
        x0, x1 = float(xs.min()), float(xs.max())
        y0, y1 = float(ys.min()), float(ys.max())
        fitd = _ols(xs, ys, level) if (fit == "linear" and len(d) >= 3) else None
        if fitd:
            y0, y1 = min(y0, fitd[2].min()), max(y1, fitd[3].max())
        xt, xst, x0, x1 = axis_range(x0, x1, 5)
        yt, yst, y0, y1 = axis_range(y0, y1, 4)
        ylabs = [tick_label(t, fmt_y, yst) for t in yt]
        xlabs = [tick_label(t, fmt_x, xst) for t in xt]
        lab_set = [i for i in range(len(d)) if label and (label_points == "all" or (label_points == "highlight" and hl[i]))]
        right = (_max_w([names[i] for i in lab_set], sv, True) * 0.6 + 0.1) if lab_set else 0.1
        right = max(right, _tw(xlabs[-1], sv) / 2 + 0.04)
        left = max(_max_w(ylabs, sv) + 0.1, _tw(xlabs[0], sv) / 2 + 0.04)
        bottom = sv * 1.3 / 72 + 0.08 + ((s * 1.4 / 72) if x_title else 0)
        top = (s * 1.4 / 72 + sv * 0.6 / 72 + 0.08) if y_title else (sv * 0.6 / 72 + 0.04)
        fr = Frame(w, h, (x0, x1), (y0, y1), left=left, right=right, top=top, bottom=bottom,
                   name="scatter")
        cv = Canvas()
        _y_axis(cv, fr, yt, ylabs, sv)
        _x_axis(cv, fr, xt, xlabs, sv)
        if y_title:
            cv.text(fr.xr[0] - fr.dx(left - 0.02), fr.yr[1] + fr.dy(sv * 0.6 / 72 + 0.06), y_title,
                    INK, s * 0.95, bold=True, va="bottom")
        if x_title:
            cv.text(fr.xr[1], fr.yr[0] - fr.dy(bottom - 0.02), x_title, INK, s * 0.95, bold=True,
                    ha="right", va="bottom")
        if ref_lines == "mean":
            mx, my = xs.mean(), ys.mean()
            cv.seg(mx, mx, fr.yr[0], fr.yr[1], MUTED, 0.7, lt="dashed")
            cv.seg(fr.xr[0], fr.xr[1], my, my, MUTED, 0.7, lt="dashed")
        if fitd:
            gx, fy, lo_, hi_, beta, r2 = fitd
            cv.band(gx, lo_, hi_, mix(PAL.brand, "#ffffff", 0.82))
            cv.line(gx, fy, PAL.brand, 1.4)
            if show_r2:
                cv.text(fr.xr[1], fr.yr[1], f"R² = {r2:.2f}", MUTED, sv, ha="right", va="top")
        order = sorted(range(len(d)), key=lambda i: hl[i])
        for i in order:
            cv.pt(xs[i], ys[i], col[i], diam_pt=6 if hl[i] else 5)
        if lab_set:
            ly = dodge([ys[i] for i in lab_set], sv * 1.2 / 72 * fr.ky)
            for i, yy in zip(lab_set, ly):
                cv.text(xs[i] + fr.dx(0.07), yy, names[i], readable(col[i]) if hl[i] else MUTED,
                        sv, bold=hl[i])
        return cv.plot(fr)
    return Chart(build, legend)


# ====================================================================== point_range (forest)
def point_range(df, cat, est, low, high, ref=0.0, highlight=None, fmt="num", nd=None,
                sort=True, show_values=True):
    """Estimates with intervals (forest plot / error bars): one row per category, point =
    estimate, line = interval, dashed vertical line at `ref` (e.g. 0 or 1). Values printed on
    the right as 'est [low, high]'."""
    d = df[[cat, est, low, high]].dropna()
    if sort:
        d = d.sort_values(est, ascending=False, kind="stable")
    names = [str(c) for c in d[cat]]
    e_, l_, h_ = (list(d[c].astype(float)) for c in (est, low, high))

    def build(w, h):
        n = len(names)
        s = _row_font(h, n, "point_range")
        sv = s * 0.88
        hl = _match(names, highlight)
        any_hl = any(hl)
        labs = [_fit_label(nm, 0.33 * w, s, x) for nm, x in zip(names, hl)]
        vls = [f"{fmt_value(a, fmt, nd)} [{fmt_value(b, fmt, nd)}, {fmt_value(c, fmt, nd)}]"
               for a, b, c in zip(e_, l_, h_)]
        lo = min(l_ + ([ref] if ref is not None else []))
        hi = max(h_ + ([ref] if ref is not None else []))
        xt, xs, lo, hi = axis_range(lo, hi, 4)
        bottom = sv * 1.3 / 72 + 0.08
        fr = Frame(w, h, (lo, hi), (-0.5, n - 0.5), left=_max_w(labs, s, True) + 0.12,
                   right=(_max_w(vls, sv) + 0.15) if show_values else 0.05, bottom=bottom,
                   name="point_range")
        cv = Canvas()
        _x_axis(cv, fr, xt, [tick_label(t, fmt, xs) for t in xt], sv, baseline=True)
        if ref is not None:
            cv.seg(ref, ref, -0.5, n - 0.5, MUTED, 0.8, lt="dashed")
        for i in range(n):
            y = n - 1 - i
            col = PAL.focus if hl[i] else (GREY if any_hl else INK)
            cv.seg(l_[i], h_[i], y, y, col, 1.6 if hl[i] else 1.2)
            cv.pt(e_[i], y, col, diam_pt=6.5 if hl[i] else 5.5)
            cv.text(fr.xr[0] - fr.dx(0.08), y, labs[i], readable(col) if hl[i] else (MUTED if any_hl else INK),
                    s, bold=hl[i], ha="right")
            if show_values:
                cv.text(fr.xr[1] + fr.dx(0.1), y, vls[i], readable(col) if hl[i] else MUTED, sv,
                        bold=hl[i])
        return cv.plot(fr)
    return Chart(build)


# ====================================================================== small_multiples
class _Grid(SizedPanel):
    def __init__(self, cells, ncol, gap):
        self.cells, self.ncol, self.gap = cells, ncol, gap

    def at(self, w, h):
        n = len(self.cells)
        ncol = self.ncol or max(1, min(n, round(math.sqrt(n * w / max(h, 0.1) / 1.6))))
        nrow = math.ceil(n / ncol)
        cw = (w - self.gap * (ncol - 1)) / ncol
        chh = (h - self.gap * (nrow - 1)) / nrow
        b = _base()
        if cw < b / 7 * 0.9 or chh < b / 7 * 0.75:
            print(f"WARNING small_multiples: {n} cells of {cw:.2f} x {chh:.2f} in are too small at "
                  f"{b}pt text; use a larger size/spec, ncol=, or fewer facets.")
        out = []
        for k, c in enumerate(self.cells):
            r, j = divmod(k, ncol)
            out.append((c(first_col=(j == 0), last_row=(r == nrow - 1)),
                        j * (cw + self.gap), r * (chh + self.gap), cw, chh))
        return out


def small_multiples(df, x, y, facet, ncol=None, highlight=None, order=None, fmt="num", nd=None,
                    context=True, zero="auto", gap=None, color=None):
    """One small line chart per facet, all on the SAME y scale, arranged in a grid that fits
    the panel. context=True draws every other facet as faint grey lines behind each cell, so
    each cell reads "this one vs the rest". highlight: facets drawn in focus colour.
    order: facet order (default: by last value, high first). Only the first column shows
    y tick labels and only the last row shows x tick labels; every cell keeps the same plot
    area, so the grid lines up exactly."""
    d = df[[x, y, facet]].dropna().copy()
    xpos, tks, tlabs = _x_positions(d[x])
    d["__x"] = xpos
    facets = list(order or d.sort_values("__x").groupby(facet, sort=False)[y].last()
                  .sort_values(ascending=False).index)
    ylo, yhi = _y_range(d[y].values, zero)
    xmin, xmax = float(d["__x"].min()), float(d["__x"].max())

    def cell(fname):
        g = d[d[facet] == fname].sort_values("__x")
        is_h = bool(_match([fname], highlight)[0])
        col = (color or PAL.focus) if is_h else PAL.brand

        def make(first_col, last_row):
            def build(w, h):
                s = _base() * 0.88
                sv = s * 0.9
                yt, ystep = nice_breaks(ylo, yhi, 3)
                yt = [t for t in yt if ylo - 1e-9 <= t <= yhi + 1e-9]
                ylabs = [tick_label(t, fmt, ystep) for t in yt]
                if tks is None:
                    xt, xs = nice_breaks(xmin, xmax, 3)
                    xt = [t for t in xt if xmin - 1e-9 <= t <= xmax + 1e-9]
                    xl = [tick_label(t, "num", xs) for t in xt]
                else:
                    xt, xl = _thin(list(tks), tlabs, 3)
                y_w = _max_w([tick_label(t, fmt, ystep) for t in yt], sv) + 0.08
                endl = fmt_value(g[y].iloc[-1], fmt, nd)
                right = max(_tw(endl, sv, True) + 0.1, (_tw(xl[-1], sv) / 2 + 0.03) if xl else 0)
                y_w = max(y_w, (_tw(xl[0], sv) / 2 + 0.03) if xl else 0)
                title_h = s * 1.35 / 72
                bottom = max((vc.line_height(l, sv) + (_lines(l) - 1) * sv * 1.15 / 72
                              for l in xl), default=0.0) + 0.08
                fr = Frame(w, h, (xmin, xmax), (ylo, yhi), left=y_w, right=right,
                           top=title_h + 0.04, bottom=bottom, name="small_multiples", quiet=True)
                cv = Canvas()
                cv.text(fr.xr[0], fr.yr[1] + fr.dy(title_h * 0.55 + 0.04),
                        _fit_label(fname, w - 0.1, s, True), readable(col) if is_h else INK, s,
                        bold=True)
                for t, lab in zip(yt, ylabs):
                    cv.seg(fr.xr[0], fr.xr[1], t, t, GRID, 0.4)
                    if first_col:
                        cv.text(fr.xr[0] - fr.dx(0.05), t, lab, MUTED, sv, ha="right")
                if last_row:
                    for t, lab in zip(xt, xl):
                        cv.text(t, fr.yr[0] - fr.dy(0.04), lab, MUTED, sv, ha="center", va="top")
                if context:
                    for other in facets:
                        if other == fname:
                            continue
                        o = d[d[facet] == other].sort_values("__x")
                        cv.line(o["__x"], o[y], GREY_LT, 0.7)
                cv.line(g["__x"], g[y], col, 1.8 if is_h else 1.5)
                cv.pt(g["__x"].iloc[-1], g[y].iloc[-1], col, diam_pt=4.5)
                cv.text(g["__x"].iloc[-1] + fr.dx(0.06), g[y].iloc[-1], endl,
                        readable(col), sv, bold=True)
                return cv.plot(fr)
            return Chart(build)
        return make

    return _Grid([cell(f) for f in facets], ncol, gap if gap is not None else 0.12)


__all__ = ["Chart", "Frame", "Canvas", "nice_breaks", "tick_label", "bar_rank", "line_trend",
           "dumbbell", "slope", "range_dot", "stacked_100", "heatmap", "waterfall",
           "distribution", "scatter", "point_range", "small_multiples"]
