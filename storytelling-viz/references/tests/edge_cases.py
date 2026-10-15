# /// script
# requires-python = ">=3.10"
# dependencies = ["plotnine>=0.15,<0.16", "pandas", "pillow", "pypdf"]
# ///
"""Regression test: every chart function on awkward real-world data, in a slide and in a
journal column. A case PASSES when it renders without an exception AND its QA/WARNING output
matches expectation (some cases are *supposed* to warn, e.g. 40 rows in 4 inches).

    uv run edge_cases.py            -> summary table; images in ./out/edge/ (current directory)
    uv run edge_cases.py bar        -> only cases whose name contains "bar"
"""
import contextlib, io, sys, pathlib, traceback
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "scripts"))
import numpy as np
import pandas as pd
import viz_common as vc
import charts as C
import biz as B

OUT = str(pathlib.Path.cwd() / "out" / "edge")   # never inside the skill
rng = np.random.default_rng(1)
LONG = "Home & kitchen – small appliances, online channel, first-time buyers"


def d(**cols):
    return pd.DataFrame(cols)


def cats(n, long=False):
    return [(f"{LONG} #{i}" if long and i % 3 == 0 else f"Category {i}") for i in range(n)]


months = pd.date_range("2024-01-01", periods=30, freq="MS")
days = pd.date_range("2026-07-01", periods=92, freq="D")

CASES = {   # name: (lambda -> chart, expect_warning: True | False | spec name where it should warn)
    "bar_40_rows_no_topn": (lambda: C.bar_rank(d(c=cats(40, True), v=rng.gamma(2, 50, 40)), "c", "v"), True),
    "bar_40_rows_top10": (lambda: C.bar_rank(d(c=cats(40, True), v=rng.gamma(2, 50, 40)), "c", "v",
                                             top_n=10, highlight="Category 4"), False),
    "bar_negative_values": (lambda: C.bar_rank(d(c=cats(8), v=[120, 80, 35, 5, -12, -40, -95, 60]), "c", "v",
                                               highlight=lambda c: c.endswith("6")), False),
    "bar_single_row": (lambda: C.bar_rank(d(c=["Only one"], v=[42.0]), "c", "v"), False),
    "bar_outlier_and_tiny": (lambda: C.bar_rank(d(c=cats(6), v=[1e9, 3e6, 2e6, 5e5, 1e4, 12]), "c", "v"), False),
    "bar_pct_with_nan": (lambda: C.bar_rank(d(c=cats(6), v=[0.31, np.nan, 0.12, 0.08, 0.004, 0.2]), "c", "v",
                                            fmt="pct"), False),
    "line_12_series_no_highlight": (lambda: C.line_trend(
        pd.concat([d(m=months, s=f"S{k}", v=rng.normal(100 + 5 * k, 6, 30)) for k in range(12)]),
        "m", "v", group="s"), True),
    "line_12_series_highlight": (lambda: C.line_trend(
        pd.concat([d(m=months, s=f"S{k}", v=rng.normal(100 + 5 * k, 6, 30)) for k in range(12)]),
        "m", "v", group="s", highlight=["S3", "S7"]), False),
    "line_nan_and_single_point": (lambda: C.line_trend(
        pd.concat([d(m=months, s="A", v=np.where(np.arange(30) % 7 == 0, np.nan, np.linspace(5, 9, 30))),
                   d(m=months[-1:], s="New product", v=[7.2])]), "m", "v", group="s"), False),
    "line_daily_dates_band": (lambda: C.line_trend(
        d(t=days, v=np.cumsum(rng.normal(0, 1, 92)) + 50).assign(lo=lambda x: x.v - 3, hi=lambda x: x.v + 3),
        "t", "v", band=("lo", "hi"), ref=(50, "target")), False),
    "line_negative_crossing_zero": (lambda: C.line_trend(
        d(x=np.arange(20), v=np.sin(np.arange(20) / 3) * 0.04), "x", "v", fmt="pct"), False),
    "dumbbell_decreases_long_labels": (lambda: C.dumbbell(
        d(c=cats(9, True), a=rng.uniform(20, 90, 9), b=rng.uniform(10, 95, 9)), "c", "a", "b",
        labels=("2024", "2025"), highlight="Category 4"), False),
    "slope_identical_values": (lambda: C.slope(d(c=cats(7), a=[10] * 7, b=[12, 12, 12, 11, 13, 12, 12]),
                                               "c", "a", "b"), False),
    "slope_groups_change_mode": (lambda: C.slope(
        d(c=cats(10), a=rng.uniform(5, 200, 10), b=rng.uniform(5, 200, 10),
          g=["North"] * 5 + ["South"] * 5), "c", "a", "b", groups="g", mode="change"), False),
    "range_all_inside": (lambda: C.range_dot(d(c=cats(5), lo=[1, 2, 3, 4, 5], hi=[3, 4, 5, 6, 7],
                                               v=[2, 3, 4, 5, 6]), "c", "lo", "hi", "v"), False),
    "stacked_zero_total_row": (lambda: C.stacked_100(
        pd.concat([d(g="A", p=["x", "y", "z"], n=[5, 3, 2]), d(g="Empty", p=["x", "y", "z"], n=[0, 0, 0])]),
        "g", "p", "n", order=["x", "y", "z"]), False),
    "heatmap_30x20_too_dense": (lambda: C.heatmap(
        d(x=np.repeat([f"C{i}" for i in range(30)], 20), y=np.tile([f"R{j}" for j in range(20)], 30),
          v=rng.normal(0, 1, 600)), "x", "y", "v"), "journal-1col"),
    "heatmap_with_missing": (lambda: C.heatmap(
        d(x=np.repeat(list("ABCD"), 4), y=np.tile(list("wxyz"), 4),
          v=[1, 2, np.nan, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 99]), "x", "y", "v"), False),
    "waterfall_all_negative": (lambda: C.waterfall(d(c=["a", "b", "c"], v=[-5, -3, -1]), "c", "v",
                                                   start=("Start", 20)), False),
    "dist_hist_groups": (lambda: C.distribution(
        d(g=np.repeat(["A", "B", "C"], 500), v=np.concatenate([rng.normal(m, 1, 500) for m in (0, 1, 3)])),
        "v", group="g", kind="hist"), False),
    "dist_strip_5000": (lambda: C.distribution(
        d(g=np.repeat(["A", "B"], 2500), v=rng.lognormal(3, 1, 5000)), "v", group="g", kind="strip"), False),
    "scatter_two_points": (lambda: C.scatter(d(x=[1.0, 2.0], y=[3.0, 1.0]), "x", "y", fit="linear"), False),
    "scatter_200_fit_labels": (lambda: C.scatter(
        d(x=rng.uniform(0, 10, 200), y=rng.normal(0, 2, 200), n=[f"p{i}" for i in range(200)])
        .assign(y=lambda t: t.y + 0.8 * t.x), "x", "y", label="n", highlight=["p1", "p2", "p3"],
        fit="linear", x_title="Spend ($k)", y_title="Revenue ($k)"), False),
    "forest_crossing_ref": (lambda: C.point_range(
        d(c=cats(6), e=[0.3, -0.1, 0.05, 0.2, -0.25, 0.0], lo=[0.1, -0.3, -0.1, 0.0, -0.4, -0.2],
          hi=[0.5, 0.1, 0.2, 0.4, -0.1, 0.2]), "c", "e", "lo", "hi", ref=0), False),
    "small_multiples_13": (lambda: C.small_multiples(
        pd.concat([d(m=months, f=f"Region {k}", v=rng.normal(50, 5, 30).cumsum() / 10) for k in range(13)]),
        "m", "v", "f", highlight="Region 2"), "journal-1col"),
    "en_with_cjk_labels": (lambda: C.bar_rank(d(c=["北区", "South", "东区 East"], v=[3, 2, 1]),
                                              "c", "v", highlight="北区"), False),
    "biz_kpi_missing_prev_and_tiny": (lambda: B.kpi_cards([
        dict(label="No comparison", value=1234.0),
        dict(label="A very long KPI label that will not fit in the card", value=5.2e9, prev=4.1e9,
             target=6e9, progress=0.5, spark=[1, 2, 3, 2, 4]),
        dict(label="Rate", value=0.5, prev=0.5, kind="pp", fmt="pct", spark=[0.5] * 6)]),
        "journal-1col"),   # 3.5in column: card 2 (target bar) truly has no room for its sparkline
    "biz_bullet_over_target": (lambda: B.bullet(d(c=cats(6), a=[120, 80, 5, 0, 300, 50],
                                                  t=[100, 100, 100, 100, 100, 100]), "c", "a", "t",
                                                progress=0.6), False),
    "biz_cumulative_day1": (lambda: B.cumulative_vs_target(
        d(date=pd.date_range("2026-10-01", periods=1), v=[100.0]), "date", "v", target=4000,
        start="2026-10-01", end="2026-10-31"), False),
    "biz_trend_daily_short": (lambda: B.trend(d(date=pd.date_range("2026-10-01", periods=10),
                                                v=rng.normal(100, 5, 10)), "date", "v"), False),
    "biz_trend_monthly_partial": (lambda: B.trend(d(m=pd.date_range("2025-01-01", periods=22, freq="MS"),
                                                    v=rng.normal(60e6, 4e6, 22)), "m", "v",
                                                  compare="year", as_of="2026-10-09",
                                                  period_end="2026-10-31"), False),
    "biz_driver_tree_3_levels": (lambda: B.driver_tree([
        dict(id="r", label="Revenue", cur=120.0, prev=100.0),
        dict(id="a", parent="r", op="+", label="Products", cur=80.0, prev=70.0),
        dict(id="b", parent="r", op="+", label="Services", cur=40.0, prev=30.0),
        dict(id="a1", parent="a", op="×", label="Visits", cur=800.0, prev=740.0),
        dict(id="a2", parent="a", op="×", label="Yield / visit", cur=0.1, prev=0.0946, fmt="pct", kind="pp"),
        dict(id="b1", parent="b", op="×", label="Orders", cur=4000.0, prev=3300.0),
        dict(id="b2", parent="b", op="×", label="Fee / order", cur=0.01, prev=0.00909, fmt="{:.4f}")]),
        "journal-1col"),
    "biz_contrib_20_rows_topn": (lambda: B.contrib_table(
        d(k=cats(20, True), p=rng.uniform(1, 50, 20), c=rng.uniform(1, 50, 20)), "k", "p", "c",
        top_n=8, growth_alert=0.2), False),
    "biz_dual_with_nan": (lambda: B.bar_line_dual(
        d(m=pd.date_range("2026-01-01", periods=9, freq="MS"), b=rng.uniform(4e4, 6e4, 9),
          r=[0.2, 0.21, np.nan, 0.22, 0.2, 0.19, 0.21, 0.2, 0.18]), "m", "b", "r"), False),
    # v3.1.1 regressions
    "slope_change_zero_start": (lambda: C.slope(d(c=["a", "b", "c"], a=[0.0, 5.0, -4.0], b=[3.0, 6.0, -2.0]),
                                                "c", "a", "b", mode="change"), True),
    "dumbbell_negative_base": (lambda: C.dumbbell(d(c=["Profit A", "Profit B"], a=[-10.0, 8.0], b=[-5.0, 4.0]),
                                                  "c", "a", "b", highlight="Profit A"), False),
    "scatter_groups_legend": (lambda: C.scatter(d(x=rng.uniform(0, 9, 60), y=rng.uniform(0, 9, 60),
                                                  g=np.repeat(["North", "South", "East"], 20)), "x", "y",
                                                groups="g"), False),
    "biz_kpi_negative_prev": (lambda: B.kpi_cards([dict(label="Net income", value=-5e6, prev=-1e7),
                                                   dict(label="Net flow", value=2e6, prev=-1e6)]), False),
}


def run_one(name, make, spec):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        vc.figure([[(vc.titled(make(), title=name), 1)]], spec=spec, name=f"{name}_{spec}",
                  outdir=OUT, formats=("png",), caption="Basis: synthetic edge-case data.")
    out = buf.getvalue()
    warns = [l.strip() for l in out.splitlines() if "WARNING" in l]
    return warns


if __name__ == "__main__":
    pick = sys.argv[1:]
    rows, bad = [], 0
    for name, (make, expect) in CASES.items():
        if pick and not any(k in name for k in pick):
            continue
        vc.set_lang("en")
        for spec in ("slide", "journal-1col"):
            try:
                warns = run_one(name, make, spec)
                exp = expect is True or expect == spec
                if bool(warns) == exp:
                    status = "PASS"
                else:
                    status = "MISS" if exp else "WARN"     # MISS: an expected warning did not fire
            except Exception:
                status, warns = "FAIL", [traceback.format_exc().splitlines()[-1]]
            if status != "PASS":
                bad += 1
            rows.append((status, name, spec, warns[:3]))
    for status, name, spec, warns in rows:
        print(f"{status:5s} {name:32s} {spec:13s}" + (f"  {warns[0][:110]}" if warns else ""))
        for w in warns[1:]:
            print(" " * 53 + w[:110])
    print(f"\n{len(rows) - bad}/{len(rows)} as expected; images in {OUT}")
    sys.exit(1 if bad else 0)
