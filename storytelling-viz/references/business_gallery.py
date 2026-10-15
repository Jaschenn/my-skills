# /// script
# requires-python = ">=3.10"
# dependencies = ["plotnine>=0.15,<0.16", "pandas", "pillow", "pypdf"]
# ///
"""Business-analysis gallery (house style): a month-to-date review in zh slide format and a
doc-width version in English. Synthetic data. Run:  uv run business_gallery.py [outdir]

Pages:
  biz_kpi        KPI cards: value + ▲▼ vs prior + target/time progress + sparkline
  biz_pace       cumulative MTD vs target pace, last month's cumulative, run-rate forecast
  biz_trend      daily trend with weekday-aligned prior month, events; monthly trend with an
                 incomplete current month + projection
  biz_drivers    driver tree (GMV = buyers × orders/buyer × basket) + contribution table
  biz_target     bullet chart of attainment by business line vs time progress
  biz_dual       scale bars + rate line (the only dual axis allowed)
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import numpy as np
import pandas as pd
import viz_common as vc
from viz_common import figure, titled, set_lang, T, time_progress
import biz as B

OUT = sys.argv[1] if len(sys.argv) > 1 else str(pathlib.Path.cwd() / "out" / "business")   # never inside the skill
rng = np.random.default_rng(3)
AS_OF = pd.Timestamp("2026-10-09")
M_START, M_END = pd.Timestamp("2026-10-01"), pd.Timestamp("2026-10-31")
PROG = time_progress(AS_OF, M_START, M_END)

# ---- synthetic data: every figure comes from the seed above (generic retail scenario) ------
# daily GMV with a weekly rhythm (weekends higher), Jul 1 – Oct 9
BASE = rng.uniform(1.5e6, 3.0e6)
days = pd.date_range("2026-07-01", AS_OF, freq="D")
gmv = BASE * (1 + 0.18 * (days.dayofweek >= 5)) * (1 + 0.0009 * np.arange(len(days))) \
      * rng.normal(1, 0.035, len(days))
daily = pd.DataFrame({"date": days, "gmv": gmv})
sep = daily[(daily.date >= "2026-09-01") & (daily.date <= "2026-09-30")]
octo = daily[daily.date >= M_START]
monthly = daily.assign(m=daily.date.dt.to_period("M").dt.to_timestamp()).groupby("m", as_index=False).gmv.sum()
monthly = pd.concat([pd.DataFrame({"m": pd.date_range("2025-10-01", periods=9, freq="MS"),
                                   "gmv": rng.normal(27 * BASE, 1.3 * BASE, 9)}), monthly], ignore_index=True)
TARGET = round(octo.gmv.sum() / PROG * rng.uniform(0.95, 1.05), -6)      # monthly GMV target

USERS = rng.uniform(0.8e6, 1.5e6)                      # buyers this month (slightly down)
USERS_PREV = USERS * rng.uniform(1.002, 1.008)
PAY = rng.uniform(0.70, 0.80)                          # payment success rate (drops past threshold)
PAY_PREV = PAY + rng.uniform(0.022, 0.035)
REF = rng.uniform(0.05, 0.08)                          # refund rate (rises past threshold)
REF_PREV = REF - rng.uniform(0.012, 0.02)

# one set of numbers for the whole report: MTD GMV (KPI card) = driver-tree root = table total
MTD = octo.gmv.sum()
MTD_PREV = sep[sep.date.dt.day <= AS_OF.day].gmv.sum()
FREQ_PREV = rng.uniform(3.2, 4.0)                      # orders / buyer
FREQ = FREQ_PREV * rng.uniform(1.005, 1.015)
BASKET, BASKET_PREV = MTD / (USERS * FREQ), MTD_PREV / (USERS_PREV * FREQ_PREV)   # $ / order
assert BASKET > BASKET_PREV, "seed no longer matches the driver-tree title; pick another seed"
ONLINE_SH_PREV = rng.uniform(0.33, 0.38)
ONLINE_SH = ONLINE_SH_PREV - rng.uniform(0.012, 0.02)

CATS = [("服装", "Apparel"), ("数码", "Electronics"), ("家居", "Home"), ("美妆", "Beauty"),
        ("食品", "Grocery"), ("图书", "Books")]
_sh = np.sort(rng.dirichlet(np.full(len(CATS), 2.0)))[::-1]              # category shares
_sh_cur = _sh * rng.uniform(0.92, 1.08, len(CATS))
CAT_SEP = MTD_PREV * _sh / 1e6                                         # $M, Sep 1–9 (unrounded:
CAT_OCT = MTD * _sh_cur / _sh_cur.sum() / 1e6                          # totals = KPI / tree exactly)
REGIONS = [("北区", "North"), ("南区", "South"), ("东区", "East"), ("西区", "West"), ("中区", "Central")]
REG_TGT = np.round(rng.uniform(5e6, 60e6, len(REGIONS)), -5)
REG_ACT = np.round(REG_TGT * PROG * rng.uniform(0.8, 1.25, len(REGIONS)), -4)
VISITS = np.round(rng.uniform(50e3, 70e3, 6), -2)
CONV = np.round(rng.uniform(0.19, 0.23, 6), 3)


def pages(lang, spec, suffix):
    set_lang(lang)
    o = f"{OUT}"
    mtd, mtd_prev = MTD, MTD_PREV
    weekly = daily.set_index("date").gmv.resample("W").sum()
    cards = B.kpi_cards([
        dict(label=T("GMV(本月累计)", "GMV (MTD)"), value=mtd, prev=mtd_prev, vs=T("vs 上月同期", "vs same days last month"),
             target=TARGET, progress=PROG, spark=list(weekly.values[-13:-1])),   # complete weeks only
        dict(label=T("下单用户", "Buyers"), value=USERS, prev=USERS_PREV, vs=T("vs 上月同期", "vs last month"),
             spark=list(rng.normal(USERS, USERS * 0.015, 12)),
             history=list(rng.normal(USERS_PREV, USERS * 0.003, 8))),
        dict(label=T("支付成功率", "Payment success rate"), value=PAY, prev=PAY_PREV, kind="pp", fmt="pct",
             vs=T("vs 上月同期", "vs last month"), threshold=0.02, spark=list(rng.normal(PAY_PREV, 0.01, 12))),
        dict(label=T("退款率", "Refund rate"), value=REF, prev=REF_PREV, kind="pp", fmt="pct",
             higher_is_better=False, threshold=0.01, vs=T("vs 9/09", "vs Sep 9"),
             spark=list(np.linspace(REF_PREV, REF, 12))),
    ])
    figure([[(cards, 1)]], spec=spec, size=(vc.SPECS[spec]["W"], vc.SPECS[spec]["W"] * 0.3),
           name=f"biz_kpi_{suffix}", outdir=o,
           caption=T("口径:GMV 为已支付订单金额(USD);本月累计截至 10/09,与 9/01–9/09 比较。",
                     "Basis: paid-order GMV (USD); MTD to Oct 9 vs Sep 1–9."))

    pace = B.cumulative_vs_target(octo, "date", "gmv", target=TARGET, start=M_START, end=M_END,
                                  as_of=AS_OF, prior=sep)
    figure([[(titled(pace, title=T("本月 GMV 累计 vs 目标进度", "October GMV: cumulative vs target pace")), 1)]],
           spec=spec, name=f"biz_pace_{suffix}", outdir=o,
           caption=T("口径:按下单日累计;预估 = 截至目前日均 × 当月天数。", "Basis: by order date; forecast = run-rate × days in month."))

    tr_d = B.trend(daily[daily.date >= "2026-08-15"], "date", "gmv", compare="month",
                   events=[("2026-09-15", T("9.15 大促", "Sep sale")), ("2026-10-01", T("国庆", "Holiday"))],
                   label="GMV")
    tr_m = B.trend(monthly, "m", "gmv", compare="year", as_of=AS_OF, period_end=M_END, label="GMV")
    figure([[(titled(tr_d, title=T("日 GMV(按星期对齐上月)", "Daily GMV (prior month aligned by weekday)")), 1)],
            [(titled(tr_m, title=T("月 GMV(10 月未完结)", "Monthly GMV (October in progress)")), 1)]],
           spec=spec, name=f"biz_trend_{suffix}", outdir=o,
           caption=T("口径:已支付 GMV,USD;日度对比 = 28 天前同星期。", "Basis: paid-order GMV, USD; daily prior = same weekday 28 days earlier."))

    # GMV = buyers × orders / buyer × basket; buyers = online + offline (consistent by construction)
    on, on_p = USERS * ONLINE_SH, USERS_PREV * ONLINE_SH_PREV
    tree = B.driver_tree([
        dict(id="gmv", label="GMV", cur=USERS * FREQ * BASKET, prev=USERS_PREV * FREQ_PREV * BASKET_PREV),
        dict(id="u", parent="gmv", op="×", label=T("下单用户", "Buyers"), cur=USERS, prev=USERS_PREV),
        dict(id="f", parent="gmv", op="×", label=T("人均单数", "Orders / buyer"), cur=FREQ, prev=FREQ_PREV, fmt="{:.2f}"),
        dict(id="t", parent="gmv", op="×", label=T("客单价(USD)", "Basket (USD)"), cur=BASKET, prev=BASKET_PREV, fmt="{:.2f}"),
        dict(id="on", parent="u", op="+", label=T("线上用户", "Online"), cur=on, prev=on_p, threshold=0.03),
        dict(id="off", parent="u", op="+", label=T("门店用户", "In-store"), cur=USERS - on, prev=USERS_PREV - on_p),
    ])
    ch = pd.DataFrame({"channel": [T(z, e) for z, e in CATS], "sep": CAT_SEP, "oct": CAT_OCT})
    tab = B.contrib_table(ch, "channel", "sep", "oct", growth_alert=0.05, fmt="{:.2f}")
    figure([[(titled(tree, title=T("GMV 拆解:客单价和频次带来增长,用户略降", "GMV drivers: basket and frequency up, buyers slightly down")), 6),
             (titled(tab, title=T("分品类贡献($M)", "Contribution by category ($M)")), 5)]],
           spec=spec, name=f"biz_drivers_{suffix}", outdir=o,
           size=None if spec == "slide" else (vc.SPECS[spec]["W"], 4.5),   # 4-leaf tree needs the height
           caption=T("口径:10/01–10/09 vs 9/01–9/09;贡献 = 对数拆解份额(乘法)/ 变化量份额(加法)。",
                     "Basis: Oct 1–9 vs Sep 1–9; contribution = log share (×) / share of change (+)."))

    lines = pd.DataFrame({"line": [T(z, e) for z, e in REGIONS], "act": REG_ACT, "tgt": REG_TGT})
    figure([[(titled(B.bullet(lines, "line", "act", "tgt", progress=PROG),
                     title=T(f"目标达成(时间进度 {vc.pct(PROG, nd=0)})", f"Attainment ({vc.pct(PROG, nd=0)} of month elapsed)")), 1)]],
           spec=spec, name=f"biz_target_{suffix}", outdir=o,
           caption=T("口径:月目标为预算口径;红色 = 落后时间进度。", "Basis: monthly budget; red = behind time progress."))

    m6 = pd.DataFrame({"m": pd.date_range("2026-04-01", periods=6, freq="MS"), "visits": VISITS, "rate": CONV})
    figure([[(titled(B.bar_line_dual(m6, "m", "visits", "rate", bar_label=T("访客数", "Visitors"),
                                     line_label=T("转化率", "Conversion rate"), line_range=(0, 0.3)),
                     title=T("访客数与转化率", "Visitors and conversion rate")), 1)]],
           spec=spec, name=f"biz_dual_{suffix}", outdir=o,
           caption=T("口径:按访问月份;转化率 = 下单访客 / 访客(D+7)。", "Basis: by visit month; conversion = buying visitors / visitors (D+7)."))


if __name__ == "__main__":
    pages("zh", "slide", "slide")
    pages("en", "doc", "doc")
