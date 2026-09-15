import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {OFF,sample,nearestFrame,stepFrame,playbackTime,heightMeasurement,zoneBounds} from './core.js';
import {episodeAt,clippedEpisodes,uiAt} from './explorer.js';
const $=id=>document.getElementById(id);
const colors=[0xe86432,0x287cce,0x25a68f,0x9b74c7,0xc79836];
const labels={READ:'阅读',WRITE:'输入',TAP:'点击',DRAG:'拖动',SCROLL_V:'竖向滚动',SCROLL_H:'横向滚动'};
const state={index:null,task:'READ',time:0,speed:1,playing:false,anchorTime:0,anchorWall:0,world:false,view:'oblique',generation:0,cache:new Map(),heightBaselines:{},taskZones:{},explorerRecords:{},dwellThreshold:400,manualBaselines:new Map()};
function clipRecord(clip){const m=clip.meta;return `P${m.participant}_${m.phone}_${m.condition}`;}
function calibrationFor(clip){return state.manualBaselines.get(clipRecord(clip))||clip.meta.height_calibration||state.heightBaselines[clipRecord(clip)]||{};}
const segments={};
const siteRoot=new URL('../',import.meta.url);
const request=async url=>{const r=await fetch(url.startsWith('/')?new URL(url.slice(1),siteRoot):url);if(!r.ok)throw Error(await r.text());return r;};
async function loadBinary(url,encoding,stride){const r=await request(String(url));const buffer=String(url).endsWith('.gz')?await new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).arrayBuffer():await r.arrayBuffer();if(encoding==='xor-shuffle-f32-le'){const src=new Uint8Array(buffer),bytes=new Uint8Array(buffer.byteLength),n=src.length/4;for(let j=0;j<4;j++)for(let i=0;i<n;i++)bytes[i*4+j]=src[j*n+i];const bits=new Uint32Array(bytes.buffer);for(let i=stride;i<bits.length;i++)bits[i]^=bits[i-stride];return new Float32Array(bytes.buffer);}return new Float32Array(buffer);}
function options(el,items,current){el.innerHTML='';for(const [v,t] of items){const o=document.createElement('option');o.value=v;o.textContent=t;el.append(o);}if(items.some(i=>i[0]===current))el.value=current;}
function recordId(){return `P${$('participant').value}_${$('phone').value}_${$('condition').value}`;}
function available(){return state.index.clips.filter(c=>String(c.participant)===$('participant').value&&c.phone===$('phone').value&&c.condition===$('condition').value);}
async function loadClip(c){
 if(state.cache.has(c.id))return state.cache.get(c.id);
 const url='/outputs/'+c.meta,md=await (await request(url)).json();
 const binary=md.binary.startsWith('/')?new URL(md.binary.slice(1),siteRoot):new URL(md.binary,new URL(url.slice(1),siteRoot));
 const data=await loadBinary(binary,md.binary_encoding,md.stride);
 if(data.length!==md.frames*md.stride)throw Error('片段长度校验失败');
 const clip={meta:md,data};state.cache.set(c.id,clip);return clip;
}
async function ensureExplorer(name){if(!state.explorerRecords[name])state.explorerRecords[name]=await (await request('/outputs/explorer/'+name+'.json')).json();return state.explorerRecords[name];}
function taskData(clip){return state.explorerRecords[clipRecord(clip)]?.tasks[clip.meta.task];}
function dwellChoice(clip){return taskData(clip)?.thresholds[String(state.dwellThreshold)];}
function connections(){let a=[];for(let f=0;f<5;f++)for(let j=0;j<3;j++)a.push([f*4+j,f*4+j+1,f]);for(let f=0;f<4;f++)a.push([f*4+3,(f+1)*4+3,5]);return a;}
class Stage{
 constructor(suffix){
  this.suffix=suffix;this.host=$('canvas'+suffix);this.scene=new THREE.Scene();this.scene.background=new THREE.Color('#edf2ee');
  this.renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});this.renderer.setPixelRatio(Math.min(devicePixelRatio,2));this.renderer.outputColorSpace=THREE.SRGBColorSpace;this.host.append(this.renderer.domElement);
  this.camera=new THREE.PerspectiveCamera(36,1,.01,2000);this.controls=new OrbitControls(this.camera,this.renderer.domElement);this.controls.enableDamping=true;
  this.scene.add(new THREE.HemisphereLight(0xffffff,0x93a393,2));const light=new THREE.DirectionalLight(0xffffff,3);light.position.set(100,150,220);this.scene.add(light);
  this.phone=new THREE.Group();this.scene.add(this.phone);this.hand=new THREE.Group();this.scene.add(this.hand);
  const geo=new THREE.SphereGeometry(2.5,12,8);this.points=[];this.bones=[];
  for(let m=0;m<25;m++){const mesh=new THREE.Mesh(geo,new THREE.MeshStandardMaterial({color:m<20?colors[Math.floor(m/4)]:0x86958a,roughness:.6}));this.hand.add(mesh);this.points.push(mesh);}
  for(const [a,b,f] of connections()){const mesh=new THREE.Mesh(new THREE.CylinderGeometry(f===0?1.25:.8,f===0?1.25:.8,1,8),new THREE.MeshStandardMaterial({color:colors[f]||0x97aaa0}));this.hand.add(mesh);this.bones.push({a,b,mesh});}
  this.trail=new THREE.LineSegments(new THREE.BufferGeometry(),new THREE.LineBasicMaterial({color:colors[0],transparent:true,opacity:.45}));this.scene.add(this.trail);
  this.zone=new THREE.Box3Helper(new THREE.Box3(),0x287cce);this.zoneRoot=new THREE.Group();this.zoneRoot.add(this.zone);this.scene.add(this.zoneRoot);
  this.idlezone=new THREE.Box3Helper(new THREE.Box3(),0x25a68f);this.idlezoneRoot=new THREE.Group();this.idlezoneRoot.add(this.idlezone);this.scene.add(this.idlezoneRoot);
  for(const helper of [this.zone,this.idlezone]){
   helper.volume=new THREE.Mesh(new THREE.BoxGeometry(1,1,1),new THREE.MeshBasicMaterial({color:helper.material.color,transparent:true,opacity:.16,depthWrite:false,side:THREE.DoubleSide}));helper.parent.add(helper.volume);
  }
  this.uiPreview=document.createElement('div');this.uiPreview.className='ui-preview';this.uiPreview.innerHTML='<small>控件放大 · 日志示意</small><canvas></canvas>';this.uiPreviewCanvas=this.uiPreview.querySelector('canvas');this.host.append(this.uiPreview);
  this.dwellLabel=document.createElement('div');this.dwellLabel.className='dwell-label';this.host.append(this.dwellLabel);
  this.zone.visible=this.idlezone.visible=false;
  this.zoneLabel=document.createElement('div');this.zoneLabel.className='zone-label';this.host.append(this.zoneLabel);
  this.heightRoot=new THREE.Group();this.scene.add(this.heightRoot);
  this.heightDimension=new THREE.LineSegments(new THREE.BufferGeometry(),new THREE.LineBasicMaterial({color:0xc95c29,depthTest:false}));this.heightRoot.add(this.heightDimension);
  this.heightStem=new THREE.Line(new THREE.BufferGeometry(),new THREE.LineDashedMaterial({color:0x799082,dashSize:1.5,gapSize:1,depthTest:false}));this.heightRoot.add(this.heightStem);
  this.heightReference=new THREE.Mesh(new THREE.SphereGeometry(1.6,12,8),new THREE.MeshBasicMaterial({color:0xc95c29,wireframe:true,depthTest:false}));this.heightRoot.add(this.heightReference);
  this.heightLabel=document.createElement('div');this.heightLabel.className='height-label';this.heightLabel.hidden=true;this.host.append(this.heightLabel);
  new ResizeObserver(()=>this.resize()).observe(this.host);this.view(state.view);
 }
 resize(){const w=this.host.clientWidth,h=this.host.clientHeight;if(!w||!h)return;this.renderer.setPixelRatio(Math.min(devicePixelRatio,2));this.renderer.setSize(w,h,false);this.camera.aspect=w/h;this.camera.updateProjectionMatrix();}
 view(v){this.focusedZone=false;this.glyphScale=1;const positions={front:[0,0,370],back:[0,0,-370],side:[360,0,0],oblique:[160,125,300]};this.camera.position.set(...positions[v]);this.controls.target.set(0,-35,0);this.controls.update();}
 setClip(clip){
  if(this.focusedZone)this.view(state.view);
  this.uiTexture?.dispose();this.uiFrame=null;
  this.clip=clip;this.origin=new THREE.Vector3(...clip.data.slice(OFF.pivot,OFF.pivot+3));
  while(this.phone.children.length){const obj=this.phone.children[0];this.phone.remove(obj);obj.geometry?.dispose();obj.material?.dispose();}
  const d=clip.meta.device,[w,h,t]=d.size;this.width=w;this.height=h;
  const body=new THREE.Mesh(new THREE.BoxGeometry(w,h,t),new THREE.MeshStandardMaterial({color:0x405c4d,roughness:.75,transparent:true,opacity:.2,side:THREE.DoubleSide,depthWrite:false}));body.position.z=-t/2;this.phone.add(body);
  const outline=new THREE.LineSegments(new THREE.EdgesGeometry(body.geometry),new THREE.LineBasicMaterial({color:0x6e8877,transparent:true,opacity:.65}));outline.position.copy(body.position);this.phone.add(outline);
  const [sw,sh]=d.screen,[ox,oy]=d.offset;this.screen=new THREE.Mesh(new THREE.PlaneGeometry(sw,sh),new THREE.MeshStandardMaterial({color:0xdce8df,transparent:true,opacity:.6,side:THREE.DoubleSide,depthWrite:false}));this.screen.position.set(w/2-ox-sw/2,h/2-oy-sh/2,0);this.phone.add(this.screen);
  const s=new THREE.LineSegments(new THREE.EdgesGeometry(this.screen.geometry),new THREE.LineBasicMaterial({color:0x9ab7a4}));s.position.copy(this.screen.position);this.phone.add(s);this.screenOutline=s;
  this.uiCanvas=document.createElement('canvas');this.uiCanvas.width=512;this.uiCanvas.height=Math.round(512*sh/sw);this.uiTexture=new THREE.CanvasTexture(this.uiCanvas);this.uiTexture.colorSpace=THREE.SRGBColorSpace;
  this.uiPlane=new THREE.Mesh(new THREE.PlaneGeometry(sw,sh),new THREE.MeshBasicMaterial({map:this.uiTexture,transparent:true,opacity:.8,side:THREE.FrontSide,depthWrite:false}));this.uiPlane.position.copy(this.screen.position);this.uiPlane.position.z=.04;this.phone.add(this.uiPlane);
  this.update(0,false);this.resize();
 }
 toLocal(p){return new THREE.Vector3(this.width/2-p[0],this.height/2-p[1],p[2]);}
 phoneMatrix(row){
  const q=new THREE.Quaternion(...row.slice(OFF.q,OFF.q+4));if(!Number.isFinite(q.lengthSq())||q.lengthSq()<.9)return null;q.normalize();
  const rot=new THREE.Matrix4().makeRotationFromQuaternion(q);
  // Inverse of upstream [local x,local z,local y] swap AND centred viewer axes.
  const basis=new THREE.Matrix4().set(-1,0,0,this.width/2,0,0,1,0,0,-1,0,this.height/2,0,0,0,1);
  rot.multiply(basis);rot.setPosition(new THREE.Vector3(...row.slice(OFF.pivot,OFF.pivot+3)).sub(this.origin).add(new THREE.Vector3().setFromMatrixPosition(rot)));return rot;
 }
 update(time,interpolate=true){
  if(!this.clip)return;const {meta,data}=this.clip,{values:r,index,interpolated}=sample(data,meta.stride,time,interpolate);this.current={values:r,index,interpolated};
  const world=state.world;this.phone.matrixAutoUpdate=!world;
  if(world){const m=this.phoneMatrix(r);this.phone.visible=!!m;if(m)this.phone.matrix.copy(m);}else{this.phone.visible=true;this.phone.position.set(0,0,0);this.phone.quaternion.identity();this.phone.scale.set(1,1,1);this.phone.updateMatrix();}
  let missing=0;
  for(let m=0;m<25;m++){
   const local=Array.from(r.slice(OFF.local+m*3,OFF.local+m*3+3));const wp=Array.from(r.slice(OFF.world+m*3,OFF.world+m*3+3));
   const valid=local.every(Number.isFinite)&&(!world||wp.every(Number.isFinite));this.points[m].visible=valid;this.points[m].scale.setScalar(this.glyphScale||1);if(!valid){missing++;continue;}
   this.points[m].position.copy(world?new THREE.Vector3(...wp).sub(this.origin):this.toLocal(local));
  }
  for(const b of this.bones){const a=this.points[b.a],c=this.points[b.b];b.mesh.visible=a.visible&&c.visible;if(!b.mesh.visible)continue;const delta=c.position.clone().sub(a.position);b.mesh.position.copy(a.position).add(c.position).multiplyScalar(.5);b.mesh.scale.set(this.glyphScale||1,delta.length(),this.glyphScale||1);b.mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),delta.normalize());}
  this.screen.visible=this.screenOutline.visible=$('screen').checked;
  const cal=calibrationFor(this.clip),zones=state.taskZones[clipRecord(this.clip)]?.[meta.task]||meta;
  const choice=dwellChoice(this.clip),home=choice?choice.home:zones.idle_sample_home_zone,activity=zones.home_zone;
  this.box(this.zone,activity,$('zone').checked,world,r,cal);
  this.box(this.idlezone,home,$('idlezone').checked,world,r,cal);
  const caption=[];
  if(this.zone.visible)caption.push('蓝 · 任务活动区');
  if(this.idlezone.visible)caption.push(`绿框 · ${labels[meta.task]} Home Zone (${home.episodes} 次 · ${this.idlezone.volume.scale.toArray().map(x=>x.toFixed(2)).join(' × ')} mm)`);
  if($('idlezone').checked&&!home)caption.push(`${labels[meta.task]}：未检出 ≥${state.dwellThreshold} ms 的 Home Zone`);
  const sm=choice?.summary,epoch=meta.start_epoch_ms+r[0],current=choice?episodeAt(choice.episodes,epoch):null;
  this.dwellCaption=sm?`${labels[meta.task]} Home Zone · 停留 ${sm.episodes} 次 · 累计合格停留 ${(sm.total_ms/1000).toFixed(3)} s · 中位 ${sm.median_ms===null?'—':sm.median_ms.toFixed(0)+' ms'} · 最短 ${state.dwellThreshold} ms`:'';
  this.dwellLabel.textContent=this.dwellCaption+(current?` / 当前本次 ${(Math.min(current.duration_ms,epoch-current.start_ms+1000/240)).toFixed(0)} / ${current.duration_ms.toFixed(0)} ms`:' / 当前帧不在合格停留内');
  this.zone.volume.visible=false;this.idlezone.volume.visible=false;
  this.drawUI(epoch);
  this.zoneCaption=caption.join(' / ');this.zoneLabel.textContent=this.zoneCaption;this.zoneLabel.hidden=!caption.length;
  this.zoneLabel.title='真实拇指样本 XYZ 各轴 P10–P90，非关节范围或联合密度区域；校准显示同步转换高度。';
  this.trail.visible=$('trajectory').checked;
  if(this.trail.visible){
   const verts=[],end=nearestFrame(data,meta.stride,time),start=Math.max(0,end-480),base=world?OFF.world:OFF.local;
   for(let k=start+1;k<=end;k++){
    const prev=(k-1)*meta.stride,cur=k*meta.stride;
    if(data[cur+1]-data[prev+1]!==1||data[cur]-data[prev]>6)continue;
    const a=Array.from(data.slice(prev+base,prev+base+3)),b=Array.from(data.slice(cur+base,cur+base+3));
    const valid=[...a,...b,...data.slice(prev+OFF.local,prev+OFF.local+3),...data.slice(cur+OFF.local,cur+OFF.local+3)].every(Number.isFinite);
    if(!valid)continue;
    const ap=world?new THREE.Vector3(...a).sub(this.origin):this.toLocal(a),bp=world?new THREE.Vector3(...b).sub(this.origin):this.toLocal(b);verts.push(...ap.toArray(),...bp.toArray());
   }
   this.trail.geometry.dispose();this.trail.geometry=new THREE.BufferGeometry();this.trail.geometry.setAttribute('position',new THREE.Float32BufferAttribute(verts,3));
  }
  const z=r[OFF.local+2],v=r[OFF.speed];const contact=['未知','离屏','触摸'][r[OFF.contact]+1]||'未知';
  const measurement=heightMeasurement(r,cal.baseline_mm,$('calibrated').checked);this.current.height=measurement;
  const heightText=measurement?(measurement.calibrated?`修正离屏 ${measurement.height_mm.toFixed(1)} mm${measurement.clamped?'（低于基线按 0 显示）':''} · 指甲 Z ${z.toFixed(1)} mm`:`标记点离屏 ${measurement.height_mm.toFixed(1)} mm · 指甲 Z ${z.toFixed(1)} mm`):'拇指标记点缺失';
  $('title'+this.suffix).textContent=labels[meta.task];$('metrics'+this.suffix).textContent=`${heightText} · 速度 ${Number.isFinite(v)?v.toFixed(1):'—'} mm/s · ${contact}`;
  $('source'+this.suffix).textContent=`P${meta.participant} · ${meta.phone} · ${meta.condition==='seated'?'坐姿':'行走'} · ${meta.source} · 原始帧 ${Math.round(r[1])} · ${missing?`缺失 ${missing}/25 个点`:'25 个点可用'}`;
  this.controls.update();this.drawHeight(r,measurement,cal);this.renderer.render(this.scene,this.camera);
 }
 drawUI(epoch){
  this.uiPlane.visible=$('taskUI').checked&&!this.focusedZone;this.uiPreview.hidden=!this.uiPlane.visible;if(!this.uiPlane.visible)return;
  const ui=taskData(this.clip)?.ui,key=Math.floor(epoch/33);if(this.uiFrame===key)return;this.uiFrame=key;
  const c=this.uiCanvas,ctx=c.getContext('2d'),w=c.width,h=c.height,current=uiAt(ui,epoch),task=this.clip.meta.task;
  ctx.clearRect(0,0,w,h);ctx.fillStyle='#f9fbfa';ctx.fillRect(0,0,w,h);ctx.fillStyle='#325749';ctx.font='bold 36px sans-serif';ctx.fillText(labels[task]+' · 控件示意',22,40);ctx.font='26px sans-serif';ctx.fillText('日志示意 · 非录屏',22,68);
  const controls=(current.trial||ui?.trials.find(t=>t.trial===this.clip.meta.interval?.trial))?.controls||(task==='READ'?ui?.trials[0]?.controls:{})||{},pixels=ui?.nominal_pixels||[w,h],point=(x,y)=>[Number(x)/pixels[0]*w,Number(y)/pixels[1]*h];
  if(task==='WRITE'){ctx.font='30px sans-serif';const phrase=(controls.textToWrite||'输入任务');let line='',lineY=125;for(const word of phrase.split(' ')){if(ctx.measureText(line+' '+word).width>w-44){ctx.fillText(line,22,lineY);lineY+=36;line=word;}else line+=(line?' ':'')+word;}ctx.fillText(line,22,lineY);const events=ui?.events||[];if(events.length){const xs=events.map(e=>e[1]/pixels[0]*w),ys=events.map(e=>e[2]/pixels[1]*h);ctx.strokeStyle='#b4c5bc';ctx.setLineDash([8,5]);ctx.strokeRect(Math.min(...xs),Math.min(...ys),Math.max(...xs)-Math.min(...xs),Math.max(...ys)-Math.min(...ys));ctx.setLineDash([]);ctx.fillText('键盘触点范围（日志）',22,h-20);}}
  if(task==='READ'){ctx.strokeStyle='#c6d2cc';ctx.strokeRect(18,100,w-36,h-125);ctx.font='30px sans-serif';ctx.fillText('阅读区域 · textId '+(controls.textId||'—'),28,140);ctx.fillText('正文/滚动位置未保存',28,172);}
  if(['TAP','DRAG','SCROLL_V','SCROLL_H'].includes(task)){
   if(task==='DRAG'){ctx.strokeStyle='#dde5df';for(let x=1;x<2;x++){ctx.beginPath();ctx.moveTo(w*x/2,90);ctx.lineTo(w*x/2,h);ctx.stroke();}for(let y=1;y<3;y++){ctx.beginPath();ctx.moveTo(0,h*y/3);ctx.lineTo(w,h*y/3);ctx.stroke();}}
   for(const [a,b,color,label]of [['tileX','tileY','#e65b37','tile 锚点'],['targetX','targetY','#287cce','target 锚点']])if(controls[a]!==undefined){const [x,y]=point(controls[a],controls[b]);ctx.strokeStyle=color;ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(x-12,y);ctx.lineTo(x+12,y);ctx.moveTo(x,y-12);ctx.lineTo(x,y+12);ctx.stroke();ctx.fillStyle=color;ctx.font='36px sans-serif';ctx.fillText(label,Math.max(4,Math.min(w-230,x+15)),Math.max(100,y-12));}
  }
  ctx.strokeStyle='#e89432';ctx.lineWidth=3;ctx.beginPath();current.recent.forEach((e,i)=>{const p=point(e[1],e[2]);i&&!e[3].includes('DOWN')&&!current.recent[i-1][3].includes('UP')?ctx.lineTo(...p):ctx.moveTo(...p);});ctx.stroke();if(current.event){ctx.fillStyle='#e65b37';ctx.beginPath();ctx.arc(...point(current.event[1],current.event[2]),9,0,2*Math.PI);if(current.event[3].includes('UP')){ctx.strokeStyle='#e65b37';ctx.stroke();}else ctx.fill();ctx.fillStyle='#e65b37';ctx.font='26px sans-serif';ctx.fillText(current.event[3],22,90);}
  this.uiTexture.needsUpdate=true;this.uiPreviewCanvas.width=w;this.uiPreviewCanvas.height=h;this.uiPreviewCanvas.getContext('2d').drawImage(c,0,0);
 }
 drawHeight(row,m,cal){
  const enabled=$('heightline').checked&&!!m&&!this.focusedZone;this.heightRoot.visible=enabled;this.heightLabel.hidden=!enabled;if(!enabled)return;
  const [x,y,z]=this.toLocal(m.position).toArray(),h=m.height_mm;
  this.heightDimension.geometry.setAttribute('position',new THREE.Float32BufferAttribute([x,y,0,x,y,h,x,y-2.5,0,x,y+2.5,0,x,y-2.5,h,x,y+2.5,h],3));this.heightDimension.geometry.computeBoundingSphere();
  this.heightReference.position.set(x,y,h);this.heightReference.visible=m.calibrated;
  this.heightStem.visible=m.calibrated;this.heightStem.geometry.setAttribute('position',new THREE.Float32BufferAttribute([x,y,z,x,y,h],3));this.heightStem.computeLineDistances();this.heightStem.geometry.computeBoundingSphere();
  this.heightRoot.matrixAutoUpdate=false;this.heightRoot.matrix.identity();
  if(state.world){const matrix=this.phoneMatrix(row);if(!matrix){this.heightRoot.visible=false;this.heightLabel.hidden=true;return;}this.heightRoot.matrix.copy(matrix);}
  const projected=new THREE.Vector3(x,y,h/2).applyMatrix4(this.heightRoot.matrix).project(this.camera),w=this.host.clientWidth,hh=this.host.clientHeight;
  this.heightLabel.hidden=projected.z< -1||projected.z>1;
  const d=this.clip.meta.device,[sw,sh]=d.screen,[ox,oy]=d.offset,outside=m.position[0]<ox||m.position[0]>ox+sw||m.position[1]<oy||m.position[1]>oy+sh;
  this.heightLabel.innerHTML=`<b>${m.calibrated?'修正离屏':'标记点离屏'} ${h.toFixed(1)} mm</b><small>${m.calibrated?`指甲 Z ${m.raw_mm.toFixed(1)} · 基线 ${m.baseline_mm.toFixed(1)} mm`:'真实指甲标记点到屏幕平面'}</small><small>${m.clamped?'低于参考平面，距离按 0 mm 显示':m.calibrated?'空心点为校准参考，不是指腹测量':'未作高度校准'}${outside?' · 屏外投影':''}</small>`;
  const left=Math.max(8,Math.min(w-this.heightLabel.offsetWidth-8-(!this.uiPreview.hidden?this.uiPreview.offsetWidth+12:0),(projected.x+1)*w/2+16)),top=Math.max(8,Math.min(hh-this.heightLabel.offsetHeight-8,(1-projected.y)*hh/2-50));
  this.heightLabel.style.left=left+'px';this.heightLabel.style.top=top+'px';
 }
 box(helper,zone,enabled,world,row,cal){
  const bounds=zoneBounds(zone,cal.baseline_mm,$('calibrated').checked);
  helper.visible=enabled&&!!bounds;helper.volume.visible=false;if(!helper.visible)return;
  const a=this.toLocal(bounds.min),b=this.toLocal(bounds.max);helper.box.setFromPoints([a,b]);
  helper.volume.position.copy(helper.box.getCenter(new THREE.Vector3()));helper.volume.scale.copy(helper.box.getSize(new THREE.Vector3()));
  helper.matrixAutoUpdate=true;helper.parent.matrixAutoUpdate=false;helper.parent.matrix.identity();
  if(world){const m=this.phoneMatrix(row);if(m)helper.parent.matrix.copy(m);else helper.visible=helper.volume.visible=false;}
 }

}
let A,B;
function error(e){$('status').textContent='读取失败：'+e.message+'。可重新选择任务重试。';state.playing=false;$('play').textContent='播放';}
function duration(){if(!A?.clip)return 0;return A.clip.meta.duration_ms;}
function bTime(t){
 if(!$('align').checked)return Math.min(t,B?.clip?.meta.duration_ms||0);
 const ea=A.clip.meta.events.find(e=>e.sync_eligible&&e.action.includes('DOWN')),eb=B.clip.meta.events.find(e=>e.sync_eligible&&e.action.includes('DOWN'));
 return Math.max(0,Math.min(B.clip.meta.duration_ms,t-ea.time_ms+eb.time_ms));
}
function anchor(){state.anchorTime=state.time;state.anchorWall=performance.now();}
function pause(){state.playing=false;$('play').textContent='播放';}
function drawTimeline(){
 if(!A.clip)return;const c=$('events');c.width=c.clientWidth*devicePixelRatio;c.height=32*devicePixelRatio;const ctx=c.getContext('2d'),d=duration()||1;
 ctx.clearRect(0,0,c.width,c.height);ctx.fillStyle='#25a68f55';for(const e of clippedEpisodes(dwellChoice(A.clip)?.episodes||[],A.clip.meta.start_epoch_ms,A.clip.meta.start_epoch_ms+duration()))ctx.fillRect(e.start_ms/d*c.width,7*devicePixelRatio,(e.end_ms-e.start_ms)/d*c.width,8*devicePixelRatio);
 for(const e of A.clip.meta.events){if(!e.action.includes('DOWN')&&!e.action.includes('UP'))continue;ctx.strokeStyle=e.action.includes('DOWN')?'#e86432':'#287cce';ctx.beginPath();ctx.moveTo(e.time_ms/d*c.width,0);ctx.lineTo(e.time_ms/d*c.width,19*devicePixelRatio);ctx.stroke();}
}
function render(interpolate=true){
 A.update(state.time,interpolate);if($('compare').checked&&B.clip)B.update(bTime(state.time),interpolate);
 $('scrub').max=duration();$('scrub').value=state.time;$('time').textContent=`${(state.time/1000).toFixed(3)} / ${(duration()/1000).toFixed(3)} s`;
 if(A.current)$('frameinfo').textContent=`原始帧 ${Math.round(A.current.values[1])} · ${A.current.interpolated?'相邻采样点显示插值':'采样帧'}`;
 $('focusZone').disabled=!A.idlezone.visible;$('focusZone').textContent='聚焦 Home Zone';
 const m=A.current?.height,cal=calibrationFor(A.clip);$('zeroContact').disabled=state.playing||!m||A.current.values[OFF.contact]!==1;
 $('calibrationInfo').textContent=Number.isFinite(cal.baseline_mm)?`${cal.method==='manual_contact_frame'?'当前帧':'自动触摸中位数'}基线 ${cal.baseline_mm.toFixed(2)} mm${cal.source_frame!==undefined?` · 源帧 ${cal.source_frame}`:''}；${m?'原始标记点未移动。':'拇指点缺失，暂不显示高度，基线保留。'}`:'没有可用触摸基线；显示原始指甲高度。';
}
async function chooseTask(task){
 const gen=++state.generation;pause();state.task=task;$('status').textContent='正在加载真实轨迹…';
 const clips=available(),c=clips.find(c=>c.task===task);if(!c)throw Error('该条件没有有效数据');await ensureExplorer(clipRecord({meta:c}));const clip=await loadClip(c);if(gen!==state.generation)return;
 for(const b of $('tasks').children)b.classList.toggle('active',b.dataset.task===task);
 A.setClip(clip);state.time=Math.max(0,clip.meta.representative_epoch_ms-clip.meta.start_epoch_ms);anchor();
 await loadB(gen);if(gen!==state.generation)return;
 await populateSegments();if(gen!==state.generation)return;populateDwell();drawTimeline();render(false);$('status').textContent='真实标记点回放。鼠标拖动旋转，滚轮缩放；未知触摸状态不计入稳定停留。';
}
async function loadB(gen=state.generation){
 const enabled=$('compare').checked;$('stageB').hidden=!enabled;$('taskB').disabled=!enabled;
 if(!enabled){$('align').checked=false;$('align').disabled=true;return;}
 const c=available().find(c=>c.task===$('taskB').value);if(!c)return;const clip=await loadClip(c);if(gen!==state.generation)return;
 if(!B)B=new Stage('B');B.setClip(clip);A.resize();B.resize();
 const verified=clip=>clip.meta.sync_status==='PHYSICAL_SYNC_VERIFIED';
 const eligible=verified(A.clip)&&verified(B.clip)&&A.clip.meta.events.some(e=>e.sync_eligible&&e.action.includes('DOWN'))&&B.clip.meta.events.some(e=>e.sync_eligible&&e.action.includes('DOWN'));
 $('align').disabled=!eligible;$('align').parentElement.title=eligible?'以已核验的按下事件为零点':'已检查时钟映射，尚缺独立触摸对齐证据；事件对齐暂不可用。';if(!eligible)$('align').checked=false;
}
async function populateSegments(){
 if(state.index.publication){options($('segment'),[['representative','典型姿态片段（下方可选全部停留）']],'representative');return;}
 const name=recordId();if(!segments[name])segments[name]=await (await request('/api/record?id='+name)).json();
 const items=[['representative','典型姿态片段']];let n=0;
 for(const r of segments[name].intervals.filter(r=>r.task===state.task)){
  const start=Math.max(r.context_start_ms,segments[name].checks.epoch_start_ms),end=Math.min(r.context_end_ms,segments[name].checks.epoch_end_ms);
  for(let s=start;s<end;s+=10000){const e=Math.min(s+10000,end);if(e-s<10)continue;const key='segment-'+n++;segments[key]={start:s,end:e,task:r.task};items.push([key,`${r.trial} · ${(s-start)/1000}–${((e-start)/1000).toFixed(1)} s`]);}
 }
 options($('segment'),items,'representative');
}
function thumbnail(canvas,clip){
 canvas.width=260;canvas.height=150;const ctx=canvas.getContext('2d'),md=clip.meta,k=nearestFrame(clip.data,md.stride,md.representative_epoch_ms-md.start_epoch_ms),r=clip.data.slice(k*md.stride,(k+1)*md.stride),[w,h,t]=md.device.size;
 const project=(x,y,z)=>[130+(w/2-x)*.6+z*.25,15+y*.65+z*.15];
 ctx.fillStyle='#edf3ed';ctx.strokeStyle='#a0b7a5';ctx.beginPath();for(const [i,p]of [[0,[0,0,0]],[1,[w,0,0]],[2,[w,h,0]],[3,[0,h,0]]]){const xy=project(...p);i?ctx.lineTo(...xy):ctx.moveTo(...xy);}ctx.closePath();ctx.fill();ctx.stroke();
 for(const [a,b,f]of connections()){const ap=Array.from(r.slice(OFF.local+a*3,OFF.local+a*3+3)),bp=Array.from(r.slice(OFF.local+b*3,OFF.local+b*3+3));if(![...ap,...bp].every(Number.isFinite))continue;ctx.strokeStyle='#'+(colors[f]||0x97aaa0).toString(16).padStart(6,'0');ctx.lineWidth=f===0?2:1.5;ctx.beginPath();ctx.moveTo(...project(...ap));ctx.lineTo(...project(...bp));ctx.stroke();}
 for(let m=0;m<20;m++){const p=Array.from(r.slice(OFF.local+m*3,OFF.local+m*3+3));if(!p.every(Number.isFinite))continue;ctx.fillStyle='#'+colors[Math.floor(m/4)].toString(16).padStart(6,'0');ctx.beginPath();ctx.arc(...project(...p),2,0,2*Math.PI);ctx.fill();}
}
async function changeDataset(){
 pause();state.cache.clear();const clips=available();if(!clips.length){$('status').textContent='这个组合没有有效记录，请选择其他手机或情境。';return;}
 const tasks=state.index.tasks;options($('taskB'),tasks.filter(t=>clips.some(c=>c.task===t.id)).map(t=>[t.id,t.name]),$('taskB').value||'TAP');$('tasks').innerHTML='';
 for(const [i,t]of tasks.entries()){
  const b=document.createElement('button');b.className='task';b.dataset.task=t.id;b.disabled=!clips.some(c=>c.task===t.id);b.innerHTML=`<span class="num">0${i+1}</span><b>${t.name}</b><small>${t.id}</small><canvas aria-label="真实典型姿态"></canvas>`;b.onclick=()=>chooseTask(t.id).catch(error);$('tasks').append(b);
 }
 const task=clips.some(c=>c.task===state.task)?state.task:clips[0].task;await chooseTask(task);
 const rec=recordId();await Promise.all(clips.map(async c=>{const clip=await loadClip(c);if(rec!==recordId())return;const canvas=$('tasks').querySelector(`[data-task="${c.task}"] canvas`);if(canvas)thumbnail(canvas,clip);}));
}
function populateDwell(){for(const b of $('tasks').children){const td=state.explorerRecords[recordId()]?.tasks[b.dataset.task],s=td?.thresholds[String(state.dwellThreshold)].summary;b.querySelector('small').textContent=s?`${s.episodes} 次 · ${(s.total_ms/1000).toFixed(3)} s（≥${state.dwellThreshold} ms）`:'无有效记录';}const eps=dwellChoice(A.clip)?.episodes||[];options($('dwellSelect'),[['none','选择停留，查看真实动作'],...eps.map((e,i)=>[String(i),`第 ${i+1} 次 · ${e.duration_ms.toFixed(0)} ms · 原始帧 ${e.start_frame}`])],'none');$('dwellSelect').disabled=!eps.length;}
async function showDwell(){
 if($('dwellSelect').value==='none')return;pause();const e=dwellChoice(A.clip).episodes[Number($('dwellSelect').value)];
 if(state.index.publication){const gen=state.generation,task=state.task;const clip=await loadClip({id:e.public_clip,meta:'dwell/'+e.public_clip+'.json'});if(gen!==state.generation||task!==state.task)return;A.setClip(clip);state.time=e.start_ms-clip.meta.start_epoch_ms;anchor();drawTimeline();render(false);return;}
 const md=segments[recordId()],interval=md.intervals.find(i=>i.task===state.task&&i.context_start_ms<=e.start_ms&&i.context_end_ms>=e.end_ms);
 const start=Math.max(interval.context_start_ms,md.checks.epoch_start_ms,e.start_ms-700),end=Math.min(interval.context_end_ms,md.checks.epoch_end_ms,e.end_ms+700,start+10000);
 const meta=await (await request(`/api/segment?record=${recordId()}&start=${start}&end=${end}&task=${state.task}`)).json(),data=new Float32Array(await (await request(meta.binary)).arrayBuffer());A.setClip({meta,data});state.time=e.start_ms-meta.start_epoch_ms;anchor();drawTimeline();render(false);
}
async function init(){
 state.index=await (await request('/outputs/index.json')).json();
 state.taskZones=(await (await request('/outputs/zones.json')).json()).records;
 state.heightBaselines=(await (await request('/outputs/calibration.json')).json()).records;
 const params=new URLSearchParams(location.search),requestedTask=params.get('task'),requestedThreshold=Number(params.get('threshold'));if(labels[requestedTask])state.task=requestedTask;if([100,200,300,400,500,600].includes(requestedThreshold)){state.dwellThreshold=requestedThreshold;$('dwellThreshold').value=requestedThreshold;$('dwellThresholdValue').textContent=requestedThreshold+' ms';}
 const requestedView=params.get('view');if(['front','back','side','oblique'].includes(requestedView))state.view=requestedView;
 for(const button of document.querySelectorAll('[data-view]'))button.classList.toggle('active',button.dataset.view===state.view);
 A=new Stage('A');const ps=[...new Set(state.index.clips.map(c=>c.participant))].sort((a,b)=>a-b);options($('participant'),ps.map(p=>[String(p),'P'+p]),'3');
 options($('phone'),Object.entries(state.index.devices).map(([k,v])=>[k,k+' · '+v.model]),'N6');options($('condition'),[['seated','坐姿'],['walking','行走 · 3 km/h']],'seated');
 $('dataset').textContent=`${ps.length} 位参与者 · ${new Set(state.index.clips.map(c=>`P${c.participant}_${c.phone}_${c.condition}`)).size} 条记录 · 六任务`;
 for(const id of ['participant','phone','condition'])$(id).onchange=()=>changeDataset().catch(error);
 $('play').onclick=()=>{if(!A.clip)return;if(state.playing)pause();else{if(state.time>=duration())state.time=0;state.playing=true;anchor();$('play').textContent='暂停';}};
 for(const [id,d]of [['prev',-1],['next',1]])$(id).onclick=()=>{pause();state.time=stepFrame(A.clip.data,A.clip.meta.stride,state.time,d);render(false);};
 const timeline=$('scrub').parentElement;timeline.onpointerdown=e=>{if(e.target===$('scrub'))return;timeline.setPointerCapture(e.pointerId);seekPointer(e);};timeline.onpointermove=e=>{if(timeline.hasPointerCapture(e.pointerId))seekPointer(e);};function seekPointer(e){pause();const rect=timeline.getBoundingClientRect();state.time=Math.max(0,Math.min(duration(),(e.clientX-rect.left)/rect.width*duration()));render(false);}
 $('scrub').oninput=()=>{pause();state.time=Number($('scrub').value);render(false);};$('rate').onchange=()=>{state.speed=Number($('rate').value);anchor();};
 for(const id of ['local','world'])$(id).onclick=()=>{state.world=id==='world';$('local').classList.toggle('active',!state.world);$('world').classList.toggle('active',state.world);render(false);};
 for(const btn of document.querySelectorAll('[data-view]'))btn.onclick=()=>{state.view=btn.dataset.view;A.view(state.view);B?.view(state.view);for(const b of document.querySelectorAll('[data-view]'))b.classList.toggle('active',b===btn);render(false);};
 for(const id of ['trajectory','zone','idlezone','screen','calibrated','heightline','taskUI'])$(id).onchange=()=>render(false);
 $('focusZone').onclick=()=>{pause();const helper=A.idlezone;if(!helper.visible)return;const centre=helper.box.getCenter(new THREE.Vector3()).applyMatrix4(helper.parent.matrix),size=helper.box.getSize(new THREE.Vector3()).length(),direction=A.camera.position.clone().sub(A.controls.target).normalize();A.focusedZone=true;A.glyphScale=Math.min(1,Math.max(size/80,.008));A.controls.target.copy(centre);A.camera.position.copy(centre).addScaledVector(direction,Math.max(size*2.5,2));A.controls.update();render(false);};
 $('dwellThreshold').oninput=()=>{pause();state.dwellThreshold=Number($('dwellThreshold').value);$('dwellThresholdValue').textContent=state.dwellThreshold+' ms';populateDwell();drawTimeline();render(false);};
 $('dwellSelect').onchange=()=>showDwell().catch(error);
 $('zeroContact').onclick=()=>{pause();render(false);const row=A.current.values;if(row[OFF.contact]!==1||!Number.isFinite(row[OFF.local+2]))return;state.manualBaselines.set(clipRecord(A.clip),{baseline_mm:row[OFF.local+2],method:'manual_contact_frame',source_frame:Math.round(row[1]),source_epoch_ms:A.clip.meta.start_epoch_ms+row[0]});$('calibrated').checked=true;render(false);};
 $('resetCalibration').onclick=()=>{state.manualBaselines.delete(clipRecord(A.clip));render(false);};
 $('compare').onchange=()=>loadB().then(()=>{drawTimeline();render(false);}).catch(error);$('taskB').onchange=()=>loadB().then(()=>render(false)).catch(error);$('align').onchange=()=>render(false);
 $('segment').onchange=async()=>{try{pause();if($('segment').value==='representative'){await chooseTask(state.task);return;}const s=segments[$('segment').value];const md=await (await request(`/api/segment?record=${recordId()}&start=${s.start}&end=${s.end}&task=${s.task}`)).json();const data=new Float32Array(await (await request(md.binary)).arrayBuffer());A.setClip({meta:md,data});state.time=0;anchor();drawTimeline();render(false);}catch(e){error(e);}};
 $('export').onclick=()=>{
  pause();const active=[A,...($('compare').checked&&B?[B]:[])];active.forEach(s=>s.resize());render(false);const width=active.reduce((a,s)=>a+s.renderer.domElement.width,0),height=Math.max(...active.map(s=>s.renderer.domElement.height));const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height+148;const ctx=canvas.getContext('2d');ctx.fillStyle='#f5f7f5';ctx.fillRect(0,0,width,height+148);let x=0;
  for(const s of active){ctx.drawImage(s.renderer.domElement,x,0);ctx.fillStyle='#244633';ctx.font='16px sans-serif';ctx.fillText(`${labels[s.clip.meta.task]} · P${s.clip.meta.participant} · ${s.clip.meta.phone} · ${s.clip.meta.condition} · ${s.clip.meta.source}`,x+12,height+24);ctx.font='12px sans-serif';ctx.fillText(`原始帧 ${Math.round(s.current.values[1])} · epoch ${(s.clip.meta.start_epoch_ms+s.current.values[0]).toFixed(3)} ms · 真实标记点 / Le 2019`,x+12,height+46);
   const m=s.current.height,cal=calibrationFor(s.clip);if(m){const txt=`${m.calibrated?'修正离屏':'标记点离屏'} ${m.height_mm.toFixed(1)} mm · 指甲 Z ${m.raw_mm.toFixed(2)} mm · ${Number.isFinite(m.baseline_mm)?`基线 ${m.baseline_mm.toFixed(2)} mm`:'无触摸基线'}`;ctx.fillText(txt,x+12,height+66);ctx.fillText(`校准参考点为显示示意，非指腹净距测量${cal.source_frame!==undefined?` · 校准源帧 ${cal.source_frame}`:''}`,x+12,height+85);
    if(!s.heightLabel.hidden){const scale=s.renderer.domElement.width/s.host.clientWidth,l=x+parseFloat(s.heightLabel.style.left)*scale,t=parseFloat(s.heightLabel.style.top)*scale;ctx.fillStyle='#ffffff';ctx.fillRect(l,t,Math.min(220*scale,s.renderer.domElement.width-(l-x)-8),54*scale);ctx.fillStyle='#a3411b';ctx.font=`${13*scale}px sans-serif`;ctx.fillText(`${m.calibrated?'修正离屏':'标记点离屏'} ${m.height_mm.toFixed(1)} mm`,l+8*scale,t+20*scale);ctx.font=`${10*scale}px sans-serif`;ctx.fillText(m.calibrated?'触摸基线修正参考 · 非指腹测量':'真实指甲标记点到屏幕平面',l+8*scale,t+39*scale);}
   }if(!s.uiPreview.hidden){const scale=s.renderer.domElement.width/s.host.clientWidth,box=s.uiPreview.getBoundingClientRect(),host=s.host.getBoundingClientRect(),px=x+(box.left-host.left)*scale,py=(box.top-host.top)*scale;ctx.fillStyle='#fff';ctx.fillRect(px,py,box.width*scale,box.height*scale);ctx.fillStyle='#356e4a';ctx.font=`${10*scale}px sans-serif`;ctx.fillText('控件放大 · 日志示意',px+8*scale,py+15*scale);ctx.drawImage(s.uiPreviewCanvas,px+8*scale,py+24*scale,(box.width-16)*scale,(box.height-32)*scale);}
   ctx.fillStyle='#245d48';ctx.font='12px sans-serif';ctx.fillText(s.zoneCaption||'三维区域已隐藏',x+12,height+108);ctx.fillText(s.dwellCaption||'',x+12,height+130);x+=s.renderer.domElement.width;}
  const a=document.createElement('a');a.download=`le2019_${recordId()}_${state.task}_${Math.round(A.current.values[1])}.png`;a.href=canvas.toDataURL('image/png');a.click();
 };
 await changeDataset();
 function tick(now){if(state.playing){state.time=playbackTime(state.anchorTime,state.anchorWall,now,state.speed,duration());if(state.time>=duration())pause();}render(state.playing);requestAnimationFrame(tick);}requestAnimationFrame(tick);
 window.addEventListener('resize',drawTimeline);
 // Small inspection surface for reproducible browser verification, no synthetic data.
 window.postureViewer={state,get stages(){return {A,B};},sample,render};
}
init().catch(error);
