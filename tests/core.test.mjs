import test from 'node:test';import assert from 'node:assert/strict';
import {wav,CaptionState} from '../web/engine.js';import {validWav,server} from '../server.mjs';
test('PCM waveform is valid mono16k WAV and clipped',()=>{const b=Buffer.from(wav(new Float32Array([2,-2,0])));assert.equal(validWav(b),true);assert.equal(b.readInt16LE(44),32767);assert.equal(b.readInt16LE(46),-32767);});
test('wrong sample rate rejected',()=>{const b=Buffer.from(wav(new Float32Array(160)));b.writeUInt32LE(48000,24);assert.equal(validWav(b),false);});
test('late, duplicate and interim events rejected; only current caption retained',()=>{const s=new CaptionState();for(const seq of [0,1,2])assert.ok(s.accept({seq,type:'final'}));assert.equal(s.lines.length,1);assert.equal(s.accept({seq:1,type:'final'}),false);assert.equal(s.accept({seq:3,type:'interim'}),false);s.clear();assert.equal(s.lines.length,0);assert.equal(s.accept({seq:2,type:'final'}),false);assert.ok(s.acceptPartial({seq:4,type:'partial'}));assert.equal(s.accept({seq:3,type:'final'}),false);assert.ok(s.accept({seq:4,type:'final'}));assert.equal(s.acceptPartial({seq:4,type:'partial'}),false);});
test('HTTP unavailable model is explicit and no fixture substituted',async()=>{await new Promise(r=>server.listen(0,'127.0.0.1',r));try{
 const base='http://127.0.0.1:'+server.address().port;
 const r=await fetch(base+'/segment',{method:'POST',body:wav(new Float32Array(160))});assert.equal(r.status,503);assert.match((await r.json()).error,/尚未設定/);
 const denied=await fetch(base+'/segment',{method:'POST',headers:{Origin:'https://evil.example'},body:wav(new Float32Array(160))});assert.equal(denied.status,403);
 const traversal=await fetch(base+'/package.json');assert.equal(traversal.status,404);
 }finally{await new Promise(r=>server.close(r));}});
