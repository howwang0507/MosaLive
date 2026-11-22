import test from 'node:test';
import assert from 'node:assert/strict';
import {readNDJSON} from '../web/ndjson.js';
import {requestSegment} from '../web/engine.js';
function body(text){const bytes=new TextEncoder().encode(text);return new ReadableStream({start(c){for(const b of bytes)c.enqueue(new Uint8Array([b]));c.close();}});}
test('NDJSON handles UTF8 split across every byte and final unterminated line',async()=>{
 const events=[];for await(const e of readNDJSON(body('{"text":"繁體中文"}\n{"text":"日文"}')))events.push(e);
 assert.deepEqual(events,[{text:'繁體中文'},{text:'日文'}]);
});
test('partial updates precede final and truncated stream cannot become final',async()=>{
 const saved=global.fetch;try{
  global.fetch=async()=>({ok:true,headers:new Headers({'Content-Type':'application/x-ndjson'}),body:body('{"type":"partial","translation":"暫定中文"}\n{"type":"final","translation":"完成譯文"}\n')});
  const partials=[];const final=await requestSegment(new ArrayBuffer(0),{onPartial:p=>partials.push(p)});
  assert.equal(partials.length,1);assert.equal(final.translation,'完成譯文');assert.ok(final.first_visible_ms>=0);
  global.fetch=async()=>({ok:true,headers:new Headers({'Content-Type':'application/x-ndjson'}),body:body('{"type":"partial","translation":"未完成"}\n')});
  await assert.rejects(requestSegment(new ArrayBuffer(0)),/未收到定稿/);
 }finally{global.fetch=saved;}
});
