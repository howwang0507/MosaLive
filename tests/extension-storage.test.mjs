import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import {SessionStats} from '../extension/session-stats.js';

test('offscreen starts with runtime only and receives review setting',async()=>{
 let listener,options;
 const code=readFileSync(new URL('../extension/offscreen.js',import.meta.url),'utf8').replace(/^import .*\n/gm,'');
 const context={chrome:{runtime:{onMessage:{addListener:fn=>listener=fn},sendMessage:async()=>{}}},
  navigator:{mediaDevices:{getUserMedia:async()=>({getTracks:()=>[]})}},
  capturePipeline:async(s,o)=>{options=o;return ()=>{};}};
 vm.runInNewContext(code,{...context,SessionStats});
 const result=await new Promise(resolve=>listener({target:'offscreen',type:'start',tabId:1,id:'test',review:false},{},resolve));
 assert.equal(result.ok,true);assert.equal(options.quality,false);
});

test('settings without storage permission returns error instead of throwing',async()=>{
 const listeners=[];
 vm.runInNewContext(readFileSync(new URL('../extension/background.js',import.meta.url),'utf8'),{
  chrome:{action:{onClicked:{addListener(){}}},runtime:{onMessage:{addListener:fn=>listeners.push(fn)}}}
 });
 const result=await new Promise(resolve=>listeners.at(-1)({target:'settings',type:'get'},{},resolve));
 assert.equal(result.ok,false);assert.match(result.error,/權限/);
});
