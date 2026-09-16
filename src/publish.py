"""Allowlisted, lossless static MOTION ATLAS build, without local Python APIs."""
import gzip,hashlib,json,shutil,re,time
from pathlib import Path
import numpy as np
from analyze import B,clip_payload,DEVICES,TASKS

SITE=B/'.tmp/public-site'
TABLES=['coverage.csv','participant_summary.csv','participant_bootstrap.csv','paired_comparisons.csv','explorer_dwell_cells.csv','explorer_dwell_episodes.csv','explorer_height_cells.csv','whole_hand_task_summary.csv']
def write(p,o):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,ensure_ascii=False,allow_nan=False,separators=(',',':')))
def binary(p,data):
 p.parent.mkdir(parents=True,exist_ok=True)
 arr=np.frombuffer(data,dtype='<u4').reshape(-1,161)
 delta=arr.copy();delta[1:]=np.bitwise_xor(arr[1:],arr[:-1])
 shuffled=delta.view('u1').reshape(-1,4).T.copy().tobytes()
 # Verify bit-for-bit reversibility, including NaNs and source-frame IDs.
 decoded=np.frombuffer(shuffled,dtype='u1').reshape(4,-1).T.copy().view('<u4').reshape(-1,161)
 decoded=np.bitwise_xor.accumulate(decoded,axis=0)
 assert np.array_equal(decoded,arr)
 with p.open('wb') as f:
  with gzip.GzipFile(fileobj=f,mode='wb',mtime=0,compresslevel=6) as g:g.write(shuffled)
def processed_tables(out):
 from zipfile import ZipFile,ZIP_DEFLATED
 with ZipFile(out/'processed-tables.zip','w',ZIP_DEFLATED) as z:
  for name in TABLES:z.write(B/'data'/name,'data/'+name)
  for name in ['natural-dwell-height.json','calibration.json','phone-pose-repair.json']:
   if (B/'outputs'/name).exists():z.write(B/'outputs'/name,'outputs/'+name)

def thresholds_only():
 """Extend dwell choices without re-encoding unchanged source-frame clips."""
 out=SITE/'outputs';assert (out/'explorer/index.json').exists(),'Build the base static site first'
 source=B/'outputs/explorer';paths=sorted(source.glob('P*.json'));expected=json.loads((out/'explorer/index.json').read_text())['records']
 assert set(expected)=={p.stem for p in paths}
 checks=[]
 for path in paths:
  rec=json.loads(path.read_text());old=json.loads((out/'explorer'/path.name).read_text())
  assert rec['source']==old['source'] and set(rec['tasks'])==set(old['tasks']),path.name
  for task,td in rec['tasks'].items():
   old_eps=old['tasks'][task]['thresholds']['100']['episodes'];new_eps=td['thresholds']['100']['episodes']
   key=lambda e:(e['start_frame'],e['end_frame'])
   clips={key(e):e['public_clip'] for e in old_eps}
   assert len(clips)==len(old_eps) and set(clips)=={key(e) for e in new_eps},(path.name,task,'100ms episodes drifted')
   for threshold,choice in td['thresholds'].items():
    eps=choice['episodes'];s=choice['summary']
    assert s['episodes']==len(eps) and abs(s['total_ms']-sum(e['duration_ms'] for e in eps))<1e-5
    assert bool(choice['home'])==bool(eps)
    for e in eps:
     assert e['duration_ms']+1e-5>=int(threshold) and key(e) in clips
     e['public_clip']=clips[key(e)]
    checks.append((path.stem,task,int(threshold),len(eps)))
   for cid in clips.values():
    assert (out/'dwell'/(cid+'.json')).exists() and (out/'dwell'/(cid+'.bin.gz')).exists(),cid
  write(out/'explorer'/path.name,rec)
 for name in ['index.json','report-controls.json','report.json']:
  write(out/'explorer'/name,json.loads((source/name).read_text()))
 for name in ['report.html','natural-dwell-height.json']:
  shutil.copy(B/'outputs'/name,out/name)
 processed_tables(out)
 publication=out/'publication.json';manifest=json.loads(publication.read_text());manifest['dwell_thresholds_ms']=list(range(100,1001,100));write(publication,manifest)
 extras=['outputs/explorer/'+p.name for p in paths]+['outputs/explorer/'+n for n in ['index.json','report-controls.json','report.json']]+['outputs/processed-tables.zip','outputs/publication.json']
 write(B/'outputs/incremental-data-files.json',extras)
 print(json.dumps(dict(records=len(paths),task_threshold_cells=len(checks),thresholds_ms=manifest['dwell_thresholds_ms'],site_bytes=sum(p.stat().st_size for p in SITE.rglob('*') if p.is_file()))),flush=True)

def main(record=None):
 SITE.mkdir(parents=True,exist_ok=True);out=SITE/'outputs';out.mkdir(exist_ok=True)
 shutil.copytree(B/'src/viewer',SITE/'viewer',dirs_exist_ok=True);shutil.copy(B/'src/viewer/index.html',SITE/'index.html')
 shutil.copytree(B/'src/node_modules/three/build',SITE/'vendor/build',dirs_exist_ok=True)
 shutil.copy(B/'src/node_modules/three/LICENSE',SITE/'vendor/LICENSE')
 # OrbitControls imports only math utilities from the Three package.
 shutil.copytree(B/'src/node_modules/three/examples/jsm/controls',SITE/'vendor/examples/jsm/controls',dirs_exist_ok=True)
 shutil.copytree(B/'src/node_modules/three/examples/jsm/math',SITE/'vendor/examples/jsm/math',dirs_exist_ok=True)
 shutil.copytree(B/'outputs/figures',out/'figures',dirs_exist_ok=True)
 for name in ['report.html','findings.md','zones.json','calibration.json','ui-position-calibration.json','participants.json','natural-dwell-height.json','phone-pose-repair.json']:
  if (B/'outputs'/name).exists():shutil.copy(B/'outputs'/name,out/name)
 index=json.loads((B/'outputs/index.json').read_text());index['publication']={'name':'MOTION ATLAS','mode':'static','dwell_context_ms':300,'all_dwell_available':True,'arbitrary_full_task_segments':'local Python server only','sample_rate_hz':240,'lossless_gzip':True}
 for c in index['clips']:
  if record and not c['id'].startswith(record+'_'):continue
  p=B/'outputs'/c['meta'];md=json.loads(p.read_text());raw=p.parent/md['binary'];dest=out/c['meta'];dest.parent.mkdir(parents=True,exist_ok=True)
  binpath=dest.with_suffix('.bin.gz');binary(binpath,raw.read_bytes());md['binary']=binpath.name;md['binary_encoding']='xor-shuffle-f32-le';write(dest,md)
 write(out/'index.json',index)
 zones=json.loads((B/'outputs/zones.json').read_text())['records'];cal=json.loads((B/'outputs/calibration.json').read_text())['records'];count=0;checks=[]
 paths=sorted((B/'outputs/explorer').glob((record if record else 'P*')+'.json'));starttime=time.time()
 for n,path in enumerate(paths):
  rec=json.loads(path.read_text());name=rec['record'];md=json.loads((B/'data/records'/(name+'.json')).read_text())
  episodes=[e for td in rec['tasks'].values() for e in td['thresholds']['100']['episodes']]
  if episodes:
   with np.load(B/'data/records'/(name+'.npz')) as z:a={k:z[k] for k in ['time_ms','frame','local_mm','world_mm','pivot_mm','quaternion_xyzw','speed_mm_s','contact_state','task_context']}
   ts=a['time_ms']
   for e in episodes:
    task=e['task'];cid=hashlib.sha256(f"{name}:{task}:{e['start_frame']}:{e['end_frame']}".encode()).hexdigest()[:24]
    matches=[i for i in md['intervals'] if i['task']==task and i['context_start_ms']<=e['start_ms'] and i['context_end_ms']>=e['end_ms']]
    if not matches:raise ValueError((name,e,'No task context'))
    interval=matches[0];start=max(interval['context_start_ms'],float(ts[0]),e['start_ms']-300);end=min(interval['context_end_ms'],float(ts[-1]),e['end_ms']+300)
    inds=np.arange(np.searchsorted(ts,start),np.searchsorted(ts,end,side='right'))
    meta=dict(participant=md['participant'],phone=md['phone'],condition=md['condition'],task=task,device=DEVICES[md['phone']],source=md['source'],interval=interval,representative_epoch_ms=e['start_ms'],representative_frame=e['start_frame'],sync_status='CLOCK_MATCHED_PHYSICAL_SYNC_UNVERIFIED',height_calibration=cal[name],phone_pose_repair=md.get('phone_pose_repair'),**{k:v for k,v in zones.get(name,{}).get(task,{}).items() if k in ['home_zone','idle_sample_home_zone']})
    meta,arr=clip_payload(cid,a,inds,meta,md['events'],md['idle']);meta['binary']=cid+'.bin.gz';meta['binary_encoding']='xor-shuffle-f32-le';write(out/'dwell'/(cid+'.json'),meta);binary(out/'dwell'/(cid+'.bin.gz'),arr.tobytes())
    assert np.any(arr[:,1]==e['start_frame']) and np.any(arr[:,1]==e['end_frame'])
    # Every threshold references the same full maximal episode, without truncation.
    for choice in rec['tasks'][task]['thresholds'].values():
     for ep in choice['episodes']:
      if ep['start_frame']==e['start_frame'] and ep['end_frame']==e['end_frame']:ep['public_clip']=cid
    count+=1
   del a
  for task,td in rec['tasks'].items():
   for threshold,choice in td['thresholds'].items():
    eps=choice['episodes'];s=choice['summary'];assert bool(choice['home'])==bool(eps)
    assert s['episodes']==len(eps) and abs(s['total_ms']-sum(e['duration_ms'] for e in eps))<1e-6
    assert all(e['duration_ms']+1e-5>=int(threshold) and 'public_clip' in e for e in eps)
    checks.append(dict(record=name,task=task,threshold=int(threshold),episodes=len(eps),total_ms=s['total_ms'],home_present=bool(choice['home'])))
  write(out/'explorer'/path.name,rec)
  print('Static records',n+1,'/',len(paths),'episodes',count,'elapsed',round(time.time()-starttime),flush=True)
 for name in ['index.json','report-controls.json','report.json']:
  write(out/'explorer'/name,json.loads((B/'outputs/explorer'/name).read_text()))
 processed_tables(out)
 (SITE/'.nojekyll').touch()
 sizes=sum(p.stat().st_size for p in SITE.rglob('*') if p.is_file());assert sizes<1_000_000_000,f'Pages site too large: {sizes}'
 if record:
  count=sum(len(td['thresholds']['100']['episodes']) for path in (out/'explorer').glob('P*.json') for td in json.loads(path.read_text())['tasks'].values())
 manifest=dict(name='MOTION ATLAS',upstream_commit=index['upstream_commit'],representatives=len(index['clips']),maximal_dwell_episodes=count,task_threshold_cells=len(checks),site_bytes=sizes,coordinate_unit='mm',sample_rate_hz=240,frames='lossless float32 source samples; no resampling',publication='green Home Zone frames in playback; 3D heat maps in report only')
 write(out/'publication.json',manifest);write(B/'qa/motion-atlas-build.json',dict(manifest=manifest,checks=checks,validated_scope=record or 'all records',errors=[]))
 if record:
  extras=['outputs/'+n for n in ['index.json','zones.json','calibration.json','findings.md','phone-pose-repair.json','processed-tables.zip','publication.json','explorer/'+record+'.json','explorer/index.json','explorer/report-controls.json','explorer/report.json']]
  extras +=[str(p.relative_to(SITE)) for p in (out/'figures').iterdir() if p.is_file()]
  for c in index['clips']:
   if c['id'].startswith(record+'_'):extras.extend(['outputs/'+c['meta'],'outputs/'+str(Path(c['meta']).with_suffix('.bin.gz'))])
  rec=json.loads((out/'explorer'/(record+'.json')).read_text())
  for td in rec['tasks'].values():
   for e in td['thresholds']['100']['episodes']:extras.extend(['outputs/dwell/'+e['public_clip']+'.json','outputs/dwell/'+e['public_clip']+'.bin.gz'])
  write(B/'outputs/incremental-data-files.json',sorted(set(extras)))
 print(json.dumps(manifest),flush=True)
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--record');parser.add_argument('--thresholds-only',action='store_true');args=parser.parse_args()
 if args.thresholds_only:thresholds_only()
 else:main(args.record)
