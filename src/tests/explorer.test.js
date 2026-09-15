import test from 'node:test';
import assert from 'node:assert/strict';
import {eligibleEpisodes,episodeAt,clippedEpisodes,uiAt,pixelToPhone,uiCanvasPoint} from '../viewer/explorer.js';
test('duration thresholds filter complete episodes without truncation; current-frame lookup is separate',()=>{
 const episodes=[{start_ms:1000,end_ms:1095.833333,duration_ms:100},{start_ms:2000,end_ms:2595.833333,duration_ms:600}];
 assert.deepEqual(eligibleEpisodes(episodes,500),[episodes[1]]);assert.equal(episodeAt(episodes,1500),null);assert.equal(episodeAt(episodes,2400).duration_ms,600);
 const clipped=clippedEpisodes(episodes,2200,2500);assert.equal(clipped[0].start_ms,0);assert.equal(clipped[0].end_ms,300);assert.equal(clipped[0].duration_ms,600);
});
test('logged touch state follows the selected trial and never leaks into another trial',()=>{
 const ui={trials:[{trial:'TAP-1',start_ms:1000,end_ms:2000},{trial:'TAP-2',start_ms:3000,end_ms:4000}],events:[[1100,20,30,'DOWN','TAP-1'],[1500,40,50,'MOVE','TAP-1'],[3100,70,80,'DOWN','TAP-2']]};
 assert.equal(uiAt(ui,1600).event[1],40);assert.equal(uiAt(ui,2600).event,null);assert.equal(uiAt(ui,3050).event,null);assert.equal(uiAt(ui,3150).event[1],70);
 const d={screen:[70,140],offset:[5,10]};assert.deepEqual(pixelToPhone(0,0,d,[100,200]),[75,10,0]);assert.deepEqual(pixelToPhone(100,200,d,[100,200]),[5,150,0]);
});

test('calibrated UI projects into recorded XY and leaves original pixel mapping available',()=>{
 const device={screen:[74.2,136.3],offset:[4.15,11.5]},pixels=[1440,2560],canvas=[512,940],fit=[.053,-8.8,.057,-12.5],x=638,y=1007;
 const [cx,cy]=uiCanvasPoint(x,y,device,pixels,canvas,fit);
 assert.ok(Math.abs((4.15+74.2-cx/512*74.2)-(fit[0]*x+fit[1]))<1e-9);
 assert.ok(Math.abs((11.5+cy/940*136.3)-(fit[2]*y+fit[3]))<1e-9);
 assert.deepEqual(uiCanvasPoint(x,y,device,pixels,canvas,null),[x/1440*512,y/2560*940]);
 assert.deepEqual(fit,[.053,-8.8,.057,-12.5]);
});
