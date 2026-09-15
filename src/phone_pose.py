"""Framewise phone-marker pose repair for an audited inconsistent source export."""
import csv,hashlib,json,zipfile
import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation
from analyze import B,logs
RECORD='P7_N6_seated'

def fit(template,observed):
    centre=template.mean(0);moving=observed.mean(1);xc=template-centre;yc=observed-moving[:,None]
    u,s,vh=np.linalg.svd(np.einsum('mi,nmj->nij',xc,yc));sign=np.linalg.det(u@vh);u[:,:,-1]*=sign[:,None];row_rotation=u@vh
    origin=moving-np.einsum('i,nij->nj',centre,row_rotation)
    residual=np.linalg.norm(np.einsum('mi,nij->nmj',template,row_rotation)+origin[:,None]-observed,axis=2)
    return row_rotation.transpose(0,2,1),origin,np.sqrt(np.mean(residual**2,axis=1)),s

def repair(record,q,p,ts):
    if record!=RECORD:return q,p,None
    with zipfile.ZipFile(B/'sources/mocap_dataset.zip') as archive:
        with archive.open(record+'.csv') as f:
            header=[next(csv.reader([f.readline().decode()])) for _ in range(7)]
            names,kinds,types,axes=header[3],header[5],header[2],header[6]
            marker_names=sorted({n for n,t in zip(names,types) if t=='Marker' and n.startswith('N6:Marker')},key=lambda n:int(n.split('Marker')[-1]))
            cols=[next(i for i in range(len(names)) if names[i]==n and axes[i]==axis and types[i]=='Marker') for n in marker_names for axis in ['X','Y','Z']]
            error_col=next(i for i in range(len(names)) if kinds[i]=='Error Per Marker' and names[i]=='N6')
            df=pd.read_csv(f,header=None,usecols=cols+[error_col]);observed=df[cols].to_numpy().reshape(-1,len(marker_names),3)*1000;errors=df[error_col].to_numpy()*1000
    trials,intervals,events,notes=logs(7,'N6','seated')
    reference=np.zeros(len(ts),bool)
    for tr in trials:
        if tr['task']=='WRITE':reference|=(ts>=tr['start_ms'])&(ts<=tr['end_ms'])
    valid=np.isfinite(observed).all(2)
    reference &= valid.all(1)&np.isfinite(q).all(1)&np.isfinite(p).all(1)&(errors<.5)
    if reference.sum()<100:raise ValueError('Insufficient independent phone-template samples')
    local=np.einsum('nji,nmj->nmi',Rotation.from_quat(q[reference]).as_matrix(),observed[reference]-p[reference,None])
    template=np.median(local,axis=0)
    qr=np.full_like(q,np.nan);pr=np.full_like(p,np.nan);rms=np.full(len(q),np.nan);kept=np.zeros(len(q),bool)
    for bits in np.unique(valid,axis=0):
        if bits.sum()<3:continue
        ix=np.flatnonzero((valid==bits).all(1));rotation,origin,error,s=fit(template[bits],observed[ix][:,bits]);good=(error<=1)&(s[:,1]/np.maximum(s[:,0],1e-12)>=.02)
        if not good.any():continue
        ixgood=ix[good];qr[ixgood]=Rotation.from_matrix(rotation[good]).as_quat();pr[ixgood]=origin[good];rms[ixgood]=error[good];kept[ixgood]=True
    complete=valid.all(1);rotation,origin,error,s=fit(template[:-1],observed[complete,:-1]);prediction=np.einsum('nij,j->ni',rotation,template[-1])+origin;held=np.linalg.norm(prediction-observed[complete,-1],axis=1)
    reading=np.zeros(len(ts),bool)
    for tr in intervals:
        if tr['task']=='READ':reading|=(ts>=tr['context_start_ms'])&(ts< tr['context_end_ms'])
    rh=held[reading[complete]]
    if np.percentile(rh,95)>1:raise ValueError('Reading marker holdout validation failed')
    audit=dict(record=record,method='same-record phone-marker template, per-frame proper rigid fit; no gap interpolation',marker_names=marker_names,template_xyz_mm=template.tolist(),template_sha256=hashlib.sha256(template.astype('<f8').tobytes()).hexdigest(),template_reference='Writing trials; all observed markers; exported error <0.5mm',reference_frames=int(reference.sum()),valid_frames=int(kept.sum()),rejected_frames=int((~kept).sum()),fit_rms_p50_p95_mm=np.percentile(rms[kept],[50,95]).tolist(),reading_heldout_marker_p50_p95_mm=np.percentile(rh,[50,95]).tolist(),source='sources/mocap_dataset.zip:'+record+'.csv',physical_touch_sync_verified=False)
    return qr,pr,audit
