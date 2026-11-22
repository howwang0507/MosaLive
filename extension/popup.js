const $=id=>document.getElementById(id);
const request=async(type,extra={})=>{const result=await chrome.runtime.sendMessage({target:'controls',type,tabId:current.id,...extra});if(!result?.ok)throw Error(result?.error||'無法連線至字幕控制');return result;};
let current,tabs=[],captureTabId=null,refreshing=false;
let serviceCheckedAt=0,serviceProblem='';
$('check-service').onclick=async()=>{
 $('service-status').textContent='檢查中…';
 try{
  const health=await(await fetch('http://localhost:8787/health',{signal:AbortSignal.timeout(5000)})).json();
  const version=chrome.runtime.getManifest().version;
  const services=health.models?.services;
  const resources=await fetch('http://localhost:8787/resources',{signal:AbortSignal.timeout(3500)}).then(r=>r.json()).catch(()=>({gpus:null}));
  $('service-status').textContent=`擴充套件 ${version}；${health.extensionVersion===version?'版本號一致（同版本更新仍須重新載入）':'請重新載入擴充套件或重啟後端'}。後端${health.ready?'可用':'未就緒'}，辨識設定 ${health.models?.device||'未知'}。`+(services?` 辨識模型${services.asr_loaded?'已載入':'未載入'}；翻譯${services.translation?.available?'可連線':'不可用'}：${services.translation?.reason||'未知'}。`:' 後端尚未提供分項健康資訊。')+(health.models?.restart_required?' 程式已更新，請重啟後端。':'')+(resources.gpus?.map(g=>` 整張顯卡 ${g.used_mib}/${g.total_mib} MiB（包含遊戲）。`).join('')||' 無法取得 GPU 用量。')+' 這不是實際推論測試。';
  const last=health.models?.recent_errors?.at(-1);
  if(last)$('service-status').textContent+=` 最近錯誤：${last.stage}／${last.category}（${last.error_type}）。`;
 }catch(e){$('service-status').textContent='無法完成檢查，請重啟本機服務：'+e.message;}
};
async function refresh(){
 const state=await request('state');
 if(Date.now()-serviceCheckedAt>10000){
  serviceCheckedAt=Date.now();
  try{await request('service');serviceProblem='';}catch(e){serviceProblem=e.message;}
 }
 captureTabId=state.active?state.tabId:null;
 $('recover').disabled=!state.active;$('apply-preset').disabled=!state.active;
 const source=tabs.find(t=>t.id===state.tabId);
 $('state').textContent=state.active?'正在收音：'+(source?.title||'影音分頁'):'尚未開始收音';
 $('stop').disabled=!state.active;
 $('activity').textContent=state.active?(state.status||'等待音訊'):'';
 if(serviceProblem)$('activity').textContent=serviceProblem;
 const ms=value=>value==null?'—':(value/1000).toFixed(1)+' 秒';
 $('session-stats').textContent=(state.minutes||[]).map(b=>`第 ${b.minute+1} 分鐘：${b.finals} 句\n說完到定稿 中位 ${ms(b.p50_ms)} / P95 ${ms(b.p95_ms)}\n開口到定稿 中位 ${ms(b.onset_p50_ms)} / P95 ${ms(b.onset_p95_ms)}\n略過 ${ms(b.dropped_ms)}（緩衝 ${ms(b.overflow_dropped_ms)}／播放重設 ${ms(b.playback_dropped_ms)}）\n擷取中斷 ${b.capture_gaps??0} 次，共 ${ms(b.capture_gap_ms??0)}\n恢復 ${b.recoveries} 次／字幕平均間隔 ${ms(b.average_gap_ms)}\n整張顯卡抽樣最高 ${b.gpu_peak_mib??'—'} MiB（含其他程式）`).join('\n\n')||'尚無統計';
 const selected=$('recent-caption').value;
 const names={capture_to_caption_ms:'語音起點至定稿呈現（估計）',asr_queue_ms:'辨識排隊',asr_ms:'辨識',nmt_queue_ms:'翻譯排隊',nmt_ms:'翻譯',delivery_wait_ms:'字幕排序等待'};
 const latest=state.minutes?.at(-1);
 if(latest?.stages)$('session-stats').textContent+='\n\n最近一分鐘分項（中位／P95）：\n'+Object.entries(latest.stages).map(([key,value])=>`${names[key]||key}：${ms(value.p50_ms)}／${ms(value.p95_ms)}（${value.count}筆）`).join('\n');
 $('recent-caption').replaceChildren();
 for(const caption of [...(state.recent||[])].reverse()){
  const option=document.createElement('option');option.value=caption.id;option.textContent=(caption.translation||caption.original).slice(0,90);$('recent-caption').append(option);
 }
 if((state.recent||[]).some(c=>c.id===selected))$('recent-caption').value=selected;
}
function selection(){
 const isCurrent=Number($('source').value)===current.id;
 $('start').textContent=isCurrent?'翻譯此分頁':'前往所選分頁';
 $('start').disabled=!$('source').value;
 $('hint').textContent=isCurrent?'收取此分頁全部聲音；請暫停同頁其他播放器。':'前往後，再點 MosaSub 圖示啟動。瀏覽器需要你在收音分頁授權。';
}
async function run(fn){$('error').textContent='';$('start').disabled=true;$('stop').disabled=true;try{await fn();await refresh();}catch(e){$('error').textContent=e.message;}finally{selection();}}
$('source').onchange=selection;
$('start').onclick=()=>run(async()=>{
 const id=Number($('source').value);
 if(id!==current.id){const tab=tabs.find(t=>t.id===id);await chrome.tabs.update(id,{active:true});await chrome.windows.update(tab.windowId,{focused:true});window.close();return;}
 await request('start');
});
$('stop').onclick=()=>run(()=>request('stop'));
 $('recover').onclick=()=>run(()=>request('recover'));
 $('apply-preset').onclick=()=>run(async()=>{
  if(!Number.isInteger(captureTabId))throw Error('請先啟動收音');
  await chrome.tabs.sendMessage(captureTabId,{target:'overlay',type:'apply-preset',preset:$('preset').value});
  $('preset-status').textContent='已送至收音分頁。省運算模式減少校對請求，但不會卸載模型或保證降低顯存。';
 });
async function reportAction(fn){try{await fn();}catch(e){$('report-status').textContent=e.message;}}
$('report-caption').onclick=()=>reportAction(async()=>{await request('report',{kind:$('report-kind').value,captionId:$('recent-caption').value,correction:$('correction').value});$('correction').value='';$('report-status').textContent='已保存在本機，未上傳。';});
$('view-reports').onclick=()=>reportAction(async()=>{const data=await request('reports');$('reports').textContent=data.reports.map(r=>(r.kind==='asr'?'辨識':'翻譯')+'錯誤\n'+r.original+'\n'+r.translation+(r.correction?'\n正確內容：'+r.correction:'')).join('\n\n')||'沒有回報';});
$('clear-reports').onclick=()=>reportAction(async()=>{await request('clear-reports');$('reports').textContent='已清除所有回報';});
$('through').onclick=()=>run(()=>chrome.tabs.sendMessage(captureTabId??current.id,{target:'overlay',type:'toggle-through'}));
async function glossaryRequest(init){
 const response=await fetch('http://localhost:8787/glossary',{...init,signal:AbortSignal.timeout(5000)});
 const data=await response.json();if(!response.ok)throw Error(data.error||'術語服務失敗');return data;
}
$('load-terms').onclick=async()=>{
 try{const data=await glossaryRequest();$('terms').value=data.terms.map(t=>t.ja+' = '+t.zh).join('\n');$('terms').disabled=false;$('save-terms').disabled=false;$('terms-status').textContent='已讀取；修改後請儲存。';}
 catch(e){$('terms-status').textContent='請確認本機服務已更新並啟動：'+e.message;}
};
$('save-terms').onclick=async()=>{
 $('save-terms').disabled=true;
 try{
  const terms=$('terms').value.split(/\r?\n/).filter(s=>s.trim()).map(line=>{
   const i=line.indexOf('=');if(i<1)throw Error('每行請使用：原詞 = 譯詞');
   const ja=line.slice(0,i).trim(),zh=line.slice(i+1).trim();if(!ja||!zh||ja.length>60||zh.length>60)throw Error('原詞與譯詞需為 1–60 字');return {ja,zh};
  });
  if(terms.length>100)throw Error('最多 100 組術語');
  await glossaryRequest({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(terms)});
  $('terms-status').textContent='已儲存，後续送入的音訊套用；處理中的字幕不重翻。';
 }catch(e){$('terms-status').textContent=e.message;}finally{$('save-terms').disabled=false;}
};
try{
 [current]=await chrome.tabs.query({active:true,currentWindow:true});
 tabs=(await chrome.tabs.query({})).filter(t=>/^https?:\/\//.test(t.url||''));
 tabs.sort((a,b)=>Number(b.id===current.id)-Number(a.id===current.id)||Number(!!b.audible)-Number(!!a.audible));
 for(const tab of tabs){const option=document.createElement('option');option.value=tab.id;option.textContent=(tab.audible?'正在播放 · ':'')+(tab.title||new URL(tab.url).hostname);$('source').append(option);}
 selection();await refresh();
 const poll=setInterval(async()=>{if(refreshing||document.hidden)return;refreshing=true;try{await refresh();}catch{$('activity').textContent='收音狀態暫時無法取得';}finally{refreshing=false;}},2000);
 window.addEventListener('pagehide',()=>clearInterval(poll),{once:true});
}catch(e){$('error').textContent=e.message;}
