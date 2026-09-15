export function eligibleEpisodes(episodes,threshold){return episodes.filter(e=>e.duration_ms+1e-5>=threshold);}
export function episodeAt(episodes,epoch){return episodes.find(e=>epoch>=e.start_ms&&epoch<=e.end_ms+1000/240)||null;}
export function clippedEpisodes(episodes,start,end){return episodes.filter(e=>e.end_ms>=start&&e.start_ms<=end).map(e=>({...e,start_ms:Math.max(start,e.start_ms)-start,end_ms:Math.min(end,e.end_ms+1000/240)-start}));}
export function uiAt(ui,epoch){
 const events=ui?.events||[];let lo=0,hi=events.length;
 while(lo<hi){const mid=(lo+hi)>>1;if(events[mid][0]<=epoch)lo=mid+1;else hi=mid;}
 const event=lo?events[lo-1]:null,trials=ui?.trials||[];
 const trial=trials.find(t=>epoch>=t.start_ms&&epoch<=t.end_ms)||null;
 return {trial,event:trial&&event?.[4]===trial.trial&&epoch-event[0]<1000?event:null,recent:trial?events.slice(Math.max(0,lo-50),lo).filter(e=>e[4]===trial.trial&&epoch-e[0]<1000):[]};
}
export function pixelToPhone(x,y,device,pixels){const [sw,sh]=device.screen,[ox,oy]=device.offset;return [ox+sw*(1-x/pixels[0]),oy+sh*y/pixels[1],0];}
export function uiCanvasPoint(x,y,device,pixels,canvas,fit){
 const [w,h]=canvas;if(!fit)return [x/pixels[0]*w,y/pixels[1]*h];
 const [a,b,d,e]=fit,[sw,sh]=device.screen,[ox,oy]=device.offset;
 return [(ox+sw-(a*x+b))/sw*w,(d*y+e-oy)/sh*h];
}
