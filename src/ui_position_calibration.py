"""Observed nail-to-touch XY reference offsets, never changes measured markers."""
import json,re,zipfile
from pathlib import Path
import numpy as np
from analyze import B,DEVICES,save_json
from scipy.stats import theilslopes
PIXELS={'S3':[480,800],'S4':[1080,1920],'OPO':[1080,1920],'N6':[1440,2560]}
def mapping_fit(pairs):
 a=np.array([[*p['pixel_xy'],*p['marker_xy_mm']] for p in pairs]);result=[]
 for axis in range(2):
  slope,intercept,_,_=theilslopes(a[:,axis+2],a[:,axis]);result.extend([float(slope),float(intercept)])
 return result

def error(pairs,fit):
 a=np.array([[*p['pixel_xy'],*p['marker_xy_mm']] for p in pairs]);pred=np.column_stack([fit[0]*a[:,0]+fit[1],fit[2]*a[:,1]+fit[3]])
 return np.linalg.norm(pred-a[:,2:],axis=1)

def main():
 records={}
 for path in sorted((B/'data/records').glob('*.npz')):
  if not re.fullmatch(r'P\d+_(S3|S4|OPO|N6)_(seated|walking)',path.stem):continue
  md=json.loads(path.with_suffix('.json').read_text());events=[e for e in md['events'] if e['task']=='TAP' and e['sync_eligible'] and 'DOWN' in e['action'] and e['x_px'] is not None and e['y_px'] is not None]
  pairs=[];d=DEVICES[md['phone']];[sw,sh]=d['screen'];[ox,oy]=d['offset'];[pw,ph]=PIXELS[md['phone']]
  with np.load(path) as z:ts=z['time_ms'];local=z['local_mm'][:,0];state=z['contact_state'];frame=z['frame']
  for e in events:
   t=e['timestamp_ms'];k=np.searchsorted(ts,t)
   if k>=len(ts):continue
   if abs(ts[k]-t)>1000/240 or not np.isfinite(local[k]).all() or state[k]!=1:continue
   touch=np.array([ox+sw*(1-e['x_px']/pw),oy+sh*e['y_px']/ph]);delta=local[k,:2]-touch
   pairs.append(dict(timestamp_ms=t,source_frame=int(frame[k]),trial=e['trial'],pixel_xy=[e['x_px'],e['y_px']],marker_xy_mm=local[k,:2].tolist(),touch_xy_mm=touch.tolist(),delta_xy_mm=delta.tolist()))
  eligible=len(pairs)>=8
  train=pairs[::2];test=pairs[1::2];fit=None;holdfit=None;before=[];after=[]
  if eligible:
   a=np.array([p['pixel_xy'] for p in train]);diverse=np.ptp(a[:,0])>=pw*.3 and np.ptp(a[:,1])>=ph*.3
   if diverse:
    holdfit=mapping_fit(train);after=error(test,holdfit);before=np.array([np.linalg.norm(p['delta_xy_mm']) for p in test]);fit=mapping_fit(pairs)
  use=fit is not None and len(after)>=4 and np.median(after)<np.median(before) and np.median(after)<8 and .5*sw/pw<abs(fit[0])<1.5*sw/pw and .5*sh/ph<abs(fit[2])<1.5*sh/ph
  records[path.stem]=dict(method='record TAP DOWN Theil-Sen diagonal affine pixel-to-recorded-nail XY; odd/even holdout',eligible=bool(use),pixel_to_marker_xy=fit if use else None,valid_pairs=len(pairs),holdout_n=len(after),holdout_raw_median_mm=float(np.median(before)) if len(before) else None,holdout_corrected_median_mm=float(np.median(after)) if len(after) else None,pairs=pairs,interpretation='UI nail-reference alignment estimate, not measured finger-pad position or verified physical screen registration; recorded markers and raw UI coordinates unchanged')
  print('XY',path.stem,len(pairs),'usable',use,flush=True)
 phone_defaults={}
 for phone in PIXELS:
  pool=[p for name,r in records.items() if name.split('_')[1]==phone for p in r['pairs']]
  train=[p for name,r in records.items() if name.split('_')[1]==phone and int(name.split('_')[0][1:])%2==0 for p in r['pairs']]
  test=[p for name,r in records.items() if name.split('_')[1]==phone and int(name.split('_')[0][1:])%2==1 for p in r['pairs']]
  fit=mapping_fit(pool);held=mapping_fit(train);after=error(test,held);before=np.array([np.linalg.norm(p['delta_xy_mm']) for p in test]);use=np.median(after)<8 and np.median(after)<np.median(before)
  phone_defaults[phone]=dict(eligible=bool(use),pixel_to_marker_xy=fit,calibration_pairs=len(pool),holdout_n=len(test),holdout_raw_median_mm=float(np.median(before)),holdout_corrected_median_mm=float(np.median(after)),scope='phone pooled estimate; heldout participants by odd/even ID; recording-specific accuracy unknown')
 for name,r in records.items():
  r['scope']='record' if r['eligible'] else 'unavailable'
  if not r['eligible'] and phone_defaults[name.split('_')[1]]['eligible']:
   d=phone_defaults[name.split('_')[1]];r.update({k:d[k] for k in ['eligible','pixel_to_marker_xy','calibration_pairs','holdout_n','holdout_raw_median_mm','holdout_corrected_median_mm']});r['scope']='phone';r['method']='phone-level pooled Theil-Sen mapping fallback; independent participant holdout; per-record accuracy unverified'
 save_json(B/'outputs/ui-position-calibration.json',dict(version=1,unit='mm',records=records,phone_defaults=phone_defaults,scope='participant_phone_condition; TAP DOWN only; never assumes tile anchor is target centre',screen_mapping='nominal full-display pixels; UI insets and target size unavailable'))
 with zipfile.ZipFile(B/'sources/mocap_dataset.zip') as z:
  motion={int(re.search(r'^P(\d+)_',n)[1]) for n in z.namelist() if re.match(r'^P\d+_.*\.csv$',n)}
 phone={int(p.name[1:]) for p in (B/'sources/phone_dataset').glob('P*') if p.is_dir() and p.name[1:].isdigit()}
 save_json(B/'outputs/participants.json',dict(motion_participants=sorted(motion),phone_log_participants=sorted(phone),log_only=sorted(phone-motion),reason='Published archive coverage only; no documented reason for absent captures; P1 phone files use StudyRun101',participants=[dict(id=p,motion=p in motion,phone_logs=p in phone) for p in sorted(phone|motion)]))
 summary=dict(records=len(records),calibrated=sum(r['eligible'] for r in records.values()),record_level=sum(r['scope']=='record' for r in records.values()),phone_level=sum(r['scope']=='phone' for r in records.values()),pairs=sum(r['valid_pairs'] for r in records.values()))
 save_json(B/'qa/ui-position-calibration.json',dict(summary=summary,records={k:{f:v for f,v in r.items() if f!='pairs'} for k,r in records.items()}));print(summary)
if __name__=='__main__':main()
