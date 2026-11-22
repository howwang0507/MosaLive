import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';

async function overlay(saved={}){
 const nodes=new Map(),timers=new Map();let message,savedSettings,now=0,nextId=0;
 function advance(ms){now+=ms;for(const [id,t] of timers)if(t.at<=now){timers.delete(id);t.fn();}}
 const node=()=>{const attrs=new Map();return {style:{},hidden:false,textContent:'',prepend(){},setAttribute(k,v){attrs.set(k,v);},getAttribute(k){return attrs.get(k);},removeAttribute(k){attrs.delete(k);},getBoundingClientRect:()=>({width:600,height:100,left:0,top:0})};};
 const shadow={querySelector(selector){if(!nodes.has(selector))nodes.set(selector,node());return nodes.get(selector);}};
 const host={...node(),attachShadow:()=>shadow};
 vm.runInNewContext(readFileSync(new URL('../extension/overlay.js',import.meta.url),'utf8'),{
  window:{innerWidth:1200,innerHeight:800,addEventListener(){}},
  document:{createElement:()=>host,querySelector:()=>null,body:{append(){}},addEventListener(){}},
  innerWidth:1200,innerHeight:800,performance:{now:()=>now},setInterval:()=>0,clearInterval(){},
  ResizeObserver:class{observe(){}},clearTimeout(id){timers.delete(id);},setTimeout(fn,ms){const id=++nextId;timers.set(id,{fn,at:now+ms});return id;},
  chrome:{runtime:{sendMessage:async m=>{if(m.type==='set')savedSettings={...m.settings};return {ok:true,settings:saved};},onMessage:{addListener(fn){message=fn;}}}}
 });
 await new Promise(resolve=>setImmediate(resolve));
 return {nodes,message,advance,getSaved:()=>{advance(120);return savedSettings;}};
}

const send=(message,m)=>message({target:'overlay',...m});


test('final-only mode can lead with confirmed source while Chinese waits for the final',async()=>{
 const {nodes,message,advance}=await overlay({finalOnly:true,stableOriginal:true,displayMode:'zh'});
 const original=nodes.get('.original'),translated=nodes.get('.translated');
 send(message,{type:'partial',phase:'asr',seq:2,original:'We should wait for',stable_original:''});advance(150);
 assert.equal(original.textContent,'');
 send(message,{type:'partial',phase:'asr',seq:2,original:'We should wait for the team',stable_original:'We should wait'});advance(150);
 assert.equal(original.textContent,'We should wait …');assert.equal(original.hidden,false);
 assert.equal(original.getAttribute('data-early'),'true');assert.equal(translated.textContent,'');
 send(message,{type:'final',seq:2,original:'We should wait for the team.',translation:'我們應該等隊友。'});
 assert.equal(translated.textContent,'我們應該等隊友。');
 assert.equal(original.hidden,true);assert.equal(original.getAttribute('data-early'),undefined);
});

test('confirmed source does not cut short the reading time of the previous final',async()=>{
 const {nodes,message,advance}=await overlay({finalOnly:true,stableOriginal:true,displayMode:'zh',holdMs:-1});
 send(message,{type:'final',seq:1,original:'Hello everyone.',translation:'大家好。'});
 send(message,{type:'partial',phase:'asr',seq:2,original:'Today we',stable_original:'Today'});advance(150);
 assert.equal(nodes.get('.translated').textContent,'大家好。');
 advance(1300);
 send(message,{type:'partial',phase:'asr',seq:2,original:'Today we play',stable_original:'Today we'});advance(150);
 assert.equal(nodes.get('.original').textContent,'Today we …');
});

test('the option is off by default and ignored when final-only is off',async()=>{
 let o=await overlay({finalOnly:true,displayMode:'zh'});
 send(o.message,{type:'partial',phase:'asr',seq:2,original:'We should',stable_original:'We'});o.advance(150);
 assert.equal(o.nodes.get('.original').textContent,'');
 o=await overlay({finalOnly:false,stableOriginal:true,displayMode:'both'});
 send(o.message,{type:'partial',phase:'asr',seq:2,original:'We should',stable_original:'We'});
 o.advance(200);
 assert.equal(o.nodes.get('.original').textContent,'We should');       // existing raw preview
 assert.equal(o.nodes.get('.original').getAttribute('data-early'),undefined);
});
