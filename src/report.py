"""Participant-weighted statistics, scientific plots and a Chinese research report."""
from pathlib import Path
import itertools,json,warnings,html
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Rectangle
from scipy.stats import ttest_1samp
from statsmodels.stats.multitest import multipletests
from analyze import B,TASKS,NAMES,FINGERS,MARKERS,DEVICES,save_json

FONT='/System/Library/Fonts/STHeiti Light.ttc'
if Path(FONT).exists():
 prop=FontProperties(fname=FONT);matplotlib.font_manager.fontManager.addfont(FONT);plt.rcParams['font.family']=prop.get_name()
plt.rcParams.update({'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white','axes.facecolor':'white','font.size':10,'savefig.dpi':170})
COLORS=['#e86432','#287cce','#25a68f','#9b74c7','#c79836'];LABEL=dict(zip(TASKS,NAMES));FN=['拇指','食指','中指','无名指','小指']
FIG=B/'outputs/figures';FIG.mkdir(exist_ok=True)

def ci(a,seed=2019):
 a=np.array(a,dtype=float);a=a[np.isfinite(a)]
 if not len(a):return np.nan,np.nan,np.nan,0
 rng=np.random.default_rng(seed);means=a[rng.integers(0,len(a),size=(5000,len(a)))].mean(1)
 lo,hi=np.percentile(means,[2.5,97.5]);return float(a.mean()),float(lo),float(hi),len(a)

def fmt(v,d=1):return '—' if not np.isfinite(v) else f'{v:.{d}f}'
def table_html(df):return df.to_html(index=False,escape=True,border=0,classes='data')
def savefig(name):plt.savefig(FIG/(name+'.png'),bbox_inches='tight');plt.savefig(FIG/(name+'.svg'),bbox_inches='tight');plt.close()

def participant_stats(df):
 # First average recording summaries across conditions within a participant. Then
 # weight each participant once; frame count / task duration never weights inference.
 metrics=['x_p50_mm','y_p50_mm','z_p50_mm','x_normalized','y_normalized','speed_median_mm_s','path_mm_per_s','tilt_median_deg','screen_projection_ratio','marker_angle_1_median_deg','marker_angle_2_median_deg','distance_to_thumb_median_mm','speed_correlation_with_thumb','thumb_corrected_z_median_mm']
 pp=df.groupby(['participant','task','finger'])[metrics].mean().reset_index();pp.to_csv(B/'data/participant_summary.csv',index=False)
 rows=[]
 for (task,finger),g in pp.groupby(['task','finger']):
  for metric in metrics:
   mean,lo,hi,n=ci(g[metric]);rows.append(dict(task=task,finger=finger,metric=metric,mean=mean,ci_low=lo,ci_high=hi,participants=n))
 out=pd.DataFrame(rows);out.to_csv(B/'data/participant_bootstrap.csv',index=False)
 return pp,out

def paired_comparisons(df):
 thumb=df[df.finger=='Thumb'];rows=[]
 for metric in ['z_p50_mm','x_normalized','y_normalized','speed_median_mm_s']:
  p=thumb.pivot_table(index=['participant','phone','condition'],columns='task',values=metric)
  for task in TASKS[1:]:
   pairs=p[[task,'READ']].dropna();diff=(pairs[task]-pairs.READ).groupby('participant').mean()
   mean,lo,hi,n=ci(diff);sd=diff.std(ddof=1);pval=float(ttest_1samp(diff,0).pvalue) if n>=3 and sd>0 else np.nan
   rows.append(dict(comparison=task+' - READ',metric=metric,mean_difference=mean,ci_low=lo,ci_high=hi,participants=n,matched_cells=len(pairs),effect_dz=mean/sd if sd>0 else np.nan,p_value=pval))
 for factor,levels in [('condition',['walking','seated']),('phone',['N6','S3'])]:
  for metric in ['z_p50_mm','speed_median_mm_s','tilt_median_deg']:
   idx=['participant','task']+(['phone'] if factor=='condition' else ['condition'])
   p=thumb.pivot_table(index=idx,columns=factor,values=metric);pairs=p[levels].dropna();diff=(pairs[levels[0]]-pairs[levels[1]]).groupby('participant').mean()
   mean,lo,hi,n=ci(diff);sd=diff.std(ddof=1);pval=float(ttest_1samp(diff,0).pvalue) if n>=3 and sd>0 else np.nan
   rows.append(dict(comparison=' - '.join(levels),metric=metric,mean_difference=mean,ci_low=lo,ci_high=hi,participants=n,matched_cells=len(pairs),effect_dz=mean/sd if sd>0 else np.nan,p_value=pval))
 r=pd.DataFrame(rows);r['p_holm']=np.nan;good=r.p_value.notna();r.loc[good,'p_holm']=multipletests(r.loc[good,'p_value'],method='holm')[1];r.to_csv(B/'data/paired_comparisons.csv',index=False);return r

def mixed_models(df):
 import statsmodels.formula.api as smf
 thumb=df[df.finger=='Thumb'].copy();out=[];logs=[]
 # Minimum meaningful coverage and participant support, not an arbitrary frame N.
 if thumb.participant.nunique()<12 or len(thumb)<600:
  save_json(B/'qa/mixed_models.json',dict(status='INSUFFICIENT_COVERAGE',rows=len(thumb)));return pd.DataFrame()
 for metric in ['z_p50_mm','y_normalized','speed_median_mm_s']:
  d=thumb.dropna(subset=[metric]);best=None
  for method in ['lbfgs','powell']:
   try:
    with warnings.catch_warnings(record=True) as ws:
     fit=smf.mixedlm(metric+' ~ C(task)*C(condition) + C(phone)',d,groups=d.participant).fit(method=method,reml=True,maxiter=500,disp=False)
    logs.append(dict(metric=metric,method=method,converged=bool(fit.converged),warnings=[str(w.message) for w in ws],random_intercept_variance=float(fit.cov_re.iloc[0,0]),residual_variance=float(fit.scale),rows=len(d)))
    if fit.converged and np.isfinite(fit.fe_params).all():best=fit;break
   except Exception as e:logs.append(dict(metric=metric,method=method,error=str(e)))
  if best is not None:
   conf=best.conf_int()
   for name,estimate in best.fe_params.items():out.append(dict(metric=metric,term=name,estimate=float(estimate),ci_low=float(conf.loc[name,0]),ci_high=float(conf.loc[name,1]),p_value=float(best.pvalues[name]),participants=d.participant.nunique(),rows=len(d)))
 r=pd.DataFrame(out)
 if len(r):
  r['p_holm']=np.nan;good=(r.term!='Intercept')&r.p_value.notna();r.loc[good,'p_holm']=multipletests(r.loc[good,'p_value'],method='holm')[1];r.to_csv(B/'data/mixed_models.csv',index=False)
 save_json(B/'qa/mixed_models.json',logs);return r

def figures(df,pp,boot,coverage,episodes,sensitivity):
 thumb=pp[pp.finger=='Thumb']
 fig,axs=plt.subplots(1,3,figsize=(15,4.4))
 for ax,metric,title,unit in zip(axs,['z_p50_mm','y_normalized','speed_median_mm_s'],['拇指标记点高度','拇指纵向位置','拇指运动速度'],['相对屏幕 Z / mm','Y / 手机高度（顶部为 0）','记录速度中位数 / mm/s']):
  for k,task in enumerate(TASKS):
   a=thumb[thumb.task==task][metric].dropna();mean,lo,hi,n=ci(a);j=np.linspace(-.13,.13,len(a));ax.scatter(k+j,a,s=16,c='#a8b8ae',alpha=.8);ax.errorbar(k,mean,yerr=[[mean-lo],[hi-mean]],fmt='o',color='#2c6650',capsize=4)
  ax.set_xticks(range(6),NAMES,rotation=30,ha='right');ax.set_title(title);ax.set_ylabel(unit);ax.grid(axis='y',alpha=.15)
 fig.suptitle('六任务比较 · 每个点为一位参与者，粗点与线为均值和 95% CI',fontsize=12);fig.tight_layout();savefig('task_comparison')
 fig,axs=plt.subplots(1,2,figsize=(12,4.5))
 for ax,metric,title in zip(axs,['z_p50_mm','speed_median_mm_s'],['标记点高度 Z / mm','运动速度中位数 / mm/s']):
  for k,(phone,d) in enumerate(DEVICES.items()):
   for cond,style in [('seated','-'),('walking','--')]:
    vals=[];lo=[];hi=[]
    for task in TASKS:
     a=df[(df.phone==phone)&(df.condition==cond)&(df.task==task)&(df.finger=='Thumb')][metric];mean,l,h,n=ci(a);vals.append(mean);lo.append(l);hi.append(h)
    x=np.arange(6);ax.plot(x,vals,style,color=['#287cce','#25a68f','#c79836','#e86432'][k],label=phone+' '+('坐姿' if cond=='seated' else '行走'),marker='o',markersize=3)
   ax.set_xticks(range(6),NAMES,rotation=25);ax.set_ylabel(title);ax.grid(axis='y',alpha=.15)
 axs[1].legend(fontsize=8,ncol=2);fig.suptitle('机型与情境 · 参与者等权的记录指标均值');fig.tight_layout();savefig('phone_condition')
 # Participant-normalised densities: aggregate record PDFs within each participant,
 # then aggregate participant PDFs. Plotting crop does not redefine valid samples.
 densities={task:{} for task in TASKS};heights={task:{} for task in TASKS};crop=[]
 denominator={(r.record,r.task):r.thumb_valid_frames for r in coverage.itertuples()}
 for p in sorted((B/'data/records').glob('*_density.npz')):
  pid=int(p.stem.split('_')[0][1:])
  record=p.stem.removesuffix('_density')
  with np.load(p) as z:
   for task in TASKS:
    hist=z[task+'_xy'];zh=z[task+'_z']
    n=denominator.get((record,task),0)
    if n:
     densities[task].setdefault(pid,[]).append(hist/n)
     heights[task].setdefault(pid,[]).append(zh/n)
   xe=z['x_edges'];ye=z['y_edges'];ze=z['z_edges']
 averaged={t:np.mean([np.mean(v,axis=0) for v in densities[t].values()],axis=0) for t in TASKS if densities[t]}
 positive=np.concatenate([a[a>0] for a in averaged.values()]);vmax=np.percentile(positive,98) if len(positive) else 1
 fig,axs=plt.subplots(2,3,figsize=(11,9))
 for ax,task in zip(axs.flat,TASKS):
  maps=[np.mean(v,axis=0) for v in densities[task].values()]
  if maps:
   avg=np.mean(maps,axis=0);im=ax.imshow(avg.T,extent=[xe[0],xe[-1],ye[-1],ye[0]],cmap='YlGnBu',aspect='auto',vmin=0,vmax=vmax)
  ax.add_patch(Rectangle((0,0),1,1,fill=False,edgecolor='#df673f',lw=1.3));ax.set_title(LABEL[task]);ax.set_xlabel('X / 手机宽度（右边缘为 0）');ax.set_ylabel('Y / 手机高度（顶部为 0）')
 fig.suptitle('拇指位置分布 · 手机坐标，参与者等权 · 红框为机身投影');fig.tight_layout();savefig('thumb_density')
 fig,axs=plt.subplots(2,3,figsize=(12,7))
 for ax,task in zip(axs.flat,TASKS):
  maps=[np.mean(v,axis=0) for v in heights[task].values()]
  if maps:ax.bar((ze[:-1]+ze[1:])/2,np.mean(maps,axis=0),width=4.5,color='#639782')
  ax.axvline(0,color='#e86432',lw=1);ax.set_xlim(-30,100);ax.set_title(LABEL[task]);ax.set_xlabel('标记点相对屏幕 Z / mm');ax.set_ylabel('5 mm 桶的占比')
 fig.suptitle('标记点高度分布 · 不等于指腹离屏净距');fig.tight_layout();savefig('height_distribution')
 fig,axs=plt.subplots(1,2,figsize=(12,4))
 for fi,finger in enumerate(FINGERS):
  vals=[];lo=[];hi=[]
  for task in TASKS:
   mean,l,h,n=ci(pp[(pp.finger==finger)&(pp.task==task)].speed_median_mm_s);vals.append(mean);lo.append(mean-l);hi.append(h-mean)
  axs[0].errorbar(range(6),vals,yerr=[lo,hi],label=FN[fi],color=COLORS[fi],capsize=2,marker='o',markersize=3)
 axs[0].set_xticks(range(6),NAMES,rotation=25);axs[0].set_ylabel('速度中位数 / mm/s');axs[0].legend(fontsize=8,ncol=2)
 for fi,finger in enumerate(FINGERS[1:]):
  vals=[pp[(pp.finger==finger)&(pp.task==t)].speed_correlation_with_thumb.mean() for t in TASKS];axs[1].plot(range(6),vals,marker='o',color=COLORS[fi+1],label=FN[fi+1],markersize=3)
 axs[1].set_xticks(range(6),NAMES,rotation=25);axs[1].set_ylabel('与拇指速度的记录内相关系数');axs[1].legend(fontsize=8,ncol=2);fig.suptitle('五指运动与协同变化 · 相关性不证明握持调整意图');fig.tight_layout();savefig('whole_hand')
 fig,axs=plt.subplots(1,2,figsize=(12,4))
 if len(episodes):
  for k,task in enumerate(TASKS):
   g=episodes[episodes.task==task];a=g.groupby('participant').duration_ms.median()
   if len(a):axs[0].scatter(np.full(len(a),k)+np.linspace(-.1,.1,len(a)),a,color='#2c6650',s=20)
   axs[1].bar(k,len(g),color='#639782')
 for ax in axs:ax.set_xticks(range(6),NAMES,rotation=25)
 axs[0].set_ylabel('参与者的 episode 时长中位数 / ms');axs[1].set_ylabel('合格稳定停留 episode 数');fig.suptitle('稳定停留子集 · 20 mm/s、400 ms、触摸排除 300 ms');fig.tight_layout();savefig('idle_dwell')
 fig,axs=plt.subplots(2,3,figsize=(12,7))
 for ax,task in zip(axs.flat,TASKS):
  g=sensitivity[(sensitivity.task==task)&(sensitivity.exclusion_ms==300)];mat=g.groupby(['velocity_threshold','min_duration_ms']).episodes.sum().unstack();im=ax.imshow(mat,cmap='YlGn',aspect='auto');ax.set_xticks(range(3),[200,400,500]);ax.set_yticks(range(3),[10,20,30]);ax.set_xlabel('最短停留 / ms');ax.set_ylabel('速度阈值 / mm/s');ax.set_title(LABEL[task]);
  for i in range(3):
   for j in range(3):ax.text(j,i,str(int(mat.iloc[i,j])),ha='center',va='center',color='white' if mat.iloc[i,j]>mat.to_numpy().max()*.55 else '#1c4230')
 fig.suptitle('阈值敏感性 · 触摸排除 300ms · 数字为片段数，阈值之间不属于独立样本');fig.tight_layout();savefig('threshold_sensitivity')
 # Selected real frames: explicitly one subject/phone/scenario, not group-average anatomy.
 fig,axs=plt.subplots(2,3,figsize=(12,11),subplot_kw={'projection':'3d'})
 index=json.loads((B/'outputs/index.json').read_text());cards=[c for c in index['clips'] if c['participant']==3 and c['phone']=='N6' and c['condition']=='seated']
 for ax,task in zip(axs.flat,TASKS):
  c=next((c for c in cards if c['task']==task),None)
  if not c:continue
  md=json.loads((B/'outputs'/c['meta']).read_text());a=np.fromfile(B/'outputs/clips'/md['binary'],dtype='<f4').reshape(-1,md['stride']);k=np.argmin(np.abs(a[:,1]-md['representative_frame']));pts=a[k,2:77].reshape(25,3)
  w,h,t=md['device']['size'];body=np.array([[0,0,0],[w,0,0],[w,h,0],[0,h,0],[0,0,0]]);ax.plot(body[:,0],body[:,1],body[:,2],color='#6b8975',alpha=.6)
  for f in range(5):
   for j in range(3):
    p=pts[f*4+j:f*4+j+2]
    if np.isfinite(p).all():ax.plot(p[:,0],p[:,1],p[:,2],color=COLORS[f],lw=2)
   p=pts[f*4:f*4+4];ax.scatter(p[:,0],p[:,1],p[:,2],color=COLORS[f],s=13)
  ax.set_xlim(110,-20);ax.set_ylim(190,-20);ax.set_zlim(-60,90);ax.set_box_aspect([1,1.6,1]);ax.view_init(35,-65);ax.set_title(LABEL[task]+f" · 帧 {md['representative_frame']}");ax.set_xlabel('X / mm');ax.set_ylabel('Y / mm');ax.text2D(.90,.70,'Z / mm',transform=ax.transAxes,rotation=90,fontsize=9)
 pd.DataFrame([{**c,'representative_epoch_ms':json.loads((B/'outputs'/c['meta']).read_text())['representative_epoch_ms']} for c in cards]).to_csv(B/'data/posture_atlas_sources.csv',index=False)
 fig.suptitle('真实六任务姿态 · P3 / N6 / 坐姿 · 各任务独立选取典型有效帧');fig.subplots_adjust(left=.04,right=.91,top=.92,bottom=.05,hspace=.22,wspace=.12);savefig('posture_atlas')
 ev=pd.read_csv(B/'data/event_trajectory.csv')
 if len(ev):
  e=ev.groupby(['participant','task','offset_ms'])[['relative_to_down_z_mm','speed_mm_s']].mean().reset_index();e.to_csv(B/'data/event_participant_summary.csv',index=False)
  fig,axs=plt.subplots(1,2,figsize=(12,4.5))
  for task,col in zip(TASKS,['#2b6e50','#287cce','#e86432','#9b74c7','#c79836','#25a68f']):
   for ax,m in zip(axs,['relative_to_down_z_mm','speed_mm_s']):
    g=e[e.task==task].groupby('offset_ms')[m].mean();ax.plot(g.index,g.values,label=LABEL[task],color=col,marker='o',markersize=3)
  for ax in axs:ax.axvline(0,color='#91a299',ls='--');ax.set_xlabel('相对 POINTER_DOWN / ms');ax.legend(fontsize=8,ncol=3)
  axs[0].set_ylabel('相对按下帧的标记点高度变化 / mm');axs[1].set_ylabel('速度 / mm/s');fig.suptitle('触摸前后轨迹 · 时钟匹配后的描述性结果，物理同步待独立验证');fig.tight_layout();savefig('event_trajectory')
 release_path=B/'data/release_trajectory.csv'
 if release_path.exists():
  release=pd.read_csv(release_path);metrics=['relative_to_up_z_mm','displacement_from_up_mm','support_displacement_mean_mm']
  e=release.groupby(['participant','task','offset_ms'])[metrics].mean().reset_index();e.to_csv(B/'data/release_participant_summary.csv',index=False)
  fig,axs=plt.subplots(1,3,figsize=(14,4.5))
  for task,col in zip(TASKS,['#2b6e50','#287cce','#e86432','#9b74c7','#c79836','#25a68f']):
   for ax,m in zip(axs,metrics):
    g=e[e.task==task].groupby('offset_ms')[m].mean();ax.plot(g.index,g.values,label=LABEL[task],color=col,marker='o',markersize=3)
  for ax,title in zip(axs,['相对抬手帧 Z 变化 / mm','距离抬手位置 / mm','有效支撑指平均位移 / mm']):ax.axvline(0,color='#91a299',ls='--');ax.set_xlabel('相对已观测 POINTER_UP / ms');ax.set_ylabel(title)
  axs[2].legend(fontsize=8,ncol=2);fig.suptitle('抬手后的运动与支撑指变化 · 允许再次触摸；不自动判定回到 Home Zone');fig.tight_layout();savefig('release_trajectory')

def sensitivity_stats(summary):
 thumb=summary[summary.finger=='Thumb'];p=thumb.pivot_table(index=['participant','phone','condition','task'],columns='basis',values=['z_p50_mm','y_normalized','speed_median_mm_s'])
 rows=[]
 for metric in ['z_p50_mm','y_normalized','speed_median_mm_s']:
  d=(p[metric]['context_500ms']-p[metric]['confirmed_core']).dropna()
  for task in TASKS:
   a=d[d.index.get_level_values('task')==task];rows.append(dict(task=task,metric=metric,matched_cells=len(a),median_absolute_change=float(a.abs().median()),p90_absolute_change=float(a.abs().quantile(.9))))
 r=pd.DataFrame(rows);r.to_csv(B/'data/segmentation_sensitivity.csv',index=False);return r

def build_report(df,pp,boot,coverage,eps,sens,paired,mixed,segment):
 ps=df.participant.nunique();records=coverage.record.nunique();available=coverage[coverage.status=='AVAILABLE'];checks=pd.read_csv(B/'data/checks.csv')
 status='全量计算完成' if records==128 else f'计算中：当前 {records}/128 条记录'
 rows=[]
 for task in TASKS:
  row={'任务':LABEL[task]};g=available[available.task==task];row['参与者']=g.participant.nunique();row['有效组合']=len(g);row['拇指有效分钟']=fmt(g.valid_duration_s.sum()/60)
  for m,n in [('x_p50_mm','X / mm'),('y_p50_mm','Y / mm'),('z_p50_mm','Z / mm'),('speed_median_mm_s','速度 / mm/s')]:
   a=pp[(pp.task==task)&(pp.finger=='Thumb')][m];mean,lo,hi,c=ci(a);row[n]=f'{fmt(mean)} [{fmt(lo)}, {fmt(hi)}]'
  rows.append(row)
 display=pd.DataFrame(rows)
 findings=[]
 for comp,metric in [('WRITE - READ','z_p50_mm'),('TAP - READ','y_normalized'),('walking - seated','speed_median_mm_s'),('N6 - S3','z_p50_mm')]:
  r=paired[(paired.comparison==comp)&(paired.metric==metric)].iloc[0];unit='手机高度比例' if metric=='y_normalized' else ('mm/s' if 'speed' in metric else 'mm')
  name={'WRITE - READ':'输入相对阅读的标记点高度','TAP - READ':'点击相对阅读的纵向位置','walking - seated':'行走相对坐姿的拇指速度','N6 - S3':'N6 相对 S3 的标记点高度'}[comp]
  p_text='<0.0001' if r.p_holm<.0001 else '='+fmt(r.p_holm,4)
  findings.append(f"{name}：平均配对差 {fmt(r.mean_difference,3 if metric=='y_normalized' else 1)} {unit}，95% CI [{fmt(r.ci_low,3 if metric=='y_normalized' else 1)}, {fmt(r.ci_high,3 if metric=='y_normalized' else 1)}]；n={int(r.participants)}，Holm 校正 p{p_text}。"+('该方向的差异在本样本中得到支持。' if r.ci_low*r.ci_high>0 and r.p_holm<.05 else '目前不能给出可靠的总体方向结论。'))
 ep_n=len(eps);ep_p=eps.participant.nunique() if len(eps) else 0
 idle_read=eps[eps.task=='READ'] if len(eps) else eps
 find5=f'严格规则仅检出 {ep_n} 个稳定停留片段，来自 {ep_p} 位参与者；阅读占 {len(idle_read)} 个。这是可用的稳定离屏子集，不能据此断言其他任务没有自然停留。'
 findings.append(find5)
 drag_segment=segment[(segment.task=='DRAG')&(segment.metric=='z_p50_mm')].iloc[0]
 findings.append(f'抽象手势对分段方法敏感：拖动加入最多 ±500ms 上下文后，标记点高度中位数的组合内绝对变化中位数为 {fmt(drag_segment.median_absolute_change)} mm，P90 为 {fmt(drag_segment.p90_absolute_change)} mm。解释任务高度时应同时查看 confirmed_core 汇总，不能把接触动作与含前后过渡的姿态混为同一分布。')
 missing=coverage[coverage.status!='AVAILABLE'];unknown=coverage.unknown_contact_frames.sum()/max(1,coverage.context_frames.sum())
 pairshow=paired.copy();pairshow['comparison']=pairshow.comparison.replace({t+' - READ':LABEL[t]+' − 阅读' for t in TASKS[1:]});pairshow=pairshow[['comparison','metric','participants','matched_cells','mean_difference','ci_low','ci_high','effect_dz','p_holm']].round(4)
 full_hand_rows=pp.groupby(['task','finger'])[['x_p50_mm','y_p50_mm','z_p50_mm','speed_median_mm_s','marker_angle_1_median_deg','marker_angle_2_median_deg','distance_to_thumb_median_mm','speed_correlation_with_thumb']].mean().round(2).reset_index()
 full_hand_rows.to_csv(B/'data/whole_hand_task_summary.csv',index=False)
 full_hand_rows['task']=full_hand_rows.task.map(LABEL);full_hand_rows['finger']=full_hand_rows.finger.replace(dict(zip(FINGERS,FN)))
 full_hand_rows=full_hand_rows.rename(columns={'task':'任务','finger':'手指','x_p50_mm':'X / mm','y_p50_mm':'Y / mm','z_p50_mm':'Z / mm','speed_median_mm_s':'速度 / mm/s','marker_angle_1_median_deg':'连线角度 1 / °','marker_angle_2_median_deg':'连线角度 2 / °','distance_to_thumb_median_mm':'距拇指标记点 / mm','speed_correlation_with_thumb':'与拇指速度相关'})
 corrected_rows=[]
 hand_observations=[]
 for task in TASKS:
  g=pp[pp.task==task];thumb=g[g.finger=='Thumb'];support=g[g.finger!='Thumb']
  mean,lo,hi,n=ci(thumb.thumb_corrected_z_median_mm)
  corrected_rows.append({'任务':LABEL[task],'参与者':n,'触摸基线修正 Z / mm':f'{fmt(mean)} [{fmt(lo)}, {fmt(hi)}]'})
  hand_observations.append(f'{LABEL[task]}：拇指速度 {fmt(thumb.speed_median_mm_s.mean())} mm/s；四个支撑指速度的参与者等权均值为 {fmt(support.speed_median_mm_s.mean())} mm/s，与拇指速度相关系数均值 {fmt(support.speed_correlation_with_thumb.mean(),2)}。这些是运动描述，不据此识别握持意图。')
 corrected_df=pd.DataFrame(corrected_rows)
 grip_path=B/'data/grip_candidates.csv';grip_count=len(pd.read_csv(grip_path)) if grip_path.exists() else 0
 idle_table=[]
 frequency=available[['record','participant','phone','condition','task','valid_duration_s']].copy()
 counts=eps.groupby(['record','task']).size().rename('episodes')
 frequency=frequency.join(counts,on=['record','task']);frequency['episodes']=frequency.episodes.fillna(0).astype(int)
 frequency['episodes_per_valid_task_minute']=frequency.episodes/(frequency.valid_duration_s/60)
 frequency.to_csv(B/'data/idle_frequency.csv',index=False)
 freq_pp=frequency[frequency.valid_duration_s>=1].groupby(['participant','task']).episodes_per_valid_task_minute.mean()
 for task in TASKS:
  g=eps[eps.task==task] if len(eps) else eps;fm,fl,fh,fn=ci(freq_pp.xs(task,level='task'))
  idle_table.append({'任务':LABEL[task],'片段数':len(g),'参与者数':g.participant.nunique() if len(g) else 0,'时长中位数 / ms':fmt(g.duration_ms.median()) if len(g) else '—','episode 中心 Z 中位数 / mm':fmt(g.median_z_mm.median()) if len(g) else '—','位置波动 XYZ std 中位数 / mm':' / '.join(fmt(g[m].median(),2) for m in ['std_x_mm','std_y_mm','std_z_mm']) if len(g) else '—','每有效任务分钟频率 [95% CI]':f'{fmt(fm,2)} [{fmt(fl,2)}, {fmt(fh,2)}]'})
 idle_df=pd.DataFrame(idle_table)
 source='https://github.com/interactionlab/unintended-input-dataset'
 md=f'# Le 2019 六任务手部姿态分析 v1\n\n状态：{status}，浏览器与视觉检查见 qa；独立物理同步未验证。\n\n覆盖 {ps} 位参与者、{records} 条记录、{len(available)}/768 个有拇指有效数据的任务组合。\n\n'
 md+='\n'.join('- '+f for f in findings)+'\n\n## 六任务拇指比较\n\n'+display.to_markdown(index=False)+'\n\n'
 md+='![六任务比较](figures/task_comparison.png)\n\n![真实姿态图谱](figures/posture_atlas.png)\n\n## 方法与解释\n\n'
 methodology=[
 '先计算每条记录的各任务中位数，再在参与者内等权平均机型和情境，最后对参与者等权汇总。CI 使用 5000 次参与者 bootstrap；配对差先匹配同一参与者/机型/情境，再参与者内平均。26 项配对比较作为一个检验家族作 Holm 校正。',
 '主分析为任务全部有效姿态；它包含触摸阶段。推断用记录×任务至少有 240 个有效采样帧（约 1 秒），更短组合仍保留在覆盖与原始汇总表中。稳定离屏停留单独分析，不把全部非触摸帧称为 Idle。',
 '阅读/输入使用第一至最后触摸事件之间的任务上下文，因此遗漏任务开始前与末尾无触摸的部分。抽象手势使用每行试次跨度，并加入最多 ±500ms 推定上下文；相邻任务按中点裁切。两种分段结果见 segmentation_sensitivity.csv。',
 f'原始事件状态不全，约 {unknown:.1%} 的已标记上下文帧为未知触摸状态。缺失抬手时只保留至最后观测事件的接触跨度，之后未知；未知状态不进入 Idle 与触摸基线。',
 '标记点经手机刚体逆变换和官方 [x,z,y] 轴置换得到局部坐标；原点为正面右上角。X 朝左、Y 朝下，Z 为按官方法线的有符号高度。原始四元数规范化，记录刚体/标记点有效性。',
 '保留原始世界标记点；派生局部坐标排除缺失、距原点超 500mm、连续帧局部位移超 4mm 的点，不作轨迹重建或统计平滑。速度不跨缺口。',
 '触摸修正高度使用参与者×机型×情境内已知接触帧的拇指 Z 中位数，并另存各任务接触基线；手指旋转与不同触点仍会影响该量，它不是指腹净距。',
 '几何关系只描述标记点连线角度、指间距离和速度相关。协同变化是握持调整候选，未由独立视频确认其动因；手机倾角是屏幕法线与重力竖直轴的锐角。',
 '沿用官方 Motive 12AM 导出问题修正：17 条中午记录头写为 12.xx AM，手机日志独立显示 +12 小时差；修正为当日中午，再按 Europe/Berlin 夏令时转 epoch。S3 使用全部时钟匹配点（无表头，保留首行）插值修正；超出匹配范围的试次保留姿态上下文并标记，但排除事件推断。其余机型依原代码使用共享 epoch。时间覆盖与采样匹配不构成独立物理同步证据。',
 '密度图先将每条记录直方图归一化，再参与者内平均，最后参与者等权平均。图示 XY 与 Z 有裁切范围；密度图不等于误触风险或无误触安全区域。',
 '机型效应同时包含宽度、长度、厚度、屏幕及外形差异，不能解释为屏幕尺寸的独立因果效应。样本为右利手年轻人和历史机型。',
 '本数据的食指是自然支撑/运动手指，不等于你新实验的托握＋食指操作条件。三维动画不含未记录的皮肤、软组织与触面形变。']
 md+='\n'.join('- '+f for f in methodology)+'\n\n## 稳定停留\n\n'+idle_df.to_markdown(index=False)+'\n\n'
 md+='稳定规则：已观测离屏、距前次抬手和下次按下均 >300ms、速度 <20mm/s、连续 >=400ms；缺口与任务变化拆段。Home Zone 以 episode 中心分位数盒表示，盒体不是最高密度体积。阈值组合为 10/20/30 mm/s × 200/400/500ms × 200/300/500ms。\n\n'
 md+='频率以完整有效任务时长为分母（包含触摸），先记录内计算、再参与者内和参与者间等权；零停留记录保留。位置波动与时长为 episode 等权描述，不代表参与者等权估计。频率明细见 idle_frequency.csv。\n\n'
 md+='## 整手配置与协同运动\n\n'+ '\n'.join('- '+o for o in hand_observations)+'\n\n![五指运动](figures/whole_hand.png)\n\n'+full_hand_rows.to_markdown(index=False)+'\n\n'
 md+=f'另检出 {grip_count} 个协同位移候选区间：至少两个支撑指甲标记点在连续 200ms 中各移动 ≥5mm，候选状态持续 ≥100ms。索引见 grip_candidates.csv。该阈值用于片段筛选，尚无独立视频确认，区间数量不等于真实握持调整次数。\n\n'
 md+='## 触摸基线修正高度\n\n'+corrected_df.to_markdown(index=False)+'\n\n该量使用同参与者／机型／情境的已知接触帧 Z 中位数作基线；有符号值允许为负。它与上方未修正标记点高度分别报告，均不等于指腹净距。\n\n'
 md+='## 操作后回位过程\n\n![抬手后的运动](figures/release_trajectory.png)\n\n使用真实 POINTER_UP 前后 -300～1000ms 的连续有效帧，比较拇指相对抬手位置的高度和位移、支撑指协同位移。同任务内允许再次触摸；位移不自动解释为成功回到 Home Zone。缺失抬手、追踪缺口及不可靠时钟试次不进入该汇总。事件与样本索引见 release_trajectory.csv，物理对齐仍待独立验证。\n\n'
 md+='## 混合模型诊断\n\n探索模型使用 task × condition + phone 和参与者随机截距，系数以 DRAG／坐姿／N6 为参考；42 个非截距系数另作 Holm 校正。优化器出现协方差奇异与数值警告，收敛及随机截距方差保存在 qa/mixed_models.json。主结论以参与者配对差异与 bootstrap 为依据，模型仅作探索补充。\n\n'
 md+='## Hover 研究的用途\n\n- 将六类自然操作姿态作为新实验 A 组的历史参照；新实验仍需重测当前设备和两种握持条件。\n- 将稳定停留、触摸后回位与支撑指活动作为易混淆条件的采样线索，不能把所有 Le 帧统称为 Hover 负类。\n- 传感范围应参考真实位置分布并在新硬件上校准；这些结果不能直接给出 UI 激活阈值、误触率或主动 Hover 意图。\n\n'
 md+='## 可追溯数据与来源\n\n'+f'[官方数据仓库]({source})，提交 625383fa38ddda5f09d888ed066cb4161667baa9。\n\n原始研究 PDF 与 Markdown 只作为研究目标与假设参照，未将其中场景推演视为本数据已有标签。\n\n主表：data/summary.csv、participant_bootstrap.csv、paired_comparisons.csv、coverage.csv；事件与稳定停留：event_trajectory.csv、episodes.csv、sensitivity.csv；每条记录保留 NPZ 数组、来源帧和原始日志信息。\n'
 (B/'outputs/findings.md').write_text(md)
 # Lightweight self-contained HTML; all charts are standalone PNG/SVG artifacts.
 css='body{font-family:Inter,"PingFang SC",sans-serif;color:#203d30;background:#f7f9f6;margin:0}main{max-width:1120px;margin:auto;padding:40px 28px}h1{font-size:32px}h2{margin-top:38px;font-size:21px}p,li{font-size:14px;line-height:1.85}img{width:100%;background:white;border:1px solid #e1e8df;border-radius:9px;margin:12px 0}a{color:#28634a}.data{width:100%;border-collapse:collapse;font-size:12px;background:white}.data td,.data th{padding:10px;text-align:left;border-bottom:1px solid #e4eae1}.scroll{overflow:auto}.note{background:#e6efe6;padding:18px;border-radius:9px}summary{cursor:pointer;color:#46715a}header{display:flex;justify-content:space-between;align-items:center}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.tile{background:white;padding:18px;border:1px solid #e2e9df;border-radius:9px}.tile b{font-size:25px;display:block}'
 def chart(name,caption):return f'<p>{html.escape(caption)}</p><a href="figures/{name}.svg"><img src="figures/{name}.png" alt="{html.escape(caption)}"></a>'
 content=f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Le 2019 六任务姿态分析</title><style>{css}</style></head><body><main><header><span>LE 2019 / POSTURE ANALYSIS</span><a href="/">打开三维回放 ↗</a></header><h1>不同任务下，手部姿态有何变化</h1><p>全量计算结果 · 右手单手自然操作 · v1</p><div class="grid"><div class="tile"><b>{ps}</b>参与者</div><div class="tile"><b>{records}</b>机型／情境记录</div><div class="tile"><b>{len(available)}/768</b>拇指有效任务组合</div></div><h2>本样本观察到的结果</h2><ul>'+''.join('<li>'+html.escape(f)+'</li>' for f in findings)+'</ul>'
 content+=chart('posture_atlas','三维图谱选用 P3／N6／坐姿的真实帧，每个任务独立选择；可在回放中检查其他参与者。')
 content+='<h2>六任务拇指位置与运动</h2><p>数值为参与者等权均值 [95% CI]；X 朝左，Y 朝下。高度包含全部有效操作阶段。</p><div class="scroll">'+table_html(display)+'</div>'+chart('task_comparison','任务间比较：每个灰点为一位参与者，绿色点和线为均值与置信区间。')+chart('thumb_density','位置分布说明手指通常出现在哪里，不直接代表安全区或 Hover 意图。')+chart('height_distribution','Z 为标记点位置；请勿直接用于指腹净距或硬件触发阈值。')
 content+='<h2>机型、情境与整手协同</h2>'+chart('phone_condition','实线为坐姿，虚线为行走；机型变化同时包含外形与尺寸差异。')+chart('whole_hand','支撑指也会移动；速度协同不能单独确认其行为意图。')+'<details><summary>查看六任务整手几何指标（参与者等权描述）</summary><div class="scroll">'+table_html(full_hand_rows)+'</div></details>'
 content+='<ul>'+''.join('<li>'+html.escape(o)+'</li>' for o in hand_observations)+f'</ul><p>筛选出 {grip_count} 个协同位移候选区间，定义为至少两个支撑指甲点在连续 200ms 中各移动 ≥5mm、候选状态持续 ≥100ms；未由独立视频确认，候选区间不等于握持调整次数。</p><h2>触摸基线修正高度</h2><p>按同参与者／机型／情境已知接触帧的拇指 Z 中位数修正。与原始高度分别报告；两者均不等于指腹净距。</p>'+table_html(corrected_df)
 content+='<h2>稳定离屏停留</h2><div class="note">'+html.escape(find5)+'</div><p>低速度与稳定位置本身不等于主动 Hover。严格子集使用已记录抬手、排除触摸前后 300ms、速度低于 20mm/s、至少持续 400ms。</p><div class="scroll">'+table_html(idle_df)+'</div>'+chart('idle_dwell','每个点为贡献稳定停留的参与者；不同任务有效人数可能不同。')+chart('threshold_sensitivity','阈值改变会影响子集规模；详细位置与时长结果保存在 sensitivity.csv。')
 content+='<p>频率分母为完整有效任务分钟，含触摸阶段；零片段记录保留，参与者等权汇总。波动与时长采用 episode 等权描述。频率明细见 idle_frequency.csv。</p>'
 if (FIG/'event_trajectory.png').exists():content+='<h2>触摸前后变化</h2>'+chart('event_trajectory','此图仅为时钟匹配后的探索观察；缺口不会跨越，事件位置未获独立物理同步确认。')
 if (FIG/'release_trajectory.png').exists():content+='<h2>抬手后的回位过程</h2>'+chart('release_trajectory','真实抬手前后连续有效帧；同任务内允许再次触摸，缺失抬手不补造。该量描述运动，未自动确认回到 Home Zone；独立物理对齐待验证。')
 content+='<h2>对你的 Hover User Study 的用途</h2><ul><li>为六种自然操作建立历史姿态参照，帮助选择静止阅读、操作后回位、支撑指活动等容易混淆的采样条件。</li><li>在你的新设备与“单手拇指／托握＋食指”条件下复测这些分布，再与主动 Hover 指向比较。</li><li>这些数据支持描述自然姿态；UI 激活阈值、误触率和主动意图需要新实验结果。</li></ul>'
 content+='<h2>方法、覆盖与限制</h2><ul>'+''.join('<li>'+html.escape(m)+'</li>' for m in methodology)+'</ul>'
 content+='<details><summary>缺少有效拇指样本的组合</summary><div class="scroll">'+table_html(missing[['participant','phone','condition','task','trials','context_frames','status']])+'</div></details>'
 content+='<details><summary>配对差异与效应量</summary><div class="scroll">'+table_html(pairshow)+'</div></details><details><summary>分段敏感性</summary><div class="scroll">'+table_html(segment.round(3))+'</div></details>'
 if len(mixed):content+='<details><summary>探索性混合模型（参与者随机截距）</summary><p>参考条件为 DRAG／坐姿／N6，42 个非截距系数另作 Holm 校正。优化过程中出现数值与协方差奇异警告；收敛和随机截距方差见 qa/mixed_models.json。主结论以参与者配对差异与 bootstrap 为依据。</p><div class="scroll">'+table_html(mixed.round(4))+'</div></details>'
 content+=f'<h2>来源与可复现性</h2><p><a href="{source}">Le et al. 官方仓库</a> · 固定提交 625383fa · 原始 ZIP 校验见 qa/archive_checks.json。原 PDF 与 Markdown 中的研究设想作为假设参照，未当作本数据已有标签。</p><p>代码、完整表格、原始帧数组和启动脚本均在工作包；图像提供可编辑 SVG。浏览器与视觉验证状态请查看 qa/validation.md。</p></main></body></html>'
 from report_explorer import enhance_report
 (B/'outputs/report.html').write_text(enhance_report(content))
 save_json(B/'outputs/findings.json',dict(participants=int(ps),records=int(records),available_task_cells=len(available),idle_episodes=ep_n,findings=findings,scope='descriptive marker posture; no intentional Hover labels'))

def main():
 summary=pd.read_csv(B/'data/summary.csv');df=summary[(summary.basis=='context_500ms')&(summary.valid_frames>=240)].copy();coverage=pd.read_csv(B/'data/coverage.csv')
 eps=pd.read_csv(B/'data/episodes.csv');sens=pd.read_csv(B/'data/sensitivity.csv')
 pp,boot=participant_stats(df);paired=paired_comparisons(df);mixed=mixed_models(df);seg=sensitivity_stats(summary);figures(df,pp,boot,coverage,eps,sens);build_report(df,pp,boot,coverage,eps,sens,paired,mixed,seg)
 print('Report complete',len(df),'record-task-finger rows',flush=True)
if __name__=='__main__':main()
