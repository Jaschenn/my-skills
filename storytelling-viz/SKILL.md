---
name: "storytelling-viz"
description: Make finished static charts with plotnine, in Chinese or English, for slides, documents, weekly/monthly business reviews and journal papers. Picks the chart from what the user wants to compare (ranking, trend, change between two points, composition, contribution to a change, target attainment, metric decomposition, distribution, relationship, estimates with intervals, KPI summary), renders it at the exact output size (slide / doc / journal column) as SVG, PDF and PNG, and checks the layout automatically. Business-review charts follow reporting conventions (▲▼ instead of red/green, colour only for anomalies, basis captions, period-aligned comparisons). Use when the user asks to draw, plot, chart or visualize data, make a figure for a deck, report, business review or paper, or fix a chart that looks "busy but says nothing". 用于画图、做图表、汇报/周报月报/论文配图、改图。Not for interactive charts (plotly/echarts) or dashboards.
---

# storytelling-viz:可直接用的图

目标是**一张能直接放进汇报、文档或期刊的图**,而不是随手画的柱状图。它要满足三点:

- **图型对。**图型与要比较的东西匹配,焦点清楚,直接标注,不用图例。
- **在真实数据上不崩。**长标签、负值、缺失、类别多、离群值都能正确显示。
- **符合输出规格。**尺寸、字号、线宽、格式、字体嵌入都合规。

本 skill 只管图。选题、分析和报告结构不在本 skill 范围内。

## 工作流

1. **判断场景。**场景决定颜色、脚注、数字等默认约定(见"两种场景的约定"):
   - **经营汇报**:给业务方或管理层看的**经营指标**图，不论频率和场合(周报、月报、日报看板、异动归因、管理层 / 董事会 / 战略会的经营数据页)。判断依据是"内容是不是经营指标、读者是不是要据此做业务决策",不是"是不是周报"。
   - **通用 / 出版**:分析或研究文档、实验结果、网页、论文配图等。
   - 拿不准时按经营汇报处理(约定更严，只多一行脚注)。**经营汇报场景必须先读 `references/business.md`**,即使示例代码看起来已经够用。
2. **按"要比较什么"选函数。**见下方选函数表;两种场景用同一张表。
3. **选输出规格。**用 `spec=` 指定(幻灯片、文档、期刊……)。
4. **出图，看自动检查结果。**`figure()` / `save()` 渲染完会打印 `QA … ok` 或列出每条警告;返回值的 `.qa` 是同一份问题列表(空列表 = 通过)。**有警告就改，不交付。**
5. **打开 PNG 按清单检查。**用 Read 打开生成的 PNG,按文末的检查清单逐条核对。

## 快速开始

```python
# /// script
# dependencies = ["plotnine>=0.15,<0.16", "pandas", "pillow", "pypdf"]
# ///
import sys; sys.path.insert(0, "<skill>/scripts")
from viz_common import figure, titled, set_lang, save
import charts as C          # 通用图表函数
import biz as B             # 经营汇报图表函数(与 C 混用无妨)

set_lang("en")                                   # 或 "zh"(默认)
c = C.bar_rank(df, "channel", "gmv", highlight="POS", top_n=8, fmt="num")
figure([[(titled(c, title="POS is the only channel that shrank"), 1)]],
       spec="doc", name="fig1", outdir="out")
save(c, "fig2", spec="journal-1col", outdir="out")   # 期刊单图：不加标题

# 经营汇报:同样的 figure(),但必须写口径脚注
k = B.kpi_cards([dict(label="GMV (MTD)", value=16.5e6, prev=15.9e6, target=57e6, progress=0.29)])
figure([[(k, 1)]], spec="doc", size=(6.5, 2), name="kpi", outdir="out",
       caption="Basis: paid-order GMV (USD); MTD to Oct 9 vs Sep 1–9.")
```

## 选函数

按**要比较的东西**找行。`C.` = `charts.py`,`B.` = `biz.py`;标 ★ 的是为经营汇报设计的函数，但任何场景都能用。

| 要比较的 | 函数 | 要点 |
|---|---|---|
| **排名**、一个时点的构成、正负值 | `C.bar_rank(df, cat, value, highlight=, top_n=, fmt=)` | 自动排序;超过 `top_n` 合并为"其他/Other";值写在条内或条外 |
| **谁带来了变化**(分维度的规模 + 增速 + 贡献) | ★ `B.contrib_table(df, dim, prev, cur, top_n=, growth_alert=)` | 规模数据条、▲▼ 增速、变化量、占总变化;合计行置顶 |
| **趋势**:1–N 条线放一起 | `C.line_trend(df, x, y, group=, highlight=, band=, ref=)` | 线尾直接标注;按月自动两层月份标签;缺失断线;`band=` 置信带 |
| **趋势**:多组分开看 | `C.small_multiples(df, x, y, facet, highlight=)` | 所有格子同一 y 刻度;灰色背景线是其他组 |
| **趋势**:一个经营指标 + 同期对比 | ★ `B.trend(df, date, value, compare="month"/"year", events=, as_of=, period_end=)` | 自动叠加对齐好的同期线;标注事件;未完结期虚线 + 预估 |
| **进度**:期内累计 vs 目标 | ★ `B.cumulative_vs_target(df, date, value, target, start, end, as_of=, prior=)` | 累计实际、目标进度线、上期累计、按日均折算的预估 |
| **实际 vs 目标**(多行) | ★ `B.bullet(df, cat, actual, target, progress=)` | 实际条 + 目标竖线 + "按进度应完成"虚线;落后进度的行变红 |
| **实际 vs 区间**(预测区间、正常范围) | `C.range_dot(df, cat, low, high, value, flag="below", bench=)` | 越界的行用焦点色;`bench=` 指定基准行 |
| **每组两个值**(前后、计划与实际) | `C.dumbbell(df, cat, start, end, labels=, highlight=)` | 空心点 = 起点,实心点 = 终点;按终点排序;每行带变化率 |
| **首尾两期**,各组规模差异大 | `C.slope(df, cat, start, end, mode="change", groups=)` | `mode="change"` 时所有线从 0% 出发;起点为 0 的行剔除并打 WARNING |
| **增减桥接**:上期 → 各项贡献 → 本期 | `C.waterfall(df, cat, delta, start=, end_label=)` | 增减默认中性色 + 正负号;好坏确有业务含义时传 `up=PAL.good, down=PAL.bad` |
| **指标拆解**(GMV = 用户 × 频次 × 客单价) | ★ `B.driver_tree(nodes)` | 每个节点写当前值、▲▼ 变化、贡献(乘法用对数份额，加法用变化量) |
| **构成**:多组各自的占比 | `C.stacked_100(df, cat, part, value, order=, focus_cat=)` | 部分按自然顺序、单色渐变;图例行在 `chart.legend` |
| **二维表**(组 × 时间、组 × 组) | `C.heatmap(df, x, y, value, fmt=)` | 白到单色,色阶取 2%–98% 分位;深色格白字 |
| **规模 + 比率**(申请数与通过率) | ★ `B.bar_line_dual(df, x, bar, line, line_range=)` | 唯一允许的双轴:规模柱(左)+ 比率线(右),比率轴从 0 或固定范围 |
| **分布** | `C.distribution(df, value, group=, kind="box"/"strip"/"hist")` | 按中位数排序;须线 1.5×IQR;点多时抽样 |
| **两个连续变量的关系** | `C.scatter(df, x, y, label=, fit="linear", groups=, x_title=, y_title=)` | OLS + 置信带,显示 R²;只标高亮的点;`groups=` 时图例在 `chart.legend` |
| **估计值与置信区间** | `C.point_range(df, cat, est, low, high, ref=0)` | 森林图;右侧写 "估计值 [下限, 上限]" |
| **几个关键数字的摘要**(报表顶部) | ★ `B.kpi_cards([dict(label, value, prev, target, progress, spark, …), …])` | 大数字、▲▼ 变化、达成率与时间进度、迷你趋势线;异常才变红 |

★ 函数的参数细节(`kpi_cards` 的字段、`driver_tree` 的节点结构、`trend` 的 `events=` / `as_of=`、`cumulative_vs_target` 的 `prior=`、异常规则、同期对齐方式)见 `references/business.md`。

**两行都像时怎么选:**

- `B.contrib_table` vs `C.waterfall`:要同时看规模、增速和占比，或维度超过约 8 个 → 表;要讲"上期怎么一步步变成本期"、项目不超过约 8 个 → 瀑布图。归因页常两个并排。
- `C.line_trend` vs `C.small_multiples`:有一条要突出的线、或不超过 4 条 → `line_trend`(超过 4 条加 `highlight=`);要逐组看形状、各组地位相当 → `small_multiples`。期刊单栏(3.5in)放不下 5 个以上分面，用 `line_trend` + `highlight=`。
- 每组两个值，先看**各组规模**:相近(最大 / 最小 < 约 10 倍)→ `C.dumbbell`。相差一个数量级以上时，小组在共同刻度上看不清，改为直接画变化率：不超过约 8 组 → `C.slope(mode="change")`;更多组 → 先算出变化率列，用 `C.bar_rank(df, cat, "chg", fmt="pct")`,绝对规模写进标签或旁边的表。

**所有函数共用的参数和返回值:**

- `highlight=`:类别名、列表或函数。被选中的项用焦点色,其余变灰,类别名也会同色加粗。
- `fmt=`:`"num"`、`"pct"`、`"pp"`、`"int"`、`"raw"`、格式字符串或函数;`nd=` 控制小数位。
- 返回的是面板对象，直接放进 `figure()` / `save()`;`chart + plotnine层` 可继续叠加;`chart.legend` 是一行彩色词图例，`titled()` 会自动用上。

**没有合适的函数时，自己画：**

1. 用 `C.Frame(w, h, xr, yr, left=…, …)` 按文字的实际宽度(`text_width`)预留四周空白;轴范围用 `C.axis_range(lo, hi)`。
2. 在 `C.Canvas()` 上用 `rect`、`seg`、`pt`、`text`、`line`、`band` 画元素,用 `cv.plot(fr)` 生成图。
3. 包成 `C.Chart(build)`,其中 `build(w, h)` 在拿到最终尺寸后才计算布局。

**不要在代码里写死坐标或轴范围。**

## 两种场景的约定

函数本身在两种场景下画法一样;不同的是这些默认约定。代码里没有"场景"参数:★ 函数自带经营汇报的画法(▲▼、异常才着红),并会让 `figure()` 在缺口径脚注时报 WARNING;同一页上的 `C.` 图则由你按下表的约定传参(如 `caption=`、`highlight=`、`up=` / `down=` 的颜色)。

| 项 | 通用 / 出版 | 经营汇报 |
|---|---|---|
| 涨跌 | 好坏确有含义时才用 `good` / `bad`,且必须配正负号或文字 | 一律 ▲▼ + 中性色，**不用红绿表示涨跌** |
| 什么时候着红 | 只在表示"坏"时 | 只有被判定为**异常**的(落后进度 / 超阈值 / 超出历史 ±2σ),好方向的异常只加粗 |
| 要读者"看这里"(如拖累增长的渠道) | `highlight=`(焦点色橙) | 同左;橙色只表示"看这里",不表示好坏，是否异常仍由 ▲▼ 和红色表达 |
| 口径脚注 | 建议写 | **必填**(`caption=`):分子分母、币种、时间窗口、对比基准;缺了 `figure()` 会报 WARNING |
| 对比基准 | 按分析需要 | 默认环比、本月累计 vs 上月同期(同样天数)、目标达成;日度流量指标按星期对齐同期 |
| 未完结的当期 | 浅色或虚线 + "截至 X 日" | 同左，并画按进度折算的全期预估 |
| 数字 | 按领域习惯 | 金额 K/M/B;比率变化用 pp,增速用 %;单位写在标题或注释里 |
| 双轴 | 不用 | 只允许"规模柱 + 比率线"(`B.bar_line_dual`) |
| 饼图 / 环形图 | 尽量不用 | 禁用 |
| 常用规格 | `doc`、`web`、`journal-*` | PPT 用 `slide`;飞书 / Lark / Notion 文档或聊天里用 `doc`(PNG 插图);用户没说放哪时用 `doc` |

原因与反例见 `references/rules.md`(经营汇报部分是 B1–B7)。

## 输出规格(`spec=`)

| spec | 尺寸(英寸) | 正文字号 | 默认格式 | 用途 |
|---|---|---|---|---|
| `slide` / `slide-4x3` | 13.33×7.5 / 10×7.5 | 12 / 11.5 | 轮廓 SVG、可编辑 SVG、PNG(150dpi) | 汇报幻灯片 |
| `web` | 8×4.5 | 10.5 | SVG、PNG(200dpi) | 网页、邮件 |
| `doc` | 6.5×4 | 9 | PDF、SVG、PNG(300dpi) | 文档正文里的一张图 |
| `a4` / `letter` | 整页 | 10 | PDF、SVG、PNG | 整页报告 |
| `journal-1col` / `-1.5col` / `-2col` | 3.5 / 5.35 / 7.2 宽 | 7–7.5 | PDF、SVG、PNG(600dpi) | 期刊(89 / 136 / 183 mm) |

- `size=(w, h)` 可以覆盖默认尺寸,比如更高的期刊图、更矮的 KPI 卡片行。
- 字号、线宽和点的大小都会随规格缩放;PDF 用 Type 42 嵌入字体,满足期刊要求。
- 期刊图不加标题，图注写在正文里：单张图用 `save(chart, name, spec="journal-1col")`;多面板图用 `figure(rows, spec="journal-2col")`,不传 `title=`,面板标号用 `titled(chart, title="a")`。
- `figure()` 出一整页(可有标题、副标题、口径脚注、多个面板);`save(chart, "fig2", spec="journal-1col")` 只导出一张图，没有页标题和脚注。经营汇报要脚注，所以用 `figure()`。
- 两种 SVG:`<name>.svg` 的文字转成了轮廓，任何地方打开都一样;`<name>_editable.svg` 保留文字，可在 Figma / PPT 里改字，但对方电脑要有同样的字体。PPT 里要改字用后者，否则用前者或 PNG。
- `slide` / `web` 默认不出 PDF,需要时传 `formats=("pdf", "png")`。

## 组合多面板

- `figure(rows, title=, subtitle=, caption=, spec=)`:`rows=[[(panel, span), …], …]`,`span` 是同一行内的相对宽度。
- 行高默认自动分配:只放文字或表格的行按内容取高度,其余行平分剩下的空间。
- `titled(chart, title=, legend=, note=)`:在图上方加面板标题、图例行和注释;`legend` 不填时自动用 `chart.legend`。
- 标题支持富文本标记:`**粗体**`;`[短语](focus)` 表示加粗并着色。颜色可以写 `focus`、`brand`、`good`、`bad`、`muted`、`ink` 或 `#hex`。
- 其他面板:`text_panel(para(...))` 放段落,`table_panel(rows, header=)` 放小表(数字列自动右对齐),`column(a, b)` 把两个面板上下叠放。
- 每个面板都按最终尺寸单独渲染,所以字号就是实际磅值;拼接 SVG 时会自动给各面板的元素 id 加前缀,避免冲突。

## 视觉规则(函数已默认执行,自己画图时照做)

- **颜色分层：**`focus`(橙)标出唯一要看的东西，本身不代表好坏;`brand`(深蓝)用于常规系列;灰色用于背景和参照;`good` / `bad` 的用法按场景(见上表)。
- **同色即同义。**文字关键词与对应数据用同一种颜色;含义不同的元素不要共用颜色。
- **文字要读得清。**文字对比度至少 4.5:1。焦点色做文字时用 `readable(color)` 自动加深;深色底上的字用 `ink_on(fill)`。函数会自动处理,自己画图时 `Canvas.text` 也会检查并警告。
- **用直接标注代替图例。**轴标题不能是字段名。所有柱子都标了数值时，就不要 y 轴和网格。
- **排序要有意义。**有自然顺序的(阶段、等级)按自然顺序，否则按数值排序;焦点项放在最显眼的位置;不要按字母序。
- **坐标轴。**柱状图必须从 0 开始;折线图数据靠近 0 时从 0 开始(`zero="auto"`);相关的几个面板用同一刻度;双轴只有"规模柱 + 比率线"一种。
- **精度。**够区分就行。数字一律由数据计算,用 `pct` / `pp` / `num` / `fmt_value` 格式化，不要手写。
- **按要比较的东西选图：**占比变化不要用绝对值堆积柱;多组构成不要画多个饼图;超过 4 条线时用 `highlight=` 突出重点或改用小多图;树图、雷达图比较两项要超过约 2 秒就换成横条。
- **数据问题要在图上标出。**未完结的当期用浅色或虚线并注明"截至 X 日";小样本写出 n;缺失时断线，不要连起来。

细则与原因见 `references/rules.md`;SWD 改图案例的设计做法见 `references/swd_practices.md`。

## 语言与排版

- `set_lang("zh" | "en")` 会同时切换默认字体、月份标签(中文"1月\n2026",英文"Jan\n2026")和"其他/Other"。金额单位两种语言都默认 K/M/B,需要万/亿时用 `set_number_style("cn")`。含中文的标签自动改用 CJK 字体。`T("其他", "Other")` 按当前语言取字符串。
- 中文字符串会自动经过 `zh()`:标点转为全角，去掉全角标点旁多余的空格，网址和缩写保持不变。
- 折行规则：数字和英文单词不拆开;标点不出现在行首;左括号不留在行尾。
- 启动时会打印所用字体。出现 `WARNING: no CJK font` 时需要安装 Noto Sans SC。

## 交付前检查

**自动检查(看 `figure()` 的输出或 `.qa`):**

- [ ] `QA … ok`:文字没有重叠、没有跑出面板、没有被绘图区裁切。
- [ ] 没有对比度警告，也没有 `rows do not fit`、`labels take most of the panel`、`cells too small`、`basis caption` 这类警告。

**人工检查(打开 PNG):**

- [ ] 遮住标题，只看图，能说出要表达的内容吗?焦点只有一个吗?
- [ ] 标题和标注里的数字，与图上的数值来自同一个变量吗?
- [ ] 图型匹配要比较的东西吗(见选函数表)?排序有意义吗?相关面板刻度一致吗?
- [ ] 颜色用法符合场景约定吗?去掉颜色后，好坏 / 涨跌还能从符号或文字读出来吗?
- [ ] 没有默认图例、字段名、3D 效果或渐变吗?
- [ ] 尺寸和字号符合目标规格吗(期刊正文 7pt 左右，幻灯片 12pt 以上)?需要 PDF 的已经导出了吗?

**经营汇报另加:**

- [ ] 口径脚注写全了吗?和其他报表对过数吗(同一份报告里，同一个数在各页一致)?
- [ ] 单位、小数位、格式全图统一吗?

## 环境与测试

- **依赖：**`plotnine>=0.15,<0.16`(已在 0.15.8 + matplotlib 3.11 下验证)、`pandas`、`pillow`,导出 PDF 还要 `pypdf`。代码在 `scripts/viz_common.py`(底层工具、规格、导出、QA)、`scripts/charts.py`(`C.`)和 `scripts/biz.py`(`B.`)。
- **输出位置：**把 `outdir` 设成用户能看到的目录;不要写进 skill 目录本身。
- **示例图库：**`uv run references/gallery.py [outdir]`(每个 `C.` 函数，中文幻灯片 + 英文期刊);`uv run references/business_gallery.py [outdir]`(每个 `B.` 函数，中文幻灯片 + 英文文档)。默认输出到当前目录的 `out/`。
- **回归测试：**`uv run references/tests/edge_cases.py` 用 38 组边界数据，在两种规格下(共 76 项)检查函数的表现和 QA 是否符合预期;改了图表函数后必须重跑，全部通过才能发布。
- **沙箱里装不上 plotnine 时:**先用 `PYTHONPATH=<skill>/scripts/plotnine_preview` 的 matplotlib 模拟器预览版式和跑 QA(线宽和裁切规则与 plotnine 一致)。模拟器的 `QA ok` **不算交付标准**:把脚本交给用户本机 `uv run`,并明确告诉用户这张图还没有用真 plotnine 渲染和检查过。
