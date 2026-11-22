let switching=false;
async function requireService(){
 let response,health;
 try{response=await fetch('http://localhost:8787/health',{signal:AbortSignal.timeout(4000),cache:'no-store'});health=await response.json();}
 catch{throw Error('本機字幕服務未連線，請開啟專案的 START_WINDOWS.bat，等待 READY 後再啟動字幕');}
 if(!response.ok||!health.ready)throw Error(health.models?.services?.startup_complete?'翻譯服務尚未就緒，請確認 Ollama 與模型已啟動':'模型正在載入或未啟動，請等待本機視窗顯示 READY');
 return {ready:true};
}
chrome.runtime.onMessage.addListener((m,s,reply)=>{
 if(m.target!=='capture-close'||!Number.isInteger(s.tab?.id))return;
 (async()=>{
  if(switching)throw Error('正在切換，請稍候');switching=true;
  try{
   const contexts=await chrome.runtime.getContexts({contextTypes:['OFFSCREEN_DOCUMENT']});
   if(contexts.length){
    const state=await chrome.runtime.sendMessage({target:'offscreen',type:'state'});
    if(!state)throw Error('收音控制無回應，請重新載入擴充套件');
    if(state.tabId!==s.tab.id)return {ok:true};
    const stopped=await chrome.runtime.sendMessage({target:'offscreen',type:'stop'});
    if(!stopped?.ok)throw Error('停止收音失敗，請再試一次');
    await chrome.offscreen.closeDocument();
   }
   await chrome.action.setBadgeText({text:''}).catch(()=>{});return {ok:true};
  }finally{switching=false;}
 })().then(reply,error=>reply({ok:false,error:error.message}));return true;
});
async function stopClosedSource(tabId){
 if(switching)return;
 switching=true;
 try{
  const contexts=await chrome.runtime.getContexts({contextTypes:['OFFSCREEN_DOCUMENT']});
  if(!contexts.length)return;
  const state=await chrome.runtime.sendMessage({target:'offscreen',type:'state'});
  if(state.tabId!==tabId)return;
  await chrome.runtime.sendMessage({target:'offscreen',type:'stop'});
  await chrome.offscreen.closeDocument();
  await chrome.action.setBadgeText({text:''});
  await chrome.action.setTitle({title:'收音頁面已關閉或重新載入，請開啟面板重新啟動'});
 }catch(e){await chrome.action.setTitle({title:'收音中斷：'+e.message});}
 finally{switching=false;}
}
chrome.tabs?.onRemoved?.addListener(id=>stopClosedSource(id));
chrome.tabs?.onUpdated?.addListener((id,change)=>{if(change.status==='loading')stopClosedSource(id);});
async function toggleCapture(tab){
 if(switching)throw Error('正在切換，請稍候');switching=true;
 let created=false;
 try{
  const contexts=await chrome.runtime.getContexts({contextTypes:['OFFSCREEN_DOCUMENT']});
  if(!/^https?:\/\//.test(tab.url||''))throw Error('請先開啟要翻譯的影音網頁，再點擊字幕圖示');
  if(contexts.length){
   const current=await chrome.runtime.sendMessage({target:'offscreen',type:'state'});
   await chrome.runtime.sendMessage({target:'offscreen',type:'stop'});
   await chrome.offscreen.closeDocument();await chrome.action.setBadgeText({text:''});
   if(current?.tabId===tab.id)return;
  }
  await requireService();
  await chrome.scripting.executeScript({target:{tabId:tab.id},files:['overlay.js','playback.js']});
  await chrome.offscreen.createDocument({url:'offscreen.html',reasons:['USER_MEDIA'],justification:'使用者啟動直播音訊字幕'});
  created=true;
  const id=await chrome.tabCapture.getMediaStreamId({targetTabId:tab.id});
  const saved=chrome.storage?.local?await chrome.storage.local.get('mosaOverlaySettings'):{};
  const result=await chrome.runtime.sendMessage({target:'offscreen',type:'start',id,tabId:tab.id,review:saved.mosaOverlaySettings?.review===true,sourceOnly:saved.mosaOverlaySettings?.displayMode==='original',asrMode:saved.mosaOverlaySettings?.asrMode||'auto'});
  if(!result?.ok)throw Error(result?.error||'音訊擷取未啟動');
  await chrome.action.setBadgeText({text:'ON'});
  await chrome.action.setTitle({title:'正在翻譯此分頁；再點停止，在其他影音分頁點擊可切換來源'});
 }catch(e){await chrome.action.setBadgeText({text:'ERR'});await chrome.action.setTitle({title:e.message});if(created)try{await chrome.offscreen.closeDocument();}catch{}throw e;}
 finally{switching=false;}
}
chrome.action.onClicked.addListener(tab=>toggleCapture(tab).catch(()=>{}));
chrome.commands?.onCommand.addListener(async command=>{
 try{
  const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
  if(!tab)return;
  if(command==='toggle-capture')await toggleCapture(tab);
  else if(['clear-caption','cycle-display','toggle-through'].includes(command))await chrome.tabs.sendMessage(tab.id,{target:'overlay',type:command});
 }catch(e){await chrome.action.setTitle({title:e.message});}
});
chrome.runtime.onMessage.addListener((m,s,reply)=>{
 if(m.target!=='controls'||s.url!==chrome.runtime.getURL('popup.html'))return;
 (async()=>{
  const contexts=await chrome.runtime.getContexts({contextTypes:['OFFSCREEN_DOCUMENT']});
  if(m.type==='service')return await requireService();
  if(m.type==='state')return contexts.length?await chrome.runtime.sendMessage({target:'offscreen',type:'state'}):{active:false};
  if(m.type==='reports')return {reports:(await chrome.storage.local.get('mosaReports')).mosaReports||[]};
  if(m.type==='recover'){
   if(!contexts.length)throw Error('請先啟動收音');
   const result=await chrome.runtime.sendMessage({target:'offscreen',type:'manual-resync'});
   if(!result?.ok)throw Error(result?.error||'無法重同步');return {};
  }
  if(m.type==='clear-reports'){await chrome.storage.local.remove('mosaReports');return {};}
  if(m.type==='report'){
   if(!['asr','translation'].includes(m.kind))throw Error('請選擇錯誤類型');
   if(!contexts.length)throw Error('本次收音已結束，沒有可回報的字幕');
   const state=await chrome.runtime.sendMessage({target:'offscreen',type:'state'});
   const caption=state.recent?.find(c=>c.id===m.captionId);
   if(!caption)throw Error('該句已過期，請選擇最近字幕');
   const reports=(await chrome.storage.local.get('mosaReports')).mosaReports||[];
   const correction=typeof m.correction==='string'?m.correction.trim().slice(0,2000):'';
   const report={...caption,kind:m.kind,correction,reportedAt:Date.now()};
   await chrome.storage.local.set({mosaReports:[...reports,report].slice(-30)});return {count:Math.min(30,reports.length+1)};
  }
  if(m.type==='stop'){
   if(switching)throw Error('正在切換，請稍候');
   switching=true;
   try{if(contexts.length){await chrome.runtime.sendMessage({target:'offscreen',type:'stop'});await chrome.offscreen.closeDocument();}await chrome.action.setBadgeText({text:''});}
   finally{switching=false;}return {};
  }
  if(m.type==='start'){
   const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
   if(tab?.id!==m.tabId)throw Error('分頁已改變，請重新開啟字幕面板');
   if(contexts.length){const state=await chrome.runtime.sendMessage({target:'offscreen',type:'state'});if(state.active&&state.tabId===tab.id)return {};}
   await toggleCapture(tab);return {};
  }
  throw Error('不支援的操作');
 })().then(data=>reply({ok:true,...data}),e=>reply({ok:false,error:e.message}));return true;
});
chrome.runtime.onMessage.addListener(m=>{
 if(m.target==='overlay'&&Number.isInteger(m.tabId))chrome.tabs.sendMessage(m.tabId,m).catch(()=>{});
});
chrome.runtime.onMessage.addListener((m,s,reply)=>{
 if(m.target!=='settings')return;
 (async()=>{
  if(!chrome.storage?.local)throw Error('缺少設定儲存權限，請重新載入擴充套件');
  if(m.type==='get')return (await chrome.storage.local.get('mosaOverlaySettings')).mosaOverlaySettings||{};
  if(m.type==='set'){
   const clean={};
   for(const [k,a,b] of [['size',16,36],['opacity',0,100],['x',0,1],['y',0,1]]){
    const v=m.settings?.[k];if(typeof v==='number'&&Number.isFinite(v))clean[k]=Math.min(b,Math.max(a,v));
   }
   for(const k of ['review','bilingual'])if(typeof m.settings?.[k]==='boolean')clean[k]=m.settings[k];
   for(const k of ['outline','clickThrough','finalOnly','stablePreview','stableOriginal','quietReading'])if(typeof m.settings?.[k]==='boolean')clean[k]=m.settings[k];
   if(['both','zh','original'].includes(m.settings?.displayMode))clean.displayMode=m.settings.displayMode;
   if(['auto','stream-en','stream-ja','stream-ko'].includes(m.settings?.asrMode))clean.asrMode=m.settings.asrMode;
   if([-1,0,2000,3000,5000,8000].includes(m.settings?.holdMs))clean.holdMs=m.settings.holdMs;
   await chrome.storage.local.set({mosaOverlaySettings:clean});return clean;
  }
  throw Error('不支援的設定操作');
 })().then(settings=>reply({ok:true,settings}),e=>reply({ok:false,error:e.message}));
 return true;
});
