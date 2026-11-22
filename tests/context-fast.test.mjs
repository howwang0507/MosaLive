import test from 'node:test';
import assert from 'node:assert/strict';
import {requestSegment} from '../web/engine.js';

test('single-pass requests preserve source context without requesting review',async()=>{
 const old=global.fetch;let captured;
 global.fetch=async(url,init)=>{captured=init;return {ok:true,json:async()=>({translation:'測試'})};};
 try{
  await requestSegment(new ArrayBuffer(0),{quality:false,context:['前の文です']});
  assert.equal(captured.headers['X-Mosa-Quality'],'fast');
  assert.deepEqual(JSON.parse(decodeURIComponent(captured.headers['X-Mosa-Context'])),['前の文です']);
 }finally{global.fetch=old;}
});
