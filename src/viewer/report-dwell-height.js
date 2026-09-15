const data=JSON.parse(document.querySelector('#naturalDwellHeightData').textContent);
const slider=document.querySelector('#reportDwellThreshold'),toggle=document.querySelector('#reportHeightToggle');
function update(){
 const threshold=slider.value,s=data.thresholds[threshold],corrected=toggle.checked,m=s[corrected?'corrected':'raw'];
 document.querySelector('#dwellHeightCurrent').textContent=`当前查看：≥${threshold} ms · ${corrected?'修正离屏参考':'原始指甲 Z'} · 典型高度 ${m.median_mm.toFixed(1)} mm，中间 50% ${m.p25_mm.toFixed(1)}–${m.p75_mm.toFixed(1)} mm。`;
 const names={READ:'阅读',WRITE:'输入',TAP:'点击',DRAG:'拖动',SCROLL_V:'竖滚',SCROLL_H:'横滚'};
 document.querySelector('#dwellHeightCoverage').textContent=`${s.participants} 位有停留参与者 · ${s.records} 条有停留记录 · ${s.episodes} 个片段，其中${Object.entries(s.tasks).map(([t,n])=>`${names[t]} ${n} 个`).join('、')}。`;
}
slider.addEventListener('input',update);toggle.addEventListener('change',update);update();
