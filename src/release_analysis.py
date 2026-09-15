"""Observed POINTER_UP trajectories; no invented releases or return-to-home labels."""
import json
import numpy as np
import pandas as pd
from analyze import B,TASKS

def nearest(ts,target):
 k=min(int(np.searchsorted(ts,target)),len(ts)-1)
 return k-1 if k and abs(ts[k-1]-target)<abs(ts[k]-target) else k

def main():
 rows=[]
 for p in sorted((B/'data/records').glob('*_result.json')):
  name=p.name.removesuffix('_result.json');md=json.loads((p.parent/(name+'.json')).read_text())
  with np.load(p.parent/(name+'.npz')) as z:
   ts=z['time_ms'];frame=z['frame'];local=z['local_mm'];valid=z['marker_valid'];speed=z['speed_mm_s'];task=z['task_context'];contact=z['contact_state']
   for e in md['events']:
    if 'UP' not in e['action'] or not e['sync_eligible']:continue
    target=e['timestamp_ms'];k=nearest(ts,target);ti=TASKS.index(e['task'])
    if abs(ts[k]-target)>3 or not valid[k,0] or task[k]!=ti:continue
    for offset in [-300,-100,0,100,300,500,1000]:
     j=nearest(ts,target+offset);lo,hi=sorted([j,k])
     if abs(ts[j]-target-offset)>3 or not valid[lo:hi+1,0].all() or not (task[lo:hi+1]==ti).all() or not (np.diff(frame[lo:hi+1])==1).all():continue
     support=[]
     for m in [4,8,12,16]:
      if valid[lo:hi+1,m].all():support.append(float(np.linalg.norm(local[j,m]-local[k,m])))
     delta=local[j,0]-local[k,0]
     rows.append(dict(record=name,participant=md['participant'],phone=md['phone'],condition=md['condition'],task=e['task'],event_ms=target,event_frame=int(frame[k]),sample_frame=int(frame[j]),offset_ms=offset,
      x_mm=float(local[j,0,0]),y_mm=float(local[j,0,1]),z_mm=float(local[j,0,2]),relative_to_up_z_mm=float(delta[2]),displacement_from_up_mm=float(np.linalg.norm(delta)),speed_mm_s=float(speed[j,0]),contact_state=int(contact[j]),support_displacement_mean_mm=float(np.mean(support)) if support else np.nan,valid_support_fingers=len(support),sync_status='CLOCK_MATCHED_PHYSICAL_SYNC_UNVERIFIED'))
 pd.DataFrame(rows).to_csv(B/'data/release_trajectory.csv',index=False)
 print('Observed release samples',len(rows),flush=True)

if __name__=='__main__':main()
