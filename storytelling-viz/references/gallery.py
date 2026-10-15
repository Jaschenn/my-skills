# /// script
# requires-python = ">=3.10"
# dependencies = ["plotnine>=0.15,<0.16", "pandas", "pillow", "pypdf"]
# ///
"""Gallery: every chart function in two settings --
  zh + business slide (16:9)          -> out/gallery/<name>_slide.*
  en + journal figure (Nature widths) -> out/gallery/<name>_journal.*
Data is synthetic. Run:  uv run gallery.py [outdir]
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import numpy as np
import pandas as pd
import viz_common as vc
from viz_common import figure, titled, set_lang, T
import charts as C

OUT = sys.argv[1] if len(sys.argv) > 1 else str(pathlib.Path.cwd() / "out" / "gallery")   # never inside the skill
# ------------------------------------------------------------------ synthetic data
# Everything below is generated from one seed (no hand-typed figures); the data is built once,
# so the zh and en runs plot exactly the same numbers. Generic retail scenario.
rng = np.random.default_rng(7)
CH_ZH = ["服装", "数码", "家居", "美妆", "食品", "母婴", "运动", "图书", "宠物"]
CH_EN = ["Apparel", "Electronics", "Home", "Beauty", "Grocery", "Baby", "Sports", "Books", "Pets"]
REG_ZH = ["北区", "南区", "东区", "西区", "中区", "沿海区"]
REG_EN = ["North", "South", "East", "West", "Central", "Coastal"]
STAGES_ZH = ["待付款", "待发货", "运输中", "待签收", "售后中"]
STAGES_EN = ["Unpaid", "To ship", "In transit", "Delivered", "After-sales"]
SEG_ZH = ["新客", "老客", "高客单", "低客单", "线上", "线下"]
SEG_EN = ["New", "Existing", "High basket", "Low basket", "Online", "Offline"]
BRIDGE_ZH = ["新客", "老客复购", "客单价", "退款", "汇率"]
BRIDGE_EN = ["New buyers", "Repeat", "Basket size", "Refunds", "FX"]
FOCUS = 2                                   # the one category that shrank (story of the bars)
months = pd.date_range("2025-01-01", periods=18, freq="MS")

G0 = np.round(np.sort(rng.uniform(5, 55, len(CH_EN)))[::-1], 1)          # last year, by category
growth = rng.uniform(1.12, 1.30, len(CH_EN))
growth[FOCUS] = rng.uniform(0.62, 0.75)
G1 = np.round(G0 * growth, 1)


def _series(n):
    """Monthly return rate per region; region 1 drifts up."""
    rows = []
    for k in range(n):
        level = 0.08 + 0.01 * k
        trend = 0.003 if k == 1 else -0.0005 * k
        for i, m in enumerate(months):
            rate = level + trend * i + 0.005 * np.sin(i / 2 + k) + rng.normal(0, 0.0015)
            rows.append(dict(month=m, k=k, rate=rate))
    return pd.DataFrame(rows)


TS = _series(len(REG_EN))
PIPE = rng.integers(80, 300, (5, len(STAGES_EN)))
PIPE[4, 0] = PIPE[4].max() + 120                                        # region 5: unpaid pile-up
LO = np.round(rng.uniform(2.5, 4.0, len(REG_EN)), 1)                     # conversion forecast range, %
HI = np.round(LO + rng.uniform(0.8, 1.4, len(REG_EN)), 1)
ACT = np.round((LO + HI) / 2 + rng.normal(0, 0.25, len(REG_EN)), 2)
ACT[3] = np.round(LO[3] - rng.uniform(0.2, 0.5), 2)                     # one region below range
BRIDGE = np.round(np.r_[rng.uniform(1, 6, 3), -rng.uniform(0.5, 3, 2)], 1)
START = round(float(rng.uniform(60, 80)), 1)
DIST = np.concatenate([rng.lognormal(mu, 0.55, 300) for mu in rng.uniform(3.8, 4.6, 4)])
SPEND = rng.uniform(3, 6.5, 2 * len(REG_EN))
SALES = 20 + 6 * SPEND + rng.normal(0, 3, len(SPEND))
EST = np.round(rng.normal(0.02, 0.015, len(SEG_EN)), 3)
SE = np.round(rng.uniform(0.006, 0.014, len(SEG_EN)), 3)


def build(lang):
    zh = lang == "zh"
    ch, reg = (CH_ZH, REG_ZH) if zh else (CH_EN, REG_EN)
    stages, seg, drivers = (STAGES_ZH, SEG_ZH, BRIDGE_ZH) if zh else (STAGES_EN, SEG_EN, BRIDGE_EN)
    return dict(
        ch=ch, reg=reg,
        gmv=pd.DataFrame({"channel": ch, "y25": G0, "y26": G1}),
        ts=TS.assign(region=[reg[k] for k in TS.k]).drop(columns="k"),
        stages=pd.DataFrame([dict(market=m, stage=st, n=int(v))
                             for m, vals in zip(reg[:5], PIPE) for st, v in zip(stages, vals)]),
        ranges=pd.DataFrame({"city": reg, "lo": LO, "hi": HI, "act": ACT}),
        bridge=pd.DataFrame({"driver": drivers, "delta": BRIDGE}),
        dist=pd.DataFrame({"segment": np.repeat(reg[:4], 300), "amount": DIST}),
        sc=pd.DataFrame({"city": reg + [r + "-2" for r in reg], "income": SPEND, "usage": SALES}),
        forest=pd.DataFrame({"segment": seg, "est": EST, "se": SE}),
    )


def run(lang, spec, suffix, size=None):
    set_lang(lang)
    D = build(lang)
    zh = lang == "zh"
    out = f"{OUT}"
    sc = D["sc"]
    fo = D["forest"].assign(lo=lambda x: x.est - 1.96 * x.se, hi=lambda x: x.est + 1.96 * x.se)
    pos = D["ch"][FOCUS]
    jobs = {
        "bar_rank": (C.bar_rank(D["gmv"], "channel", "y26", highlight=pos, top_n=7),
                     T("各品类 GMV(百万)", "GMV by category ($m)")),
        "line_trend": (C.line_trend(D["ts"], "month", "rate", group="region", highlight=D["reg"][1], fmt="pct"),
                       T("各区域退货率", "Return rate by region")),
        "dumbbell": (C.dumbbell(D["gmv"], "channel", "y25", "y26", labels=("2025", "2026"), highlight=pos),
                     T("品类 GMV:2025 → 2026", "Category GMV, 2025 → 2026")),
        "slope": (C.slope(D["gmv"].head(6), "channel", "y25", "y26", labels=("2025", "2026"),
                          mode="change", highlight=pos), T("同比变化", "Change vs 2025")),
        "range_dot": (C.range_dot(D["ranges"], "city", "lo", "hi", "act", flag="below", fmt="raw"),
                      T("转化率 vs 预测区间(%)", "Conversion rate vs forecast range (%)")),
        "stacked_100": (C.stacked_100(D["stages"], "market", "stage", "n", focus_cat=D["reg"][4]),
                        T("在途订单的状态构成", "Open orders by status")),
        "heatmap": (C.heatmap(D["ts"].assign(m=D["ts"].month.dt.strftime("%y-%m")).query("month >= '2026-01-01'"),
                              "region", "m", "rate", fmt="pct", nd=1), T("月度退货率", "Monthly return rate")),
        "waterfall": (C.waterfall(D["bridge"], "driver", "delta", start=(T("9 月", "Sep"), START),
                                  end_label=T("10 月", "Oct")), T("GMV 变化拆解(百万)", "GMV bridge ($m)")),
        "distribution": (C.distribution(D["dist"], "amount", group="segment", kind="box",
                                        highlight=D["reg"][3]), T("客单价分布", "Order value distribution")),
        "scatter": (C.scatter(sc, "income", "usage", label="city", fit="linear",
                              highlight=[sc.city.iloc[0]], x_title=T("广告投入(百万)", "Ad spend ($m)"),
                              y_title=T("销售额(百万)", "Sales ($m)")), T("广告投入与销售额", "Ad spend vs sales")),
        "point_range": (C.point_range(fo, "segment", "est", "lo", "hi", ref=0, fmt="pct",
                                      highlight=fo.segment.iloc[0]), T("各客群促销效应(95% CI)", "Promotion effect by segment (95% CI)")),
        "small_multiples": (C.small_multiples(D["ts"], "month", "rate", "region", fmt="pct",
                                              highlight=D["reg"][1]), T("各区域退货率", "Return rate by region")),
    }
    for name, (chart, ttl) in jobs.items():
        panel = titled(chart, title=ttl)          # legend line comes from chart.legend
        figure([[(panel, 1)]], spec=spec, size=size, name=f"{name}_{suffix}", outdir=out)


if __name__ == "__main__":
    run("zh", "slide", "slide")
    run("en", "journal-2col", "journal")
