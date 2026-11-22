import test from 'node:test';
import assert from 'node:assert/strict';
import {liveInput} from '../web/live-client.js';

const batch=events=>new Response(events.map(e=>JSON.stringify(e)).join('\n')+'\n');
const tick=()=>new Promise(resolve=>setImmediate(resolve));

test('reset immediately cancels old session without audio and ignores late callbacks',async()=>{
 const calls=[],events=[];let resolveOld;
 const input=liveInput({base:'http://local',onEvent:e=>events.push(e),request:(u,o)=>{
  calls.push(o);
  if(calls.length===1)return new Promise(r=>{resolveOld=r;});
  return Promise.resolve(batch(o.body.length?[{type:'final',seq:0,original:'fresh',commit_samples:o.body.length},{type:'batch_end',safe_samples:o.body.length}]:[{type:'batch_end',safe_samples:0}]));
 }});
 try{
  input.push(new Float32Array(5120));input.resetAudio();await tick();
  assert.equal(calls.length,2);assert.equal(calls[1].body.length,0);
  assert.equal(calls[1].headers['X-Mosa-Supersedes'],calls[0].headers['X-Mosa-Session']);
  assert.ok(calls[0].signal.aborted);
  resolveOld(batch([{type:'final',seq:0,original:'obsolete'},{type:'batch_end',safe_samples:5120}]));await tick();
  assert.equal(events.filter(e=>e.type==='final').length,0);
  input.push(new Float32Array(5120));await tick();
  assert.deepEqual(events.filter(e=>e.type==='final').map(e=>e.original),['fresh']);
 }finally{input.stop();}
});
test('permanent model errors stop after three attempts instead of replaying forever',async()=>{
 let calls=0;const events=[];
 const input=liveInput({base:'http://local',onEvent:e=>events.push(e),request:async()=>{calls++;return batch([{type:'error',error:'model unavailable'}]);}});
 try{
  input.push(new Float32Array(5120));await new Promise(r=>setTimeout(r,1150));
  assert.equal(calls,3);assert.ok(events.some(e=>e.text?.includes('處理已暫停')));
 }finally{input.stop();}
});
test('lost acknowledgement during pipelining replays first batch without duplicating or reordering finals',async()=>{
 const events=[];let firstCalls=0;
 const final=n=>({type:'final',seq:n,original:'caption'+n,speech_start_ms:n*320,speech_end_ms:(n+1)*320,commit_samples:(n+1)*5120});
 const input=liveInput({base:'http://local',onEvent:e=>events.push(e),request:async(u,o)=>{
  const n=Number(o.headers['X-Mosa-Batch']);
  if(n===0&&++firstCalls===1)return batch([{type:'audio_ready'},final(0)]);
  return batch([{type:'audio_ready'},final(n),{type:'batch_end',safe_samples:(n+1)*5120}]);
 }});
 try{
  input.push(new Float32Array(5120));input.push(new Float32Array(5120));
  await new Promise(r=>setTimeout(r,650));
  assert.equal(firstCalls,2);
  assert.deepEqual(events.filter(e=>e.type==='final').map(e=>e.original),['caption0','caption1']);
  assert.equal(input.idle,true);
 }finally{input.stop();}
});
test('two batches overlap but later captions and commits wait for the first response',async()=>{
 const events=[],calls=[];let stream;
 const encode=e=>new TextEncoder().encode(JSON.stringify(e)+'\n');
 const input=liveInput({base:'http://local',onEvent:e=>events.push(e),request:async(u,o)=>{
  calls.push(o);
  if(calls.length===1)return new Response(new ReadableStream({start(c){stream=c;c.enqueue(encode({type:'audio_ready'}));}}));
  return batch([{type:'audio_ready'},{type:'final',seq:calls.length-1,original:'later',speech_start_ms:320,speech_end_ms:640,commit_samples:10240},{type:'batch_end',safe_samples:10240}]);
 }});
 try{
  input.push(new Float32Array(5120));await tick();
  input.push(new Float32Array(5120));await tick();
  input.push(new Float32Array(5120));await tick();
  assert.equal(calls.length,2,'at most two responses remain outstanding');
  assert.equal(events.filter(e=>e.type==='final').length,0,'later final cannot skip a pending caption');
  assert.equal(calls[1].headers['X-Mosa-Offset'],'5120');
  stream.enqueue(encode({type:'final',seq:0,original:'first',speech_start_ms:0,speech_end_ms:320,commit_samples:5120}));
  stream.enqueue(encode({type:'batch_end',safe_samples:5120}));stream.close();await tick();
  assert.deepEqual(events.filter(e=>e.type==='final').slice(0,2).map(e=>e.original),['first','later']);
  assert.equal(calls.length,3);assert.equal(input.idle,true);
 }finally{input.stop();}
});
test('playback reset preserves totals, counts discarded audio and clears old translation context',async()=>{
 const calls=[],events=[];
 const input=liveInput({base:'http://local',onEvent:e=>events.push(e),request:async(u,o)=>{
  calls.push(o);
  if(calls.length===2)return new Promise((r,j)=>o.signal.addEventListener('abort',()=>j(new DOMException('Aborted','AbortError'))));
  if(!o.body.length)return batch([{type:'batch_end',safe_samples:0}]);
  return batch([{type:'final',seq:0,original:'old topic',speech_start_ms:0,speech_end_ms:320,commit_samples:5120},{type:'batch_end',safe_samples:5120}]);
 }});
 try{
  input.push(new Float32Array(5120));await tick();
  input.push(new Float32Array(16000));input.resetAudio();
  const reset=events.filter(e=>e.type==='metrics').at(-1);
  assert.equal(reset.received_audio_ms,1320);assert.equal(reset.dropped_audio_ms,1000);
  assert.equal(reset.playback_reset_count,1);assert.equal(reset.playback_dropped_audio_ms,1000);
  assert.equal(reset.overflow_count,0);assert.equal(reset.overflow_dropped_audio_ms,0);
  input.push(new Float32Array(5120));await tick();
  assert.equal(decodeURIComponent(calls.at(-1).headers['X-Mosa-Context']),'[]');
  assert.equal(calls.at(-1).headers['X-Mosa-Offset'],'0');
  assert.equal(calls[2].headers['X-Mosa-Supersedes'],calls[0].headers['X-Mosa-Session']);
  assert.equal(calls[2].body.length,0);
  assert.equal(calls[2].headers['X-Mosa-Flush'],'1');
  assert.ok(events.filter(e=>e.type==='final').at(-1).capture_to_caption_ms<600);
 }finally{input.stop();}
});
test('lost acknowledgement replays final once and preserves batch identity',async()=>{
 const calls=[],events=[];
 const final={type:'final',seq:0,original:'confirmed',translation:'已確認',speech_start_ms:0,speech_end_ms:320,commit_samples:5120};
 const input=liveInput({base:'http://local',onEvent:e=>events.push(e),request:async(url,init)=>{
  calls.push(init);return batch(calls.length===1?[final]:[final,{type:'batch_end',safe_samples:5120}]);
 }});
 try{
  input.push(new Float32Array(5120));await new Promise(r=>setTimeout(r,550));
  assert.equal(calls.length,2);assert.deepEqual(calls[0].headers,calls[1].headers);
  assert.equal(events.filter(e=>e.type==='final').length,1);
  assert.equal(events.filter(e=>e.type==='metrics').at(-1).dropped_audio_ms,0);
  assert.ok(input.idle);
 }finally{input.stop();}
});
test('live input sends continuous PCM and source-only settings; drains final tail',async()=>{
 const calls=[],events=[];
 const input=liveInput({base:'http://local',onEvent:e=>events.push(e),sourceOnly:true,makeId:()=> 'session-test',
  request:async(url,init)=>{calls.push(init);return batch([{type:'final',seq:calls.length-1,original:'hello',translation:'',source_only:true,speech_start_ms:0,speech_end_ms:480},{type:'batch_end'}]);}});
 try{
  input.push(new Float32Array([1,-1]));await tick();
  assert.deepEqual([...calls[0].body],[32767,-32767]);
  assert.equal(calls[0].headers['X-Mosa-Display'],'original');
  input.setSourceOnly(false);input.setQuality(true);input.push({flush:true});await tick();
  assert.equal(calls[1].headers['X-Mosa-Flush'],'1');
  assert.equal(calls[1].headers['X-Mosa-Quality'],'review');
  assert.equal(calls[1].headers['X-Mosa-Display'],'both');
  assert.equal(events.filter(e=>e.type==='final').length,2);
 }finally{input.stop();}
});

test('failed transport replays the identical batch without losing audio',async()=>{
 const calls=[],events=[];let counter=0;
 const input=liveInput({base:'http://local',onEvent:e=>events.push(e),makeId:()=> 'session-'+counter++,
  request:async(url,init)=>{calls.push(init);if(calls.length===1)throw Error('offline');return batch([{type:'final',seq:0,original:'restored',translation:'恢復',speech_start_ms:0,speech_end_ms:0},{type:'batch_end'}]);}});
 try{
  input.push(new Float32Array(7680));await tick();
  input.push(new Float32Array(7680));
  await new Promise(resolve=>setTimeout(resolve,550));
  assert.equal(calls.length,3);
  assert.equal(calls[0].headers['X-Mosa-Session'],calls[1].headers['X-Mosa-Session']);
  assert.equal(calls[0].headers['X-Mosa-Batch'],calls[1].headers['X-Mosa-Batch']);
  assert.deepEqual(calls[0].body,calls[1].body);
  assert.equal(events.filter(e=>e.type==='metrics').at(-1).dropped_audio_ms,0);
  assert.ok(events.some(e=>e.type==='final'&&e.original==='restored'));
  assert.equal(events.filter(e=>e.type==='status').at(-1).clearPartial,undefined);
  assert.equal(events.filter(e=>e.type==='metrics').at(-1).reconnects,1);
 }finally{input.stop();}
});

test('server state loss advances caption sequence even without a failed request',async()=>{
 let n=0;const events=[];
 const input=liveInput({base:'http://local',onEvent:e=>events.push(e),
  request:async()=>batch([{type:'session',instance:++n===1?'before':'after'},{type:'final',seq:0,original:'hello',translation:'你好',speech_start_ms:0,speech_end_ms:480,commit_samples:7680},{type:'batch_end'}])});
 try{
  input.push(new Float32Array(7680));await tick();
  input.push(new Float32Array(7680));await new Promise(resolve=>setTimeout(resolve,550));
  const finals=events.filter(e=>e.type==='final');
  assert.equal(finals.length,2);assert.ok(finals[1].seq>finals[0].seq);
 }finally{input.stop();}
});

test('overload drops bounded old audio and suppresses stale responses',async()=>{
 let resolve;let requests=0;const events=[];
 const input=liveInput({base:'http://local',onEvent:e=>events.push(e),
  request:async()=>{requests++;if(requests===1)return new Promise(r=>resolve=r);return batch([{type:'batch_end'}]);}});
 try{
  input.push(new Float32Array(7680));
  for(let i=0;i<40;i++)input.push(new Float32Array(7680));
  resolve(batch([{type:'final',seq:0,original:'stale',translation:'old'},{type:'batch_end'}]));await tick();
  assert.equal(events.filter(e=>e.type==='final').length,0);
  const metrics=events.filter(e=>e.type==='metrics').at(-1);
  assert.ok(metrics.dropped_audio_ms>0);assert.ok(metrics.queue_audio_ms<=16000);
  assert.ok(metrics.overflow_count>0);assert.equal(metrics.playback_reset_count,0);
  assert.equal(metrics.overflow_dropped_audio_ms,metrics.dropped_audio_ms);
  assert.equal(metrics.playback_dropped_audio_ms,0);
 }finally{input.stop();}
});

test('audio resync drops only uncommitted buffered samples and starts a fresh session',async()=>{
 let ids=0;const calls=[];const input=liveInput({base:'http://local',onEvent:()=>{},makeId:()=>`session-${++ids}`,request:async(url,init)=>{calls.push(init);return batch([{type:'batch_end',safe_samples:32000}]);}});
 try{input.push(new Float32Array(32000));await tick();input.push(new Float32Array(16000));input.resetAudio();input.push(new Float32Array(5120));await tick();assert.ok(calls.length>=2);assert.notEqual(calls.at(-1).headers['X-Mosa-Session'],calls[0].headers['X-Mosa-Session']);assert.equal(input.idle,true);}
 finally{input.stop();}
});
