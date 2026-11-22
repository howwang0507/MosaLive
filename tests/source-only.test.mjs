import test from 'node:test';
import assert from 'node:assert/strict';

test('source-only returns ASR even when translation service is absent',async()=>{
 const saved={fetch:global.fetch,asr:process.env.ASR_URL,nmt:process.env.TRANSLATION_URL};
 process.env.ASR_URL='http://asr.test/transcribe';delete process.env.TRANSLATION_URL;
 let calls=0;
 global.fetch=async url=>{calls++;assert.equal(url,process.env.ASR_URL);return {ok:true,json:async()=>({text:'Hello everyone'})};};
 try{
  const {infer}=await import('../server.mjs?source-only-test');
  const result=await infer(Buffer.alloc(0),null,null,{sourceOnly:true});
  assert.equal(calls,1);assert.equal(result.original,'Hello everyone');
  assert.equal(result.translation,'');assert.equal(result.translation_ms,0);assert.equal(result.source_only,true);
 }finally{
  global.fetch=saved.fetch;
  for(const [key,value] of [['ASR_URL',saved.asr],['TRANSLATION_URL',saved.nmt]])if(value===undefined)delete process.env[key];else process.env[key]=value;
 }
});
