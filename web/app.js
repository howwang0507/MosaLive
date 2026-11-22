import {capturePipeline,CaptionState,wav,requestSegment} from './engine.js';
const samplePath=()=>'/test-'+document.getElementById('sampleLanguage').value+'.wav';
const $=id=>document.getElementById(id);let halt=null,timer=null,expiry=null,state=new CaptionState(),records=[],url=null,epoch=0;
function clear(){clearTimeout(expiry);state.clear();$('translation').textContent='';$('original').textContent='';}
// Keep the latest caption visible long enough to read a translated line.
let holdMs=5000;
try{const saved=localStorage.getItem('mosaHoldMs');if(saved!==null&&[-1,0,2000,3000,5000,8000].includes(Number(saved)))holdMs=Number(saved);}catch{}
$('holdMs').value=String(holdMs);
function expire(){clearTimeout(expiry);const text=$('displayMode').value==='original'?$('original').textContent:$('translation').textContent||$('original').textContent;const duration=holdMs===-1?Math.min(8000,Math.max(2500,1500+Array.from(text).length*120)):holdMs;if(duration)expiry=setTimeout(clear,duration);}
$('holdMs').onchange=e=>{const value=Number(e.target.value);if(![-1,0,2000,3000,5000,8000].includes(value))return;holdMs=value;expire();try{localStorage.setItem('mosaHoldMs',String(value));}catch{}};
function stop(){epoch++;halt?.();halt=null;clearInterval(timer);clearTimeout(expiry);$('video').pause();$('video').loop=false;clear();$('status').textContent='已停止';}
function receive(e){
 if(e.type==='activity'){$('status').textContent=e.text;return;}
 if(e.type==='metrics'){$('metrics').textContent='已收音 '+Math.round(e.received_audio_ms/1000)+' 秒 · 略過 '+(e.dropped_audio_ms/1000).toFixed(1)+' 秒 · 重送嘗試 '+((e.replayed_audio_ms||0)/1000).toFixed(1)+' 秒 · 重新連線 '+e.reconnects+' 次';return;}
 if(e.type==='status'){$('status').textContent=e.text;if(e.clearPartial)clear();return;}
 if(e.type==='partial'){
  if(!state.acceptPartial(e))return;
  if(e.translation)$('original').hidden=$('displayMode').value==='zh';
  if(!e.translation&&$('translation').textContent&&$('displayMode').value!=='original'){$('status').textContent='上一段字幕 · 下一段翻譯中';return;}
  $('translation').textContent=e.translation||'';$('original').textContent=e.original||'';expire();$('status').textContent=e.phase==='asr'?'正在聽 · 原文可能修訂':e.phase==='review'?'機器校對中 · 文字仍可能修訂':'暫定字幕 · 翻譯中，文字可能修訂';$('latency').textContent=e.capture_to_caption_ms!=null?'本句開始至這次更新：約 '+Math.round(e.capture_to_caption_ms)+' ms':'送出至首段字幕：約 '+Math.round(e.first_visible_ms)+' ms';return;
 }
 if(!state.accept(e))return;
 records.push({...e,displayed_at:new Date().toISOString()});if(records.length>500)records.shift();
 $('translation').textContent=state.lines.map(x=>x.translation).join('\n');$('original').textContent=e.original;
 $('original').hidden=$('displayMode').value==='zh'&&!e.translation_unavailable;
 $('status').textContent=e.mode==='fixture'?'介面示範 · 非模型結果':e.reviewed?'已完成機器校對 · 不代表正確／未人工校對':'已收到模型結果 · 未人工校對';
 if(e.needs_human_review)$('status').textContent+=e.asr_uncertain?' · 原文辨識不確定':' · 數字、否定或用語待確認';
 if(e.translation_unavailable)$('status').textContent='翻譯暫時不可用，先保留原文；稍後自動嘗試恢復';
 $('latency').textContent=e.mode==='fixture'?'示範模式不計延遲':e.after_speech_ms!=null?'停句至定稿：約 '+Math.round(e.after_speech_ms)+' ms':(e.first_visible_ms!=null?'首段 '+Math.round(e.first_visible_ms)+' ms · ':'')+'定稿 '+Math.round(e.transport_model_ms)+' ms（送出後）';
 $('log').textContent=JSON.stringify(records.slice(-5),null,2);expire();
}
$('demo').onclick=async()=>{stop();const token=epoch,items=await(await fetch('/fixtures.json')).json();if(token!==epoch)return;records=[];state=new CaptionState();let n=0;
 const next=()=>{const x=items[n%items.length];receive({...x,type:'final',seq:n++,mode:'fixture'});};next();timer=setInterval(next,3000);};
async function start(stream,monitor=false,token=epoch){if(token!==epoch){stream.getTracks().forEach(t=>t.stop());return;}state=new CaptionState();records=[];const h=await capturePipeline(stream,{monitor,quality:$('quality').value==='review',asrMode:$('asrMode').value,sourceOnly:$('displayMode').value==='original',onEvent:e=>{if(token===epoch)receive(e);}});if(token!==epoch)h();else halt=h;}
$('capture').onclick=async()=>{stop();const token=epoch;try{const s=await navigator.mediaDevices.getDisplayMedia({video:true,audio:true});if(token!==epoch){s.getTracks().forEach(t=>t.stop());return;}if(!s.getAudioTracks().length){s.getTracks().forEach(t=>t.stop());throw Error('未取得音訊，請選擇瀏覽器分頁並勾選分享音訊');}await start(s,false,token);if(token===epoch)$('status').textContent='正在接收分頁音訊';}catch(e){if(token===epoch)$('status').textContent=e.message;}};
$('file').onchange=async e=>{stop();const token=epoch;if(!e.target.files[0])return;if(url)URL.revokeObjectURL(url);url=URL.createObjectURL(e.target.files[0]);$('video').src=url;$('placeholder').hidden=true;
 try{await $('video').play();if(token!==epoch)return;if(!$('video').captureStream)throw Error('此瀏覽器沒有影片音訊擷取功能，請用 Chrome 或分享本地影片分頁');await start($('video').captureStream(),false,token);if(token===epoch)$('status').textContent='正在播放本地音訊';}catch(e){if(token===epoch)$('status').textContent=e.message;}};
$('video').addEventListener('ended',()=>halt?.flush?.());
let videoWaitingAt=null;
['waiting','stalled'].forEach(type=>$('video').addEventListener(type,()=>{videoWaitingAt??=performance.now();}));
$('video').addEventListener('seeking',()=>{videoWaitingAt=null;halt?.resetAudio?.();});
$('video').addEventListener('playing',()=>{if(videoWaitingAt!==null&&performance.now()-videoWaitingAt>=1500)halt?.resetAudio?.();videoWaitingAt=null;});
$('stop').onclick=stop;$('clear').onclick=clear;
$('quality').onchange=stop;
$('asrMode').onchange=e=>{clear();halt?.setAsrMode?.(e.target.value);};
$('size').oninput=e=>$('caption').style.fontSize=e.target.value+'px';
$('opacity').oninput=e=>$('caption').style.background='rgba(0,0,0,'+e.target.value/100+')';
$('position').onchange=e=>{$('caption').style.top=e.target.value==='top'?'8%':'auto';$('caption').style.bottom=e.target.value==='bottom'?'12%':'auto';};
function displayCaptions(mode){
 $('original').hidden=mode==='zh';$('translation').hidden=mode==='original';
 $('original').style.fontSize=mode==='original'?'1em':'';
}
try{const saved=localStorage.getItem('mosaDisplayMode');if(['both','zh','original'].includes(saved))$('displayMode').value=saved;}catch{}
displayCaptions($('displayMode').value);
$('displayMode').onchange=e=>{displayCaptions(e.target.value);halt?.setSourceOnly?.(e.target.value==='original');clear();try{localStorage.setItem('mosaDisplayMode',e.target.value);}catch{}};
$('export').onclick=()=>{const u=URL.createObjectURL(new Blob([JSON.stringify({note:'機器結果未人工校對；fixture 為預寫示範',records},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download='mosasub-session.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);};
window.addEventListener('beforeunload',stop);

$('sample').onclick=async()=>{
 stop();const token=epoch;state=new CaptionState();records=[];
 const controller=new AbortController();halt=()=>controller.abort();
 let ctx;
 try{
  $('status').textContent='正在讀取選定語言的合成音訊，交給真實模型辨識…';
  ctx=new AudioContext({sampleRate:16000});
  const bytes=await(await fetch(samplePath(),{signal:controller.signal})).arrayBuffer();
  const decoded=await ctx.decodeAudioData(bytes);
  if(token!==epoch)return;
  $('video').src=samplePath();$('placeholder').hidden=true;await $('video').play();
  const started=performance.now();
  const result=await requestSegment(wav(decoded.getChannelData(0)),{quality:$('quality').value==='review',sourceOnly:$('displayMode').value==='original',signal:controller.signal,onPartial:p=>{if(token===epoch)receive({...p,seq:0});}});
  if(token===epoch){receive({...result,seq:0,type:'final',transport_model_ms:performance.now()-started});}
 }catch(e){if(token===epoch){clear();$('status').textContent=e.message;}}
 finally{if(ctx)await ctx.close();}
};
async function readiness(){try{const h=await(await fetch('/health')).json();$('health').textContent=h.ready?'● 本機自動語言辨識＋繁中翻譯已就緒':h.models?.error?'模型啟動失敗：'+h.models.error:h.configured?'◌ 模型載入中，請稍候…':'尚未啟動本機模型，請雙擊「開始測試.command」';}catch{$('health').textContent='本機服務未啟動';}}
readiness();setInterval(readiness,5000);
$('streamsample').onclick=async()=>{stop();const token=epoch;try{
 $('video').src=samplePath();$('video').loop=true;$('placeholder').hidden=true;await $('video').play();
 if(token!==epoch)return;
 if(!$('video').captureStream)throw Error('請使用 Google Chrome 測試連續收音');
 await start($('video').captureStream(),false,token);
 if(token===epoch)$('status').textContent='循環播放選定語言，正在連續辨識';
}catch(e){if(token===epoch)$('status').textContent=e.message;}};
