"""Tiny matplotlib-based emulator of the plotnine subset used by storytelling-viz.

ONLY for previewing layout in a sandbox where plotnine can't be installed:
    PYTHONPATH=<skill>/scripts/plotnine_preview python3 my_slide.py
Covers: ggplot/aes, geom_text/rect/segment/point/line/ribbon/tile/col/blank/hline,
scale_*_continuous (limits/breaks/labels), identity/manual/gradient colour scales,
theme_void/theme_minimal + axis_text blanking, labs(title/subtitle), coord_fixed.
NOT covered: facets, coord_flip text, stat_*, legends, real theme margins.
Line widths/point sizes follow plotnine's SIZE_FACTOR; text is clipped at the panel edge
like plotnine. Use it to check overflow/overlap/proportions; final output must come
from real plotnine (>= 0.15)."""
import copy, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.colors import to_rgb
SF = np.sqrt(np.pi)          # plotnine SIZE_FACTOR (line width = size * SF points)
BLANK = "BLANK"


def element_blank(): return BLANK
def element_text(**k): return dict(k)
def element_line(**k): return dict(k)
def element_rect(**k): return dict(k)


class aes(dict):
    def __init__(self, *a, **k):
        super().__init__(**k)
        if len(a) > 0: self["x"] = a[0]
        if len(a) > 1: self["y"] = a[1]


class Theme:
    def __init__(self, kind=None, **k): self.kind = kind; self.s = dict(k)
    def __add__(self, o):
        t = copy.copy(self); t.s = dict(self.s)
        if isinstance(o, Theme):
            if o.kind: t.kind = o.kind
            t.s.update(o.s)
        return t


def theme(**k): return Theme(None, **k)
def theme_minimal(**k): return Theme("minimal")
def theme_void(**k): return Theme("void")


class Scale:
    def __init__(self, kind, **k): self.kind = kind; self.k = k


def _sc(kind):
    return lambda *a, **k: Scale(kind, **k)


scale_x_continuous = _sc("x"); scale_y_continuous = _sc("y")
scale_x_discrete = _sc("xd"); scale_color_identity = _sc("cid"); scale_fill_identity = _sc("fid")
scale_color_manual = _sc("cman"); scale_fill_gradient = _sc("fgrad")
scale_size_identity = _sc("sid"); scale_alpha_identity = _sc("aid")


class Labs:
    def __init__(self, **k): self.k = k


def labs(**k): return Labs(**k)


class Coord:
    def __init__(self, kind): self.kind = kind


def coord_fixed(*a, **k): return Coord("fixed")
def coord_flip(*a, **k): return Coord("flip")


class arrow:
    def __init__(self, **k): pass


class Layer:
    def __init__(self, geom, mapping=None, data=None, inherit_aes=True, **p):
        self.geom = geom; self.mapping = mapping or aes(); self.data = data
        self.inherit = inherit_aes; self.p = p


def _g(name):
    def f(mapping=None, data=None, **k):
        ia = k.pop("inherit_aes", True)
        return Layer(name, mapping, data, ia, **k)
    return f


for _n in ["geom_text", "geom_rect", "geom_segment", "geom_point", "geom_line", "geom_path", "geom_ribbon",
           "geom_tile", "geom_blank", "geom_col"]:
    globals()[_n] = _g(_n)


def geom_hline(yintercept=0, **k): return Layer("geom_hline", None, None, False, yintercept=yintercept, **k)


class ggplot:
    def __init__(self, data=None, mapping=None):
        self.data = data; self.mapping = mapping or aes(); self.layers = []; self.scales = {}
        self.theme = Theme(); self.labs = {}; self.coord = None

    def __add__(self, o):
        g = copy.copy(self); g.layers = list(self.layers); g.scales = dict(self.scales)
        g.labs = dict(self.labs)
        g._add(o); return g
    __iadd__ = __add__

    def _add(self, o):
        if isinstance(o, (list, tuple)):
            for x in o: self._add(x)
        elif isinstance(o, Layer): self.layers.append(o)
        elif isinstance(o, Scale): self.scales[o.kind] = o.k
        elif isinstance(o, Theme): self.theme = self.theme + o
        elif isinstance(o, Labs): self.labs.update(o.k)
        elif isinstance(o, Coord): self.coord = o.kind
        elif o is None: pass
        else: raise TypeError(f"cannot add {type(o)}")

    def _col(self, df, m, key, n):
        if key not in m: return None
        v = m[key]
        if isinstance(v, str) and df is not None and v in df.columns: return list(df[v])
        if isinstance(v, (list, np.ndarray, pd.Series)): return list(v)
        return [v] * n

    def draw(self, show=False):
        w, h = self.theme.s.get("figure_size", (6.4, 4.8))
        return self._build(w, h, 100)

    def save(self, f, width, height, dpi=100, verbose=False, transparent=False, **kw):
        fig = self._build(width, height, dpi)
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        FigureCanvasAgg(fig)
        fig.savefig(f, dpi=dpi, transparent=self.theme.kind == "void" or transparent)

    def _build(self, width, height, dpi):
        from matplotlib.figure import Figure      # like plotnine: canvas = FigureCanvasBase
        fig = Figure(figsize=(width, height), dpi=dpi)
        t = self.theme.s; void = self.theme.kind == "void"
        xs, ys = self.scales.get("x", {}), self.scales.get("y", {})
        ax_x = (not void and t.get("axis_text") != BLANK and t.get("axis_text_x") != BLANK
                and "breaks" in xs)
        ax_y = (not void and t.get("axis_text") != BLANK and t.get("axis_text_y") != BLANK
                and "breaks" in ys)
        title = self.labs.get("title"); sub = self.labs.get("subtitle")
        top = (0.32 if title else 0) + (0.25 if sub else 0)
        nl = max((str(s).count("\n") for s in xs.get("labels", [""])), default=0)
        l = 0.5 if ax_y else 0; b = (0.3 + 0.17 * nl) if ax_x else 0
        ax = fig.add_axes([l / width, b / height, 1 - l / width, 1 - (b + top) / height])
        ax.set_facecolor("none")
        for s in ax.spines.values(): s.set_visible(False)
        if title: fig.text(0, 1 - 0.05 / height, title, va="top", fontsize=13, weight="bold")
        if sub: fig.text(0, 1 - 0.37 / height, sub, va="top", fontsize=11, color="#6b7280")
        for L in self.layers: self._draw(ax, L)
        if xs.get("limits") is not None: ax.set_xlim(*xs["limits"])
        if ys.get("limits") is not None: ax.set_ylim(*ys["limits"])
        if ax_x:
            ax.set_xticks(xs["breaks"]); ax.set_xticklabels(xs.get("labels", xs["breaks"]), fontsize=9.5, color="#6b7280")
        else: ax.set_xticks([])
        if ax_y:
            ax.set_yticks(ys["breaks"]); ax.set_yticklabels(ys.get("labels", ys["breaks"]), fontsize=9.5, color="#6b7280")
        else: ax.set_yticks([])
        ax.tick_params(length=0)
        if self.coord == "fixed": ax.set_aspect("equal", adjustable="box", anchor="NW")
        if void:
            fig.patch.set_alpha(0)
        return fig

    def _draw(self, ax, L):
        df = L.data if L.data is not None else self.data
        m = dict(self.mapping) if L.inherit else {}
        m.update(L.mapping); p = L.p
        n = len(df) if df is not None else 1
        if L.geom == "geom_blank": return
        if L.geom == "geom_hline":
            ax.axhline(p["yintercept"], color=p.get("color", "k"), lw=p.get("size", 0.5) * SF, ls="--"); return

        def get(k, default=None):
            v = self._col(df, m, k, n)
            if v is not None: return v
            if k in p: return [p[k]] * n
            return [default] * n
        col = get("color", "#333333"); fill = get("fill", None)
        if "fill" in m and "fgrad" in self.scales and isinstance(m["fill"], str):
            g = self.scales["fgrad"]; lo, hi = np.array(to_rgb(g["low"])), np.array(to_rgb(g["high"]))
            a, b = g.get("limits", (min(fill), max(fill)))
            fill = [tuple(lo + (hi - lo) * min(max((v - a) / (b - a), 0), 1)) for v in fill]
        if "color" in m and "cman" in self.scales:
            vals = self.scales["cman"]["values"]; col = [vals.get(c, c) for c in col]
        size = get("size", 0.5)
        ls = {"dashed": "--", "dotted": ":"}.get(p.get("linetype", "solid"), "-")
        if L.geom == "geom_text":
            X, Y, lab = get("x"), get("y"), get("label")
            for i in range(n):
                ax.text(X[i], Y[i], str(lab[i]), fontsize=size[i] if ("size" in p or "size" in m) else 11,
                        color=col[i], ha=p.get("ha", "center"), va=p.get("va", "center"),
                        family=p.get("family"), weight=p.get("fontweight", "normal"),
                        style=p.get("fontstyle", "normal"), linespacing=p.get("lineheight", 1.2), clip_on=True,
                        rotation=p.get("angle", 0))
        elif L.geom in ("geom_rect", "geom_tile"):
            if L.geom == "geom_rect":
                a, b2, c, d = get("xmin"), get("xmax"), get("ymin"), get("ymax")
            else:
                X, Y = get("x"), get("y"); w, h = p.get("width", 1), p.get("height", 1)
                a = [x - w / 2 for x in X]; b2 = [x + w / 2 for x in X]
                c = [y - h / 2 for y in Y]; d = [y + h / 2 for y in Y]
            has_edge = "color" in p or "color" in m
            for i in range(n):
                ax.add_patch(Rectangle((a[i], c[i]), b2[i] - a[i], d[i] - c[i], facecolor=fill[i] or "none",
                                       edgecolor=col[i] if has_edge else "none",
                                       lw=(size[i] or 0) * SF if has_edge else 0, ls=ls))
        elif L.geom == "geom_segment":
            X, XE, Y, YE = get("x"), get("xend"), get("y"), get("yend")
            cap = "round" if p.get("lineend") == "round" else "butt"
            for i in range(n):
                ax.plot([X[i], XE[i]], [Y[i], YE[i]], color=col[i], lw=size[i] * SF, ls=ls, solid_capstyle=cap)
        elif L.geom == "geom_point":
            X, Y = get("x"), get("y"); st = p.get("stroke", 0.5)
            fl = [f if f is not None else c for f, c in zip(fill, col)]
            ax.scatter(X, Y, s=[np.pi * (s + st) ** 2 for s in size], c=fl,
                       edgecolors=col, linewidths=st * SF, zorder=3)
        elif L.geom in ("geom_line", "geom_path"):
            X, Y = get("x"), get("y")
            grp = get("group", 0)
            d = pd.DataFrame({"x": X, "y": Y, "g": grp, "c": col, "s": size})
            if L.geom == "geom_line":
                d = d.sort_values("x", kind="stable")
            for _, gg in d.groupby("g", sort=False):
                ax.plot(gg.x, gg.y, color=gg.c.iloc[0], lw=gg.s.iloc[0] * SF, ls=ls,
                        solid_capstyle="round", solid_joinstyle="round")
        elif L.geom == "geom_ribbon":
            X, a, b2 = get("x"), get("ymin"), get("ymax")
            grp = get("group", 0)
            d = pd.DataFrame({"x": X, "a": a, "b": b2, "g": grp, "f": fill})
            for _, gg in d.groupby("g", sort=False):
                ax.fill_between(gg.x, gg.a, gg.b, color=gg.f.iloc[0], lw=0)
        elif L.geom == "geom_col":
            X, Y = get("x"), get("y"); w = p.get("width", 0.9)
            if not all(isinstance(v, (int, float, np.integer, np.floating)) for v in X):
                cats = list(getattr(pd.Series(X).dtype, "categories", sorted(set(X), key=str)))
                X = [cats.index(v) + 1 for v in X]
                self._cats = cats
            for i in range(n):
                if self.coord == "flip":
                    ax.barh(X[i], Y[i], height=w, color=fill[i] or col[i])
                else:
                    ax.bar(X[i], Y[i], width=w, color=fill[i] or col[i])
        else:
            raise NotImplementedError(L.geom)
