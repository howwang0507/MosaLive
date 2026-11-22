// Replays authored/reference WAVs at real-time speed through the same browser
// network client. Does not include browser rendering or real microphone clocks.
import {readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {liveInput} from '../web/live-client.js';
const root=fileURLToPath(new URL('../',import.meta.url));
const manifest=JSON.parse(await readFile(root+(process.argv[2]||'quality/manifest.json'),'utf8'));
const filter=process.argv[3];
const selectedMode=process.env.MOSA_EVAL_ASR||'auto';
const outputName=process.env.MOSA_EVAL_OUTPUT||('results'+(filter?'-'+filter:'')+'.json');
const fault=process.env.MOSA_EVAL_FAULT||'';
const normalize=s=>s.normalize('NFKC').toLowerCase().replace(/[\p{P}\p{Z}\s]/gu,'');
export function edits(a,b){
 let row=Array.from({length:b.length+1},(_,i)=>i);
 for(let i=0;i<a.length;i++){const next=[i+1];for(let j=0;j<b.length;j++)next[j+1]=Math.min(next[j]+1,row[j+1]+1,row[j]+(a[i]===b[j]?0:1));row=next;}
 return row[b.length];
}
const percentile=(xs,p)=>xs.length?[...xs].sort((a,b)=>a-b)[Math.ceil(xs.length*p)-1]:null;
const health=await(await fetch('http://localhost:8787/health')).json();
health.evaluation_client_sha256=createHash('sha256').update(await readFile(root+'web/live-client.js')).digest('hex');
if(!health.ready||!health.models?.live)throw Error('Updated local streaming service is not ready');
const results=[];
for(const sample of manifest.samples.filter(s=>!filter||s.id.includes(filter))){
 const buf=await readFile(root+sample.path);
 // PCM header may contain extra WAV chunks (Python wave emits canonical PCM).
 let pos=12,data;
 while(pos+8<=buf.length){const tag=buf.toString('ascii',pos,pos+4),n=buf.readUInt32LE(pos+4);if(tag==='data'){data=buf.subarray(pos+8,pos+8+n);break;}pos+=8+n+(n%2);}
 if(!data)throw Error('Invalid PCM WAV: '+sample.path);
 const audio=Float32Array.from({length:data.length/2},(_,i)=>data.readInt16LE(i*2)/32768);
 const events=[],firstSource=new Map(),firstTranslation=new Map(),finals=[];let metrics={};
 let requests=0,injected=false;
 const request=async(url,init)=>{
  requests++;
  if(fault==='transport'&&!injected&&requests===5){injected=true;throw Error('Injected network interruption');}
  if(fault==='state'&&!injected&&requests===6){
   injected=true;init={...init,headers:{...init.headers,'X-Mosa-Session':crypto.randomUUID()}};
  }
  const response=await fetch(url,init);
  if(fault==='ack'&&!injected&&response.ok){
   const text=await response.text();
   if(text.split('\n').some(s=>s&&JSON.parse(s).type==='final')){
    injected=true;return new Response(text.split('\n').filter(s=>!s||JSON.parse(s).type!=='batch_end').join('\n'));
   }
   return new Response(text,{status:response.status});
  }
  return response;
 };
 const lang=sample.language||sample.id.slice(0,2);
 const asrMode=selectedMode==='native'?'stream-'+(['en','ja','ko'].includes(lang)?lang:'en'):selectedMode;
 const input=liveInput({base:'http://localhost:8787',request,asrMode,endpointMode:process.env.MOSA_EVAL_ENDPOINT,sourceOnly:process.env.MOSA_EVAL_SOURCE_ONLY==='1',onEvent:e=>{
  if(e.type==='metrics'){metrics=e;return;}
  events.push(e);
  if(e.original&&!firstSource.has(e.seq))firstSource.set(e.seq,e.capture_to_caption_ms);
  if(e.translation&&!firstTranslation.has(e.seq))firstTranslation.set(e.seq,e.capture_to_caption_ms);
  if(e.type==='final')finals.push(e);
 }});
 const begin=performance.now();let offset=0;
 try{
  while(offset<audio.length){
   const end=Math.min(audio.length,offset+5120),due=begin+end/16;
   await new Promise(r=>setTimeout(r,Math.max(0,due-performance.now())));
   input.push(audio.slice(offset,end));offset=end;
  }
  input.push({flush:true});
  const deadline=performance.now()+60000;
  while(!input.idle){if(performance.now()>deadline)throw Error('Replay timeout');await new Promise(r=>setTimeout(r,20));}
 }finally{input.stop();}
 const original=finals.map(e=>e.original).join(' '),translation=finals.map(e=>e.translation).join(' ');
 const ref=normalize(sample.source),hyp=normalize(original);
 const revisions=events.filter((e,i)=>e.phase==='asr'&&events.slice(0,i).some(p=>p.seq===e.seq&&p.phase==='asr'&&p.original!==e.original)).length;
 const result={...sample,asrMode,endpointMode:process.env.MOSA_EVAL_ENDPOINT||'server-default',original,translation,cer:ref.length?edits([...ref],[...hyp])/ref.length:null,
  unexpected_speech:!ref.length&&Boolean(hyp),first_source_p50_ms:percentile([...firstSource.values()],.5),
  first_translation_p50_ms:percentile([...firstTranslation.values()],.5),
  after_speech_p50_ms:percentile(finals.map(e=>e.after_speech_ms),.5),
  after_speech_p95_ms:percentile(finals.map(e=>e.after_speech_ms),.95),
  revisions,metrics,fault,injected,duplicate_finals:finals.length-new Set(finals.map(e=>e.seq)).size,meaning_review:null,events};
 results.push(result);
 console.log(JSON.stringify({id:sample.id,cer:result.cer,first_source:result.first_source_p50_ms,first_translation:result.first_translation_p50_ms,after_speech:result.after_speech_p50_ms,original,translation,dropped:metrics.dropped_audio_ms}));
 // Health after the case keeps end-of-run counters (Ollama timings, endpoint counts); failure is recorded, not fatal.
 const health_after=await fetch('http://localhost:8787/health').then(r=>r.json()).catch(error=>({error:String(error)}));
 // Preserve completed cases even if a later case fails.
 await writeFile(root+'quality/'+outputName,JSON.stringify({note:'Real-time paced replay. Dataset kind is recorded per case. CER measures text edits, not translation meaning; meaning_review requires human review.',health,health_after,results},null,2));
}
