"""Every-record numerical checks and traceable visual sample contact sheets."""
from pathlib import Path
import json,csv,zipfile
import numpy as np
import pandas as pd
from PIL import Image,ImageDraw,ImageFont
from scipy.spatial.transform import Rotation
from analyze import B,MARKERS,DEVICES,save_json

COLORS=['#e86432','#287cce','#25a68f','#9b74c7','#c79836']
def tile(points,phone,label):
 im=Image.new('RGB',(200,205),'#f4f7f3');d=ImageDraw.Draw(im);w,h,t=DEVICES[phone]['size']
 def proj(p):x,y,z=p;return (115-(x-w/2)*.6+z*.38,32+y*.58+z*.18)
 body=[proj(p) for p in [[0,0,0],[w,0,0],[w,h,0],[0,h,0]]];d.polygon(body,fill='#e2eae1',outline='#91ab98')
 for fi in range(5):
  for j in range(3):
   p=points[fi*4+j:fi*4+j+2]
   if np.isfinite(p).all():d.line([proj(p[0]),proj(p[1])],fill=COLORS[fi],width=2)
  for p in points[fi*4:fi*4+4]:
   if np.isfinite(p).all():x,y=proj(p);d.ellipse((x-2,y-2,x+2,y+2),fill=COLORS[fi])
 for i,line in enumerate(label.split('\n')):d.text((6,5+i*11),line,fill='#355943')
 return im

def main():
 inventory=[]
 with zipfile.ZipFile(B/'sources/mocap_dataset.zip') as archive:
  for n in archive.namelist():
   if not n.endswith('.csv') or n.startswith('__'):continue
   with archive.open(n) as f:h=next(csv.reader([f.readline().decode()]))
   assert h[h.index('Length Units')+1]=='Meters'
   assert h[h.index('Coordinate Space')+1]=='Global'
   assert h[h.index('Rotation Type')+1]=='Quaternion'
   assert abs(float(h[h.index('Capture Frame Rate')+1])-240)<.01
   inventory.append(dict(source=n,capture_start_original=h[9],total_frames=int(h[11])))
 assert len(inventory)==128
 save_json(B/'qa/source_inventory.json',inventory)
 paths=sorted((B/'data/records').glob('*_result.json'),key=lambda p:(int(p.name.split('_')[0][1:]),p.name));tiles=[];checks=[];candidates=[]
 assert len(paths)==128
 for p in paths:
  name=p.name.removesuffix('_result.json');md=json.loads((p.parent/(name+'.json')).read_text());phone=md['phone']
  with np.load(p.parent/(name+'.npz')) as z:
   frame=z['frame'];time=z['time_ms'];local=z['local_mm'];world=z['world_mm'];q=z['quaternion_xyzw'];pivot=z['pivot_mm'];valid=z['marker_valid'];rb=z['rigid_valid'];context=z['task_context'];speed=z['speed_mm_s']
   assert len(frame)==len(time)==len(local);assert (np.diff(time)>0).all()
   assert np.isfinite(local).all(2).tolist()==valid.tolist()
   good=np.flatnonzero(rb&(context>=0)&(valid[:,:20].sum(1)>=16));rng=np.random.default_rng(md['participant']*7+len(name));idx=np.sort(rng.choice(good,min(5,len(good)),replace=False))
   R=Rotation.from_quat(q[idx]).as_matrix();back=np.einsum('nij,nmj->nmi',R,local[idx][:,:,[0,2,1]])+pivot[idx,None,:]
   delta=np.abs(back-world[idx]);err=float(np.nanmax(delta));assert err<.02,err
   missing=np.flatnonzero(~np.isfinite(local[:,0]).all(1))
   if len(missing):assert np.isnan(speed[missing,0]).all()
   checks.append(dict(record=name,random_source_frames=frame[idx].tolist(),world_local_roundtrip_max_mm=err,validity_consistent=True,missing_speed_consistent=True))
   # Exploratory grip-adjustment CANDIDATES: >=2 support-fingernail markers move
   # >=5mm over 200ms, observed continuously in the same task. Not intent labels.
   span=48;support=[4,8,12,16];displacement=np.linalg.norm(local[span:,support]-local[:-span,support],axis=2)
   bad=(~valid[:,support]).astype(int);cs=np.vstack([np.zeros((1,4),int),np.cumsum(bad,axis=0)])
   uninterrupted=(cs[span+1:]-cs[:-span-1])==0
   same=(context[span:]==context[:-span])&(context[span:]>=0)&(frame[span:]-frame[:-span]==span)
   flag=np.zeros(len(frame),bool);flag[span:]=((displacement>=5)&uninterrupted).sum(1)>=2;flag[span:] &= same
   starts=np.flatnonzero(flag&~np.r_[False,flag[:-1]])
   for s in starts:
    e=s+1
    while e<len(frame) and flag[e] and context[e]==context[s] and frame[e]-frame[e-1]==1:e+=1
    if time[e-1]-time[s]<100:continue
    from analyze import TASKS
    candidates.append(dict(record=name,participant=md['participant'],phone=phone,condition=md['condition'],task=TASKS[int(context[s])],
     start_epoch_ms=float(time[s]),end_epoch_ms=float(time[e-1]),start_frame=int(frame[s]),end_frame=int(frame[e-1]),
     definition='>=2 support Fn displacements >=5mm/200ms for >=100ms; same task and continuous valid samples',status='CO_MOVEMENT_CANDIDATE_NOT_VIDEO_CONFIRMED'))
   for k in idx[:2]:
    tiles.append(tile(local[k],phone,f"{name}\nf{frame[k]} / {valid[k].sum()}/25 valid"))
   for k in idx:
    # More detailed samples retained individually for follow-up review.
    folder=B/'qa/random_frames'/name;folder.mkdir(parents=True,exist_ok=True)
    tile(local[k],phone,f'{name}\nf{frame[k]} / {valid[k].sum()}/25 valid').resize((400,410)).save(folder/(str(frame[k])+'.png'))
 for start in range(0,len(tiles),32):
  sheet=Image.new('RGB',(1600,820),'white')
  for j,t in enumerate(tiles[start:start+32]):sheet.paste(t,((j%8)*200,(j//8)*205))
  sheet.save(B/'qa'/f'contact-sheet-{start//32+1}.png')
 # Independently compare every exported representative clip against complete arrays.
 index=json.loads((B/'outputs/index.json').read_text());clip_checks=[]
 for p in paths:
  name=p.name.removesuffix('_result.json')
  with np.load(p.parent/(name+'.npz')) as z:
   frame=z['frame'];local=z['local_mm'];world=z['world_mm'];time=z['time_ms']
   for c in index['clips']:
    if not c['id'].startswith(name+'_'):continue
    md=json.loads((B/'outputs'/c['meta']).read_text());a=np.fromfile(B/'outputs/clips'/md['binary'],dtype='<f4').reshape(-1,md['stride']);kk=np.searchsorted(frame,a[:,1].astype(int))
    np.testing.assert_allclose(a[:,2:77].reshape(-1,25,3),local[kk],equal_nan=True)
    np.testing.assert_allclose(a[:,77:152].reshape(-1,25,3),world[kk],equal_nan=True)
    err=float(np.max(np.abs(a[:,0].astype(float)+md['start_epoch_ms']-time[kk])));assert err<.001
    clip_checks.append(dict(id=c['id'],frames=len(a),timestamp_max_error_ms=err,coordinates_match_npz=True))
 save_json(B/'qa/record_checks.json',checks);save_json(B/'qa/clip_checks.json',clip_checks)
 pd.DataFrame(candidates,columns=['record','participant','phone','condition','task','start_epoch_ms','end_epoch_ms','start_frame','end_frame','definition','status']).to_csv(B/'data/grip_candidates.csv',index=False)
 print('Audit PASS',len(checks),'records',len(clip_checks),'clips',flush=True)
if __name__=='__main__':main()
