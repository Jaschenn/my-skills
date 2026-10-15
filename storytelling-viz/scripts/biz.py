"""storytelling-viz · business-analysis charts (house style for weekly / monthly reviews,
anomaly deep-dives, management decks and daily monitoring).

House style (see SKILL.md "经营分析"):
- ups / downs use arrows (▲ ▼) and neutral ink -- NO red / green for direction;
  colour (PAL.bad) only for what is_anomaly() flags (behind pace / beyond threshold /
  outside ±2σ of history), bold for a good-direction anomaly.
- default comparisons: vs prior period, MTD vs same days last month, vs target / budget.
- amounts K / M / B; ratio changes in pp, growth in %; units in titles / notes, not on
  every number.
- prior-period overlays: daily flow metrics aligned by weekday (t-28d / t-364d); MTD
  cumulatives and calendar-tied metrics (billing / due dates, balances) by day of month.
- incomplete current period: dashed / light + "as of" + run-rate projection.

Functions: kpi_cards, bullet, cumulative_vs_target, trend, driver_tree, contrib_table,
bar_line_dual. All return panels that lay themselves out at their final size.
"""
import math

import numpy as np
import pandas as pd

import viz_common as vc
from viz_common import (PAL, INK, MUTED, GRID, mix, zh, fmt_value, dodge, SizedPanel, readable,
                        ink_on, T, delta, is_anomaly, line_height)
from charts import (Chart, Frame, Canvas, nice_breaks, tick_label, GREY, GREY_LT, _base, _tw,
                    _max_w, _fit_label, _row_font, _x_positions, _thin, _y_range, _y_axis,
                    _x_axis, _match, _MonthLabels, _spread)

BAD = lambda: readable(PAL.bad)          # alert text colour (dark enough to read)
PANEL_BG = "#f6f7f9"


def _alert_color(flag, bad):
    return BAD() if (flag and bad) else INK


# ====================================================================== KPI cards
def _card(item, w, h):
    """One KPI card drawn in inch coordinates."""
    b = _base()
    lab = item.get("label", "")
    val, prev = item.get("value"), item.get("prev")
    kind, fmt, nd = item.get("kind", "growth"), item.get("fmt", "num"), item.get("nd")
    hib = item.get("higher_is_better", True)
    vs = item.get("vs", T("vs 上期", "vs prior"))
    dtext, dval = delta(val, prev, kind) if prev is not None else ("", None)
    flag, bad, _ = is_anomaly(value=val, change=dval, history=item.get("history"),
                              threshold=item.get("threshold"), higher_is_better=hib)
    tgt, prog = item.get("target"), item.get("progress")
    fr = Frame(w, h, (0, w), (0, h), name="kpi_cards", quiet=True)
    cv = Canvas()
    cv.rect(0, w, 0, h, PANEL_BG)
    pad = 0.1 * b / 12 + 0.04
    y = h - pad
    s_lab, s_big, s_small = b * 0.85, b * 2.1, b * 0.82
    gap = 0.03 * b / 12                      # between text lines; heights from font metrics
    lab_t, big_t = _fit_label(lab, w - 2 * pad, s_lab), fmt_value(val, fmt, nd)
    cv.text(pad, y, lab_t, MUTED, s_lab, va="top")
    y -= line_height(lab_t, s_lab) + gap
    cv.text(pad, y, big_t, INK, s_big, bold=True, va="top")
    y -= line_height(big_t, s_big, True) + gap
    if dtext:
        col = _alert_color(flag, bad)
        cv.text(pad, y, dtext, col, s_small, bold=flag, va="top")
        x_vs = pad + _tw(dtext, s_small, flag) + 0.06
        if w - pad - x_vs > 0.2:
            cv.text(x_vs, y, _fit_label(vs, w - pad - x_vs, s_small), MUTED, s_small, va="top")
        y -= line_height(dtext, s_small, flag) + gap
    if tgt:
        ach = val / tgt
        behind = prog is not None and (ach < prog if hib else ach > prog)
        lines = [T(f"达成 {vc.pct(ach, nd=0)}", f"{vc.pct(ach, nd=0)} of target")]
        if prog is not None:
            p_txt = T(f"时间进度 {vc.pct(prog, nd=0)}", f"{vc.pct(prog, nd=0)} of period")
            if _tw(f"{lines[0]} · {p_txt}", s_small, behind) <= w - 2 * pad:
                lines = [f"{lines[0]} · {p_txt}"]
            else:                                # narrow card: achievement / progress on 2 lines
                lines.append(p_txt)
        for ln in lines:
            cv.text(pad, y, _fit_label(ln, w - 2 * pad, s_small, behind), BAD() if behind else MUTED,
                    s_small, bold=behind, va="top")
            y -= line_height(ln, s_small, behind) + gap
        bh = max(0.05, b / 12 * 0.07)
        cv.rect(pad, w - pad, y - bh, y, GRID)
        cv.rect(pad, pad + (w - 2 * pad) * min(ach, 1.0), y - bh, y,
                PAL.bad if behind else PAL.brand)
        if prog is not None:
            xp = pad + (w - 2 * pad) * prog
            cv.seg(xp, xp, y - bh - 0.03, y + 0.03, INK, 1.0)
        y -= bh + 0.06
    spark = item.get("spark")
    min_sp = 0.12 * b / 12                   # smallest useful sparkline, scaled with the spec
    if spark is not None and len(spark) > 1 and y - pad > min_sp:
        sv = np.asarray(spark, float)
        lo, hi = np.nanmin(sv), np.nanmax(sv)
        hi = hi if hi > lo else lo + 1
        sp_h = min(y - pad - 0.04, max(0.18, 0.22 * h))
        bot = pad
        top = bot + sp_h
        xs = np.linspace(pad, w - pad, len(sv))
        ys = bot + (sv - lo) / (hi - lo) * (top - bot)
        cv.line(xs, ys, mix(PAL.brand, "#ffffff", 0.35), 1.0)
        cv.pt(xs[-1], ys[-1], BAD() if (flag and bad) else PAL.brand, diam_pt=3.5)
    elif spark is not None and y - pad <= min_sp:
        print(f"WARNING kpi_cards: no room for the sparkline of '{lab}'; give the row more height.")
    if y < 0:
        print(f"WARNING kpi_cards: card '{lab}' needs {h - y:.2f} in height, has {h:.2f}.")
    return cv.plot(fr)


def _mark(panel):
    """Tag a business chart so figure() can warn when the page has no basis caption."""
    panel.biz = True
    return panel


class _Cards(SizedPanel):
    def __init__(self, items, ncol, gap):
        self.items, self.ncol, self.gap = items, ncol, gap

    def at(self, w, h):
        n = len(self.items)
        ncol = self.ncol or min(n, 4 if w > 6 else 2)
        nrow = math.ceil(n / ncol)
        g = self.gap if self.gap is not None else 0.12 * _base() / 12
        cw = (w - g * (ncol - 1)) / ncol
        ch = (h - g * (nrow - 1)) / nrow
        out = []
        for k, it in enumerate(self.items):
            r, j = divmod(k, ncol)
            out.append((Chart(lambda ww, hh, it=it: _card(it, ww, hh)),
                        j * (cw + g), r * (ch + g), cw, ch))
        return out


def kpi_cards(items, ncol=None, gap=None):
    """KPI cards (big number + ▲▼ change + target/time progress + sparkline).
    items: list of dicts with keys
      label, value, prev (comparison value), kind ('growth' | 'pp' | 'abs'), fmt, nd,
      vs (text after the change, e.g. "vs 上月同期"), target, progress (0–1 time elapsed),
      spark (list of recent values), history (for the ±2σ rule), threshold,
      higher_is_better (default True).
    Change text is neutral; it turns red only when the change is an anomaly in the bad
    direction; achievement turns red when it lags the time progress."""
    return _mark(_Cards(items, ncol, gap))


# ====================================================================== bullet
def bullet(df, cat, actual, target, progress=None, fmt="num", nd=None, sort=False,
           higher_is_better=True):
    """Target attainment per row: actual bar, target tick, and (with progress) a dashed
    "expected by now" marker = target × progress. Rows behind pace turn red (bar + label).
    Right labels: 'xx% of target'."""
    d = df[[cat, actual, target]].dropna()
    if sort:
        d = d.assign(_a=d[actual] / d[target]).sort_values("_a", ascending=False)
    names = [str(c) for c in d[cat]]
    act, tgt = list(d[actual].astype(float)), list(d[target].astype(float))

    def build(w, h):
        n = len(names)
        s = _row_font(h, n, "bullet")
        sv = s * 0.9
        ach = [a / t if t else np.nan for a, t in zip(act, tgt)]
        behind = [progress is not None and np.isfinite(x) and ((x < progress) if higher_is_better
                                                                 else (x > progress)) for x in ach]
        labs = [_fit_label(nm, 0.32 * w, s, b) for nm, b in zip(names, behind)]
        rl = [f"{vc.pct(x, nd=0)}  {fmt_value(a, fmt, nd)} / {fmt_value(t, fmt, nd)}"
              for x, a, t in zip(ach, act, tgt)]
        hi = max(act + tgt) * 1.02
        top = (sv * 1.3 / 72 + 0.05) if progress is not None else 0.04
        fr = Frame(w, h, (0, hi), (-0.5, n - 0.5), left=_max_w(labs, s, True) + 0.12,
                   right=_max_w(rl, sv, True) + 0.14, top=top, name="bullet")
        cv = Canvas()
        if progress is not None:
            cv.text(0, n - 0.5 + fr.dy(0.04), T(f"虚线 = 按时间进度 {vc.pct(progress, nd=0)} 应完成",
                                                 f"dashed = expected at {vc.pct(progress, nd=0)} of period"),
                    MUTED, sv * 0.9, va="bottom")
        for i in range(n):
            y = n - 1 - i
            col = PAL.bad if behind[i] else PAL.brand
            cv.rect(0, tgt[i], y - 0.32, y + 0.32, GREY_LT)
            cv.rect(0, act[i], y - 0.18, y + 0.18, col)
            cv.seg(tgt[i], tgt[i], y - 0.36, y + 0.36, INK, 1.6)
            if progress is not None:
                e = tgt[i] * progress
                cv.seg(e, e, y - 0.36, y + 0.36, INK, 0.9, lt="dashed")
            tc = BAD() if behind[i] else INK
            cv.text(fr.xr[0] - fr.dx(0.08), y, labs[i], tc, s, bold=behind[i], ha="right")
            cv.text(max(act[i], tgt[i]) + fr.dx(0.1), y, rl[i], tc, sv, bold=behind[i])
        return cv.plot(fr)
    legend = T("[实际](brand) | 竖线 = 目标", "[actual](brand) | tick = target")
    return _mark(Chart(build, legend))


# ====================================================================== cumulative vs target
def cumulative_vs_target(df, date, value, target, start, end, as_of=None, prior=None,
                         fmt="num", nd=None, labels=None):
    """Within-period cumulative (MTD / YTD) vs a linear target pace, with a run-rate
    projection to period end and, optionally, last period's cumulative (aligned by day of
    period). df: daily values of the CURRENT period. prior: daily values of the comparison
    period (same columns). labels: dict to rename 'actual' / 'target' / 'prior' / 'forecast'."""
    L = dict(actual=T("实际", "Actual"), target=T("目标", "Target"), prior=T("上期", "Prior"),
             forecast=T("预估", "Forecast"))
    L.update(labels or {})
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    n_days = (end - start).days + 1
    d = df[[date, value]].copy()
    d[date] = pd.to_datetime(d[date])
    d = d[(d[date] >= start) & (d[date] <= end)].groupby(date)[value].sum().sort_index()
    as_of = pd.Timestamp(as_of) if as_of is not None else d.index.max()
    d = d[d.index <= as_of]
    if d.empty:
        raise ValueError(f"cumulative_vs_target: no '{value}' rows between {start:%Y-%m-%d} and "
                         f"{(as_of if pd.notna(as_of) else end):%Y-%m-%d}; check the date column / "
                         "start / as_of.")
    day = (d.index - start).days + 1
    cum = d.cumsum().values
    pr = None
    if prior is not None:
        p = prior[[date, value]].copy()
        p[date] = pd.to_datetime(p[date])
        p = p.groupby(date)[value].sum().sort_index()
        pr_day = (p.index - p.index.min()).days + 1
        pr = (pr_day[pr_day <= n_days], p.cumsum().values[:len(pr_day[pr_day <= n_days])])

    def build(w, h):
        s = _base()
        sv = s * 0.88
        elapsed = (as_of - start).days + 1
        proj = cum[-1] / elapsed * n_days if elapsed > 0 else np.nan
        ach_proj = proj / target if target else np.nan
        vals = [target, proj, cum[-1]] + (list(pr[1]) if pr else [])
        yhi = max(v for v in vals if np.isfinite(v)) * 1.06
        yt, ys = nice_breaks(0, yhi, 4)
        yt = [t for t in yt if t <= yhi]
        ylabs = [tick_label(t, fmt, ys) for t in yt]
        end_labs = [f"{L['target']} {fmt_value(target, fmt, nd)}",
                    f"{L['forecast']} {fmt_value(proj, fmt, nd)} ({vc.pct(ach_proj, nd=0)})"]
        if pr:
            end_labs.append(f"{L['prior']} {fmt_value(pr[1][-1], fmt, nd)}")
        right = _max_w(end_labs, s, True) + 0.2
        xt = [1] + [x for x in (7, 14, 21, 28) if x <= n_days - 5] + [n_days]   # no 10/28|10/31 clash
        xl = [(start + pd.Timedelta(days=x - 1)).strftime("%m/%d") for x in xt]
        left = max(_max_w(ylabs, sv) + 0.1, _tw(xl[0], sv) / 2 + 0.04)
        bottom = sv * 1.3 / 72 + 0.08
        fr = Frame(w, h, (1, n_days), (0, yhi), left=left, right=right, top=0.08, bottom=bottom,
                   name="cumulative_vs_target")
        cv = Canvas()
        _y_axis(cv, fr, yt, ylabs, sv)
        _x_axis(cv, fr, xt, xl, sv, edge_align=True)
        cv.line([1, n_days], [target / n_days, target], MUTED, 1.0, lt="dashed")
        if pr:
            cv.line(pr[0], pr[1], GREY, 1.1)
        behind = cum[-1] < target * elapsed / n_days
        col = PAL.bad if behind else PAL.brand
        cv.line(day, cum, col, 2.2)
        cv.pt(day[-1], cum[-1], col, diam_pt=6)
        cv.line([day[-1], n_days], [cum[-1], proj], col, 1.2, lt="dotted")
        cv.pt(n_days, proj, col, "#ffffff", diam_pt=6, stroke_pt=1.2)
        lab_as_of = T(f"截至 {as_of:%m/%d}:{fmt_value(cum[-1], fmt, nd)}",
                      f"as of {as_of:%b %d}: {fmt_value(cum[-1], fmt, nd)}")
        fits_left = day[-1] - fr.dx(0.06 + _tw(lab_as_of, s * 0.95, True)) >= fr.xlim[0]
        cv.text(day[-1] + fr.dx(-0.06 if fits_left else 0.06), cum[-1] + fr.dy(0.08), lab_as_of,
                readable(col), s * 0.95, bold=True, ha="right" if fits_left else "left", va="bottom")
        ends = [target, proj] + ([pr[1][-1]] if pr else [])
        cols = [MUTED, readable(col), MUTED]
        ly, _, _ = _spread(ends, s * 1.3 / 72 * fr.ky, *fr.ylim)       # keep labels inside
        for lab, yy, c in zip(end_labs, ly, cols):
            cv.text(n_days + fr.dx(0.1), yy, lab, c, s, bold=c != MUTED)
        return cv.plot(fr)
    op = T("(", " (")                        # zh() turns "(" full-width; English needs a space
    legend = (f"[{L['actual']}](brand) | {L['target']}{op}" + T("虚线", "dashed") + ") | " +
              (f"{L['prior']}{op}" + T("灰", "grey") + ") | " if prior is not None else "") +
              f"{L['forecast']}{op}" + T("点线,按当前日均", "dotted, run-rate") + ")")
    return _mark(Chart(build, legend))


# ====================================================================== trend (single metric)
def _freq(dates):
    d = pd.Series(pd.to_datetime(dates)).sort_values().drop_duplicates()
    if len(d) < 2:
        return "D"
    step = d.diff().dt.days.median()
    return "D" if step <= 1.5 else "W" if step <= 8 else "M"


def trend(df, date, value, compare="month", align="auto", kind="flow", events=None,
          as_of=None, period_end=None, fmt="num", nd=None, label=None, projection=True):
    """One business metric over time with the house conventions:
    - prior-period overlay (grey dashed): compare='month' | 'year' | None.
      align='auto' -> daily flow metrics by weekday (t-28d / t-364d); kind='stock' (balances,
      billing / due-date metrics) or align='dom' -> same day of month; weekly / monthly data ->
      the previous 1 (month) or 12/52 (year) periods.
    - events: [(date, "label"), ...] -> dotted vertical lines with labels (staggered).
    - incomplete last period (weekly / monthly data with as_of before period_end): last
      segment dashed, point hollow, "as of" note, and a run-rate projection (projection=True).
    label: series name for the end label (default: value column)."""
    d = df[[date, value]].dropna().copy()
    d[date] = pd.to_datetime(d[date])
    d = d.groupby(date)[value].sum().sort_index()
    fq = _freq(d.index)
    if compare:
        if fq == "D":
            al = ("dom" if kind == "stock" else "weekday") if align == "auto" else align
            prior = vc.prior_values(d.index, d.values, compare, al).values
        else:
            k = {("M", "month"): 1, ("M", "year"): 12, ("W", "month"): 4, ("W", "year"): 52}[(fq, compare)]
            prior = d.shift(k).values
    else:
        prior = None
    name = label or str(value)

    def build(w, h):
        s = _base()
        sv = s * 0.88
        n = len(d)
        xs = np.arange(n, dtype=float)
        vals = list(d.values) + ([v for v in prior if np.isfinite(v)] if prior is not None else [])
        partial = False
        proj = None
        if fq in ("W", "M") and as_of is not None and period_end is not None:
            pe, ao = pd.Timestamp(period_end), pd.Timestamp(as_of)
            if ao < pe:
                partial = True
                pstart = d.index[-1]
                prog = vc.time_progress(ao, pstart, pe)
                if projection and prog > 0:
                    proj = d.values[-1] / prog
                    vals.append(proj)
        ylo, yhi = _y_range(np.asarray(vals, float), "auto")
        yt, ys = nice_breaks(ylo, yhi, 4 if h > 2.2 else 3)
        yt = [t for t in yt if ylo - 1e-9 <= t <= yhi + 1e-9]
        ylabs = [tick_label(t, fmt, ys) for t in yt]
        if fq == "M":
            xl_all = _MonthLabels([(t.year, t.month) for t in d.index])
        elif fq == "W":
            xl_all = [t.strftime("%m/%d") for t in d.index]
        else:
            xl_all = [t.strftime("%m/%d") if vc.LANG == "zh" else t.strftime("%b %d") for t in d.index]
        endl = f"{zh(name)}  {fmt_value(d.values[-1], fmt, nd)}"
        right_labs = [endl]
        if proj is not None:
            right_labs.append(T(f"预估 {fmt_value(proj, fmt, nd)}", f"forecast {fmt_value(proj, fmt, nd)}"))
        if prior is not None and np.isfinite(prior[-1]):
            right_labs.append(T(f"上期 {fmt_value(prior[-1], fmt, nd)}", f"prior {fmt_value(prior[-1], fmt, nd)}"))
        right = _max_w(right_labs, s, True) + 0.14
        y_w = _max_w(ylabs, sv) + 0.1
        avail = w - y_w - right
        xt, xl = _thin(list(range(n)), xl_all, max(2, int(avail / (_max_w(xl_all, sv) + 0.2))))
        right = max(right, _tw(xl[-1], sv) / 2 + 0.04)
        y_w = max(y_w, _tw(xl[0], sv) / 2 + 0.04)
        ev_h = (s * 0.85 * 1.3 / 72 * 2 + 0.06) if events else 0.06
        bottom = max(len(str(l).split("\n")) for l in xl) * sv * 1.25 / 72 + 0.08
        fr = Frame(w, h, (0, n - 1), (ylo, yhi), left=y_w, right=right, top=ev_h, bottom=bottom,
                   name="trend")
        cv = Canvas()
        _y_axis(cv, fr, yt, ylabs, sv)
        _x_axis(cv, fr, xt, xl, sv, baseline=ylo == 0, edge_align=True)
        if events:
            pos = {t: i for i, t in enumerate(d.index)}
            for k, (ed, el) in enumerate(sorted(events, key=lambda e: pd.Timestamp(e[0]))):
                ed = pd.Timestamp(ed)
                xi = np.interp(ed.value, [t.value for t in d.index], xs) if ed not in pos else pos[ed]
                cv.seg(xi, xi, fr.yr[0], fr.yr[1], MUTED, 0.7, lt="dotted")
                lvl = k % 2
                cv.text(xi, fr.yr[1] + fr.dy(0.04 + lvl * s * 0.85 * 1.3 / 72), el, MUTED, s * 0.85,
                        ha="center", va="bottom")
        if prior is not None:
            ok = np.isfinite(prior)
            if ok.sum() > 1:
                cv.line(xs[ok], prior[ok], GREY, 1.1, lt="dashed")
        v = d.values
        if partial and n >= 2:
            cv.line(xs[:-1], v[:-1], PAL.brand, 2.0)
            cv.line(xs[-2:], v[-2:], mix(PAL.brand, "#ffffff", 0.35), 1.6, lt="dashed")
            cv.pt(xs[-1], v[-1], PAL.brand, "#ffffff", diam_pt=6, stroke_pt=1.2)
            note = T(f"截至 {pd.Timestamp(as_of):%m/%d}", f"as of {pd.Timestamp(as_of):%b %d}")
            cv.text(xs[-1], v[-1] - fr.dy(0.1), note, MUTED, sv, ha="right", va="top")
            if proj is not None:
                cv.seg(xs[-1], xs[-1], v[-1], proj, MUTED, 0.8, lt="dotted")
                cv.pt(xs[-1], proj, MUTED, "#ffffff", diam_pt=5, stroke_pt=1.0)
        else:
            cv.line(xs, v, PAL.brand, 2.0)
            cv.pt(xs[-1], v[-1], PAL.brand, diam_pt=5.5)
        ends = [v[-1]] + ([proj] if proj is not None else []) + (
            [prior[-1]] if prior is not None and np.isfinite(prior[-1]) else [])
        cols = [readable(PAL.brand)] + ([MUTED] if proj is not None else []) + (
            [MUTED] if prior is not None and np.isfinite(prior[-1]) else [])
        ly, _, _ = _spread(ends, s * 1.25 / 72 * fr.ky, *fr.ylim)
        for lab, yy, c in zip(right_labs, ly, cols):
            cv.text(n - 1 + fr.dx(0.1), yy, lab, c, s, bold=c != MUTED)
        return cv.plot(fr)
    cmp_txt = {"month": T("上月同期", "same period last month"),
               "year": T("去年同期", "same period last year")}.get(compare, "")
    legend = (f"[{name}](brand)" + (f" | {cmp_txt}(" + T("灰虚线", "grey dashed") + ")" if compare else ""))
    return _mark(Chart(build, legend))


# ====================================================================== driver tree
def driver_tree(nodes, highlight_top=True, kind_default="growth"):
    """Metric decomposition tree, left to right, e.g. GMV = users × txn/user × ticket.
    nodes: list of dicts {id, label, cur, prev, parent (None for root), op ('×' | '+' | '−'
    | '÷' -- how the node combines with its siblings), fmt, nd, kind ('growth' | 'pp'),
    higher_is_better, threshold}.
    Each box shows label, current value, ▲▼ change and the node's contribution to its
    parent's change (× / ÷: log-share of the parent's change; + / −: the absolute change,
    which stays meaningful when siblings offset each other). The largest contributor among
    the root's direct drivers gets a focus border."""
    by_id = {n["id"]: dict(n) for n in nodes}
    kids = {k: [] for k in by_id}
    root = None
    for n in nodes:
        if n.get("parent") is None:
            root = n["id"]
        else:
            kids[n["parent"]].append(n["id"])
    if root is None:
        raise ValueError("driver_tree: one node needs parent=None (the root)")

    def contrib(nid):
        n = by_id[nid]
        par = n.get("parent")
        if par is None:
            return None
        p = by_id[par]
        ops = {by_id[c].get("op", "×") for c in kids[par]}
        try:
            if ops <= {"×", "÷"}:
                lr = math.log(p["cur"] / p["prev"])
                sign = -1 if n.get("op") == "÷" else 1
                return sign * math.log(n["cur"] / n["prev"]) / lr if lr else None
            dp = p["cur"] - p["prev"]
            sign = -1 if n.get("op") == "−" else 1
            return sign * (n["cur"] - n["prev"]) / dp if dp else None
        except (ValueError, ZeroDivisionError, TypeError):
            return None

    depth, order = {}, []

    def walk(nid, dd):
        depth[nid] = dd
        order.append(nid)
        for c in kids[nid]:
            walk(c, dd + 1)
    walk(root, 0)
    leaves = [nid for nid in order if not kids[nid]]
    shares = {nid: contrib(nid) for nid in order}
    top_leaf = None
    if highlight_top:
        cand = [(abs(shares[c]), c) for c in kids[root] if shares.get(c) is not None]
        top_leaf = max(cand)[1] if cand else None

    def build(w, h):
        b = _base()
        s_lab, s_val, s_d = b * 0.82, b * 1.15, b * 0.8
        ncol = max(depth.values()) + 1
        gap_x = 0.35 * b / 12 + 0.1
        bw = (w - gap_x * (ncol - 1)) / ncol
        texts = {}
        for nid in order:
            n = by_id[nid]
            dtext, dval = delta(n["cur"], n["prev"], n.get("kind", kind_default), 1)
            sh = shares.get(nid)
            if n.get("parent") is not None and n.get("op", "×") in ("+", "−"):
                dd = n["cur"] - n["prev"]
                extra = ("+" if dd > 0 else "") + fmt_value(dd, n.get("fmt", "num"), n.get("nd"))
            else:
                extra = (T(f"贡献 {vc.pct(sh, nd=0)}", f"{vc.pct(sh, nd=0)} of change")
                         if sh is not None else "")
            texts[nid] = (dtext, dval, extra)
        one_line = all(_tw(t[0] + (" · " + t[2] if t[2] else ""), s_d, True) <= bw - 0.16
                       for t in texts.values())
        n_d = 1 if one_line else 2
        bh = (s_lab * 1.3 + s_val * 1.3 + s_d * 1.35 * n_d) / 72 + 0.12
        gap_y = 0.12 * b / 12 + 0.04
        need = len(leaves) * bh + (len(leaves) - 1) * gap_y
        if need > h + 1e-6:
            print(f"WARNING driver_tree: {len(leaves)} leaves need {need:.2f} in height, have "
                  f"{h:.2f}; use a taller panel or fewer nodes.")
        ypos = {}
        cur_y = [h - (h - need) / 2 - bh / 2]

        def place(nid):
            if not kids[nid]:
                ypos[nid] = cur_y[0]
                cur_y[0] -= bh + gap_y
            else:
                for c in kids[nid]:
                    place(c)
                ys = [ypos[c] for c in kids[nid]]
                ypos[nid] = (max(ys) + min(ys)) / 2
        place(root)
        fr = Frame(w, h, (0, w), (0, h), name="driver_tree", quiet=True)
        cv = Canvas()
        for nid in order:
            n = by_id[nid]
            x0 = depth[nid] * (bw + gap_x)
            yc = ypos[nid]
            is_top = nid == top_leaf
            dtext, dval, extra = texts[nid]
            flag, bad, _ = is_anomaly(value=n["cur"], change=dval, threshold=n.get("threshold"),
                                      higher_is_better=n.get("higher_is_better", True))
            cv.rect(x0, x0 + bw, yc - bh / 2, yc + bh / 2, "#ffffff" if not is_top else
                    mix(PAL.focus, "#ffffff", 0.88), PAL.focus if is_top else GRID,
                    1.4 if is_top else 0.8)
            tx = x0 + 0.08
            ty = yc + bh / 2 - 0.06
            cv.text(tx, ty, _fit_label(n["label"], bw - 0.16, s_lab), MUTED, s_lab, va="top")
            ty -= s_lab * 1.3 / 72
            cv.text(tx, ty, fmt_value(n["cur"], n.get("fmt", "num"), n.get("nd")), INK, s_val,
                    bold=True, va="top")
            ty -= s_val * 1.3 / 72
            dc = _alert_color(flag, bad)
            if n_d == 1:
                cv.text(tx, ty, dtext + (" · " + extra if extra else ""), dc, s_d,
                        bold=flag or is_top, va="top")
            else:
                cv.text(tx, ty, dtext, dc, s_d, bold=flag or is_top, va="top")
                if extra:
                    cv.text(tx, ty - s_d * 1.35 / 72, _fit_label(extra, bw - 0.16, s_d), MUTED, s_d,
                            va="top")
            ch = kids[nid]
            if ch:
                xr_ = x0 + bw
                xm = xr_ + gap_x / 2
                cv.seg(xr_, xm, yc, yc, MUTED, 0.8)
                ys = [ypos[c] for c in ch]
                cv.seg(xm, xm, min(ys), max(ys), MUTED, 0.8)
                for c in ch:
                    cv.seg(xm, xr_ + gap_x, ypos[c], ypos[c], MUTED, 0.8)
                for a, c in zip(ch[:-1], ch[1:]):
                    op = by_id[c].get("op", "×")
                    ym = (ypos[a] + ypos[c]) / 2
                    cv.rect(xm - 0.07, xm + 0.07, ym - 0.07, ym + 0.07, "#ffffff")
                    cv.text(xm, ym, op, INK, b * 0.95, bold=True, ha="center")
        return cv.plot(fr)
    return _mark(Chart(build))


# ====================================================================== contribution table
def contrib_table(df, dim, prev, cur, top_n=None, other=None, fmt="num", nd=None,
                  sort="contrib", growth_alert=None, higher_is_better=True, total=True):
    """Dimension table for 'who drove the change': name | current (with data bar) | growth
    (▲▼) | change | share of total change. Sorted by |contribution| (or 'cur'). Rows beyond
    top_n are merged into "Other". growth_alert: e.g. 0.05 -> |growth| > 5% is an anomaly
    (red if bad direction, bold if good). The total row sits on top in bold."""
    d = df[[dim, prev, cur]].dropna().groupby(dim, as_index=False)[[prev, cur]].sum()
    d["chg"] = d[cur] - d[prev]
    d = d.reindex(d["chg"].abs().sort_values(ascending=False).index if sort == "contrib"
                  else d[cur].sort_values(ascending=False).index)
    other = other or T("其他", "Other")
    if top_n and len(d) > top_n:
        head, tail = d.iloc[:top_n - 1], d.iloc[top_n - 1:]
        d = pd.concat([head, pd.DataFrame({dim: [other], prev: [tail[prev].sum()],
                                           cur: [tail[cur].sum()], "chg": [tail["chg"].sum()]})])
    tot_prev, tot_cur = d[prev].sum(), d[cur].sum()
    tot_chg = tot_cur - tot_prev
    rows = []
    if total:
        rows.append(dict(name=T("合计", "Total"), p=tot_prev, c=tot_cur, chg=tot_chg, total=True))
    for _, r in d.iterrows():
        rows.append(dict(name=str(r[dim]), p=r[prev], c=r[cur], chg=r["chg"], total=False))
    heads = [T("维度", "Segment"), T("本期", "Current"), T("增速", "Growth"), T("变化", "Change"),
             T("占变化", "Share")]

    def build(w, h):
        n = len(rows) + 1
        s = _row_font(h, n, "contrib_table", gap=1.75)
        rh = h / n
        cmax = max(r["c"] for r in rows if not r["total"]) or 1
        cells = []
        for r in rows:
            g = r["c"] / r["p"] - 1 if r["p"] else np.nan
            gtxt = delta(r["c"], r["p"], "growth")[0] if r["p"] else "–"
            ctxt = ("+" if r["chg"] > 0 else "") + fmt_value(r["chg"], fmt, nd)
            share = r["chg"] / tot_chg if tot_chg else np.nan
            flag, bad = False, False
            if growth_alert is not None and np.isfinite(g) and not r["total"]:
                flag, bad, _ = is_anomaly(change=g, threshold=growth_alert,
                                          higher_is_better=higher_is_better)
            cells.append((r, fmt_value(r["c"], fmt, nd), gtxt, ctxt,
                          vc.pct(share, nd=0) if np.isfinite(share) else "–", flag, bad))
        floor = _base() * 0.7
        while True:                                  # shrink the font until the columns fit
            name_w = max(_max_w([_fit_label(c[0]["name"], 0.3 * w, s) for c in cells] + [heads[0]], s, True), 0.4) + 0.12
            val_w = _max_w([c[1] for c in cells] + [heads[1]], s, True) + 0.1
            g_w = _max_w([c[2] for c in cells] + [heads[2]], s, True) + 0.16
            c_w = _max_w([c[3] for c in cells] + [heads[3]], s, True) + 0.16
            sh_w = _max_w([c[4] for c in cells] + [heads[4]], s, True) + 0.12
            fixed = name_w + val_w + g_w + c_w + sh_w
            if fixed + 0.3 <= w or s <= floor:
                break
            s = max(floor, s * 0.92)
        if fixed + 0.3 > w:
            print(f"WARNING contrib_table: {w:.2f} in is too narrow for the columns; widen the panel.")
        bar_w = max(0.1, min(0.45 * w, w - fixed - 0.05))
        spare = max(0.0, w - fixed - bar_w - 0.02) / 4
        val_w, g_w, c_w, sh_w = val_w + spare, g_w + spare, c_w + spare, sh_w + spare
        xs = np.cumsum([0, name_w, val_w, bar_w, g_w, c_w, sh_w])
        fr = Frame(w, h, (0, w), (0, h), name="contrib_table", quiet=True)
        cv = Canvas()
        yh = h - rh / 2
        cv.text(0.04, yh, heads[0], MUTED, s * 0.9)
        cv.text(xs[2] - 0.06, yh, heads[1], MUTED, s * 0.9, ha="right")
        cv.text(xs[4] - 0.06, yh, heads[2], MUTED, s * 0.9, ha="right")
        cv.text(xs[5] - 0.06, yh, heads[3], MUTED, s * 0.9, ha="right")
        cv.text(xs[6] - 0.06, yh, heads[4], MUTED, s * 0.9, ha="right")
        cv.seg(0, w, h - rh, h - rh, MUTED, 0.6)
        for i, (r, vt, gt, ct, st, flag, bad) in enumerate(cells):
            y = h - rh * (i + 1.5)
            bold = r["total"]
            cv.text(0.04, y, _fit_label(r["name"], name_w - 0.1, s, bold), INK, s, bold=bold)
            cv.text(xs[2] - 0.06, y, vt, INK, s, bold=bold, ha="right")
            if not r["total"]:
                bl = (bar_w - 0.12) * max(r["c"], 0) / cmax
                cv.rect(xs[2] + 0.04, xs[2] + 0.04 + bl, y - rh * 0.22, y + rh * 0.22,
                        mix(PAL.brand, "#ffffff", 0.7))
            gc = _alert_color(flag, bad) if not bold else INK
            cv.text(xs[4] - 0.06, y, gt, gc, s, bold=bold or flag, ha="right")
            cv.text(xs[5] - 0.06, y, ct, INK if bold else MUTED, s, bold=bold, ha="right")
            cv.text(xs[6] - 0.06, y, st, INK if bold else MUTED, s, bold=bold, ha="right")
            if i < len(cells) - 1:
                cv.seg(0, w, y - rh / 2, y - rh / 2, GRID, 0.4 if not bold else 0.6)
        return cv.plot(fr)
    return _mark(Chart(build))


# ====================================================================== bar + rate (the one allowed dual axis)
def bar_line_dual(df, x, bar, line, bar_label=None, line_label=None, bar_fmt="num",
                  line_fmt="pct", line_range=None, nd=None):
    """Scale bars (left axis) + a rate line (right axis) -- the only dual-axis chart in the
    house style. Each axis is coloured like its series; the rate axis starts at 0 unless
    `line_range=(lo, hi)` is given (never auto-zoomed, so crossings are not over-read).
    Only the latest bar and latest point carry value labels."""
    d = df[[x, bar, line]].dropna(subset=[bar]).copy()
    xpos, tks, tlabs = _x_positions(d[x])
    d["__x"] = xpos
    d = d.sort_values("__x")
    bl, ll = bar_label or str(bar), line_label or str(line)
    bar_c, line_c = mix(PAL.brand, "#ffffff", 0.45), PAL.focus
    legend = f"[{bl}]({readable(bar_c)}) " + T("(柱,左轴)", "(bars, left)") + \
             f" | [{ll}](focus) " + T("(线,右轴)", "(line, right)")

    def build(w, h):
        s = _base()
        sv = s * 0.88
        bhi = d[bar].max() * 1.12
        bt, bs = nice_breaks(0, bhi, 4)
        bt = [t for t in bt if t <= bhi]
        llo, lhi = line_range or (0.0, float(d[line].max()) * 1.15)
        lt_ = [llo + (t / bt[-1]) * (lhi - llo) for t in bt] if bt[-1] else bt
        lstep = (lhi - llo) / max(len(bt) - 1, 1)
        ll_labs = [tick_label(v, line_fmt, lstep) for v in lt_]
        bl_labs = [tick_label(t, bar_fmt, bs) for t in bt]
        n = len(d)
        xs = d["__x"].values.astype(float)
        if tks is None:
            xl_all = [str(v) for v in d[x]]
        else:
            xl_all = tlabs
        left = _max_w(bl_labs, sv) + 0.1
        right = _max_w(ll_labs, sv) + 0.1
        xt, xl = _thin(list(tks if tks is not None else xs), xl_all,
                       max(2, int((w - left - right) / (_max_w(xl_all, sv) + 0.2))))
        bottom = max(len(str(l).split("\n")) for l in xl) * sv * 1.25 / 72 + 0.08
        top = sv * 1.3 / 72 + sv * 0.6 / 72 + 0.1
        # the latest bar's value label sits above the bar: extend the y range so it stays below
        # the axis titles (bars near the top tick would otherwise push it out of the panel)
        need = 0.04 + vc.line_height("0", sv, True) + 0.02
        dh = max(h - top - bottom, 0.15 * h)
        ytop = bt[-1]
        if need < dh:
            ytop = max(ytop, float(d[bar].values[-1]) / (1 - need / dh))
        fr = Frame(w, h, (xs.min() - 0.5, xs.max() + 0.5), (0, ytop), left=left, right=right,
                   top=top, bottom=bottom, name="bar_line_dual")
        cv = Canvas()
        for t, lb, lr in zip(bt, bl_labs, ll_labs):
            cv.seg(fr.xr[0], fr.xr[1], t, t, GRID, 0.4)
            cv.text(fr.xr[0] - fr.dx(0.05), t, lb, readable(bar_c), sv, ha="right")
            cv.text(fr.xr[1] + fr.dx(0.05), t, lr, readable(line_c), sv)
        _x_axis(cv, fr, xt, xl, sv)
        for xv, bv in zip(xs, d[bar].values):
            cv.rect(xv - 0.36, xv + 0.36, 0, bv, bar_c)
        scale = lambda v: (v - llo) / (lhi - llo) * bt[-1] if lhi > llo else 0
        ly = [scale(v) for v in d[line].values]
        cv.line(xs, ly, line_c, 2.0)
        cv.pt(xs[-1], ly[-1], line_c, diam_pt=5.5)
        cv.text(xs[-1], d[bar].values[-1] + fr.dy(0.04), fmt_value(d[bar].values[-1], bar_fmt, nd),
                readable(bar_c), sv, ha="center", va="bottom", bold=True)
        cv.text(xs[-1] - fr.dx(0.08), ly[-1] + fr.dy(0.06), fmt_value(d[line].values[-1], line_fmt, nd),
                readable(line_c), s, ha="right", va="bottom", bold=True)
        yt_ = fr.yr[1] + fr.dy(sv * 0.6 / 72 + 0.06)
        cv.text(fr.xr[0] - fr.dx(left - 0.02), yt_, bl, readable(bar_c), sv, bold=True, va="bottom")
        cv.text(fr.xr[1] + fr.dx(right - 0.02), yt_, ll, readable(line_c), sv, bold=True,
                ha="right", va="bottom")
        return cv.plot(fr)
    return _mark(Chart(build, legend))


__all__ = ["kpi_cards", "bullet", "cumulative_vs_target", "trend", "driver_tree",
           "contrib_table", "bar_line_dual"]
