import test from 'node:test';
import assert from 'node:assert/strict';
import {server} from '../server.mjs';
test('glossary API reads terms and rejects invalid writes and unrelated origins',async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const url=`http://127.0.0.1:${server.address().port}/glossary`;
 try{
  const before=await (await fetch(url)).json();assert.ok(Array.isArray(before.terms));
  const invalid=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify([{ja:'',zh:'test'}])});
  assert.equal(invalid.status,400);
  const blocked=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json',Origin:'https://example.com'},body:'[]'});assert.equal(blocked.status,403);
  assert.deepEqual(await (await fetch(url)).json(),before);
 }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});
