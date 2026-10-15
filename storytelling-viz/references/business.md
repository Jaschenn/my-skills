# 经营分析场景(house style)

场景是经营汇报(周报/月报、异动归因、管理层汇报、日报看板)时读这一页。SKILL.md 的"两种场景的约定"是摘要，这里是细则和 ★ 函数(`scripts/biz.py`,`import biz as B`)的参数;规则的原因与反例见 `rules.md` B1–B7。

这些约定作用于整页，不只是 ★ 函数:同一页里的 `C.` 图(如 `C.waterfall`、`C.bar_rank`)也按这里的颜色、数字和脚注规则出。

**约定**

| 项 | 规则 |
|---|---|
| 涨跌 | 用 ▲▼ 和中性色(INK),**不用红绿表示涨跌**;只有被判定为异常的才着色:坏方向用 `PAL.bad`,好方向只加粗 |
| 异常 | `is_anomaly()` 三条规则任一命中:①达成率落后时间进度;②变化超过固定阈值(`threshold=`);③超出近 8 期均值 ±2σ(`history=`) |
| 默认对比 | 环比(上周/上月)、本月累计对比上月同期(同样天数)、目标/预算达成;同比按需 |
| 同期对齐 | 日度流量指标(订单、活跃、访问)**按星期对齐**:上月 = 28 天前,去年 = 364 天前;月内累计和与日历日挂钩的指标(账单日、到期日、余额类)**按第 N 天对齐**;`prior_values(..., align=)` |
| 数字 | 金额 K/M/B;比率的变化用 pp,增速用 %;单位写在标题或注释里,图上数字不带单位 |
| 未完结期 | 虚线或浅色 + "截至 X 日",并画按进度折算的全期预估(`time_progress()`) |
| 双轴 | 只允许"规模柱(左轴)+ 比率线(右轴)":两轴刻度与对应系列同色,比率轴从 0 开始或固定范围,不自动缩放 |
| 禁用 | 饼图、环形图 |
| 口径 | 每张图都要有口径脚注(`caption=`):分子分母、币种、时间窗口、对比基准;页面含 biz 图却没有 caption 时 `figure()` 会报 WARNING |
| 交付 | PPT 用 `spec="slide"`;飞书/Lark/Notion 文档用 `spec="doc"`(PNG 插图) |

**函数**

| 场景 | 函数 | 要点 |
|---|---|---|
| 报表顶部指标卡 | `kpi_cards([dict(label, value, prev, target, progress, spark, history, threshold, kind, fmt), …])` | 大数字、▲▼ 变化、达成率与时间进度、迷你趋势线;异常才变红 |
| 目标达成(多条线) | `bullet(df, cat, actual, target, progress=)` | 实际条 + 目标竖线 + "按进度应完成"虚线;落后进度的行变红 |
| 月内/年内累计对比目标 | `cumulative_vs_target(df, date, value, target, start, end, as_of=, prior=)` | 累计实际、线性目标进度线、上月累计(灰线)、按日均折算的预估及达成率 |
| 单指标趋势 | `trend(df, date, value, compare="month"/"year", kind="flow"/"stock", events=, as_of=, period_end=)` | 自动叠加对齐好的同期线(灰虚线);标注事件;未完结期虚线加预估 |
| 指标拆解 | `driver_tree(nodes)` | 如 GMV = 用户 × 人均笔数 × 笔均;每个节点写当前值、▲▼ 变化、贡献(乘法用对数份额,加法用变化量);贡献最大的驱动项加框 |
| 谁带来了变化 | `contrib_table(df, dim, prev, cur, top_n=, growth_alert=)` | 规模 + 数据条、增速(▲▼,异常着色)、变化量、占总变化;合计行置顶 |
| 贡献拆解 | `waterfall(...)`(charts.py) | 上期 → 各维度贡献 → 本期 |
| 规模与比率 | `bar_line_dual(df, x, bar, line, line_range=)` | 唯一允许的双轴图 |

**参数细节**

- `kpi_cards(items, ncol=None)`:每张卡一个 dict。必填 `label`、`value`;可选 `prev`(对比值，有它才显示 ▲▼)、`kind`(`"growth"` 增速 / `"pp"` 两个比率之差 / `"abs"` 绝对差)、`fmt`、`nd`、`vs`(变化后面的说明，如 "vs 上月同期")、`target` + `progress`(0–1,时间进度;有 target 才画达成条)、`spark`(近期值列表)、`history`(近 8 期值，用于 ±2σ 规则)、`threshold`(与变化同单位:growth 用比例,pp 用比率差)、`higher_is_better`(默认 True)。卡片一行多张时用 `figure(..., size=(W, 约 0.3W))` 给一个矮的面板。
- `driver_tree(nodes)`:每个节点一个 dict。`id`、`label`、`cur`、`prev` 必填;`parent` 为父节点 id(根节点为 None,有且只有一个);`op` 写在**每个子节点**上，表示它与兄弟节点的组合方式:`"×"`、`"÷"`、`"+"`、`"−"`(U+2212 减号),默认 `"×"`;根节点不写 `op`(写了也忽略)。同一父节点下的子节点要么全是乘除、要么全是加减;可选 `fmt`、`nd`、`kind`、`higher_is_better`、`threshold`。乘法拆解要满足 父 = 子之积，加法拆解要满足 父 = 子之和，否则贡献份额没有意义。
- `trend(df, date, value, ...)`:`df` 为长表，一行一个日期;日度 / 周度 / 月度自动识别。`compare="month"` / `"year"` / `None`;`kind="stock"`(余额、到期类)或 `align="dom"` 时按第 N 天对齐，否则日度按星期对齐。`events=[("2026-09-15", "9.15 大促"), ...]`(日期字符串或 Timestamp)。`as_of=` 数据截至日、`period_end=` 当期结束日：两者都给且 as_of 早于 period_end 时，最后一期按未完结处理(虚线 + 预估)。
- `cumulative_vs_target(df, date, value, target, start, end, as_of=, prior=)`:`df` 为**当期**日度值(不是累计值);`target` 为全期目标;`start` / `end` 为当期起止日;`prior=` 为对比期的日度值，列名与 `df` 相同，从对比期第 1 天开始，按"第 N 天"对齐。
- `bullet(df, cat, actual, target, progress=)`、`contrib_table(df, dim, prev, cur, top_n=, growth_alert=)`、`bar_line_dual(df, x, bar, line, line_range=)`:都是一行一个类别 / 时点的宽表;`growth_alert=0.05` 表示 |增速| > 5% 记为异常。

**交付前额外检查(经营汇报里最常被挑的问题):**
- 口径脚注写全了吗?
- 和其他报表对过数吗?
- 单位、小数位、格式全图统一吗?
- 一眼能看出重点吗?

示例:`uv run references/business_gallery.py [outdir]`(中文幻灯片 + 英文文档两种规格,各 6 页)。
