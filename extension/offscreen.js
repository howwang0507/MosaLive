import {capturePipeline} from './engine.js';
import {SessionStats} from './session-stats.js';
let halt=null,tabId=null;
let stats=new SessionStats();
let lastGpuCheck=0;
let lastManualReset=-Infinity;
const emit=e=>{
 stats.accept(e);
 if(e.type==='metrics'&&Date.now()-lastGpuCheck>=15000){
  lastGpuCheck=Date.now();const currentStats=stats;
  fetch('http://localhost:8787/resources',{signal:AbortSignal.timeout(3500)}).then(r=>r.json()).then(data=>{
   if(stats===currentStats&&data.gpus?.length)stats.accept({type:'gpu',used_mib:Math.max(...data.gpus.map(g=>g.used_mib))});
  }).catch(()=>{});
 }
 return chrome.runtime.sendMessage({...e,target:'overlay',tabId}).catch(()=>{});
};
chrome.runtime.onMessage.addListener((m,s,reply)=>{
 if(m.target!=='offscreen')return;
 if(m.type==='state'){reply({ok:true,tabId,active:!!halt,...stats.snapshot()});return;}
 (async()=>{
 if(m.type==='manual-resync'){
  if(s.url!==chrome.runtime.getURL('background.js'))throw Error('無效的控制來源');
  if(!halt)throw Error('請先啟動字幕');
  if(Date.now()-lastManualReset<3000)throw Error('正在接續，請稍候三秒');
  lastManualReset=Date.now();
  halt.resetAudio();await emit({type:'status',clearPartial:true,text:'已略過積壓音訊，從現在重新接續；收音授權保留'});
 }
 if(m.type==='playback-paused'){
  if(s.tab?.id!==tabId)throw Error('不是目前收音分頁');
  await emit({type:'status',text:'主播放器已暫停 15 秒；仍監聽此分頁聲音'});
 }
 if(m.type==='resync'){
  if(s.tab?.id!==tabId)throw Error('不是目前收音分頁');
  halt?.resetAudio();
 }
 if(m.type==='asr'){
  if(s.tab?.id!==tabId||!['auto','stream-en','stream-ja','stream-ko'].includes(m.asrMode))throw Error('無效的辨識模式');
  if(!halt)throw Error('請先啟動字幕');
  halt.setAsrMode(m.asrMode);
 }
 if(m.type==='display'){
  if(s.tab?.id!==tabId||typeof m.sourceOnly!=='boolean')throw Error('不是目前收音分頁');
  if(!halt)throw Error('字幕尚未啟動');
  halt.setSourceOnly(m.sourceOnly);
 }
 if(m.type==='quality'){
  if(s.tab?.id!==tabId||typeof m.review!=='boolean')throw Error('不是目前收音分頁');
  if(!halt)throw Error('字幕尚未啟動');
  halt.setQuality(m.review);
 }
 if(m.type==='stop'){
  halt?.();halt=null;
  // Capture is stopped even when the old content script cannot receive a notice.
  await chrome.runtime.sendMessage({target:'overlay',tabId,type:'status',text:'已停止',clear:true}).catch(()=>{});
 }
 if(m.type==='start'){
  tabId=m.tabId;
  stats=new SessionStats();
  const stream=await navigator.mediaDevices.getUserMedia({audio:{mandatory:{chromeMediaSource:'tab',chromeMediaSourceId:m.id}},video:false});
  try{
   halt=await capturePipeline(stream,{worklet:'worklet.js',monitor:true,quality:m.review===true,sourceOnly:m.sourceOnly===true,asrMode:m.asrMode||'auto',onEvent:emit});
   stream.getTracks().forEach(track=>track.addEventListener('ended',()=>{halt=null;emit({type:'status',text:'音訊分享已結束，請重新啟動字幕',clear:true});},{once:true}));
  }catch(e){stream.getTracks().forEach(t=>t.stop());throw e;}
  await chrome.runtime.sendMessage({target:'overlay',tabId,type:'status',text:'正在收取此分頁全部聲音 · 請暫停其他播放器 · 自動識別語言',reset:true});
 }
 reply({ok:true});
 })().catch(e=>{chrome.runtime.sendMessage({target:'overlay',tabId,type:'status',text:e.message});reply({ok:false,error:e.message});});
 return true;
});
