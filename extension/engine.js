import {readNDJSON} from './ndjson.js';
import {liveInput} from './live-client.js';
export async function requestSegment(data,{base='http://localhost:8787',signal,onPartial=()=>{},quality=false,context=[],sourceOnly=false}={}){
 const started=performance.now();let first=null;
 const r=await fetch(base+'/segment',{method:'POST',headers:{Accept:'application/x-ndjson','X-Mosa-Display':sourceOnly?'original':'both','X-Mosa-Quality':quality?'review':'fast','X-Mosa-Context':encodeURIComponent(JSON.stringify(context))},body:data,signal});
 if(!r.ok){const e=await r.json();throw Error(e.error||'模型服務失敗');}
 if(!r.headers?.get('content-type')?.includes('application/x-ndjson'))return r.json();
 let final=null;
 for await(const e of readNDJSON(r.body)){
  if(e.type==='error')throw Error(e.error);
  if(e.type==='partial'){if(first===null)first=performance.now()-started;onPartial({...e,first_visible_ms:first});}
  if(e.type==='final')final=e;
 }
 if(!final)throw Error('字幕串流中斷，未收到定稿');
 return {...final,first_visible_ms:first};
}
export function wav(samples) {
 const b=new ArrayBuffer(44+samples.length*2),v=new DataView(b);
 const s=(p,t)=>[...t].forEach((c,i)=>v.setUint8(p+i,c.charCodeAt(0)));
 s(0,'RIFF');v.setUint32(4,b.byteLength-8,true);s(8,'WAVE');s(12,'fmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,16000,true);v.setUint32(28,32000,true);v.setUint16(32,2,true);v.setUint16(34,16,true);s(36,'data');v.setUint32(40,samples.length*2,true);
 samples.forEach((x,i)=>v.setInt16(44+i*2,Math.round(Math.max(-1,Math.min(1,x))*32767),true));return b;
}
export class CaptionState{
 constructor(){this.seq=-1;this.latestSeq=-1;this.lines=[];}
 acceptPartial(e){if(e.type!=='partial'||e.seq<=this.seq||e.seq<this.latestSeq)return false;this.latestSeq=e.seq;return true;}
 accept(e){if(e.seq<=this.seq||e.seq<this.latestSeq||e.type!=='final')return false;this.seq=e.seq;this.latestSeq=e.seq;this.lines=[e];return true;}
 clear(){this.lines=[];}
}
export async function capturePipeline(stream,{base='http://localhost:8787',worklet='/worklet.js',monitor=false,quality=true,sourceOnly=false,live=true,asrMode='auto',onEvent=()=>{}}={}){
 const ctx=new AudioContext();let source,node;
 try{
  source=ctx.createMediaStreamSource(stream);await ctx.audioWorklet.addModule(worklet);
  node=new AudioWorkletNode(ctx,'segmenter',{processorOptions:{live}});source.connect(node);
  const mute=ctx.createGain();mute.gain.value=0;node.connect(mute).connect(ctx.destination);
  if(monitor)source.connect(ctx.destination);
  await ctx.resume();
 }catch(error){
  node?.disconnect();source?.disconnect();stream.getTracks().forEach(t=>t.stop());await ctx.close();throw error;
 }
 if(live){
  const input=liveInput({base,onEvent,sourceOnly,quality,asrMode});let active=true;
  let resetPending=false;
  node.port.onmessage=({data})=>{if(data?.resetDone){resetPending=false;return;}if(!resetPending)input.push(data);};
  const stop=()=>{if(!active)return;active=false;input.stop();node.disconnect();source.disconnect();stream.getTracks().forEach(t=>t.stop());ctx.close();};
  stop.flush=()=>{if(active)node.port.postMessage('flush');};
  stop.setSourceOnly=value=>input.setSourceOnly(value);stop.setQuality=value=>input.setQuality(value);
  stop.setAsrMode=value=>input.setAsrMode(value);
  stop.resetAudio=()=>{if(!active||resetPending)return;resetPending=true;input.resetAudio();node.port.postMessage('reset');};
  stream.getTracks().forEach(t=>t.addEventListener('ended',()=>{stop();onEvent({type:'status',clearPartial:true,text:'音訊分享已結束，請重新啟動字幕'});},{once:true}));
  return stop;
 }
 let active=true,busy=false,seq=0,controller=null,pending=null;
 let history=[],lastSpeech=0,historyEpoch=0;
 const consume=async(data,readyAt=performance.now())=>{
  if(!active)return;
  if(busy){if(pending){history=[];historyEpoch++;onEvent({type:'status',text:'處理落後，已略過一段音訊，前文已清除'});}pending={data,readyAt};return;}
  busy=true;controller=new AbortController();const id=seq++,ended=performance.now();
  onEvent({type:'status',text:'辨識與翻譯中'});
  try{
   const timeout=setTimeout(()=>controller?.abort(),95000);
   if(ended-lastSpeech>20000)history=[];
   const contextEpoch=historyEpoch;
   let e;try{e=await requestSegment(wav(data),{base,quality,sourceOnly,context:history.slice(),signal:controller.signal,onPartial:p=>{if(active)onEvent({...p,seq:id});}});}finally{clearTimeout(timeout);}
   if(active&&e.original&&contextEpoch===historyEpoch){history=[...history,e.original.slice(-300)].slice(-2);lastSpeech=performance.now();}
   if(active&&(e.translation||(e.source_only&&e.original)))onEvent({...e,seq:id,type:'final',audio_ms:data.length/16,queue_ms:ended-readyAt,transport_model_ms:performance.now()-ended});
   else if(active)onEvent({type:'status',text:'未辨識到語音'});
  }catch(e){history=[];if(active)onEvent({type:'status',clearPartial:true,text:e.name==='AbortError'?'模型處理逾時':e.message});}
  finally{busy=false;if(active&&pending){const next=pending;pending=null;consume(next.data,next.readyAt);}}
 };
 node.port.onmessage=({data})=>consume(data);
 const stop=()=>{if(!active)return;active=false;pending=null;controller?.abort();node.disconnect();source.disconnect();stream.getTracks().forEach(t=>t.stop());ctx.close();};
 stop.flush=()=>{if(active)node.port.postMessage('flush');};
 stop.setSourceOnly=value=>{sourceOnly=Boolean(value);};
 stop.setQuality=value=>{quality=Boolean(value);history=[];historyEpoch++;};
 stream.getTracks().forEach(t=>t.addEventListener('ended',()=>{stop();onEvent({type:'status',text:'音訊分享已結束'});},{once:true}));
 return stop;
}
