"""Add reproducible interactive controls while preserving the original static findings."""
import json,html,re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from analyze import B,TASKS,NAMES,DEVICES
from report import ci,savefig,FIG


def enhance_report(content):
 from report_dwell_height import enhance_dwell_height
 content=enhance_dwell_height(content)
 content=content.replace('不同任务下，手部姿态有何变化','原实验三大任务下的手部姿态')
 if '<h2>原实验的任务定义</h2>' not in content:
  tasks='<section class="note"><h2>原实验的任务定义</h2><p><b>阅读 Reading：</b>阅读并滚动英语学习文章 2 分钟，随后回答 3 道理解题。</p><p><b>输入 Writing：</b>抄录 MacKenzie 短语，模拟给朋友发消息。</p><p><b>抽象输入 Abstract input：</b>点击随机目标（显示 1 秒）；在覆盖全屏的 2×3 网格中将 tile 拖入随机目标；将横向或竖向条滚动到目标。各手势随机重复 12 次。六类操作为分析层级，阅读中的滚动仍属阅读。</p><p><a href="https://www.medien.ifi.lmu.de/pubdb/publications/pub/le2019investigatingunintended/le2019investigatingunintended.pdf#page=4">原论文任务定义</a>。绿色 Home Zone 是当前操作全任务有效拇指 XYZ P10–P90 位置参考，与停留阈值独立。</p></section>'
  content=content.replace('<div class="grid">',tasks+'<div class="grid">',1)
 if (B/'outputs/phone-pose-repair.json').exists() and 'id="phonePoseNotice"' not in content:
  notice='<section id="phonePoseNotice" class="note"><h2>P7 手机位姿修正记录</h2><p>P7／N6／坐姿的源手机刚体位姿与自身标记点几何不一致，原阅读热力图偏到手机上方。现用同记录输入段建立手机标记点模板，逐帧以至少三个非共线实测点重新估计手机位姿；拟合 RMS 超过 1mm 或几何退化的帧不补造。阅读留出一个手机标记点验证，P95 偏差 0.36mm。</p><p>原始手部世界坐标、时间戳和源帧保持不变；手机相对坐标、速度、停留片段、统计图表与回放共同重建。修正前派生数据及报告保留在本地。标记点几何验证不等于独立触摸物理同步。<a href="phone-pose-repair.json">查看修正方法和验证数字</a>。</p></section>'
  content=content.replace('<h2>本样本观察',notice+'<h2>本样本观察',1)
 content=re.sub(r'(src|href)="(figures/[^"?]+)(?:\?[^" ]*)?"',r'\1="\2?v=1.1.4"',content)
 content=re.sub(r'(src="[^" ]*report-(?:controls|heat|dwell-height)\.js)(?:\?[^" ]*)?"',r'\1?v=1.1.4"',content)
 if 'id="reportExplorer"' in content:return add_heat(content)
 panel='''<section id="reportExplorer" class="note"><h2>交互查看</h2><label><input id="reportHeightToggle" type="checkbox"> 显示修正离屏高度（最低 0 mm）</label><p id="heightModeInfo">原始指甲 Z：有符号屏幕坐标。</p><label>最短连续停留 <input id="reportDwellThreshold" aria-label="报告最短停留时长" type="range" min="100" max="600" step="100" value="400"><b id="reportDwellValue">400 ms</b></label><p>速度 &lt;20 mm/s；触摸前后排除 300 ms。下表片段数、累计时长为全部有效记录合计；占比为参与者等权，保留零停留记录。</p><div id="reportDwellSummary" class="scroll">读取真实阈值数据…</div></section>'''
 content=content.replace('<h2>本样本观察',panel+'<h2>本样本观察',1)
 content=content.replace('</style>','#reportExplorer label{display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-size:14px}#reportExplorer input{accent-color:#356e4a}#reportExplorer input[type=range]{width:220px;max-width:55vw}#reportExplorer h2{margin-top:10px}</style>',1)
 content=content.replace('触摸基线修正高度</h2>','带符号触摸基线修正 Z（科研差值）</h2>')
 return add_heat(content.replace('</body>','<script type="module" src="../viewer/report-controls.js?v=1.1.4"></script></body>'))

def add_heat(content):
 content=content.replace('Le 2019 六任务姿态分析','MOTION ATLAS · 六任务姿态分析').replace('LE 2019 / POSTURE ANALYSIS','MOTION ATLAS / LE 2019').replace('href="/"','href="../"')
 if 'processed-tables.zip' not in content:
  content=content.replace('<h2>来源与可复现性</h2>','<h2>来源与可复现性</h2><p><a href="https://github.com/purryc/MOTION-ATLAS">MOTION ATLAS 源代码</a> · <a href="processed-tables.zip" download>下载处理后统计与停留表格</a></p>')
 if 'report-heat.js' in content:return content
 imports='<script type="importmap">{"imports":{"three":"../vendor/build/three.module.js","three/addons/":"../vendor/examples/jsm/"}}</script>'
 content=content.replace('</head>',imports+'</head>').replace('src="/viewer/report-controls.js"','src="../viewer/report-controls.js?v=1.1.4"')
 return content.replace('</body>','<script type="module" src="../viewer/report-heat.js?v=1.1.4"></script></body>')

def main():
 data=json.loads((B/'outputs/explorer/report.json').read_text());s=pd.read_csv(B/'data/summary.csv');d=s[(s.finger=='Thumb')&(s.basis=='context_500ms')&(s.valid_frames>=240)].copy()
 cells={(r['record'],r['task']):r for r in data['height_cells']}
 d['corrected_z']=[cells[(f'P{int(r.participant)}_{r.phone}_{r.condition}',r.task)]['corrected_median_mm'] for r in d.itertuples()]
 metrics=['corrected_z','z_p50_mm','y_normalized','speed_median_mm_s'];pp=d.groupby(['participant','task'])[metrics].mean().reset_index()
 stats={}
 for task in TASKS:
  stats[task]={}
  for field,key in [('z_p50_mm','raw'),('corrected_z','corrected')]:
   m,l,h,n=ci(pp[pp.task==task][field]);stats[task][key]=dict(mean=m,ci_low=l,ci_high=h,participants=n,text=f'{m:.1f} [{l:.1f}, {h:.1f}]')
 save_data=dict(height=stats,thresholds=data['thresholds']);(B/'outputs/explorer/report-controls.json').write_text(json.dumps(save_data,ensure_ascii=False,allow_nan=False))
 fig,axs=plt.subplots(1,3,figsize=(15,4.4))
 for ax,metric,title,unit in zip(axs,['corrected_z','y_normalized','speed_median_mm_s'],['修正离屏高度（下限 0）','拇指纵向位置','拇指运动速度'],['max(0, Z − 触摸基线) / mm','Y / 手机高度','速度 / mm/s']):
  for k,task in enumerate(TASKS):
   a=pp[pp.task==task][metric].dropna();m,l,h,n=ci(a);ax.scatter(k+np.linspace(-.13,.13,len(a)),a,s=16,c='#a8b8ae');ax.errorbar(k,m,yerr=[[m-l],[h-m]],fmt='o',color='#2c6650',capsize=4)
  ax.set_xticks(range(6),NAMES,rotation=30,ha='right');ax.set_title(title);ax.set_ylabel(unit);ax.grid(axis='y',alpha=.15)
 fig.suptitle('参与者等权均值和 95% CI · 修正量为显示参考，非指腹净距');fig.tight_layout();savefig('task_comparison_corrected')
 fig,axs=plt.subplots(1,2,figsize=(12,4.5))
 for ax,metric,title in zip(axs,['corrected_z','speed_median_mm_s'],['修正离屏参考 / mm（下限 0）','速度 / mm/s']):
  for k,phone in enumerate(DEVICES):
   for cond,style in [('seated','-'),('walking','--')]:
    vals=[d[(d.phone==phone)&(d.condition==cond)&(d.task==task)][metric].mean() for task in TASKS];ax.plot(range(6),vals,style,color=['#287cce','#25a68f','#c79836','#e86432'][k],label=phone+' '+('坐姿' if cond=='seated' else '行走'),marker='o',markersize=3)
  ax.set_xticks(range(6),NAMES,rotation=25);ax.set_ylabel(title);ax.grid(axis='y',alpha=.15)
 axs[1].legend(fontsize=8,ncol=2);fig.suptitle('机型与情境 · 记录指标的参与者等权均值');fig.tight_layout();savefig('phone_condition_corrected')
 fig,axs=plt.subplots(2,3,figsize=(12,7));edges=np.array(data['height_bin_edges_mm'])
 for ax,task,name in zip(axs.flat,TASKS,NAMES):
  ax.bar((edges[:-1]+edges[1:])/2,data['corrected_histogram'][task],width=4.5,color='#639782');ax.set_xlim(0,105);ax.set_title(name);ax.set_xlabel('max(0, Z − 触摸基线) / mm');ax.set_ylabel('5 mm 桶占比')
 fig.suptitle('修正参考高度分布 · 参与者等权 · 裁切外点未重新归一化');fig.tight_layout();savefig('height_distribution_corrected')
 page=B/'outputs/report.html'
 before=page.read_text();backup=B/'outputs/report_before_explorer.html'
 if not backup.exists():backup.write_text(before)
 page.write_text(enhance_report(before));print('Report controls and corrected figures complete',flush=True)

if __name__=='__main__':main()
