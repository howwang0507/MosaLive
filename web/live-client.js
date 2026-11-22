import {readNDJSON} from './ndjson.js';

// At most two accepted batches: recognize the next while translating the first.
// Only the oldest response may advance captions/commit points. Retry bodies and
// event identities stay immutable until acknowledgement.
// Audio arriving later than real time by more than this means capture paused (for example
// while the video buffered); the latency clock is re-anchored instead of counting the pause.
const CAPTURE_GAP_MS=1000;
export function liveInput({base,onEvent,sourceOnly=false,quality=false,asrMode='auto',endpointMode,request=fetch,makeId=()=>crypto.randomUUID()}){
 let active=true,ring=[],received=0,next=0,committed=0,baseSample=0,clockStart=null;
 let session=makeId(),generation=0,batchNumber=0,flights=[],flush=false;
 let reconnects=0,dropped=0,replayed=0,serverInstance=null,history=[],superseded=[];
 let overflowCount=0,playbackResetCount=0,overflowDropped=0,playbackDropped=0;
 let restartTimer=null,processingFailures=0,suspended=false,recoveryTimer=null,recoveries=0;
 let lastActivity=0,lastAudible=0,lastCaption=performance.now();
 let captureGaps=0,captureGapMs=0;
 const current=f=>active&&f.gen===generation&&flights.includes(f);
 const metrics=()=>onEvent({type:'metrics',received_audio_ms:received/16,dropped_audio_ms:dropped/16,
  replayed_audio_ms:replayed/16,reconnects,auto_recoveries:recoveries,queue_audio_ms:(received-next)/16,in_flight_batches:flights.length,
  overflow_count:overflowCount,playback_reset_count:playbackResetCount,
  overflow_dropped_audio_ms:overflowDropped/16,playback_dropped_audio_ms:playbackDropped/16,
  capture_gap_count:captureGaps,capture_gap_ms:Math.round(captureGapMs)});
 const status=(text,clear=false)=>onEvent({type:'status',text,...(clear?{clear:true}:{})});
 function prune(){ring=ring.filter(x=>x.start+x.data.length>committed);}
 function restart(from=committed){
  clearTimeout(restartTimer);restartTimer=null;
  superseded=[...new Set([...superseded,...flights.flatMap(f=>f.superseded.split(',').filter(Boolean)),session])].slice(-8);
  const old=flights;flights=[];generation++;
  for(const f of old){clearTimeout(f.retryTimer);f.controller?.abort();}
  session=makeId();batchNumber=0;next=from;baseSample=from;serverInstance=null;
  onEvent({type:'status',text:'已重建收音狀態，正在接續新音訊'});
 }
 function resetAudio(){
  if(!active)return;
  clearTimeout(recoveryTimer);recoveryTimer=null;
  suspended=false;processingFailures=0;
  playbackResetCount++;playbackDropped+=received-committed;
  dropped+=received-committed;committed=received;ring=[];history=[];flush=false;clockStart=null;
  restart(received);flush=true;status('偵測到播放串流跳躍，已重設音訊緩衝',true);metrics();drain();
 }
 function samples(from,to){
  const pcm=new Int16Array(to-from);
  for(const chunk of ring){
   const lo=Math.max(from,chunk.start),hi=Math.min(to,chunk.start+chunk.data.length);
   for(let i=lo;i<hi;i++)pcm[i-from]=Math.round(Math.max(-1,Math.min(1,chunk.data[i-chunk.start]))*32767);
  }
  return pcm;
 }
 function deliver(){
  while(flights.length){
   const f=flights[0];
   for(const {event:e,arrived} of f.events.splice(0)){
    const visible=performance.now(),seq=f.gen*1000000+e.seq;
    if(e.type==='final'){
     lastCaption=performance.now();
     if(Number.isFinite(e.commit_samples))committed=Math.max(committed,Math.min(f.to,f.baseSample+e.commit_samples));
     if(e.original&&!e.asr_uncertain)history=[...history,e.original.slice(-300)].slice(-2);
    }
    onEvent({...e,seq,first_visible_ms:visible-f.started,request_elapsed_ms:visible-f.started,
     transport_model_ms:e.transport_model_ms??visible-f.started,
     delivery_wait_ms:visible-arrived,audio_ms:f.body.length/16,queue_audio_ms:(received-next)/16,
     capture_to_caption_ms:Math.max(0,visible-f.clockStart-f.baseSample/16-e.speech_start_ms),
     after_speech_ms:Math.max(0,visible-f.clockStart-f.baseSample/16-e.speech_end_ms)});
   }
   if(!f.complete)break;
   if(Number.isFinite(f.safe))committed=Math.max(committed,Math.min(f.to,f.baseSample+f.safe));
   flights.shift();prune();
  }
 }
 function drain(){
  if(!active||suspended||restartTimer||flights.length>=2||flights.some(f=>f.retryTimer)||flights.at(-1)&&!flights.at(-1).accepted||next===received&&!flush)return;
  const end=Math.min(received,next+32000),ending=flush&&end===received;
  const f={id:session,gen:generation,number:batchNumber++,from:next,to:end,body:samples(next,end),
   ending,seen:new Set(),events:[],sourceOnly,quality,asrMode,baseSample,clockStart,
   history:history.slice(),superseded:superseded.join(','),failures:0};
  superseded=[];next=end;if(ending)flush=false;flights.push(f);run(f);
 }
 async function run(f){
  if(!current(f))return;
  const abort=new AbortController();f.controller=abort;f.started=performance.now();
  const timeout=setTimeout(()=>abort.abort(),20000);
  try{
   const response=await request(base+'/live/frame',{method:'POST',body:f.body,signal:abort.signal,
    headers:{'Content-Type':'application/octet-stream','X-Mosa-Session':f.id,
     'X-Mosa-Batch':String(f.number),'X-Mosa-Offset':String(f.from-f.baseSample),
     'X-Mosa-Supersedes':f.superseded,
     'X-Mosa-Flush':f.ending?'1':'0','X-Mosa-ASR':f.asrMode,
     ...(endpointMode?{'X-Mosa-Endpoint':endpointMode}:{}),
     'X-Mosa-Context':encodeURIComponent(JSON.stringify(f.history)),
     'X-Mosa-Display':f.sourceOnly?'original':'both','X-Mosa-Quality':f.quality?'review':'fast'}});
   if(!response.ok){const error=Error('本機服務回應 '+response.status);if([400,403,404,409,413,422].includes(response.status))error.code='invalid_request';throw error;}
   let complete=false,index=0;
   for await(const e of readNDJSON(response.body)){
    if(!current(f))continue;
    if(e.type==='error'){const error=Error(e.error);error.code=e.code||'processing_failed';throw error;}
    if(e.type==='session'){
     if(serverInstance&&serverInstance!==e.instance){const error=Error('Session changed');error.code='session_lost';throw error;}
     serverInstance=e.instance;continue;
    }
    if(e.type==='audio_ready'){f.accepted=true;drain();continue;}
    if(e.type==='batch_end'){complete=true;f.safe=e.safe_samples;continue;}
    const eventId=index++;if(f.seen.has(eventId))continue;f.seen.add(eventId);
    f.events.push({event:e,arrived:performance.now()});deliver();
   }
   if(!complete)throw Error('字幕串流中斷');
   if(current(f)){
    f.complete=true;f.accepted=true;
    processingFailures=0;
    if(f.failures){reconnects++;onEvent({type:'status',text:'已重新連線，保留的音訊已接續處理'});}
    deliver();
   }
  }catch(error){
   if(current(f)){
    f.failures++;replayed+=f.body.length;
    if(error.code){
     const ending=flights.some(x=>x.ending);restart();flush=flush||ending;
     if(error.code!=='session_lost')processingFailures++;
     if(error.code==='invalid_request'||processingFailures>=3){
      suspended=true;status('處理已暫停：'+error.message+'。請確認本機服務，重新啟動字幕。');
      if(error.code!=='invalid_request'&&recoveries<2){
       status('模型連續失敗，30 秒後自動嘗試恢復');
       recoveryTimer=setTimeout(()=>{
        recoveryTimer=null;if(!active)return;recoveries++;
        dropped+=received-committed;committed=received;ring=[];history=[];flush=false;
        suspended=false;processingFailures=0;restart(received);
        status('正在恢復翻譯，已略過過期音訊');metrics();drain();
       },30000);
      }
     }else{
      status('辨識狀態已失效，稍後重送未確認音訊');
      restartTimer=setTimeout(()=>{restartTimer=null;drain();},500);
     }
    }else{
     const delay=Math.min(8000,500*2**Math.min(f.failures-1,4));
     status('連線中斷，保留音訊中；'+delay/1000+' 秒後重試');
     f.retryTimer=setTimeout(()=>{f.retryTimer=null;run(f);},delay);
    }
   }
  }finally{
   clearTimeout(timeout);if(active){metrics();drain();}
  }
 }
 return {
  push(data){
   if(!active)return;
   if(data?.flush){flush=true;drain();return;}
   if(!(data instanceof Float32Array))return;
   const now=performance.now();let energy=0;for(const x of data)energy+=x*x;
   if(data.length&&Math.sqrt(energy/data.length)>.006)lastAudible=now;
   if(now-lastActivity>=5000&&!suspended&&!restartTimer&&!flights.some(f=>f.retryTimer)){
    lastActivity=now;
    onEvent({type:'activity',text:now-lastAudible>5000?'目前音量很低，等待聲音':now-lastCaption>15000?'持續收到聲音，但尚未產生字幕；可能是音樂或辨識延遲':'持續收音中'});
   }
   if(clockStart===null)clockStart=performance.now()-(received+data.length)/16;
   else{
    // capture_to_caption/after_speech use this clock; a capture pause is reported as a gap.
    const lag=now-(clockStart+(received+data.length)/16);
    if(lag>CAPTURE_GAP_MS){clockStart+=lag;captureGaps++;captureGapMs+=lag;}
   }
   ring.push({start:received,data});received+=data.length;
   if(received-committed>256000){
    const from=received-128000;overflowCount++;overflowDropped+=from-committed;dropped+=from-committed;committed=from;prune();
    const ending=flights.some(f=>f.ending);restart(from);flush=flush||ending;history=[];
    status('超過 16 秒緩衝，已略過舊音訊並重新接續');
    metrics();
   }
   drain();
  },
  get idle(){return next===received&&!flights.length&&!flush&&!restartTimer;},
  stop(){active=false;clearTimeout(restartTimer);clearTimeout(recoveryTimer);ring=[];for(const f of flights){clearTimeout(f.retryTimer);f.controller?.abort();}flights=[];},
  setSourceOnly(value){sourceOnly=Boolean(value);},
  setQuality(value){quality=Boolean(value);},
  setAsrMode(value){
   if(!active||!['auto','stream-en','stream-ja','stream-ko'].includes(value)||value===asrMode)return;
   asrMode=value;flush=flush||flights.some(f=>f.ending);restart();history=[];drain();
  },
  resetAudio
 };
}
