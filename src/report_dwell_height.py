"""Participant-equal natural dwell height, preserving episode-centre provenance."""
import csv, json, math, re, hashlib
from collections import defaultdict, Counter
import numpy as np
from analyze import B


def summarize():
    episode_path=B/'data/explorer_dwell_episodes.csv'
    baseline_path=B/'outputs/calibration.json'
    rows=list(csv.DictReader(episode_path.open()))
    calibration=json.loads(baseline_path.read_text())['records']
    result={'unit':'mm','method':'episode median Z; corrected=max(0, episode median Z - record contact median); participant median over episodes; across-participant median and P25-P75','velocity_threshold_mm_s':20,'touch_exclusion_ms':300,'source_sha256':{str(p.relative_to(B)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [episode_path,baseline_path]},'thresholds':{}}
    for threshold in [100,200,300,400,500,600]:
        selected=[r for r in rows if int(r['threshold_ms'])==threshold]
        raw=defaultdict(list);corrected=defaultdict(list);records=set();tasks=Counter();excluded=0
        for row in selected:
            baseline=calibration[row['record']]['baseline_mm']
            z=float(row['median_z_mm'])
            if baseline is None or not math.isfinite(baseline) or not math.isfinite(z):
                excluded+=1;continue
            participant=int(row['participant'])
            raw[participant].append(z);corrected[participant].append(max(0,z-baseline))
            records.add(row['record']);tasks[row['task']]+=1
        summary={'participants':len(raw),'records':len(records),'episodes':sum(tasks.values()),'excluded_episodes':excluded,'tasks':dict(tasks),'participant_values':[]}
        for mode,groups in [('raw',raw),('corrected',corrected)]:
            values=np.array([np.median(groups[p]) for p in sorted(groups)])
            q=np.percentile(values,[25,50,75])
            summary[mode]={'p25_mm':float(q[0]),'median_mm':float(q[1]),'p75_mm':float(q[2])}
        summary['participant_values']=[{'participant':p,'episodes':len(raw[p]),'raw_median_mm':float(np.median(raw[p])),'corrected_median_mm':float(np.median(corrected[p]))} for p in sorted(raw)]
        result['thresholds'][str(threshold)]=summary
    return result


def enhance_dwell_height(content):
    data=summarize();s=data['thresholds']['400'];raw=s['raw'];cor=s['corrected']
    values=[v['corrected']['median_mm'] for v in data['thresholds'].values()]
    sensitivity=f'{min(values):.1f}–{max(values):.1f}'
    table=''.join(f'<tr><td>{threshold} ms</td><td>{r["episodes"]}</td><td>{r["participants"]}</td><td>{r["raw"]["median_mm"]:.1f}</td><td>{r["corrected"]["median_mm"]:.1f}</td></tr>' for threshold,r in data['thresholds'].items())
    panel=f'''<section id="naturalDwellHeight" class="note"><h2>自然离屏停留：修正参考高度约 1 cm</h2>
<p>持续至少 400 ms 时，16 位参与者的典型修正参考高度中位数为 <b>{cor['median_mm']:.1f} mm</b>；参与者典型高度的中间 50% 在 <b>{cor['p25_mm']:.1f}–{cor['p75_mm']:.1f} mm</b>。原始指甲标记点到屏幕平面的典型高度为 <b>{raw['median_mm']:.1f} mm</b>。</p>
<p id="dwellHeightCurrent">当前查看：≥400 ms · 原始指甲 Z · 典型高度 {raw['median_mm']:.1f} mm，中间 50% {raw['p25_mm']:.1f}–{raw['p75_mm']:.1f} mm。</p><p id="dwellHeightCoverage">{s['participants']} 位有停留参与者 · {s['records']} 条有停留记录 · {s['episodes']} 个片段，其中阅读 {s['tasks'].get('READ',0)} 个、输入 {s['tasks'].get('WRITE',0)} 个。</p>
<p><b>计算口径：</b>无活动触摸、距前后触摸均超过 300 ms、速度低于 20 mm/s，筛选完整连续片段。每片段取拇指 Z 中位数；修正参考为 max(0, 片段 Z 中位数 − 同记录触摸时指甲基线)。先在每位参与者内部对片段取中位数，再对参与者中位数取中位数和 P25–P75，各参与者等权。P25–P75 描述参与者之间的分布，不是置信区间；机型和情境在参与者内按片段合并，不代表每个条件都有相同高度。</p>
<details><summary>停留阈值变化与来源</summary><p>最短时长改为 100–600 ms，典型修正参考高度仍约 {sensitivity} mm。上方高度开关和停留滑块同步更新本节“当前查看”；本表保留两个口径以便核对。</p><div class="scroll"><table class="data dwell-height-table"><thead><tr><th>最短停留</th><th>片段数</th><th>有停留人数</th><th>原始指甲典型高度 / mm</th><th>修正参考典型高度 / mm</th></tr></thead><tbody>{table}</tbody></table></div><p>来源：data/explorer_dwell_episodes.csv、outputs/calibration.json；可复现命令：<code>python src/report_dwell_height.py</code>。<a href="natural-dwell-height.json" download>下载本节统计、参与者值与来源校验</a>。</p></details>
<p><b>对 Hover 的意义：</b>这些主要是阅读中的自然停放，原实验未记录主动 Hover 意图。约 1 cm 的自然停留可能与“高度＋停留时间”触发规则混淆；尚未限定实际感应范围和目标控件，也没有测出 Hover 误触率。这些数值不能直接作为安全触发阈值。</p>
<p><b>高度限制：</b>修正参考补偿指甲标记点在触摸时仍高于屏幕的偏移；指甲角度和接触姿态可能变化，独立物理同步未验证。它不是测得的真实指腹离屏净距。低于基线的片段显示为零，不能据此判定实际接触；本统计不受浏览器手动零点影响。Home Zone 继续仅显示位置参考。</p></section>'''
    content=re.sub(r'<section id="naturalDwellHeight".*?</section>','',content,flags=re.S)
    content=re.sub(r'<script id="naturalDwellHeightData".*?</script>','',content,flags=re.S)
    content=re.sub(r'<script type="module" src="[^\"]*report-dwell-height.js[^\"]*"></script>','',content)
    content=content.replace('<h2>本样本观察',panel+'<h2>本样本观察',1)
    content=re.sub(r'(src="[^\"]*report-controls.js)(?:\?[^\"]*)?"',r'\1?v=1.1.4"',content)
    scripts='<script id="naturalDwellHeightData" type="application/json">'+json.dumps(data,ensure_ascii=False,allow_nan=False)+'</script><script type="module" src="../viewer/report-dwell-height.js?v=1.1.4"></script>'
    (B/'outputs/natural-dwell-height.json').write_text(json.dumps(data,ensure_ascii=False,allow_nan=False,indent=2))
    return content.replace('</body>',scripts+'</body>')


def main():
    page=B/'outputs/report.html'
    backup=B/'outputs/report_before_natural_dwell_height.html'
    if not backup.exists():backup.write_text(page.read_text())
    page.write_text(enhance_dwell_height(page.read_text()))
    print('Natural dwell height section updated; 400ms corrected median',summarize()['thresholds']['400']['corrected']['median_mm'])

if __name__=='__main__':main()
