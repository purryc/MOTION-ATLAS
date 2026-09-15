"""Build display volumes from actual stable thumb samples; preserve analysis summaries."""
import json
import re
import numpy as np
from analyze import B, TASKS, COORD, save_json

def quantiles(points, **extra):
 return dict(median=np.median(points,axis=0).tolist(),p10=np.percentile(points,10,axis=0).tolist(),p90=np.percentile(points,90,axis=0).tolist(),valid_frames=len(points),**extra)

def main():
 index=json.loads((B/'outputs/index.json').read_text());records={};count=0
 for path in sorted((B/'data/records').glob('*.npz')):
  if not re.fullmatch(r'P\d+_(S3|S4|OPO|N6)_(seated|walking)',path.stem):continue
  md=json.loads(path.with_suffix('.json').read_text());record=md['record'];task_zones={}
  with np.load(path) as z:
   thumb=z['local_mm'][:,0,:];ts=z['time_ms'];context=z['task_context'];valid=np.isfinite(thumb).all(axis=1)
  for ti,task in enumerate(TASKS):
   good=valid&(context==ti)
   if not good.any():continue
   activity=quantiles(thumb[good],meaning='actual task-context thumb samples; marginal XYZ P10-P90 box, not an 80-percent joint density region')
   eps=[e for e in md['idle'] if e['task']==task];idle_mask=np.zeros(len(ts),dtype=bool)
   for e in eps:idle_mask|=(ts>=e['start_ms'])&(ts<=e['end_ms'])
   stable=good&idle_mask
   home=quantiles(thumb[stable],episodes=len(eps),meaning='actual stable thumb samples; marginal XYZ P10-P90 box, not episode-centre quantiles or joint density region') if stable.any() else None
   task_zones[task]=dict(home_zone=activity,idle_sample_home_zone=home,source=f'data/records/{record}.npz',task=task)
   count+=int(home is not None)
  records[record]=task_zones
  if len(records)%16==0:print('Task volumes',len(records),flush=True)
 save_json(B/'outputs/zones.json',dict(version=1,unit='mm',coordinate_system=COORD,marker='Thumb_Fn',basis='context_500ms',idle_rule=dict(exclusion_ms=300,velocity_mm_s=20,minimum_duration_ms=400),records=records))
 for c in index['clips']:
  path=B/'outputs'/c['meta'];md=json.loads(path.read_text());record=f'P{c["participant"]}_{c["phone"]}_{c["condition"]}';zone=records[record][c['task']]
  # Keep original home_zone and idle_home_zone unchanged for historical reports.
  md['idle_sample_home_zone']=zone['idle_sample_home_zone'];md['zone_source']=zone['source'];save_json(path,md)
 print('Done',len(records),'records;',count,'task cells with stable Home Zone',flush=True)

if __name__=='__main__':main()
