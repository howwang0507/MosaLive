(()=>{
 if(window.__mosaOverlay)return;window.__mosaOverlay=true;
 const key='mosaOverlaySettings',defaults={size:26,opacity:80,displayMode:'both',review:false,asrMode:'auto',holdMs:5000,x:.5,y:.82};
 let captionCount=0,closed=false,pendingPartial=null,partialTimer=null,lastPartialAt=0,statusTimer=null;
 defaults.outline=false;defaults.clickThrough=false;defaults.finalOnly=false;defaults.stablePreview=false;defaults.stableOriginal=false;
 let settings={...defaults},seq=-1,latestSeq=-1,expiry,saveTimer,dirty=false;
 const host=document.createElement('div'),shadow=host.attachShadow({mode:'closed'});
 host.id='mosa-sub-live';
 host.style.cssText='position:fixed;width:min(80vw,960px);z-index:2147483647;pointer-events:none';
 shadow.innerHTML=`<style>
 :host{color-scheme:dark}*{box-sizing:border-box}
 .box{color:white;text-align:center;font:26px system-ui;border-radius:12px;padding:10px 16px;overflow-wrap:anywhere}
 .bar{display:flex;gap:8px;justify-content:center;align-items:center;pointer-events:auto;font:13px system-ui}
 button,select{font:inherit;color:#fff;background:#242a35;border:1px solid #8290a6;border-radius:6px;padding:6px;cursor:pointer}
 button:focus-visible,select:focus-visible,input:focus-visible{outline:3px solid #80cfff}
 .drag{touch-action:none;cursor:grab}.drag:active{cursor:grabbing}
 .panel{pointer-events:auto;display:flex;gap:10px;flex-wrap:wrap;justify-content:center;font:14px system-ui;padding:10px 0}
 [hidden]{display:none!important}label{display:flex;align-items:center;gap:5px}input[type=range]{width:100px}
 .status,.hint{font:12px system-ui;color:#e0e7f0}.status{margin:6px}.original{font-size:.65em}
 .original,.translated{white-space:pre-line;max-height:25vh;overflow:auto;pointer-events:auto}
 .outline .original,.outline .translated{text-shadow:-1px -1px 1px #000,1px -1px 1px #000,-1px 1px 1px #000,1px 1px 1px #000,0 2px 4px #000}
 .through,.through *{pointer-events:none!important}.through .bar,.through .panel,.through .status,.through .hint{display:none!important}
 .box{position:relative;min-height:92px;font-family:"Segoe UI","Microsoft JhengHei",system-ui,sans-serif;line-height:1.5;padding:12px 38px;border-radius:10px}
 .original{color:#d6e2eb;line-height:1.45}.original[data-early]{opacity:.75;font-style:italic}.translated{font-weight:600;line-height:1.5;letter-spacing:.015em}
 .original:not(:empty)+.translated:not(:empty){margin-top:7px}
 .original,.translated{max-height:28vh;scrollbar-width:thin;scrollbar-color:#71818d transparent}
 .bar{position:absolute;right:5px;top:6px;gap:4px;margin:0;flex-direction:column;flex-wrap:nowrap}
 .bar button{padding:4px;width:24px;height:24px;min-height:24px;display:inline-flex;align-items:center;justify-content:center;border-radius:5px}
 .bar svg{width:15px;height:15px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round;pointer-events:none}
 .bar button[aria-pressed="true"],.bar button[aria-expanded="true"]{background:#3a5260;border-color:#a9d7e5}
 .quiet-toggle .eye-slash{display:none}.quiet .quiet-toggle .eye-slash{display:block}
 .box{min-height:120px}.bar .close{font-size:20px;line-height:1;color:#f0c3bb}
 .through .bar{display:flex!important}.through .bar button{display:none}.through .bar .close{display:inline-flex;pointer-events:auto!important}
 button:hover,select:hover{background:#35424f}
 .panel{background:rgba(23,32,41,.96);border:1px solid #586b7b;border-radius:8px;padding:14px;gap:14px;max-height:35vh;overflow:auto;margin-bottom:10px}
 .panel label{line-height:1.5}.panel input[type=text]{max-width:160px}
 .status,.hint{font-size:11px;line-height:1.5;color:#bdcbd5;overflow-wrap:anywhere}
 .status{font-variant-numeric:tabular-nums;margin:5px 0}.hint:empty{display:none}
 .quiet .status[data-caption="true"]{display:none}.quiet .bar{opacity:.55}.quiet:hover .bar,.quiet:focus-within .bar{opacity:1}
 .box.through{min-height:0;padding:12px 20px}
 @media(max-width:600px){.box{padding:10px 34px}.box.through{padding:10px 12px}.panel{max-height:30vh;justify-content:flex-start}.panel label{flex-wrap:wrap}}
 </style><section class="box" aria-label="MosaSub 字幕">
 <div class="bar"><button class="drag" aria-label="移動字幕" title="拖曳移動字幕；方向鍵微調"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v18M3 12h18M9 6l3-3 3 3M9 18l3 3 3-3M6 9l-3 3 3 3M18 9l3 3-3 3"/></svg></button><button class="toggle" aria-label="字幕設定" title="字幕設定" aria-expanded="false"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 3-.5 3-2 1.2L3.7 6.2l-2 3.5L4 11.6v2.3l-2.3 1.9 2 3.5 2.8-1 2 1.2.5 2.5h4l.5-2.5 2-1 2.8.8 2-3.5-2.3-1.9v-2.3l2.3-1.9-2-3.5-2.8 1-2-1.2L13 3Z"/><circle cx="11" cy="12.5" r="3"/></svg></button><button class="quiet-toggle" aria-label="專心閱讀" aria-pressed="false" title="隱藏狀態資訊"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/><path class="eye-slash" d="m3 3 18 18"/></svg></button></div>
 <div class="panel" hidden>
 <label>字級 <input class="size" type="range" min="16" max="36" aria-label="字幕字級"><output class="sizeValue"></output></label>
 <label>背景 <input class="opacity" type="range" min="0" max="100" aria-label="背景不透明度"><output class="opacityValue"></output></label>
 <label>顯示 <select class="language"><option value="both">雙字幕（原文＋繁中）</option><option value="zh">僅繁中</option><option value="original">僅原文（英文／日文／韓文等）</option></select></label>
 <label>翻譯 <select class="quality"><option value="review">二次校對（較慢）</option><option value="fast">即時翻譯（含前文用語）</option></select></label>
 <label>辨識 <select class="asr"><option value="auto">自動多語（建議）</option><option value="stream-en">鎖定英文</option><option value="stream-ja">鎖定日文</option><option value="stream-ko">鎖定韓文</option></select></label>
 <button class="reset">重設位置</button>
 <label><input class="outline-option" type="checkbox">文字描邊（可搭配透明背景）</label>
 <label><input class="final-option" type="checkbox">只顯示定稿（減少文字跳動）</label>
 <label><input class="stable-option" type="checkbox">提前顯示穩定譯文（較早出現，定稿可能修訂）</label><label><input class="stable-original-option" type="checkbox">定稿前先顯示原文（需開啟「只顯示定稿」；中文仍等定稿）</label>
 <label><input class="through-option" type="checkbox">點擊穿透（在收音面板解除）</label>
 <label>字幕停留 <select class="hold"><option value="-1">依字數自動（2.5–8 秒）</option><option value="2000">2 秒</option><option value="3000">3 秒</option><option value="5000">5 秒（建議）</option><option value="8000">8 秒</option><option value="0">直到下一句／手動清除</option></select></label><button class="clear-caption">清除字幕</button>
 </div><div class="hint" role="status"></div><div class="status"></div><div class="original"></div><div class="translated" aria-live="polite"></div></section>`;
 const $=s=>shadow.querySelector(s),box=$('.box'),original=$('.original'),translated=$('.translated'),status=$('.status'),hint=$('.hint');
 const clamp=(n,a,b)=>Math.min(b,Math.max(a,n));
 const closeButton=document.createElement('button');closeButton.className='close';closeButton.textContent='×';closeButton.title='停止收音並關閉字幕';closeButton.setAttribute('aria-label',closeButton.title);$('.bar').prepend(closeButton);
 closeButton.onclick=async()=>{
  closeButton.disabled=true;
  try{const result=await chrome.runtime.sendMessage({target:'capture-close'});if(!result?.ok)throw Error(result?.error||'關閉控制未回應：請在 chrome://extensions 重新載入 MosaSub，再重新整理影片分頁');closed=true;clear();clearTimeout(statusTimer);host.style.display='none';}
  catch(error){hint.textContent=error.message;}finally{closeButton.disabled=false;}
 };
 function playerBounds(){
  const video=document.querySelector('[data-a-target="video-player"] video')||document.querySelector('video.html5-main-video')||document.querySelector('video');
  const r=video?.getBoundingClientRect();
  if(r&&r.width>150&&r.height>100){const left=Math.max(0,r.left),top=Math.max(0,r.top),right=Math.min(innerWidth,r.right),bottom=Math.min(innerHeight,r.bottom);if(right-left>150&&bottom-top>100)return {left,top,width:right-left,height:bottom-top};}
  return {left:0,top:0,width:innerWidth,height:innerHeight};
 }
 let quietReading=false;
 $('.quiet-toggle').onclick=()=>{quietReading=!quietReading;settings.quietReading=quietReading;paint();save();};
 function position(){
  if(closed)return;
  const b=playerBounds();host.style.width=Math.min(960,b.width*.92)+'px';
  const r=host.getBoundingClientRect(),bottom=Math.max(b.top,b.top+b.height-48-r.height);
  host.style.left=clamp(b.left+settings.x*b.width-r.width/2,b.left,Math.max(b.left,b.left+b.width-r.width))+'px';
  host.style.top=clamp(b.top+settings.y*b.height-r.height/2,b.top,bottom)+'px';
 }
 function paint(){
  $('.quiet-toggle').setAttribute('aria-pressed',String(quietReading));$('.quiet-toggle').title=quietReading?'顯示狀態資訊':'隱藏狀態資訊';
  box.style.fontSize=settings.size+'px';box.style.background='rgba(0,0,0,'+settings.opacity/100+')';
  box.className='box'+(settings.outline?' outline':'')+(settings.clickThrough?' through':'')+(quietReading?' quiet':'');
  $('.outline-option').checked=settings.outline;$('.through-option').checked=settings.clickThrough;
  $('.final-option').checked=settings.finalOnly;$('.stable-option').checked=settings.stablePreview;$('.stable-original-option').checked=settings.stableOriginal;
  original.hidden=settings.displayMode==='zh';
  translated.hidden=settings.displayMode==='original';
  original.style.fontSize=settings.displayMode==='original'?'1em':'.78em';
  $('.size').value=settings.size;$('.sizeValue').textContent=settings.size+'px';
  $('.opacity').value=settings.opacity;$('.opacityValue').textContent=settings.opacity+'%';
  $('.language').value=settings.displayMode;$('.quality').value=settings.review?'review':'fast';
  $('.asr').value=settings.asrMode;
  $('.hold').value=String(settings.holdMs);
  position();
 }
 async function settingsRequest(type,settings){
  const result=await chrome.runtime.sendMessage({target:'settings',type,settings});
  if(!result?.ok)throw Error(result?.error||'設定服務無回應');
  return result.settings;
 }
 function save(){
  dirty=true;clearTimeout(saveTimer);
  saveTimer=setTimeout(()=>settingsRequest('set',settings).catch(()=>{hint.textContent='設定無法保存，請重新載入擴充套件';}),120);
 }
 $('.asr').onchange=async e=>{
  settings.asrMode=e.target.value;clear();save();
  const response=await chrome.runtime.sendMessage({target:'offscreen',type:'asr',asrMode:settings.asrMode}).catch(()=>null);
  hint.textContent=response?.ok?'辨識模式已切換；鎖定模式會把所有語音依指定語言辨識。':'已保存，下次啟動字幕套用。';
 };
 const attach=()=>{(document.fullscreenElement||document.body).append(host);position();};
 attach();paint();document.addEventListener('fullscreenchange',attach);window.addEventListener('resize',position);
 new ResizeObserver(position).observe(host);
 const followPlayer=setInterval(()=>{if(!document.hidden&&!closed)position();},750);
 window.addEventListener('pagehide',()=>{clearInterval(followPlayer);clearTimeout(partialTimer);clearTimeout(statusTimer);},{once:true});
 settingsRequest('get').then(data=>{
  if(dirty)return;const s=data||{};
  for(const k of ['size','opacity','x','y'])if(typeof s[k]==='number'&&Number.isFinite(s[k]))settings[k]=s[k];
  settings.size=clamp(settings.size,16,36);settings.opacity=clamp(settings.opacity,0,100);
  settings.x=clamp(settings.x,0,1);settings.y=clamp(settings.y,0,1);
  if(typeof s.review==='boolean')settings.review=s.review;
  if(typeof s.quietReading==='boolean'){settings.quietReading=s.quietReading;quietReading=s.quietReading;}
  for(const k of ['outline','clickThrough','finalOnly','stablePreview','stableOriginal'])if(typeof s[k]==='boolean')settings[k]=s[k];
  if([-1,0,2000,3000,5000,8000].includes(s.holdMs))settings.holdMs=s.holdMs;
  if(['auto','stream-en','stream-ja','stream-ko'].includes(s.asrMode))settings.asrMode=s.asrMode;
  settings.displayMode=['both','zh','original'].includes(s.displayMode)?s.displayMode:s.bilingual===false?'zh':'both';
  paint();
 }).catch(()=>{hint.textContent='無法讀取設定，使用預設值';});
 $('.toggle').onclick=()=>{const p=$('.panel');p.hidden=!p.hidden;$('.toggle').setAttribute('aria-expanded',String(!p.hidden));position();};
 for(const k of ['size','opacity'])$('.'+k).oninput=e=>{settings[k]=Number(e.target.value);paint();save();};
 $('.language').onchange=e=>{
  settings.displayMode=e.target.value;clear();paint();save();
  chrome.runtime.sendMessage({target:'offscreen',type:'display',sourceOnly:settings.displayMode==='original'}).then(r=>{
   hint.textContent=r?.ok?'顯示已切換，下一段音訊套用；僅原文模式會跳過翻譯。':'顯示已切換，重新啟動字幕後套用處理模式。';
  }).catch(()=>{hint.textContent='顯示已切換，重新啟動字幕後套用處理模式。';});
 };
 $('.quality').onchange=async e=>{
  const control=e.currentTarget,previous=settings.review,next=control.value==='review';control.disabled=true;
  try{
   const result=await chrome.runtime.sendMessage({target:'offscreen',type:'quality',review:next});
   if(!result?.ok)throw Error(result?.error||'請先啟動字幕');
   settings.review=next;save();hint.textContent='模式已切換：下一個送出的片段生效；處理中的片段維持原模式。';
  }catch(error){settings.review=previous;hint.textContent=error.message;}
  finally{control.disabled=false;paint();}
 };
 $('.reset').onclick=()=>{settings.x=defaults.x;settings.y=defaults.y;paint();save();};
 $('.outline-option').onchange=e=>{settings.outline=e.target.checked;paint();save();};
 $('.final-option').onchange=e=>{settings.finalOnly=e.target.checked;clear();paint();save();};
 $('.stable-option').onchange=e=>{settings.stablePreview=e.target.checked;clear();paint();save();};$('.stable-original-option').onchange=e=>{settings.stableOriginal=e.target.checked;clear();paint();save();};
 $('.through-option').onchange=e=>{settings.clickThrough=e.target.checked;paint();save();};
 let drag=null;const handle=$('.drag');
 handle.onpointerdown=e=>{if(e.button!==0)return;const r=host.getBoundingClientRect();drag={id:e.pointerId,x:e.clientX,y:e.clientY,cx:r.left+r.width/2,cy:r.top+r.height/2};handle.setPointerCapture(e.pointerId);e.preventDefault();};
 handle.onpointermove=e=>{if(!drag||drag.id!==e.pointerId)return;const b=playerBounds();settings.x=clamp((drag.cx+e.clientX-drag.x-b.left)/b.width,0,1);settings.y=clamp((drag.cy+e.clientY-drag.y-b.top)/b.height,0,1);position();};
 const endDrag=()=>{if(drag){drag=null;save();}};handle.onpointerup=endDrag;handle.onpointercancel=endDrag;handle.onlostpointercapture=endDrag;
 handle.onkeydown=e=>{const d={ArrowLeft:[-10,0],ArrowRight:[10,0],ArrowUp:[0,-10],ArrowDown:[0,10]}[e.key];if(!d)return;e.preventDefault();const b=playerBounds();settings.x=clamp(settings.x+d[0]/b.width,0,1);settings.y=clamp(settings.y+d[1]/b.height,0,1);position();save();};
 // Stable previews never replace a final before it has been readable for finalMinMs.
 let finalVisible=false,finalShownAt=0,finalMinMs=0,earlyTimer=null;
 function clear(){finalVisible=false;clearTimeout(earlyTimer);earlyTimer=null;clearTimeout(expiry);clearTimeout(partialTimer);partialTimer=null;pendingPartial=null;original.removeAttribute('data-early');original.textContent='';translated.textContent='';}
 function expire(){
  clearTimeout(expiry);
  const text=settings.displayMode==='original'?original.textContent:translated.textContent||original.textContent;
  const length=Array.from(text).length;
  const duration=settings.holdMs===-1?Math.min(8000,Math.max(2500,1500+length*120)):settings.holdMs;
  if(duration)expiry=setTimeout(clear,duration);
 }
 $('.hold').onchange=e=>{const value=Number(e.target.value);if(![-1,0,2000,3000,5000,8000].includes(value))return;settings.holdMs=value;save();expire();};
 $('.clear-caption').onclick=clear;
 function receive(m){
  if(m.target!=='overlay')return;
  if(m.reset){closed=false;host.style.display='';position();}
  if(closed)return;
  if(m.type==='apply-preset'){
   const presets={light:{review:false,finalOnly:true,displayMode:'zh',holdMs:5000},read:{review:false,finalOnly:true,displayMode:'zh',holdMs:-1},learn:{review:false,finalOnly:false,displayMode:'both',holdMs:8000},original:{review:false,finalOnly:true,displayMode:'original',holdMs:-1}};
   if(!presets[m.preset])return;
   Object.assign(settings,presets[m.preset]);clear();paint();save();
   Promise.all([
    chrome.runtime.sendMessage({target:'offscreen',type:'quality',review:settings.review}),
    chrome.runtime.sendMessage({target:'offscreen',type:'display',sourceOnly:settings.displayMode==='original'})
   ]).then(results=>{hint.textContent=results.every(r=>r?.ok)?'已套用；處理中的字幕完成後使用新設定':'已保存，下次收音套用';}).catch(()=>{hint.textContent='已保存，下次收音套用';});return;
  }
  if(m.type==='clear-caption'){clear();return;}
  if(m.type==='toggle-through'){settings.clickThrough=!settings.clickThrough;paint();save();return;}
  if(m.type==='cycle-display'){
   const modes=['both','zh','original'];$('.language').onchange({target:{value:modes[(modes.indexOf(settings.displayMode)+1)%3]}});return;
  }
  if(m.type==='metrics'){host.setAttribute('data-mosa-metrics',JSON.stringify(m));return;}
  if(m.reset){seq=-1;latestSeq=-1;captionCount=0;clear();hint.textContent='';}
  if(m.clear)clear();
  if(m.clearPartial)clear();
  if(m.type==='status'||m.type==='activity'){status.removeAttribute('data-caption');status.textContent=m.text;return;}
  if(m.type==='partial'){
   status.setAttribute('data-caption','true');
   // A "stable" partial is a finished translation of text two ASR passes agreed on;
   // it may be shown early even when other previews are hidden.
   if(settings.stablePreview&&m.phase==='stable'&&m.translation&&settings.displayMode!=='original'){
    if(m.seq<=seq||m.seq<latestSeq)return;
    clearTimeout(earlyTimer);earlyTimer=null;
    const wait=finalVisible?finalMinMs-(performance.now()-finalShownAt):0;
    if(wait>0){earlyTimer=setTimeout(()=>{earlyTimer=null;receive(m);},wait);status.textContent='下一句譯文已備妥';return;}
    latestSeq=m.seq;finalVisible=false;original.hidden=settings.displayMode==='zh';
    original.removeAttribute('data-early');original.textContent=m.original||'';translated.textContent=m.translation;expire();
    status.textContent='暫定譯文 · 定稿可能修訂';return;
   }
   if(settings.finalOnly&&settings.stableOriginal&&m.phase!=='stable'&&m.stable_original&&!(m.seq<=seq||m.seq<latestSeq)&&!(finalVisible&&performance.now()-finalShownAt<finalMinMs)){/* Confirmed source (two ASR passes agreed) may lead in final-only mode; Chinese still waits for the final. */latestSeq=m.seq;finalVisible=false;original.hidden=false;original.setAttribute('data-early','true');if(original.textContent!==m.stable_original+' …'){original.textContent=m.stable_original+' …';translated.textContent='';expire();}status.textContent='原文先行 · 中文等定稿';return;}if(finalVisible){status.textContent='正在翻譯下一句';return;}
   if(settings.finalOnly){status.textContent='正在處理下一句，等待定稿';return;}
   if(m.seq<=seq||m.seq<latestSeq)return;latestSeq=m.seq;
   if(m.translation)original.hidden=settings.displayMode==='zh';
   if(!m.translation&&translated.textContent&&settings.displayMode!=='original'){
    status.textContent='上一段字幕 · 下一段翻譯中';return;
   }
   original.removeAttribute('data-early');original.textContent=m.original||'';translated.textContent=m.translation||'';expire();status.textContent=m.phase==='asr'?'正在聽 · 原文可能修訂':'暫定字幕 · 翻譯中';return;
  }
  if(m.type!=='final'||m.seq<=seq||m.seq<latestSeq)return;seq=m.seq;latestSeq=m.seq;
  clearTimeout(earlyTimer);earlyTimer=null;finalShownAt=performance.now();
  finalMinMs=Math.min(3000,Math.max(1200,600+Array.from(m.translation||m.original||'').length*80));
  status.setAttribute('data-caption','true');
  clearTimeout(statusTimer);statusTimer=setTimeout(()=>{if(status.getAttribute('data-caption')==='true')status.textContent='';},3000);
  host.setAttribute('data-mosa-caption-count',String(++captionCount));
  host.setAttribute('data-mosa-last-final-at',String(Date.now()));
  status.textContent=(m.source_only?'語音辨識 · 未翻譯':m.reviewed?'AI 校對 · 非人工確認':'機器字幕 · 未校對')+(m.after_speech_ms!=null?' · 停句後 '+Math.round(m.after_speech_ms):' · 送出後 '+Math.round(m.transport_model_ms))+' ms';
  original.textContent=m.original||'';translated.textContent=m.translation||'';
  finalVisible=Boolean(original.textContent||translated.textContent);
  original.removeAttribute('data-early');original.hidden=settings.displayMode==='zh'&&!m.translation_unavailable;
  if(m.translation_unavailable){status.removeAttribute('data-caption');status.textContent='翻譯暫時不可用，先保留原文；稍後自動嘗試恢復';}
  if(m.needs_human_review)status.textContent+=m.asr_uncertain?' · 原文辨識不確定':' · 譯文待確認';
  expire();
 }
 chrome.runtime.onMessage.addListener(m=>{
  if(m.target!=='overlay')return;
  if(m.type==='partial'){
   // Stable previews are rare (about one per sentence); never let a later raw partial overwrite one.
   if(settings.stablePreview&&m.phase==='stable'){clearTimeout(partialTimer);partialTimer=null;pendingPartial=null;receive(m);return;}
   pendingPartial=m;
   if(!partialTimer)partialTimer=setTimeout(()=>{partialTimer=null;const next=pendingPartial;pendingPartial=null;lastPartialAt=performance.now();if(next)receive(next);},Math.max(0,120-(performance.now()-lastPartialAt)));
   return;
  }
  if(m.type==='final'||m.reset||m.clear||m.clearPartial||m.type==='clear-caption'){clearTimeout(partialTimer);partialTimer=null;pendingPartial=null;}
  receive(m);
 });
})();
