import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';

test('empty, stalled, source switch, pause and ad events reset immediately and coalesce',()=>{
 let now=0,scan;const video=new EventTarget(),messages=[];video.currentSrc='first';
 vm.runInNewContext(readFileSync(new URL('../extension/playback.js',import.meta.url),'utf8'),{
  setTimeout:()=>1,clearTimeout(){},window:{},document:{documentElement:{},querySelector:()=>video},performance:{now:()=>now},
  MutationObserver:class{constructor(fn){scan=fn;}observe(){}},chrome:{runtime:{sendMessage:async m=>messages.push(m)}}
 });
 video.dispatchEvent(new Event('emptied'));video.dispatchEvent(new Event('stalled'));assert.equal(messages.length,1);
 now=600;video.currentSrc='second';video.dispatchEvent(new Event('timeupdate'));assert.equal(messages.length,2);
 scan();assert.equal(messages.length,2);
 for(const type of ['pause','adstart','adend','stalled']){now+=600;video.dispatchEvent(new Event(type));}
 assert.equal(messages.length,6);
});
test('Twitch playback ignores brief buffering, resets on seek, long stall and video replacement',()=>{
 let now=0,scan,video=new EventTarget();const messages=[];
 vm.runInNewContext(readFileSync(new URL('../extension/playback.js',import.meta.url),'utf8'),{
  setTimeout,clearTimeout,window:{},document:{documentElement:{},querySelector:()=>video},performance:{now:()=>now},
  MutationObserver:class{constructor(fn){scan=fn;}observe(){}},
  chrome:{runtime:{sendMessage:async m=>messages.push(m)}}
 });
 video.dispatchEvent(new Event('waiting'));now=200;video.dispatchEvent(new Event('playing'));
 assert.equal(messages.length,0);
 video.dispatchEvent(new Event('seeking'));assert.equal(messages.length,1);
 now=1000;video.dispatchEvent(new Event('stalled'));now=3000;video.dispatchEvent(new Event('playing'));
 assert.equal(messages.length,2);
 const old=video;now=4000;video=new EventTarget();scan();assert.equal(messages.length,3);
 old.dispatchEvent(new Event('seeking'));assert.equal(messages.length,3);
 assert.equal(messages[0].target,'offscreen');
});

test('preview videos cannot trigger a main-player audio reset',()=>{
 let now=1000,scan,main=new EventTarget(),preview=new EventTarget();const messages=[];
 vm.runInNewContext(readFileSync(new URL('../extension/playback.js',import.meta.url),'utf8'),{
  setTimeout,clearTimeout,window:{},document:{documentElement:{},querySelector:s=>s.includes('data-a-target')?main:preview},performance:{now:()=>now},
  MutationObserver:class{constructor(fn){scan=fn;}observe(){}},
  chrome:{runtime:{sendMessage:async m=>messages.push(m)}}
 });
 preview.dispatchEvent(new Event('seeking'));assert.equal(messages.length,0);
 preview=new EventTarget();scan();assert.equal(messages.length,0);
 main.dispatchEvent(new Event('seeking'));assert.equal(messages.length,1);
 const old=main;main=new EventTarget();now=2000;scan();assert.equal(messages.length,2);
 now=3000;old.dispatchEvent(new Event('seeking'));assert.equal(messages.length,2);
 main.dispatchEvent(new Event('seeking'));assert.equal(messages.length,3);
});
