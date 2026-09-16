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

默认只显示绿色 Home Zone 框，为当前任务全部有效拇指样本 XYZ 各轴 P10–P90 位置参考，独立于停留阈值。没有有效拇指样本时不显示框。蓝框活动范围可按需打开。框不填充、不叠加热度；小区域可通过“聚焦 Home Zone”观察。

回放顶部及六任务卡片显示对应条件、任务、阈值下的合格停留次数和累计时长；顶部另显示单次中位时长以及当前本次的已持续／完整时长。次数与累计时间覆盖全任务的完整合格片段；P10–P90 位置参考框覆盖全任务有效拇指样本，不表示停留区域。

## 研究边界

这份数据支持右手单手自然操作的标记点姿态分析。主动 Hover 意图、托握＋食指、全身姿态与皮肤接触形变未被直接记录。查看报告中的分段、缺失抬手、屏幕几何估计及物理同步限制后再解释结果。

## 停留、热度与任务控件交互（本次更新）

- 回放顶部显示整个任务的停留次数、累计时长、单次中位时长与当前停留已持续时间。下方最短停留滑块为 100–1000ms，步长 100ms；保持速度 <20mm/s、触摸前后排除 >300ms，筛选完整连续片段，不把较长片段截短。选择某次停留立即加载其前后真实片段，最长 10 秒；时间轴和绿色停留段可拖动前后回看。
- **3D 空间热度图仅在分析报告中显示**：独立选择六任务、参与者、机型、情境及活动／停留样本。报告高度开关和 100–1000ms 滑块同步影响热度数据。蓝→红为每幅图独立 log1p 色标，显示每格最大秒数，跨图比较看数字。活动格 2mm，停留格 0.5mm；时间为有效采样计数/240。修正数据先逐帧 max(0,Z−baseline)，再分桶；缺失不补造，没有停留时保持空图。
- 勾选任务控件示意，在屏幕上与放大预览显示日志的 tile/target 锚点、触摸轨迹及当前事件；输入显示记录短语和键盘触点范围，阅读显示 textId。它是控件位置示意，不是原始录屏；机型标称像素到整屏为估计映射，未确认状态栏/应用偏移、控件大小、键盘排布与正文/滚动偏移。原论文 Figure4 为参考：https://www.medien.ifi.lmu.de/pubdb/publications/pub/le2019investigatingunintended/le2019investigatingunintended.pdf#page=5
- 报告顶部开关切换拇指绝对高度主表、六任务比较、机型情境、高度分布三张图。修正量逐帧取非负下限，再记录内取中位数、参与者内平均并参与者等权 bootstrap。正文检验、相对事件高度和其他手指保留原始研究结果，科研差值表仍允许负数。报告也支持相同停留阈值滑块和六任务时长表。

新派生数据：data/explorer_height_cells.csv、explorer_dwell_cells.csv、explorer_dwell_episodes.csv；outputs/explorer/ 为每记录的阈值、真实事件、体素和来源；outputs/report_before_explorer.html 保存更新前报告。原数组、原 PDF/Markdown 和已有统计不改。更新后数据与浏览器验证见 qa/interactive-explorer.md。

## GitHub Pages 发布

公开项目：MOTION ATLAS，仓库 `purryc/MOTION-ATLAS`。运行 `.venv/bin/python src/publish.py` 生成 `.tmp/public-site/`，包含 761 个典型片段及所有 5,362 个 ≥100ms 完整停留片段（各阈值复用，不截短），保留 240Hz 原始帧、世界／手机坐标和有效性。gzip 为无损压缩。网页选择下方某次停留即可加载；任意全任务分段仍由本地服务器提供。报告使用同一套处理后数据。

`deploy/deploy-pages.yml` 为项目发布命令的工作流：下载指定版本的 `public-site.tar.gz` Release 资产、核对 SHA256，再部署 GitHub Pages；发布流程不提交私有研究文档、完整原始数据或缓存。构建检查见 `qa/motion-atlas-build.json`。

## v1.1：原任务与位置显示

入口按原论文分为 Reading、Writing、Abstract input，并保留原始要求。抽象输入再展开四操作。Home Zone 绿色框是全操作有效拇指XYZ P10–P90位置参考，独立于停留规则；停留在独立折叠面板和报告中分析。UI位置校准采用同记录有效TAP DOWN的Theil-Sen像素到指甲参考XY拟合，留出验证未通过的记录保持原始映射；原始标记点/触点/锚点均保留。此估计不代表指腹位置或验证过的真实屏幕配准。重建 `.venv/bin/python src/ui_position_calibration.py`；小版本 `.venv/bin/python src/publish_patch.py`，workflow同时验证基础和补丁Release SHA256。

公开动捕编号为P3、4、5、6、7、8、10、11、12、13、14、16、17、19、20、21。P1、P2、P9、P15、P18仅有手机日志，官方动捕包没有对应记录；缺失原因未公开说明，不当作已证实的试验排除或预试编号。机型列表显示4/5/5.5/6英寸和官方机身宽高厚、屏幕宽高毫米尺寸。

## v1.1.1：卡片内直接选择操作

点击、拖动、竖向滚动、横向滚动始终显示在抽象输入卡片内，点击即可切换回放和该操作的原始要求；阅读或输入选中时也可直接选择。移动端使用两列按钮，保持三大任务层级。

## v1.1.3：自然停留高度

报告新增自然离屏停留的参与者等权中位高度、中间50%范围、阈值敏感性和意图/指腹净距边界。同步现有高度开关与停留滑块。运行 `.venv/bin/python src/report_dwell_height.py`，数据及来源SHA256输出至 outputs/natural-dwell-height.json；保留更新前报告。

## v1.1.4：P7／N6／坐姿手机位姿修正

该记录源手机刚体位姿在阅读段与自身标记点几何不一致。src/phone_pose.py 从同记录输入段建立标记点模板，以每帧至少3个非共线实测点重新估计手机位姿；留出点验证P95约0.36mm，缺失/不可靠帧不插值。原始世界手部、时间与帧号不变，修正前派生数组和报告分别保留在 data/pose-audit、outputs/report_before_phone_pose。重算手机相对坐标、速度、Home Zone位置、停留、高度统计及图表。

复现：analyze.py --record P7_N6_seated --force --workers 1；calibration.py；zones.py、interactive_analysis.py、release_analysis.py、audit.py、ui_position_calibration.py；report.py；report_explorer.py；publish.py --record P7_N6_seated；publish_patch.py。各脚本使用本项目Python虚拟环境，后续步骤依赖前面产物。publish.py的record选项保留其他已验证静态片段，输出增量发布显式清单。

## v1.1.5：停留阈值扩至 1000ms

报告与回放的最短连续停留滑块均为 100–1000ms、步长100ms，默认仍为400ms。每一档都从同一批未截短的最大连续片段筛选，统计表、自然停留高度、报告3D停留热图和回放片段同步更新；Home Zone 位置框不随阈值变化。运行 `.venv/bin/python src/interactive_analysis.py`、`.venv/bin/python src/report_explorer.py`、`.venv/bin/python src/publish.py --thresholds-only` 可重建派生数据与静态站；最后一步复用经核对的原始帧回放文件，更新全部128条记录的阈值索引及处理表格。
