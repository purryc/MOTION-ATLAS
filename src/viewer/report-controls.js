const labels={READ:'阅读',WRITE:'输入',TAP:'点击',DRAG:'拖动',SCROLL_V:'竖滚',SCROLL_H:'横滚'};
const root=document.querySelector('#reportExplorer');
async function init(){
 const res=await fetch('explorer/report-controls.json');if(!res.ok)throw Error('请先生成交互分析数据');const data=await res.json();
 const toggle=document.querySelector('#reportHeightToggle'),slider=document.querySelector('#reportDwellThreshold'),table=document.querySelector('table.data:not(.dwell-height-table)');
 const heads=Array.from(table.querySelectorAll('thead th')),heightIndex=heads.findIndex(h=>h.textContent==='Z / mm'),rows=Array.from(table.querySelectorAll('tbody tr')),tasks=Object.keys(labels);
 function height(){
  const corrected=toggle.checked;heads[heightIndex].textContent=corrected?'修正离屏 / mm':'Z / mm';rows.forEach((r,i)=>r.children[heightIndex].textContent=data.height[tasks[i]][corrected?'corrected':'raw'].text);
  for(const name of ['task_comparison','phone_condition','height_distribution']){
   const img=document.querySelector(`img[src*="figures/${name}"]`),file=name+(corrected?'_corrected':'');img.src=`figures/${file}.png`;img.parentElement.href=`figures/${file}.svg`;img.alt=corrected?'参与者等权修正离屏参考高度（下限 0 mm）':name;
  }
  document.querySelector('#heightModeInfo').textContent=corrected?'修正参考 = max(0, 指甲 Z − 同记录触摸基线)，先逐帧取下限，再记录内汇总、参与者等权。此开关切换拇指绝对高度表和三张图；正文检验和其他手指保留原始研究结果。此量非指腹净距。':'原始指甲 Z：有符号屏幕坐标；切换可看修正后的非负离屏参考。正文检验和其他手指为原始研究结果。';
 }
 function dwell(){
  const threshold=slider.value;document.querySelector('#reportDwellValue').textContent=threshold+' ms';const selected=data.thresholds[threshold];
  document.querySelector('#reportDwellSummary').innerHTML='<table class="data"><thead><tr><th>任务</th><th>停留次数</th><th>累计 / s</th><th>单次中位 / ms</th><th>有停留人数</th><th>有效人数</th><th>参与者等权停留占比</th></tr></thead><tbody>'+tasks.map(t=>{const s=selected[t];return `<tr><td>${labels[t]}</td><td>${s.episodes}</td><td>${s.total_s.toFixed(3)}</td><td>${s.median_ms===null?'—':s.median_ms.toFixed(0)}</td><td>${s.participants_with_dwell}</td><td>${s.participants}</td><td>${s.participant_equal_occupancy_percent.toFixed(2)}%</td></tr>`;}).join('')+'</tbody></table>';
 }
 toggle.onchange=height;slider.oninput=dwell;height();dwell();
 window.reportExplorer={data,height,dwell};
}
init().catch(e=>root.querySelector('#reportDwellSummary').textContent=e.message+'，可重新载入报告。');
