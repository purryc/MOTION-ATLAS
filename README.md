# MOTION ATLAS

Le 2019 六任务姿态分析与三维回放。

双击 `open_viewer.command` 打开本地工具；分析报告位于 `outputs/report.html`，完整中文文字位于 `outputs/findings.md`。

## 重新运行

在本工作包目录运行：

```bash
python3 -m venv .venv
.venv/bin/pip install -r src/requirements-lock.txt
npm ci --prefix src
.venv/bin/python src/analyze.py --verify
.venv/bin/python src/analyze.py --workers 2
.venv/bin/python src/audit.py
.venv/bin/python src/release_analysis.py
.venv/bin/python src/report.py
.venv/bin/python src/calibration.py
.venv/bin/python src/zones.py
.venv/bin/python src/interactive_analysis.py
.venv/bin/python src/report_explorer.py
.venv/bin/python -m unittest discover -s src/tests -p 'test_*.py'
npm test --prefix src
.venv/bin/python src/serve.py --port 8879
```

`analyze.py` 默认跳过已处理记录，`--force` 重新生成派生数据；原始 ZIP 不变。先下载官方 README 的两个 ZIP 到 `sources/`，解压手机 ZIP 到 `sources/phone_dataset/`。`src/stream_pilot.py` 仅为首次下载中的 P3 小样提取工具，正式分析直接读取完整 ZIP，不需要解压动捕包。

## 目录

`sources/` 原始数据与固定官方代码；`src/` 分析、统计和 Three.js；`data/` 完整数组及研究表格；`outputs/` 报告、图表、回放索引和代表片段；`qa/` 校验与截图。

`data/summary.csv` 每条记录×任务×手指×分段方法的分位数、速度及几何指标；`participant_summary.csv` 参与者等权指标；`participant_bootstrap.csv` 95% CI；`paired_comparisons.csv` 匹配条件的差异；`coverage.csv` 覆盖和缺口；`episodes.csv` 严格稳定停留；`sensitivity.csv` 27 组阈值；`event_trajectory.csv` 描述性事件对齐轨迹。

`data/records/*.npz` 保留原始采样时间、帧号、世界标记点、处理后局部标记点、刚体、有效性及任务/触摸状态。代表片段在 `outputs/clips/`；更多片段由本地服务器按需读取完整数组。

`release_trajectory.csv` 为已观测抬手后的连续有效轨迹；`whole_hand_task_summary.csv` 为六任务五指配置；`grip_candidates.csv` 为待复核的协同位移候选。事件对齐模式仅在片段带有 `PHYSICAL_SYNC_VERIFIED` 证据标签时开放；当前数据尚缺独立物理对齐证据，双窗按真实片段时间播放。

## 高度校准与侧视图

默认打开“触摸高度校准”：每位参与者×机型×情境用已知接触帧的拇指甲标记点 Z 中位数为零点，显示 `修正离屏距离 = max(0, 指甲 Z − 触摸基线)`。真实标记点不移动，新增空心校准参考点和到屏幕平面的高度线。侧视图与世界视图均支持，PNG 包含数值和校准来源。低于基线的差值显示为 0 mm，并标注原因。原始 Z 与带符号差值继续保留供核查，屏外投影明确标注。

选到已知触摸且标记点有效的采样帧后，可点“当前触摸帧设为零点”，该帧修正高度为 0mm；同一记录切任务继续使用这一基线。手动基线仅在当前浏览器会话中有效，刷新恢复自动校准；“恢复自动校准”可立即还原。其他任务、手指姿态变化以及指腹形变不由一个指甲高度偏移消除，修正参考不是指腹净距测量。校准元数据见 outputs/calibration.json。

## 每任务三维区域

默认只显示绿色 Home Zone 框，为当前任务达到所选最短停留阈值的真实拇指样本 XYZ 各轴 P10–P90。没有合格停留时不显示框，明确标注“未检出 Home Zone”。蓝框活动范围可按需打开。框不填充、不叠加热度；小区域通过“聚焦 Home Zone”观察，没有 Home Zone 时聚焦按钮不可用。

回放顶部及六任务卡片显示对应条件、任务、阈值下的合格停留次数和累计时长；顶部另显示单次中位时长以及当前本次的已持续／完整时长。次数与累计时间覆盖全任务的完整合格片段，P10–P90 框是这些帧的分位范围，不表示所有帧都在框内。

## 研究边界

这份数据支持右手单手自然操作的标记点姿态分析。主动 Hover 意图、托握＋食指、全身姿态与皮肤接触形变未被直接记录。查看报告中的分段、缺失抬手、屏幕几何估计及物理同步限制后再解释结果。

## 停留、热度与任务控件交互（本次更新）

- 回放顶部显示整个任务的停留次数、累计时长、单次中位时长与当前停留已持续时间。下方最短停留滑块为 100/200/300/400/500/600ms；保持速度 <20mm/s、触摸前后排除 >300ms，筛选完整连续片段，不把较长片段截短。选择某次停留立即加载其前后真实片段，最长 10 秒；时间轴和绿色停留段可拖动前后回看。
- **3D 空间热度图仅在分析报告中显示**：独立选择六任务、参与者、机型、情境及活动／停留样本。报告高度开关和 100–600ms 滑块同步影响热度数据。蓝→红为每幅图独立 log1p 色标，显示每格最大秒数，跨图比较看数字。活动格 2mm，停留格 0.5mm；时间为有效采样计数/240。修正数据先逐帧 max(0,Z−baseline)，再分桶；缺失不补造，没有停留时保持空图。
- 勾选任务控件示意，在屏幕上与放大预览显示日志的 tile/target 锚点、触摸轨迹及当前事件；输入显示记录短语和键盘触点范围，阅读显示 textId。它是控件位置示意，不是原始录屏；机型标称像素到整屏为估计映射，未确认状态栏/应用偏移、控件大小、键盘排布与正文/滚动偏移。原论文 Figure4 为参考：https://www.medien.ifi.lmu.de/pubdb/publications/pub/le2019investigatingunintended/le2019investigatingunintended.pdf#page=5
- 报告顶部开关切换拇指绝对高度主表、六任务比较、机型情境、高度分布三张图。修正量逐帧取非负下限，再记录内取中位数、参与者内平均并参与者等权 bootstrap。正文检验、相对事件高度和其他手指保留原始研究结果，科研差值表仍允许负数。报告也支持相同停留阈值滑块和六任务时长表。

新派生数据：data/explorer_height_cells.csv、explorer_dwell_cells.csv、explorer_dwell_episodes.csv；outputs/explorer/ 为每记录的阈值、真实事件、体素和来源；outputs/report_before_explorer.html 保存更新前报告。原数组、原 PDF/Markdown 和已有统计不改。更新后数据与浏览器验证见 qa/interactive-explorer.md。

## GitHub Pages 发布

公开项目：MOTION ATLAS，仓库 `purryc/MOTION-ATLAS`。运行 `.venv/bin/python src/publish.py` 生成 `.tmp/public-site/`，包含 761 个典型片段及所有 5,365 个 ≥100ms 完整停留片段（各阈值复用，不截短），保留 240Hz 原始帧、世界／手机坐标和有效性。gzip 为无损压缩。网页选择下方某次停留即可加载；任意全任务分段仍由本地服务器提供。报告使用同一套处理后数据。

`deploy/deploy-pages.yml` 为项目发布命令的工作流：下载指定版本的 `public-site.tar.gz` Release 资产、核对 SHA256，再部署 GitHub Pages；发布流程不提交私有研究文档、完整原始数据或缓存。构建检查见 `qa/motion-atlas-build.json`。
