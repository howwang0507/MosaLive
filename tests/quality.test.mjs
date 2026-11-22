import test from 'node:test';
import assert from 'node:assert/strict';
import {decodeContext,validateGlossary} from '../quality.mjs';
test('context accepts only two bounded Japanese-source strings',()=>{
 assert.deepEqual(decodeContext(encodeURIComponent(JSON.stringify(['前文一','前文二']))),['前文一','前文二']);
 assert.throws(()=>decodeContext(encodeURIComponent('[1]')));
 assert.throws(()=>decodeContext(encodeURIComponent('["a","b","c"]')));
 assert.throws(()=>decodeContext('x'.repeat(8001)));
});
test('glossary rejects malformed entries and excessive sizes',()=>{
 assert.deepEqual(validateGlossary([{ja:'配信',zh:'直播'}]),[{ja:'配信',zh:'直播'}]);
 assert.throws(()=>validateGlossary([{ja:'',zh:'直播'}]));
 assert.throws(()=>validateGlossary([{ja:'配信',zh:{}}]));
});
