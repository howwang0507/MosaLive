import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {capturePipeline} from '../web/engine.js';

test('web and extension use identical audio code',()=>{
 for(const f of ['engine.js','worklet.js','ndjson.js','live-client.js'])assert.equal(readFileSync(new URL('../web/'+f,import.meta.url),'utf8'),readFileSync(new URL('../extension/'+f,import.meta.url),'utf8'));
});

test('failed audio initialization releases context and capture tracks',async()=>{
 const saved=global.AudioContext;let closed=0,stopped=0;
 global.AudioContext=class{
  constructor(){this.audioWorklet={addModule:async()=>{throw Error('load failed');}};}
  createMediaStreamSource(){return {disconnect(){}};}
  async close(){closed++;}
 };
 try{
  await assert.rejects(capturePipeline({getTracks:()=>[{stop(){stopped++;}}]}),/load failed/);
  assert.equal(closed,1);assert.equal(stopped,1);
 }finally{global.AudioContext=saved;}
});

test('one pending chunk, clear cancellation, and idempotent stop',async()=>{
 const saved={fetch:global.fetch,AudioContext:global.AudioContext,AudioWorkletNode:global.AudioWorkletNode};
 let worklet,closeCount=0,stopCount=0;const inflight=[],events=[];
 const component=()=>({connect(){return this;},disconnect(){}});
 global.AudioContext=class{
  constructor(){this.audioWorklet={addModule:async()=>{}};this.destination={};}
  createMediaStreamSource(){return component();}
  createGain(){return {...component(),gain:{value:0}};}
  resume(){return Promise.resolve();}close(){closeCount++;}
 };
 global.AudioWorkletNode=class {constructor(){Object.assign(this,component());this.port={postMessage:()=>{}};worklet=this;}};
 global.fetch=(url,init)=>new Promise((resolve,reject)=>{inflight.push({resolve,init});init.signal.addEventListener('abort',()=>reject(Object.assign(new Error(),{name:'AbortError'})));});
 const track={stop(){stopCount++;},addEventListener(){}};
 let stop;
 const settle=()=>new Promise(resolve=>setImmediate(resolve));
 try{
  stop=await capturePipeline({getTracks:()=>[track]},{live:false,onEvent:e=>events.push(e)});
  const samples=new Float32Array(1600);
  worklet.port.onmessage({data:samples});worklet.port.onmessage({data:samples});worklet.port.onmessage({data:samples});
  assert.equal(inflight.length,1);assert.ok(events.some(e=>e.text.includes('略過')));
  assert.equal(inflight[0].init.headers['X-Mosa-Quality'],'review');
  stop.setQuality(false);
  stop.setSourceOnly(true);
  assert.equal(inflight[0].init.headers['X-Mosa-Quality'],'review','active request keeps original mode');
  inflight[0].resolve({ok:true,json:async()=>({original:'日文',translation:'譯文',mode:'real'})});
  await settle();assert.equal(inflight.length,2);
  assert.equal(inflight[1].init.headers['X-Mosa-Quality'],'fast','next queued request uses updated mode');
  assert.equal(inflight[1].init.headers['X-Mosa-Display'],'original');
  assert.deepEqual(JSON.parse(decodeURIComponent(inflight[1].init.headers['X-Mosa-Context'])),[], 'do not reuse context from before an audio drop');
  inflight[1].resolve({ok:true,json:async()=>({original:'Hello',translation:'',source_only:true,mode:'real'})});
  await settle();assert.ok(events.some(e=>e.type==='final'&&e.original==='Hello'&&e.translation===''));
  stop.setSourceOnly(false);worklet.port.onmessage({data:samples});
  assert.equal(inflight[2].init.headers['X-Mosa-Display'],'both');
  stop();stop();await settle();assert.equal(closeCount,1);assert.equal(stopCount,1);
  assert.equal(events.filter(e=>e.type==='final').length,2);assert.ok(inflight[2].init.signal.aborted);
 }finally{stop?.();Object.assign(global,saved);}
});
