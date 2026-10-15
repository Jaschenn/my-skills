# Changelog

## v3.1.1 —— 发布前修复(plotnine 0.15.8 + matplotlib 3.11 实测)
自动检查
- **修复检查误报**:matplotlib 3.11 改了文字排版(默认行距 "normal"、文字框用字体完整行高),旧的文字面板高度比 matplotlib 报告的框矮约 3px,导致几乎每张带标题/脚注的图都报"text runs outside its panel"(回归测试 7/68,图库 23/24 页报警)。`vmetrics` 改为直接量 matplotlib 的文字框(与 plotnine 同样用数字行距 1.2);新增 `line_height()`。
- 字宽改在 720dpi 下测量(72dpi 会按整点取整;多段富文本拼接时会吃掉空格，如 "(bars, left) |Approval rate")。
- `figure()` / `save()` 返回值新增 `.qa`(问题列表，空 = 通过);仍是路径列表，向后兼容。
- `_draw` 不再吞掉 AttributeError / TypeError 悄悄跳过检查：只有对象没有 `.draw()` 时才走无检查的保存路径，并打 WARNING。
- 对比度警告改为每页每种颜色报一次(原来整个进程只报一次);渲染用的临时目录会清理。
数据与含义
- `delta()`:上期为负数时方向反了(−10 → −5 显示 ▼ 50%);改为按 |上期| 计算。影响 kpi_cards / driver_tree / contrib_table。`dumbbell` / `slope` 的变化率同样修正。
- `slope(mode="change")`:起点为 0 的行原来被悄悄丢掉且 QA 显示 ok;现在剔除并打 WARNING。
- `heatmap` 全缺失、`cumulative_vs_target` 时间窗内没有数据：原来抛 `IndexError: index -1`,现在给出说明原因的 ValueError。
- `fmt_value` 自定义格式串里的连字符不再被改成减号(只替换开头的负号)。
图表
- 新增 `charts.axis_range()`:dumbbell / range_dot / distribution / point_range / scatter 的轴不再延伸到很远的整刻度(数据到 61、轴画到 80)。
- `dumbbell`:图例颜色与实心点一致(有高亮时为焦点色),颜色在渲染时解析、跟随 `set_palette()`;`labels` 默认"之前/之后"。
- `scatter(groups=)`:返回彩色图例行 `chart.legend`(原来按组上色但没有图例)。
- `waterfall`:减少默认用灰色而不是焦点色(焦点色不代表好坏，规则 R10)。
- `kpi_cards`:行距按字体度量;迷你趋势线的最小高度随规格缩放。
- `cumulative_vs_target`:x 刻度不再与月末刻度挤在一起(10/28 与 10/31);"预估 3,100 (78%)" 补空格;右侧标签不越界。`trend`:"截至"注释向左展开，不再压住右侧标签;两者首尾刻度标签贴边对齐，不再与 y 轴的 0 重叠。
- `small_multiples`:底部留白按字体度量，两行月份标签不再越界。
- `bar_line_dual`:最新一根柱子接近顶部刻度时，数值标签会冲出面板、压住右轴标题;现在自动留出标签高度。
- `kpi_cards`:卡片窄时"达成 · 时间进度"自动分两行，不再越出卡片。
发布
- 删除打包进 skill 的生成图(`references/out/`,4.1MB)、`.DS_Store`、`__pycache__`;新增 `.gitignore`;图库和测试默认输出到当前目录的 `out/`,不再写进 skill 目录。
- 依赖锁定为 `plotnine>=0.15,<0.16`。
- SKILL.md 重组：通用图和经营分析图原来是两张按不同维度分类的函数表、两套颜色规则。现在工作流第一步先判断场景(经营汇报 / 通用出版，给出判断标准);两张表合并为一张按"要比较什么"组织的选函数表(经营函数标 ★),附"两行都像时怎么选";两种场景的差异集中在一张约定对照表。description 改为按用途和比较类型描述，不再罗列两组函数名。经营场景的细则和 ★ 函数的全部参数(含 `driver_tree` 节点结构、`trend` 的 `events=`、`cumulative_vs_target` 的 `prior=`)放在 `references/business.md`。用两轮新 Agent 测试(共 13 个选图问题)验证，选图全部正确。
- 示例数据(gallery / business_gallery)全部改为固定随机种子生成，不再有手写数字;场景改为通用零售;中英文两套图使用同一份数据;经营图库各页互相对得上数(KPI 卡的本月 GMV = 拆解树根节点 = 贡献表合计)。
- 新增 MIT LICENSE。
- 回归测试新增 4 组(slope 零起点、dumbbell 负基数、scatter 分组图例、KPI 负基数),共 38 组 × 2 规格 = 76 项。`biz_kpi_missing_prev_and_tiny` 在 journal-1col 下改为预期报警：3.5in 栏宽里带目标条的那张卡确实放不下迷你趋势线，原来不报警是因为文字框量小了。

验证:回归测试 76/76;`gallery.py` 24/24 页、`business_gallery.py` 12/12 页 QA ok。

## v3.1 —— 经营分析图表
- 新增 `scripts/biz.py`:`kpi_cards`、`bullet`、`cumulative_vs_target`、`trend`(自动对齐的同期线、事件标注、未完结期虚线 + 预估)、`driver_tree`、`contrib_table`、`bar_line_dual`(唯一允许的双轴:规模柱 + 比率线)。
- `viz_common` 新增 `delta()`、`is_anomaly()`(落后进度 / 固定阈值 / ±2σ)、`time_progress()`、`prior_values()`(按星期或按第 N 天对齐同期)、`set_number_style()`。
- 经营分析约定写入文档(涨跌不用红绿、异常才着色、同期对齐、未完结期、双轴限制、禁用饼图、口径脚注必填);页面含经营图却没有口径脚注时 `figure()` 报 WARNING。
- 新增 `references/business_gallery.py` 和 8 组经营图边界用例。

## v3.0.1 —— 真 plotnine 首跑修复
- plotnine `draw()` 返回的画布没有 `get_renderer`,QA 前自动挂 Agg 画布。
- 文字面板高度改用字体真实度量;符号(●○■→①)自动用 CJK 字体。
- scatter / small_multiples / distribution 首末刻度标签留边;重叠检测忽略 1.5pt 以内的误差。

## v3.0 —— 生产级 / 出版级图表
- 图表函数库 `scripts/charts.py`(12 个),布局在知道最终尺寸后由数据计算，不写死坐标。
- 输出规格 `SPECS`:slide / slide-4x3 / web / doc / a4 / letter / journal-1col / 1.5col / 2col。
- PDF 导出(TrueType 嵌入字体);自动 QA(文字重叠、越界、裁切、对比度)。
- 中英双语(`set_lang`、`T()`);`titled()` 渲染时构建;表格数字列自动右对齐。
- 新增 `references/gallery.py` 和 `references/tests/edge_cases.py`。
- 报告流程类内容移出，本 skill 只负责图。

## v1.x –v2.0
- 早期版本:富文本标记(两色标题、彩色词图例)、文字/表格面板、多面板拼版、SVG id 前缀、中文标点规范 `zh()` 与禁则折行 `wrap_cjk()`、CJK 字体探测、配色(focus / brand / good / bad)、数字格式工具、SWD 改图案例笔记(`references/swd_practices.md`)、plotnine 预览模拟器。
