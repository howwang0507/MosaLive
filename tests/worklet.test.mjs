import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';

test('reset clears fractional resampler state as well as packet samples',()=>{
 let Klass;const messages=[];
 vm.runInNewContext(readFileSync(new URL('../web/worklet.js',import.meta.url),'utf8'),{sampleRate:48000,Float32Array,AudioWorkletProcessor:class{constructor(){this.port={postMessage:x=>messages.push(x)};}},registerProcessor:(n,k)=>{Klass=k;}});
 const p=new Klass({processorOptions:{live:true}});
 p.process([[new Float32Array([1,1])]],[]);p.port.onmessage({data:'reset'});
 p.process([[new Float32Array([.25,.25,.25])]],[]);p.port.onmessage({data:'flush'});
 assert.equal(messages[0].resetDone,true);assert.deepEqual([...messages[1]],[.25]);
});
test('reset acknowledges after clearing old partial audio',()=>{
 let Klass;const messages=[];
 vm.runInNewContext(readFileSync(new URL('../web/worklet.js',import.meta.url),'utf8'),{sampleRate:16000,Float32Array,AudioWorkletProcessor:class{constructor(){this.port={postMessage:x=>messages.push(x)};}},registerProcessor:(n,k)=>{Klass=k;}});
 const p=new Klass({processorOptions:{live:true}});
 p.process([[new Float32Array(160).fill(.5)]],[]);
 p.port.onmessage({data:'reset'});
 assert.equal(messages[0].resetDone,true);
 p.process([[new Float32Array(160).fill(.25)]],[]);p.port.onmessage({data:'flush'});
 assert.equal(messages[1].length,160);assert.ok(messages[1].every(x=>x===.25));
});

test('long utterances settle on a short pause, short utterances keep the longer pause',()=>{
 for(const [duration,expected] of [[3.2,1],[1,0]]){
  let Klass;const chunks=[];
  vm.runInNewContext(readFileSync(new URL('../web/worklet.js',import.meta.url),'utf8'),{sampleRate:16000,Float32Array,AudioWorkletProcessor:class{constructor(){this.port={postMessage:x=>chunks.push(x)};}},registerProcessor:(n,k)=>{Klass=k;}});
  const processor=new Klass();
  for(let i=0;i<duration*100;i++)processor.process([[new Float32Array(160).fill(.1)]],[]);
  for(let i=0;i<25;i++)processor.process([[new Float32Array(160)]],[]);
  assert.equal(chunks.length,expected);
 }
});
test('five minutes of continuous 48k stereo yields 50 ordered 6s mono chunks',()=>{
 let Klass;const chunks=[];
 const context={sampleRate:48000,Float32Array,AudioWorkletProcessor:class {constructor(){this.port={postMessage:x=>chunks.push(x)};}},registerProcessor:(name,k)=>{Klass=k;}};
 vm.runInNewContext(readFileSync(new URL('../web/worklet.js',import.meta.url),'utf8'),context);
 const processor=new Klass(),left=new Float32Array(128).fill(.5),right=new Float32Array(128).fill(-.25);
 for(let n=0;n<48000*300/128;n++)processor.process([[left,right]],[]);
 assert.equal(chunks.length,50);
 assert.ok(chunks.every(x=>x.length===96000&&Math.abs(x[0]-.125)<1e-6));
});
test('live mode sends silence and speech every 320ms and flushes remainder',()=>{
 let Klass;const chunks=[];
 vm.runInNewContext(readFileSync(new URL('../web/worklet.js',import.meta.url),'utf8'),{sampleRate:48000,Float32Array,
  AudioWorkletProcessor:class{constructor(){this.port={postMessage:x=>chunks.push(x)};}},registerProcessor:(name,k)=>{Klass=k;}});
 const processor=new Klass({processorOptions:{live:true}});
 for(let i=0;i<400;i++)processor.process([[new Float32Array(128)]],[]);
 assert.equal(chunks.length,3);assert.ok(chunks.every(x=>x.length===5120));
 processor.port.onmessage({data:'flush'});
 assert.ok(chunks[3].length<5120);assert.equal(chunks[4].flush,true);
 assert.equal(chunks.slice(0,4).reduce((n,x)=>n+x.length,0),Math.floor(400*128/3));
});

test('flush emits short tail once',()=>{
 let Klass;const chunks=[];
 const context={sampleRate:16000,Float32Array,AudioWorkletProcessor:class {constructor(){this.port={postMessage:x=>chunks.push(x)};}},registerProcessor:(name,k)=>{Klass=k;}};
 vm.runInNewContext(readFileSync(new URL('../web/worklet.js',import.meta.url),'utf8'),context);
 const processor=new Klass();processor.process([[new Float32Array(1600).fill(.25)]],[]);
 assert.equal(chunks.length,0);processor.port.onmessage({data:'flush'});
 assert.equal(chunks.length,1);assert.equal(chunks[0].length,1600);
 processor.port.onmessage({data:'flush'});assert.equal(chunks.length,1);
});
