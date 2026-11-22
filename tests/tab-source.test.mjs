import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';

function setup(current=null,ready=true){
 let click;const events=[],listeners=[];
 const chrome={action:{onClicked:{addListener:fn=>click=fn},setBadgeText:async()=>{},setTitle:async()=>{}},
 runtime:{getURL:p=>'chrome-extension://test/'+p,getContexts:async()=>current===null?[]:[{}],onMessage:{addListener:fn=>listeners.push(fn)},sendMessage:async m=>{events.push(m.type);return m.type==='state'?{tabId:current,active:true}:{ok:true};}},
 tabs:{query:async()=>[{id:2,url:'https://example.com/video'}]},
 offscreen:{createDocument:async()=>events.push('create'),closeDocument:async()=>events.push('close')},
 scripting:{executeScript:async()=>events.push('inject')},tabCapture:{getMediaStreamId:async()=> 'stream'}};
 vm.runInNewContext(readFileSync(new URL('../extension/background.js',import.meta.url),'utf8'),{chrome,AbortSignal,fetch:async()=>({ok:true,json:async()=>({ready})})});
 return {click,events,control:(type,tabId=2)=>new Promise((resolve,reject)=>{
  const message={target:'controls',type,tabId},sender={url:'chrome-extension://test/popup.html'};
  // Chrome dispatches to every registered listener, not only listener zero.
  if(!listeners.some(listener=>listener(message,sender,resolve)===true))reject(Error('No response listener'));
 }),listeners};
}
test('closing the captured tab stops audio; unrelated tabs do not',async()=>{
 let removed;const events=[];
 vm.runInNewContext(readFileSync(new URL('../extension/background.js',import.meta.url),'utf8'),{
  chrome:{tabs:{onRemoved:{addListener:fn=>removed=fn}},action:{onClicked:{addListener(){}},setBadgeText:async()=>{},setTitle:async()=>{}},
   runtime:{onMessage:{addListener(){}},getContexts:async()=>[{}],sendMessage:async m=>{events.push(m.type);return {tabId:2};}},offscreen:{closeDocument:async()=>events.push('close')}}
 });
 await removed(3);assert.deepEqual(events,['state']);events.length=0;
 await removed(2);assert.deepEqual(events,['state','stop','close']);
});
test('a non-Twitch HTTPS tab can start capture',async()=>{
 const s=setup();await s.click({id:2,url:'https://example.com/video'});
 assert.deepEqual(s.events,['inject','create','start']);
});

test('unready service does not inject scripts or start audio capture',async()=>{
 const s=setup(null,false);
 assert.equal((await s.control('start')).ok,false);
 assert.deepEqual(s.events,[]);
});
test('popup starts current tab and exposes capture state',async()=>{
 const s=setup();assert.equal((await s.control('start')).ok,true);
 assert.deepEqual(s.events,['inject','create','start']);
 const live=setup(2);const state=await live.control('state');assert.equal(state.active,true);assert.equal(state.tabId,2);
 assert.equal((await live.control('start')).ok,true);assert.ok(!live.events.includes('stop'));
});
test('popup rejects stale selected tab and can stop an existing capture',async()=>{
 const s=setup();assert.equal((await s.control('start',3)).ok,false);assert.ok(!s.events.includes('start'));
 const live=setup(2);assert.equal((await live.control('stop')).ok,true);assert.deepEqual(live.events,['stop','close']);
});
test('content scripts cannot invoke popup controls',()=>{
 const s=setup();let replied=false;
 const result=s.listeners[0]({target:'controls',type:'stop'},{url:'https://example.com/video'},()=>replied=true);
 assert.equal(result,undefined);assert.equal(replied,false);assert.deepEqual(s.events,[]);
});
test('clicking the captured tab stops; clicking another tab switches',async()=>{
 const stop=setup(2);await stop.click({id:2,url:'https://example.com/video'});
 assert.deepEqual(stop.events,['state','stop','close']);
 const change=setup(2);await change.click({id:3,url:'https://example.org/video'});
 assert.deepEqual(change.events,['state','stop','close','inject','create','start']);
});
test('an internal browser page does not interrupt an active capture',async()=>{
 const s=setup(2);await s.click({id:3,url:'chrome://extensions'});
 assert.ok(!s.events.includes('stop'));
 assert.ok(!s.events.includes('close'));
});
