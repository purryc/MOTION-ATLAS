export const OFF={local:2,world:77,pivot:152,q:155,speed:159,contact:160};
export function heightMeasurement(row,baseline,calibrated=true){
 const position=Array.from(row.slice(OFF.local,OFF.local+3));
 if(!position.every(Number.isFinite))return null;
 const raw=position[2],hasBaseline=Number.isFinite(baseline);
 const corrected=hasBaseline?raw-baseline:null,signedHeight=calibrated&&hasBaseline?corrected:raw;
 return {raw_mm:raw,baseline_mm:hasBaseline?baseline:null,corrected_mm:corrected,height_mm:Math.max(0,signedHeight),clamped:signedHeight<0,calibrated:calibrated&&hasBaseline,position};
}
export function zoneBounds(zone,baseline,calibrated=true){
 if(!zone||![...zone.p10,...zone.p90].every(Number.isFinite))return null;
 const min=zone.p10.map((x,i)=>Math.min(x,zone.p90[i])),max=zone.p10.map((x,i)=>Math.max(x,zone.p90[i]));
 if(calibrated&&Number.isFinite(baseline)){min[2]=Math.max(0,min[2]-baseline);max[2]=Math.max(0,max[2]-baseline);}
 return {min,max};
}
export function nearestFrame(data,stride,time){
 let lo=0,hi=data.length/stride-1;
 while(lo<hi){const mid=Math.floor((lo+hi)/2);if(data[mid*stride]<time)lo=mid+1;else hi=mid;}
 return lo>0&&Math.abs(data[(lo-1)*stride]-time)<Math.abs(data[lo*stride]-time)?lo-1:lo;
}
export function sample(data,stride,time,interpolate=true){
 const n=data.length/stride;let k=nearestFrame(data,stride,time),a=k,b=k;
 if(interpolate){if(data[k*stride]>time&&k>0)a=k-1;else if(data[k*stride]<time&&k<n-1)b=k+1;}
 const dt=data[b*stride]-data[a*stride];
 const contiguous=b===a||(data[b*stride+1]-data[a*stride+1]===1&&dt>0&&dt<=6);
 const alpha=contiguous&&dt>0?Math.max(0,Math.min(1,(time-data[a*stride])/dt)):0;
 if(!contiguous)a=b=k;
 const out=data.slice(a*stride,(a+1)*stride);
 // Original frame ID and discrete contact state are NEVER interpolated.
 for(let j=2;j<OFF.contact;j++){
  const x=data[a*stride+j],y=data[b*stride+j];out[j]=Number.isFinite(x)&&Number.isFinite(y)?x+(y-x)*alpha:NaN;
 }
 // Shortest-hemisphere normalized quaternion interpolation between adjacent samples.
 const qa=Array.from(data.slice(a*stride+OFF.q,a*stride+OFF.q+4)),qb=Array.from(data.slice(b*stride+OFF.q,b*stride+OFF.q+4));
 if([...qa,...qb].every(Number.isFinite)){
  const sign=qa.reduce((s,x,i)=>s+x*qb[i],0)<0?-1:1;
  const q=qa.map((x,i)=>x+(qb[i]*sign-x)*alpha),norm=Math.hypot(...q);
  for(let i=0;i<4;i++)out[OFF.q+i]=norm>0?q[i]/norm:NaN;
 }
 out[0]=data[a*stride]+(data[b*stride]-data[a*stride])*alpha;
 out[1]=data[k*stride+1];out[OFF.contact]=data[k*stride+OFF.contact];
 // One missing coordinate invalidates the entire marker, not just one component.
 for(let m=0;m<25;m++)for(const base of [OFF.local,OFF.world]){
  const j=base+m*3;if(![out[j],out[j+1],out[j+2]].every(Number.isFinite))out.fill(NaN,j,j+3);
 }
 return {values:out,index:k,interpolated:a!==b&&alpha>0&&alpha<1};
}
export function playbackTime(anchorDataMs,anchorWallMs,now,speed,duration){return Math.min(duration,anchorDataMs+(now-anchorWallMs)*speed);}
export function stepFrame(data,stride,time,direction){return data[Math.max(0,Math.min(data.length/stride-1,nearestFrame(data,stride,time)+direction))*stride];}
