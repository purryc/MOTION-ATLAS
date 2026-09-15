# 数据接口 v1

## 完整记录 NPZ

N 为原始采样帧数，M=25（MARKERS 顺序见 src/analyze.py）。

- frame: N int32，原始源帧号。
- time_ms: N float64，Europe/Berlin 捕获开始时间转 epoch，加原始相对时间。无整数毫秒截断。
- world_mm: N×25×3 float32，原始世界标记点，毫米；NaN 为原始缺失。
- local_mm: N×25×3 float32，过滤后的手机相对标记点，NaN 为无效。
- pivot_mm: N×3，刚体世界原点；quaternion_xyzw: N×4。
- marker_valid: N×25 bool；rigid_valid: N bool。
- speed_mm_s: N×25，只计算相邻有效源帧，NaN 不跨越。
- task_core/task_context: N int8，0..5 对应 READ/WRITE/TAP/DRAG/SCROLL_V/SCROLL_H，-1 无任务。
- contact_state: N int8，1 已知触摸跨度、0 已观测释放、-1 未知。
- sync_eligible: N bool，S3 无外推时钟映射或其他机型上游共享 epoch；不是物理同步验证标签。

JSON 附件包含来源、header、原始 trial/log row、事件、上下文边界、稳定停留与校验。来源引用只在工作包内解析，不接受任意路径。

## 回放接口

GET /outputs/index.json 返回代表片段索引，包含 participant、phone、condition、task、meta 路径。

GET /outputs/clips/{id}.json 返回单位、坐标系、设备几何、MARKERS 顺序、epoch 起点、stride、frames、源帧、事件、稳定停留区间及 binary 文件名。

Binary 为小端 Float32，每帧 stride=161：0 相对时间 ms；1 原始源帧；2..76 局部标记点；77..151 世界标记点；152..154 世界原点；155..158 四元数 xyzw；159 拇指速度；160 触摸状态。NaN 保留为无效，不零填。浮点显示精度不影响完整 NPZ 时间戳。

GET /api/record?id={record} 返回任务区间和校验摘要。

GET /api/segment?record={record}&start={epoch_ms}&end={epoch_ms}&task={task} 返回最多 10 秒、属于一个任务上下文的真实源帧片段。binary 为 /api/binary?id={key}；仅本地监听 127.0.0.1。

报告与静态图直接使用完整派生数组/统计表；代表片段不用于代替全量统计。

Motive 导出头的 12.xx AM 沿用官方 12AM workaround 修正为当日中午；17 条受影响记录已与手机日志 +12h 差核对。checks 保存原始捕获时间和 motive_12am_workaround，其他记录为 false。

动捕包中 P10 的四条坐姿记录使用 sitting 文件名；规范情境为 seated，原始 sources 文件名保持 sitting 并写入来源字段。原始文件清单与规范记录覆盖须同时达到 128。

事件对齐按钮要求两片段 `sync_status=PHYSICAL_SYNC_VERIFIED` 且有合格 DOWN 事件。当前均标为 `CLOCK_MATCHED_PHYSICAL_SYNC_UNVERIFIED`，故按钮禁用，保留真实时间比较。

release_trajectory.csv 每行是已观测 UP 事件的一个前后采样点，含事件／采样源帧、epoch、任务条件、相对高度与位移、接触状态、支撑指位移及有效支撑指数。允许再触摸；不自动标注回位成功。grip_candidates.csv 为至少两个支撑 Fn 在连续 200ms 中位移 ≥5mm、候选状态持续 ≥100ms 的区间，尚未由独立视频确认，不视为握持调整次数。

outputs/calibration.json 以规范 record ID 索引 `baseline_mm`、method、marker、来源和物理同步资格；同一基线已写入静态片段的 `height_calibration`。更多片段由 clip_payload 使用整条记录已知接触帧生成基线。基线为指甲标记点 Z 中位数，最少 20 个有效接触采样。三维标记点、完整数组及已有统计不改动；校准显示参考点及离屏距离 `max(0,Z−baseline)`，带符号差值 `corrected_mm=Z−baseline` 继续保留，负差值通过 `clamped` 标记并显示为 0 mm。用户在已观测触摸帧临时设零时，另保存 source_frame/source_epoch_ms，PNG 标注该源帧；未知接触或缺失帧禁用设零。

## 任务三维区域（显示派生数据）

`outputs/zones.json.records[record][task]`：`home_zone` 为真实有效任务上下文拇指样本，`idle_sample_home_zone` 为严格稳定停留区间内真实有效样本，缺失时为 null。各区包含 median/p10/p90 的 XYZ 毫米坐标、valid_frames；稳定区另含 episodes。顶层给出单位、坐标系、Thumb_Fn、context_500ms 与停留阈值。source 指向完整处理后 NPZ，范围使用整个任务，不随当前片段长度变化。原 clip `idle_home_zone` 的片段中心统计保持原样，新显示使用 `idle_sample_home_zone`。

静态片段与按需 API 均包含区域及 `zone_source`。三维体积使用每轴分位范围，不保证联合覆盖 80% 样本。开启高度校准时显示 Z 边界按 `max(0,Z−baseline)` 转换，XYZ 原数据不改动。

## 交互探索数据

`GET /outputs/explorer/{record}.json` 包含 tasks[task].activity.raw/corrected，thresholds[100..600] 的 summary、episodes、home、heat.raw/corrected 和 ui。episode 保留绝对 epoch 起止、完整 duration_ms、源帧及既有规则参数；本次分析派生表另存 explorer_dwell_episodes.csv，不覆盖旧400ms研究表。

热度对象 {size_mm, voxels:[[floorX,floorY,floorZ,count],...], valid_frames,total_s,max_s}；桶坐标为 floor(mm/size)，显示中心为 (index+.5)*size，计数/240 表示采样时长。全部有效帧均进入桶，不作 KDE、平滑或缺口补帧。raw/corrected 计数总和一致；校准在分桶前逐帧取 max(0,Z−baseline)。`GET /api/heat?record=...&task=...&scope=home|activity&threshold=100..600&baseline=...` 为手动基线从完整真实数组重新生成同一接口。

ui.trials 包含原日志 source/row/trial、目标锚点和短语/textId；ui.events 为 [epoch,x_px,y_px,action,trial]，仅用时钟资格通过的事件，但不声明独立物理同步。nominal_pixels 为标称全屏尺寸，应用偏移未知，像素映射为示意。坐标原点为屏幕像素左上角，手机局部 X 反向；投影为 [ox+sw*(1−px/W), oy+sh*py/H,0]。

`outputs/explorer/report-controls.json` 保存原始/非负修正高度参与者等权均值、95% bootstrap CI 与六阈值全任务时长。报告绝对高度切换不重写原始配对检验或其他手指。
