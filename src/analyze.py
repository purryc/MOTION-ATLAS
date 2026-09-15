"""Reproducible marker-based posture analysis. No gap reconstruction or intent labels."""
import argparse
import csv
import hashlib
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation

B = Path(__file__).resolve().parents[1]
TASKS = ['READ', 'WRITE', 'TAP', 'DRAG', 'SCROLL_V', 'SCROLL_H']
NAMES = ['阅读', '输入', '点击', '拖动', '竖向滚动', '横向滚动']
FINGERS = ['Thumb', 'Index', 'Middle', 'Ring', 'Little']
MARKERS = [f+'_'+j for f in FINGERS for j in ['Fn', 'DIP', 'PIP', 'MCP']] + ['Wrist'] + ['R_Shape_'+str(i) for i in range(1,5)]
DEVICES = {
 'S3': dict(model='Samsung Galaxy S3 Mini', size=[63,121.55,9.9], screen=[52.3,87.1], offset=[5.35,17.225]),
 'S4': dict(model='Samsung Galaxy S4', size=[70,137,7.9], screen=[62.3,110.7], offset=[3.85,13.15]),
 'OPO': dict(model='OnePlus One', size=[75.9,152.9,8.9], screen=[68.5,121.8], offset=[3.7,15.55]),
 'N6': dict(model='Motorola Nexus 6', size=[83,159.3,10.1], screen=[74.2,136.3], offset=[4.15,11.5])}
MODEL = {'GT-I8190':'S3','GT-I9505':'S4','A0001':'OPO','Nexus 6':'N6'}
COORD = 'pivot at front top-right; +X toward left edge; +Y toward bottom; +Z signed normal from upstream axis swap; millimetres'

def save_json(path, obj):
 path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(obj, ensure_ascii=False, allow_nan=False, indent=2), encoding='utf8');tmp.replace(path)

def save_npz(path, **arrays):
 tmp=path.with_suffix('.npz.tmp')
 with tmp.open('wb') as f:np.savez_compressed(f,**arrays)
 tmp.replace(path)

def numbers(s):
 if not s or str(s).lower()=='nan': return np.array([],dtype=float)
 return np.fromstring(str(s).strip('[]()'),sep=',')

def clock_map(pid, cond, ts):
 """S3 matching file has NO header: retain its first clock landmark."""
 p=B/'sources/phone_dataset/timestamp_adjusted'/f'timestamp_matching_s3_P{pid}_{cond}.txt'
 if not p.exists(): return ts, {'method':'S3_MAPPING_MISSING','eligible':False}
 a=np.loadtxt(p,delimiter=',',ndmin=2); a=a[np.argsort(a[:,0])]
 unique,ix=np.unique(a[:,0],return_index=True); a=a[ix]
 delta=a[:,1]-a[:,0]
 mapped=ts+np.interp(ts,unique,delta)
 outside=(ts<unique[0])|(ts>unique[-1])
 return mapped,dict(method='S3_LANDMARK_INTERPOLATION',eligible=True,landmarks=len(a),
  offset_median_ms=float(np.median(delta)),offset_range_ms=float(np.ptp(delta)),
  extrapolated_events=int(outside.sum()),landmark_start_ms=float(unique[0]),landmark_end_ms=float(unique[-1]))

def logs(pid, phone, cond):
 trials=[]; events=[]; notes=[]
 root=B/'sources/phone_dataset'/f'P{pid}'/'files'
 for task in TASKS:
  path=root/f'StudyRun{pid}_{next(k for k,v in MODEL.items() if v==phone)}_{cond}_{task}.txt'
  if not path.exists(): continue
  with path.open() as f:
   for rownum,row in enumerate(csv.DictReader(f,delimiter=';')):
    ts=numbers(row.get('timestamp')); acts=row.get('action','').split(',')
    xx=numbers(row.get('movementX')); yy=numbers(row.get('movementY'))
    if not len(ts): continue
    if len(acts)!=len(ts):
     notes.append(dict(source=str(path.relative_to(B)),row=rownum,issue='ACTION_LENGTH_MISMATCH',timestamps=len(ts),actions=len(acts)))
     continue
    mapped,sync=clock_map(pid,cond,ts) if phone=='S3' else (ts,dict(method='SHARED_EPOCH_AS_UPSTREAM',eligible=True))
    # Clock extrapolation is explicitly excluded from event inference.
    sync_ok=sync['eligible']
    mp=B/'sources/phone_dataset/timestamp_adjusted'/f'timestamp_matching_s3_P{pid}_{cond}.txt'
    if phone=='S3' and mp.exists():
     landmarks=np.loadtxt(mp,delimiter=',',ndmin=2)[:,0]
     sync_ok &= bool(ts.min()>=landmarks.min() and ts.max()<=landmarks.max())
    tid=f'{task}-{rownum+1}'
    trials.append(dict(task=task,trial=tid,start_ms=float(mapped.min()),end_ms=float(mapped.max()),
      source=str(path.relative_to(B)),row=rownum,sync_eligible=sync_ok,clock=sync))
    for k,(t,act) in enumerate(zip(mapped,acts)):
     events.append(dict(timestamp_ms=float(t),action=act.strip(),task=task,trial=tid,
      x_px=float(xx[k]) if k<len(xx) else np.nan,y_px=float(yy[k]) if k<len(yy) else np.nan,
      source=str(path.relative_to(B)),row=rownum,sync_eligible=sync_ok))
 trials.sort(key=lambda r:r['start_ms']); events.sort(key=lambda r:r['timestamp_ms'])
 # READ/WRITE span includes inter-action pauses; abstract gesture labels stay per trial.
 intervals=[]
 for task in ['READ','WRITE']:
  a=[r for r in trials if r['task']==task]
  if a: intervals.append(dict(task=task,trial=task+'-block',start_ms=min(r['start_ms'] for r in a),end_ms=max(r['end_ms'] for r in a),source=a[0]['source'],sync_eligible=all(r['sync_eligible'] for r in a)))
 intervals += [dict(r) for r in trials if r['task'] not in ['READ','WRITE']]
 intervals.sort(key=lambda r:r['start_ms'])
 # Trial-context padding is bounded by the midpoint to neighbouring labelled intervals.
 # Both confirmed core and inferred +/-500ms context are retained for sensitivity checks.
 for i,r in enumerate(intervals):
  r['context_start_ms']=r['start_ms']-500
  r['context_end_ms']=r['end_ms']+500
  if i: r['context_start_ms']=max(r['context_start_ms'],(intervals[i-1]['end_ms']+r['start_ms'])/2)
  if i+1<len(intervals):r['context_end_ms']=min(r['context_end_ms'],(r['end_ms']+intervals[i+1]['start_ms'])/2)
 return trials,intervals,events,notes

def motive_epoch(text):
 dt=datetime.strptime(text,'%Y-%m-%d %I.%M.%S.%f %p')
 # Upstream read_take explicitly documents Motive's "12AM error". These daytime
 # sessions' phone logs independently differ by +12h. Retain the upstream correction.
 if dt.hour==0:dt=dt.replace(hour=12)
 return dt.replace(tzinfo=ZoneInfo('Europe/Berlin')).timestamp()*1000

def read_motion(stream):
 rows=[next(csv.reader([stream.readline()])) for _ in range(7)]
 header=rows[0]; names=rows[3]; axes=rows[6]; kinds=rows[5]
 if header[header.index('Length Units')+1]!='Meters' or header[header.index('Coordinate Space')+1]!='Global' or header[header.index('Rotation Type')+1]!='Quaternion':raise ValueError('Unsupported coordinate schema')
 if abs(float(header[header.index('Capture Frame Rate')+1])-240)>.01:raise ValueError('Unexpected capture frame rate')
 start=motive_epoch(header[9])
 cols=[0,1]; keys=['frame','relative_time']
 rigid=names[2]
 for kind,suffix in [('Rotation',['X','Y','Z','W']),('Position',['X','Y','Z'])]:
  for axis in suffix:
   ids=[i for i,n in enumerate(names) if n==rigid and kinds[i]==kind and axes[i]==axis]
   if len(ids)!=1: raise ValueError('Rigid body columns ambiguous')
   cols.append(ids[0]); keys.append('q'+axis if kind=='Rotation' else 'p'+axis)
 for marker in MARKERS:
  for axis in ['X','Y','Z']:
   ids=[i for i,n in enumerate(names) if n.split(':')[-1].lower()==marker.lower() and axes[i]==axis and kinds[i]=='Position']
   if len(ids)!=1: raise ValueError('Marker columns missing or ambiguous: '+marker)
   cols.append(ids[0]); keys.append(marker+'_'+axis)
 # pandas maintains source-column order; explicitly reorder after reading.
 raw=pd.read_csv(stream,header=None,usecols=cols,dtype=np.float64)
 a=raw[cols].to_numpy(); ts=start+a[:,1]*1000
 return a[:,0].astype(np.int32),ts,a[:,2:6],a[:,6:9]*1000,a[:,9:].reshape(-1,len(MARKERS),3)*1000,header

def transform(q,p,world):
 valid=np.isfinite(q).all(1)&np.isfinite(p).all(1)
 norm=np.linalg.norm(q,axis=1);valid &= (norm>0.98)&(norm<1.02)
 R=np.full((len(q),3,3),np.nan)
 R[valid]=Rotation.from_quat(q[valid]).as_matrix()
 raw=np.einsum('nji,nmj->nmi',R,world-p[:,None,:])
 return raw[:,:,[0,2,1]],valid,R

def speed_of(ts,points,frame):
 dt=np.diff(ts)/1000; dp=np.diff(points,axis=0)
 contiguous=(np.diff(frame)==1)&(dt>0)&(dt<0.006)
 speed=np.full(points.shape[:2],np.nan)
 speed[1:]=np.where(contiguous[:,None],np.linalg.norm(dp,axis=2)/dt[:,None],np.nan)
 return speed

def labels(ts,intervals):
 core=np.full(len(ts),-1,dtype=np.int8);context=core.copy(); eligible=np.zeros(len(ts),bool)
 for r in intervals:
  k=TASKS.index(r['task']); mask=(ts>=r['context_start_ms'])&(ts<r['context_end_ms'])
  conflict=mask&(context>=0)&(context!=k)
  if conflict.any():raise ValueError('Conflicting task context intervals')
  context[mask]=k;eligible[mask]=r['sync_eligible']
  core[(ts>=r['start_ms'])&(ts<=r['end_ms'])]=k
 return core,context,eligible

def contacts(ts,events,trials):
 state=np.full(len(ts),-1,dtype=np.int8);downs=[];ups=[]
 # UP means released until next event. Incomplete contacts stop at final observed event,
 # leaving the rest UNKNOWN rather than inventing a release timestamp.
 ev=sorted([e for e in events if e['sync_eligible']],key=lambda e:e['timestamp_ms'])
 et=np.array([e['timestamp_ms'] for e in ev]); ea=[e['action'] for e in ev]
 for i,e in enumerate(ev):
  if 'UP' in e['action']:
   end=et[i+1] if i+1<len(et) else ts[-1]+1
   state[(ts>=et[i])&(ts<end)]=0; ups.append(et[i])
  if 'DOWN' in e['action']:
   downs.append(et[i]);j=i+1
   while j<len(et) and ev[j]['trial']==e['trial'] and ev[j]['action']=='MOVE':j+=1
   if j<len(et) and ev[j]['trial']==e['trial'] and 'UP' in ea[j]:end=et[j]
   else:end=et[j-1] if j>i+1 else et[i]
   state[(ts>=et[i])&(ts<=end)]=1
 return state,np.unique(downs),np.unique(ups)

def episodes(ts,frame,speed,local,task,state,downs,ups,v=20,duration=400,exclude=300):
 # Requires observed release and a future DOWN within the same labelled task context.
 prev=np.searchsorted(ups,ts,side='right')-1; nxt=np.searchsorted(downs,ts,side='left')
 since=np.full(len(ts),np.inf);until=since.copy()
 ok=prev>=0;since[ok]=ts[ok]-ups[prev[ok]]
 ok=nxt<len(downs);until[ok]=downs[nxt[ok]]-ts[ok]
 cand=(state==0)&(task>=0)&(speed[:,0]<v)&(since>exclude)&(until>exclude)&np.isfinite(local[:,0]).all(1)
 # Unknown raw time gaps and task changes split episodes even when both endpoints qualify.
 breaks=np.ones(len(ts),bool);breaks[1:]=(np.diff(frame)!=1)|(np.diff(ts)>6)|(np.diff(task)!=0)
 starts=np.flatnonzero(cand & (breaks|~np.r_[False,cand[:-1]]))
 result=[]
 for s in starts:
  e=s+1
  while e<len(ts) and cand[e] and not breaks[e]:e+=1
  length=ts[e-1]-ts[s]+1000/240
  if length>=duration:
   pts=local[s:e,0]
   result.append(dict(task=TASKS[int(task[s])],start_ms=float(ts[s]),end_ms=float(ts[e-1]),duration_ms=float(length),
    start_frame=int(frame[s]),end_frame=int(frame[e-1]),median_x_mm=float(np.median(pts[:,0])),median_y_mm=float(np.median(pts[:,1])),median_z_mm=float(np.median(pts[:,2])),
    std_x_mm=float(np.std(pts[:,0])),std_y_mm=float(np.std(pts[:,1])),std_z_mm=float(np.std(pts[:,2])),mean_speed_mm_s=float(np.nanmean(speed[s:e,0])),
    velocity_threshold=v,min_duration_ms=duration,exclusion_ms=exclude))
 return result

def quant(x):
 x=np.asarray(x);x=x[np.isfinite(x)]
 if not len(x):return [np.nan]*5
 return np.percentile(x,[10,25,50,75,90]).tolist()

def feature_rows(pid,phone,cond,ts,frame,local,speed,context,core,state,R,eps):
 result=[];w,h,th=DEVICES[phone]['size'];sw,sh=DEVICES[phone]['screen'];ox,oy=DEVICES[phone]['offset']
 baseline_mask=(context>=0)&(state==1)&np.isfinite(local[:,0,2])
 global_base=float(np.median(local[baseline_mask,0,2])) if baseline_mask.sum()>=20 else np.nan
 for ti,task in enumerate(TASKS):
  for basis,labels_ in [('context_500ms',context),('confirmed_core',core)]:
   mask=labels_==ti
   if not mask.any():continue
   te=[e for e in eps if e['task']==task]
   tilt=np.degrees(np.arccos(np.clip(np.abs(R[:,1,1]),0,1)))
   for fi,finger in enumerate(FINGERS):
    ix=fi*4;pts=local[mask,ix]; good=np.isfinite(pts).all(1);p=pts[good]
    row=dict(participant=pid,phone=phone,condition=cond,task=task,basis=basis,finger=finger,
     frames=int(mask.sum()),valid_frames=int(good.sum()),valid_ratio=float(good.mean()),context_duration_s=float(mask.sum()/240),valid_duration_s=float(good.sum()/240))
    for k,axis in enumerate('xyz'):
     for name,val in zip(['p10','p25','p50','p75','p90'],quant(p[:,k] if len(p) else [])):row[axis+'_'+name+'_mm']=val
    sp=speed[mask,ix]
    row['speed_median_mm_s']=quant(sp)[2];row['speed_p90_mm_s']=quant(sp)[4]
    # Only links whose both frames have the same task/basis count toward task path length.
    links=mask[1:]&mask[:-1]&(np.diff(frame)==1)&(np.diff(ts)<6)
    distances=np.linalg.norm(np.diff(local[:,ix],axis=0),axis=1)
    usable=links&np.isfinite(distances)
    row['path_mm_per_s']=float(np.sum(distances[usable])/np.sum(np.diff(ts)[usable]/1000)) if usable.any() else np.nan
    row['screen_projection_ratio']=float(((p[:,0]>=ox)&(p[:,0]<=ox+sw)&(p[:,1]>=oy)&(p[:,1]<=oy+sh)).mean()) if len(p) else np.nan
    row['x_normalized']=row['x_p50_mm']/w;row['y_normalized']=row['y_p50_mm']/h
    row['tilt_median_deg']=quant(tilt[mask])[2]
    for j in [1,2]:
     a=local[:,ix+j-1]-local[:,ix+j];b=local[:,ix+j+1]-local[:,ix+j]
     denom=np.linalg.norm(a,axis=1)*np.linalg.norm(b,axis=1)
     angle=np.degrees(np.arccos(np.clip(np.sum(a*b,axis=1)/np.where(denom>0,denom,np.nan),-1,1)))
     row[f'marker_angle_{j}_median_deg']=quant(angle[mask])[2]
    if fi:
     d=np.linalg.norm(local[:,ix]-local[:,0],axis=1);row['distance_to_thumb_median_mm']=quant(d[mask])[2]
     g=mask&np.isfinite(speed[:,0])&np.isfinite(speed[:,ix])
     row['speed_correlation_with_thumb']=float(np.corrcoef(speed[g,0],speed[g,ix])[0,1]) if g.sum()>10 and np.std(speed[g,ix])>0 and np.std(speed[g,0])>0 else np.nan
    touch=mask&(state==1)&np.isfinite(local[:,0,2])
    row['thumb_touch_marker_baseline_mm']=global_base
    row['thumb_task_touch_marker_baseline_mm']=float(np.median(local[touch,0,2])) if touch.sum()>=20 else np.nan
    row['thumb_corrected_z_median_mm']=row['z_p50_mm']-global_base if fi==0 else np.nan
    row['idle_episodes']=len(te) if fi==0 and basis=='context_500ms' else np.nan
    row['idle_duration_median_ms']=quant([e['duration_ms'] for e in te])[2] if fi==0 else np.nan
    result.append(row)
 return result

def clip_payload(record,arrays,inds,meta,events,eps):
 # Float32 stride: time (relative), source frame, local 75, world 75, pivot 3,
 # quaternion 4, thumb speed, contact state. NaN means invalid, never zero-filled.
 ts=arrays['time_ms'][inds]; start=float(ts[0]);m=len(MARKERS)
 a=np.column_stack([ts-start,arrays['frame'][inds],arrays['local_mm'][inds].reshape(-1,m*3),
  arrays['world_mm'][inds].reshape(-1,m*3),arrays['pivot_mm'][inds],arrays['quaternion_xyzw'][inds],arrays['speed_mm_s'][inds,0],arrays['contact_state'][inds]])
 md=dict(meta,id=record,unit='mm',coordinate_system=COORD,markers=MARKERS,stride=a.shape[1],frames=len(a),start_epoch_ms=start,
  duration_ms=float(ts[-1]-start),source_frame_start=int(arrays['frame'][inds[0]]),source_frame_end=int(arrays['frame'][inds[-1]]),
  events=[dict(time_ms=e['timestamp_ms']-start,action=e['action'],task=e['task'],sync_eligible=e['sync_eligible']) for e in events if start<=e['timestamp_ms']<=ts[-1] and e['action']!='MOVE'],
  idle=[dict(start_ms=max(start,e['start_ms'])-start,end_ms=min(ts[-1],e['end_ms'])-start) for e in eps if e['end_ms']>=start and e['start_ms']<=ts[-1]])
 if 'height_calibration' not in md:
  mask=(arrays['task_context']>=0)&(arrays['contact_state']==1)&np.isfinite(arrays['local_mm'][:,0,2])
  md['height_calibration']=dict(baseline_mm=float(np.median(arrays['local_mm'][mask,0,2])) if mask.sum()>=20 else None,method='record_contact_median',marker='Thumb_Fn',scope='participant_phone_condition',valid_contact_samples=int(mask.sum()),interpretation='signed marker height minus known-contact median; not measured finger-pad clearance',physical_sync_verified=False)
 return md,a.astype('<f4')

def canonical_record(name):
 return Path(name).stem.removesuffix('_sitting')+'_seated' if Path(name).stem.endswith('_sitting') else Path(name).stem

def process(name,stream):
 record=canonical_record(name);pid,phone,cond=record.split('_');pid=int(pid[1:])
 frame,ts,q,p,world,header=read_motion(stream)
 from phone_pose import repair
 q,p,pose_audit=repair(record,q,p,ts)
 if pose_audit:save_json(B/'outputs/phone-pose-repair.json',pose_audit)
 local,rb,R=transform(q,p,world)
 # Physical guard against swaps/outliers; flag samples, preserve unfiltered world arrays.
 valid=np.isfinite(local).all(2)&rb[:,None]
 valid &= np.linalg.norm(local,axis=2)<500
 spikes=np.linalg.norm(np.diff(local,axis=0),axis=2)>4
 contiguous=np.diff(frame)==1
 bad=np.zeros(valid.shape,bool);bad[1:] |= spikes&contiguous[:,None];bad[:-1] |= spikes&contiguous[:,None]
 valid &= ~bad;local[~valid]=np.nan
 speed=speed_of(ts,local,frame)
 trials,intervals,events,notes=logs(pid,phone,cond)
 core,context,sync_eligible=labels(ts,intervals)
 state,downs,ups=contacts(ts,events,trials);state[~sync_eligible]=-1
 eps=episodes(ts,frame,speed,local,context,state,downs,ups)
 rows=feature_rows(pid,phone,cond,ts,frame,local,speed,context,core,state,R,eps)
 arrays=dict(frame=frame,time_ms=ts,local_mm=local.astype('f4'),world_mm=world.astype('f4'),pivot_mm=p.astype('f4'),quaternion_xyzw=q.astype('f4'),
   marker_valid=valid,rigid_valid=rb,speed_mm_s=speed.astype('f4'),task_core=core,task_context=context,contact_state=state,sync_eligible=sync_eligible)
 save_npz(B/'data/records'/f'{record}.npz',**arrays)
 density={}
 for ti,task in enumerate(TASKS):
  pts=local[(context==ti)&valid[:,0],0]
  w,h,_=DEVICES[phone]['size']
  xy,xe,ye=np.histogram2d(pts[:,0]/w,pts[:,1]/h,bins=[np.linspace(-.5,1.5,61),np.linspace(-.25,1.75,81)])
  zh,ze=np.histogram(pts[:,2],bins=np.arange(-100,205,5))
  density[task+'_xy']=xy.astype('i4');density[task+'_z']=zh.astype('i4')
 density.update(x_edges=xe,y_edges=ye,z_edges=ze)
 save_npz(B/'data/records'/f'{record}_density.npz',**density)
 # Validate transform on random complete raw samples before filtering.
 rng=np.random.default_rng(pid);ii=rng.choice(np.flatnonzero(rb),min(20,rb.sum()),replace=False)
 raw_local=np.einsum('nji,nmj->nmi',R[ii],world[ii]-p[ii,None,:])
 back=np.einsum('nij,nmj->nmi',R[ii],raw_local)+p[ii,None,:]
 roundtrip=float(np.nanmax(np.abs(back-world[ii])))
 distance_error=float(np.nanmax(np.abs(np.linalg.norm(raw_local[:,0]-raw_local[:,4],axis=1)-np.linalg.norm(world[ii,0]-world[ii,4],axis=1))))
 sync=dict(record=record,frames=len(frame),rigid_valid_ratio=float(rb.mean()),time_monotonic=bool(np.all(np.diff(ts)>0)),
   capture_start_original=header[9],motive_12am_workaround=bool(datetime.strptime(header[9],'%Y-%m-%d %I.%M.%S.%f %p').hour==0),
   transform_roundtrip_max_mm=roundtrip,distance_error_max_mm=distance_error,epoch_start_ms=float(ts[0]),epoch_end_ms=float(ts[-1]),
   labelled_context_frames=int((context>=0).sum()),down_events=len(downs),up_events=len(ups),
   missing_release_trials=sum(not any('UP' in e['action'] for e in events if e['trial']==r['trial']) for r in trials),
   sync_note='Clock mapping/overlap are computational checks; independent physical synchronization is not established.')
 if roundtrip>1e-6 or distance_error>1e-6 or not sync['time_monotonic']:raise ValueError('Transform or timestamp validation failed')
 save_json(B/'data/records'/f'{record}.json',dict(record=record,participant=pid,phone=phone,condition=cond,source=name,phone_pose_repair=pose_audit,header=header,intervals=intervals,trials=trials,events=[{k:(None if isinstance(v,float) and not np.isfinite(v) else v) for k,v in e.items()} for e in events],idle=eps,notes=notes,checks=sync))
 coverage=[];clips=[];sens=[];eventrows=[]
 for ti,task in enumerate(TASKS):
  mask=context==ti; good=mask&valid[:,0]
  ttr=[r for r in trials if r['task']==task]
  coverage.append(dict(participant=pid,phone=phone,condition=cond,task=task,record=record,raw_frames=len(frame),trials=len(ttr),
   core_frames=int((core==ti).sum()),context_frames=int(mask.sum()),thumb_valid_frames=int(good.sum()),valid_duration_s=float(good.sum()/240),
   unknown_contact_frames=int((mask&(state<0)).sum()),sync_eligible_frames=int((mask&sync_eligible).sum()),
   status='AVAILABLE' if good.any() else 'NO_VALID_SAMPLES'))
  # representative full-hand frame: closest real frame to robust centre, not averaged pose.
  complete=mask&valid[:,:20].all(1);candidates=np.flatnonzero(complete)
  if not len(candidates):candidates=np.flatnonzero(good)
  if not len(candidates):continue
  idxs=[0,4,8,12,16];features=local[candidates][:,idxs].reshape(-1,15)
  centre=np.nanmedian(features,axis=0);scale=np.nanpercentile(features,75,axis=0)-np.nanpercentile(features,25,axis=0);scale=np.maximum(scale,5)
  score=np.nanmean(((features-centre)/scale)**2,axis=1);representative=int(candidates[np.nanargmin(score)])
  interval=next(r for r in intervals if r['task']==task and r['context_start_ms']<=ts[representative]<=r['context_end_ms'])
  start=max(interval['context_start_ms'],ts[representative]-4000);end=min(interval['context_end_ms'],start+8000)
  start=max(interval['context_start_ms'],end-8000)
  inds=np.flatnonzero((ts>=start)&(ts<=end))
  cid=record+'_'+task
  meta=dict(participant=pid,phone=phone,condition=cond,task=task,device=DEVICES[phone],source=name,
   phone_pose_repair=pose_audit,representative_epoch_ms=float(ts[representative]),representative_frame=int(frame[representative]),full_hand_representative=bool(complete[representative]),
   sync_status='CLOCK_MATCHED_PHYSICAL_SYNC_UNVERIFIED',interval=interval,
   home_zone=dict(median=np.nanmedian(local[good,0],axis=0).tolist(),p10=np.nanpercentile(local[good,0],10,axis=0).tolist(),p90=np.nanpercentile(local[good,0],90,axis=0).tolist(),meaning='task activity P10-P90 box, not idle density volume'))
  te=[e for e in eps if e['task']==task]
  if te:
   pos=np.array([[e['median_x_mm'],e['median_y_mm'],e['median_z_mm']] for e in te])
   meta['idle_home_zone']=dict(median=np.median(pos,axis=0).tolist(),p10=np.percentile(pos,10,axis=0).tolist(),p90=np.percentile(pos,90,axis=0).tolist(),episodes=len(te),meaning='episode-centre P10-P90 box; not KDE highest-density volume')
  md,a=clip_payload(cid,arrays,inds,meta,events,eps)
  md['binary']=cid+'.bin';dest=B/'outputs/clips'/md['binary'];tmp=dest.with_suffix('.bin.tmp');a.tofile(tmp);tmp.replace(dest);save_json(B/'outputs/clips'/f'{cid}.json',md)
  clips.append(dict(id=cid,participant=pid,phone=phone,condition=cond,task=task,meta='clips/'+cid+'.json',duration_ms=md['duration_ms'],representative_frame=meta['representative_frame']))
  for e in events:
   if e['task']!=task or 'DOWN' not in e['action'] or not e['sync_eligible']:continue
   target=e['timestamp_ms'];k=np.searchsorted(ts,target);k=min(k,len(ts)-1)
   if k and abs(ts[k-1]-target)<abs(ts[k]-target):k-=1
   if abs(ts[k]-target)>3 or not valid[k,0] or context[k]!=ti:continue
   for horizon in [-500,-300,-100,0,100,300,500]:
    j=np.searchsorted(ts,target+horizon);j=min(j,len(ts)-1)
    if j and abs(ts[j-1]-target-horizon)<abs(ts[j]-target-horizon):j-=1
    # Same task, no missing marker frames or tracking gaps between event and sample.
    lo,hi=sorted([j,k]);cont=valid[lo:hi+1,0].all() and np.all(np.diff(frame[lo:hi+1])==1)
    if abs(ts[j]-target-horizon)>3 or context[j]!=ti or not cont:continue
    eventrows.append(dict(participant=pid,phone=phone,condition=cond,task=task,event_ms=target,event_frame=int(frame[k]),offset_ms=horizon,
      x_mm=float(local[j,0,0]),y_mm=float(local[j,0,1]),z_mm=float(local[j,0,2]),speed_mm_s=float(speed[j,0]),
      relative_to_down_z_mm=float(local[j,0,2]-local[k,0,2]),sync_status='CLOCK_MATCHED_PHYSICAL_SYNC_UNVERIFIED'))
 for v in [10,20,30]:
  for dur in [200,400,500]:
   for ex in [200,300,500]:
    ee=eps if (v,dur,ex)==(20,400,300) else episodes(ts,frame,speed,local,context,state,downs,ups,v,dur,ex)
    for task in TASKS:
     a=[r for r in ee if r['task']==task]
     sens.append(dict(participant=pid,phone=phone,condition=cond,task=task,velocity_threshold=v,min_duration_ms=dur,exclusion_ms=ex,episodes=len(a),
       median_z_mm=quant([r['median_z_mm'] for r in a])[2],median_duration_ms=quant([r['duration_ms'] for r in a])[2]))
 for e in eps:e.update(participant=pid,phone=phone,condition=cond,record=record)
 out=dict(summary=rows,coverage=coverage,clips=clips,episodes=eps,sensitivity=sens,event_trajectory=eventrows,checks=[sync])
 save_json(B/'data/records'/f'{record}_result.json',json.loads(json.dumps(out,default=lambda o:float(o)),parse_constant=lambda _:None))
 print(record,'frames',len(frame),'labelled',int((context>=0).sum()),'idle',len(eps),'clips',len(clips),flush=True)
 return out

def merge():
 keys=['summary','coverage','clips','episodes','sensitivity','event_trajectory','checks']; all_={k:[] for k in keys}
 for p in sorted((B/'data/records').glob('*_result.json')):
  r=json.loads(p.read_text())
  for k in keys:all_[k]+=r[k]
 for k in keys:
  if k!='clips':pd.DataFrame(all_[k]).to_csv(B/'data'/f'{k}.csv',index=False)
 save_json(B/'outputs/index.json',dict(version=1,upstream_commit='625383fa38ddda5f09d888ed066cb4161667baa9',tasks=[dict(id=t,name=n) for t,n in zip(TASKS,NAMES)],devices=DEVICES,markers=MARKERS,
  clips=all_['clips'],coordinate_system=COORD,scope='right-handed one-hand; no intentional Hover labels'))
 print('Merged',len(all_['checks']),'records',len(all_['clips']),'clips',flush=True)

def verify_archives():
 result=[]
 for name in ['phone_dataset.zip','mocap_dataset.zip']:
  p=B/'sources'/name;digest=hashlib.sha256()
  with p.open('rb') as f:
   while True:
    chunk=f.read(8*1024*1024)
    if not chunk:break
    digest.update(chunk)
  with zipfile.ZipFile(p) as z:
   bad=z.testzip();assert bad is None,bad
   result.append(dict(file=name,bytes=p.stat().st_size,sha256=digest.hexdigest(),entries=len(z.infolist()),uncompressed_bytes=sum(i.file_size for i in z.infolist()),crc='PASS'))
 save_json(B/'qa/archive_checks.json',result);print(result,flush=True)

def process_zip_member(name):
 import io
 with zipfile.ZipFile(B/'sources/mocap_dataset.zip') as z:
  with z.open(name) as s:process(name,io.TextIOWrapper(s))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--pilot',action='store_true');ap.add_argument('--verify',action='store_true');ap.add_argument('--merge',action='store_true');ap.add_argument('--record');ap.add_argument('--force',action='store_true');ap.add_argument('--workers',type=int,default=2);args=ap.parse_args()
 for d in ['data/records','outputs/clips']: (B/d).mkdir(parents=True,exist_ok=True)
 if args.verify:verify_archives();return
 if args.merge:merge();return
 if args.pilot:
  paths=sorted((B/'.tmp').glob('P3_*.csv'))
  for p in paths:
   if not args.force and (B/'data/records'/f'{p.stem}_result.json').exists():continue
   with p.open() as f:process(p.name,f)
 else:
  with zipfile.ZipFile(B/'sources/mocap_dataset.zip') as z:
   files=[n for n in z.namelist() if re.fullmatch(r'P\d+_(S3|S4|OPO|N6)_(seated|sitting|walking)\.csv',n)]
  if len(files)!=128:raise ValueError(f'Expected 128 source records, found {len(files)}')
  files=[n for n in files if (not args.record or canonical_record(n)==args.record) and (args.force or not (B/'data/records'/f'{canonical_record(n)}_result.json').exists())]
  from concurrent.futures import ProcessPoolExecutor
  with ProcessPoolExecutor(max_workers=max(1,args.workers)) as pool:
   for _ in pool.map(process_zip_member,files):pass
 merge()

if __name__=='__main__':main()
