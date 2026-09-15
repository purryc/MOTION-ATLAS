"""Task-wide dwell thresholds, conservative sparse 3D occupancy and UI log context."""
import csv,json,re
from pathlib import Path
import numpy as np
import pandas as pd
from analyze import B,TASKS,COORD,episodes,save_json,numbers
from zones import quantiles

THRESHOLDS=[100,200,300,400,500,600]
# Nominal physical display resolutions; application/status-bar insets not captured.
PIXELS={'S3':[480,800],'S4':[1080,1920],'OPO':[1080,1920],'N6':[1440,2560]}

def voxelize(points,size):
 if not len(points):return dict(size_mm=size,voxels=[],valid_frames=0,total_s=0,max_s=0)
 keys=np.floor(points/size).astype(np.int32);cells,counts=np.unique(keys,axis=0,return_counts=True)
 return dict(size_mm=size,voxels=np.column_stack([cells,counts]).tolist(),valid_frames=len(points),total_s=len(points)/240,max_s=int(counts.max())/240)

def threshold_stats(eps):
 d=[e['duration_ms'] for e in eps]
 return dict(episodes=len(eps),total_ms=sum(d),median_ms=float(np.median(d)) if d else None,max_ms=max(d) if d else None)

def ui_context(md,task):
 trials=[];files={}
 for tr in md['trials']:
  if tr['task']!=task:continue
  source=tr['source']
  if source not in files:
   with (B/source).open() as f:files[source]=list(csv.DictReader(f,delimiter=';'))
  raw=files[source][tr['row']]
  allowed=['tileX','tileY','targetX','targetY','textId','textToWrite']
  trials.append(dict(tr,controls={k:raw[k] for k in allowed if k in raw}))
 ev=[[e['timestamp_ms'],e['x_px'],e['y_px'],e['action'],e['trial']] for e in md['events'] if e['task']==task and e['sync_eligible'] and e['x_px'] is not None and e['y_px'] is not None]
 return dict(trials=trials,events=ev,nominal_pixels=PIXELS[md['phone']],evidence='schematic: logged anchor/touch positions; nominal full-display mapping; insets, sizes and reading body/keyboard geometry unavailable',paper='https://www.medien.ifi.lmu.de/pubdb/publications/pub/le2019investigatingunintended/le2019investigatingunintended.pdf#page=5')

def main():
 out=B/'outputs/explorer';out.mkdir(exist_ok=True);base=json.loads((B/'outputs/calibration.json').read_text())['records'];records={};rows=[];freq=[];dwell=[];hist={}
 for path in sorted((B/'data/records').glob('*.npz')):
  if not re.fullmatch(r'P\d+_(S3|S4|OPO|N6)_(seated|walking)',path.stem):continue
  md=json.loads(path.with_suffix('.json').read_text());name=path.stem
  with np.load(path) as z:a={k:z[k] for k in ['time_ms','frame','local_mm','speed_mm_s','task_context','contact_state']}
  ts=a['time_ms'];context=a['task_context'];thumb=a['local_mm'][:,0];valid=np.isfinite(thumb).all(1);baseline=base[name]['baseline_mm']
  downs=np.unique([e['timestamp_ms'] for e in md['events'] if e['sync_eligible'] and 'DOWN' in e['action']]);ups=np.unique([e['timestamp_ms'] for e in md['events'] if e['sync_eligible'] and 'UP' in e['action']])
  candidates=episodes(ts,a['frame'],a['speed_mm_s'],a['local_mm'],context,a['contact_state'],downs,ups,duration=100)
  tasks={}
  for ti,task in enumerate(TASKS):
   mask=valid&(context==ti);points=thumb[mask]
   if not len(points):continue
   corrected=points.copy()
   if baseline is not None:corrected[:,2]=np.maximum(0,corrected[:,2]-baseline)
   activity=dict(raw=voxelize(points,2),corrected=voxelize(corrected,2) if baseline is not None else None)
   choices={}
   for threshold in THRESHOLDS:
    eps=[e for e in candidates if e['task']==task and e['duration_ms']+1e-5>=threshold];sm=np.zeros(len(ts),dtype=bool)
    for e in eps:sm|=(ts>=e['start_ms'])&(ts<=e['end_ms'])
    stable=thumb[sm&mask];cp=stable.copy()
    if baseline is not None:cp[:,2]=np.maximum(0,cp[:,2]-baseline)
    stat=threshold_stats(eps)
    choices[str(threshold)]=dict(summary=stat,episodes=eps,home=quantiles(stable,episodes=len(eps)) if len(stable) else None,heat=dict(raw=voxelize(stable,.5),corrected=voxelize(cp,.5) if baseline is not None else None))
    freq.append(dict(record=name,participant=md['participant'],task=task,threshold_ms=threshold,episodes=len(eps),total_ms=stat['total_ms'],occupancy_percent=stat['total_ms']/(len(points)/240*1000)*100))
    for e in eps:dwell.append(dict(record=name,participant=md['participant'],phone=md['phone'],condition=md['condition'],threshold_ms=threshold,**e))
   tasks[task]=dict(activity=activity,thresholds=choices,ui=ui_context(md,task),valid_frames=len(points))
   rows.append(dict(record=name,participant=md['participant'],phone=md['phone'],condition=md['condition'],task=task,valid_frames=len(points),raw_median_mm=float(np.median(points[:,2])),corrected_median_mm=float(np.median(corrected[:,2])) if baseline is not None else None))
   key=(md['participant'],task)
   if baseline is not None:hist.setdefault(key,[]).append(np.histogram(corrected[:,2],bins=np.arange(0,106,5))[0]/len(points))
  save_json(out/(name+'.json'),dict(record=name,source=md['source'],unit='mm',coordinate_system=COORD,baseline_mm=baseline,tasks=tasks))
  records[name]=name+'.json'
  if len(records)%16==0:print('Explorer',len(records),'records',flush=True)
 save_json(out/'index.json',dict(version=1,records=records,thresholds_ms=THRESHOLDS,rule=dict(velocity_mm_s=20,touch_exclusion_ms=300,sample_rate_hz=240),heat_definition='sparse floor XYZ voxel occupancy; 2mm activity/0.5mm dwell; all valid frames conserved; counts/240=sampling-time seconds; raw and max(0,Z-baseline) histograms computed separately'))
 pd.DataFrame(rows).to_csv(B/'data/explorer_height_cells.csv',index=False);pd.DataFrame(dwell).to_csv(B/'data/explorer_dwell_episodes.csv',index=False);f=pd.DataFrame(freq);f.to_csv(B/'data/explorer_dwell_cells.csv',index=False)
 summaries={}
 for t in THRESHOLDS:
  by_task={}
  for task in TASKS:
   g=f[(f.threshold_ms==t)&(f.task==task)];es=[e for e in dwell if e['task']==task and e['threshold_ms']==t];dur=[e['duration_ms'] for e in es]
   by_task[task]=dict(episodes=int(g.episodes.sum()),total_s=float(g.total_ms.sum()/1000),median_ms=float(np.median(dur)) if dur else None,participants_with_dwell=int(g[g.episodes>0].participant.nunique()),participants=int(g.participant.nunique()),participant_equal_occupancy_percent=float(g.groupby('participant').occupancy_percent.mean().mean()))
  summaries[str(t)]=by_task
 save_json(out/'report.json',dict(thresholds=summaries,height_cells=rows,corrected_histogram={task:np.mean([np.mean(h,axis=0) for (p,t),h in hist.items() if t==task],axis=0).tolist() for task in TASKS},height_bin_edges_mm=list(range(0,106,5))))
 print('Explorer complete',len(records),'records',flush=True)

if __name__=='__main__':main()
