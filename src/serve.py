"""Local-only viewer server, with on-demand original-frame segments."""
from functools import lru_cache
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import argparse, hashlib, json, mimetypes, re
from urllib.parse import urlparse,parse_qs
import numpy as np
from analyze import B, clip_payload, DEVICES, TASKS
from interactive_analysis import voxelize

@lru_cache(maxsize=2)
def record(name):
 if not re.fullmatch(r'P\d+_(S3|S4|OPO|N6)_(seated|walking)',name):raise ValueError('Invalid record')
 p=B/'data/records'/name
 with np.load(str(p)+'.npz') as z:a={k:z[k] for k in z.files}
 return a,json.loads(Path(str(p)+'.json').read_text())

class Handler(BaseHTTPRequestHandler):
 def send(self,data,mime='application/json',code=200):
  self.send_response(code);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
 def obj(self,o):self.send(json.dumps(o,ensure_ascii=False,allow_nan=False).encode())
 def do_GET(self):
  try:
   u=urlparse(self.path);q=parse_qs(u.query)
   if u.path=='/api/status':
    return self.obj(dict(records=len(list((B/'data/records').glob('*_result.json'))),ready=(B/'outputs/index.json').exists()))
   if u.path=='/api/record':
    a,md=record(q['id'][0]);return self.obj({k:md[k] for k in ['record','participant','phone','condition','source','intervals','checks']})
   if u.path=='/api/segment':
    name=q['record'][0];a,r=record(name);start=float(q['start'][0]);end=min(float(q['end'][0]),start+10000)
    inds=np.flatnonzero((a['time_ms']>=start)&(a['time_ms']<=end))
    if not len(inds):raise ValueError('No frames in requested segment')
    task=q['task'][0]
    if task not in ['READ','WRITE','TAP','DRAG','SCROLL_V','SCROLL_H']:raise ValueError('Invalid task')
    # Require requested bounds within one labelled task context, not a neighbouring task.
    interval=next(i for i in r['intervals'] if i['task']==task and i['context_start_ms']<=start and i['context_end_ms']>=end)
    cid=hashlib.sha256(f'{name}:{start}:{end}:{task}'.encode()).hexdigest()[:24]
    meta=dict(participant=r['participant'],phone=r['phone'],condition=r['condition'],task=task,device=DEVICES[r['phone']],source=r['source'],
     representative_epoch_ms=float(a['time_ms'][inds[0]]),representative_frame=int(a['frame'][inds[0]]),interval=interval,sync_status='CLOCK_MATCHED_PHYSICAL_SYNC_UNVERIFIED')
    zones=json.loads((B/'outputs/zones.json').read_text())['records'].get(name,{}).get(task,{})
    meta.update({k:zones[k] for k in ["home_zone","idle_sample_home_zone"] if k in zones})
    meta["zone_source"]=zones.get("source")
    md,arr=clip_payload(cid,a,inds,meta,r['events'],r['idle'])
    folder=B/'.tmp/viewer';folder.mkdir(exist_ok=True)
    arr.tofile(folder/(cid+'.bin'));md['binary']='/api/binary?id='+cid
    return self.obj(md)
   if u.path=='/api/heat':
    name=q['record'][0];a,r=record(name);task=q['task'][0];scope=q['scope'][0];threshold=int(q['threshold'][0]);baseline=float(q['baseline'][0])
    if task not in TASKS or scope not in ['home','activity'] or threshold not in [100,200,300,400,500,600] or not np.isfinite(baseline) or abs(baseline)>500:raise ValueError('Invalid heat parameters')
    mask=(a['task_context']==TASKS.index(task))&np.isfinite(a['local_mm'][:,0]).all(1)
    if scope=='home':
     choices=json.loads((B/'outputs/explorer'/(name+'.json')).read_text())['tasks'][task]['thresholds'][str(threshold)];stable=np.zeros(len(mask),dtype=bool)
     for e in choices['episodes']:stable|=(a['time_ms']>=e['start_ms'])&(a['time_ms']<=e['end_ms'])
     mask&=stable
    points=a['local_mm'][mask,0].copy();points[:,2]=np.maximum(0,points[:,2]-baseline)
    return self.obj(voxelize(points,.5 if scope=='home' else 2))
   if u.path=='/api/binary':
    key=q['id'][0]
    if not re.fullmatch('[0-9a-f]{24}',key):raise ValueError('Invalid segment')
    return self.send((B/'.tmp/viewer'/(key+'.bin')).read_bytes(),'application/octet-stream')
   if u.path.startswith('/vendor/'):
    path=B/'src/node_modules/three'/u.path.removeprefix('/vendor/')
    root=B/'src/node_modules/three'
   elif u.path=='/' or u.path.startswith('/viewer/'):
    root=B/'src/viewer';path=root/('index.html' if u.path=='/' else u.path.removeprefix('/viewer/'))
   elif u.path.startswith('/outputs/'):
    root=B/'outputs';path=B/u.path.lstrip('/')
   else:return self.send(b'Not found','text/plain',404)
   if not path.resolve().is_relative_to(root.resolve()):return self.send(b'Forbidden','text/plain',403)
   self.send(path.read_bytes(),mimetypes.guess_type(path)[0] or 'application/octet-stream')
  except (ValueError,KeyError,StopIteration) as e:self.send(str(e).encode(),'text/plain',400)
  except FileNotFoundError:self.send(b'Not found','text/plain',404)
 def log_message(self,*args):pass

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=8879);a=ap.parse_args()
 print(f'Le 2019 viewer http://127.0.0.1:{a.port}',flush=True)
 ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
