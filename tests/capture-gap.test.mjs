import test from 'node:test';
import assert from 'node:assert/strict';
import {liveInput} from '../web/live-client.js';

const batch=events=>new Response(events.map(e=>JSON.stringify(e)).join('\n')+'\n');
const tick=()=>new Promise(resolve=>setImmediate(resolve));

// 2026-11-08 Twitch test: after the video buffered, measured latency stayed ~7.5 s high for
// minutes while captions were visibly ~1 s behind, until a playback reset re-anchored the clock.
test('a capture pause re-anchors the latency clock and is reported as a gap',async()=>{
 const realNow=performance.now;let t=1000;performance.now=()=>t;
 const events=[];let calls=0;
 const input=liveInput({base:'http://local',onEvent:e=>events.push(e),request:async(u,o)=>{
  calls++;
  if(calls===2)return batch([{type:'final',seq:0,original:'after pause',speech_start_ms:1000,speech_end_ms:1500,commit_samples:16000},{type:'batch_end',safe_samples:16000}]);
  return batch([{type:'batch_end',safe_samples:o.body.length}]);
 }});
 try{
  input.push(new Float32Array(16000));await tick();      // 1 s of audio, arrived on time
  t=11000;input.push(new Float32Array(16000));            // next second arrives 9 s late
  t=11500;await tick();await tick();
  const final=events.find(e=>e.type==='final');
  assert.ok(final,'final delivered');
  assert.equal(Math.round(final.capture_to_caption_ms),1500);   // was 10500 before the fix
  assert.equal(Math.round(final.after_speech_ms),1000);
  input.resetAudio();
  const m=events.filter(e=>e.type==='metrics').at(-1);
  assert.equal(m.capture_gap_count,1);assert.equal(m.capture_gap_ms,9000);
 }finally{input.stop();performance.now=realNow;}
});

test('audio arriving on time or early does not count as a gap',async()=>{
 const realNow=performance.now;let t=0;performance.now=()=>t;
 const events=[];
 const input=liveInput({base:'http://local',onEvent:e=>events.push(e),request:async(u,o)=>batch([{type:'batch_end',safe_samples:o.body.length}])});
 try{
  for(let i=1;i<=5;i++){t=i*1000+600;input.push(new Float32Array(16000));await tick();}  // up to 600 ms jitter
  input.push(new Float32Array(16000));                       // burst, earlier than real time
  input.resetAudio();
  const m=events.filter(e=>e.type==='metrics').at(-1);
  assert.equal(m.capture_gap_count,0);assert.equal(m.capture_gap_ms,0);
 }finally{input.stop();performance.now=realNow;}
});
