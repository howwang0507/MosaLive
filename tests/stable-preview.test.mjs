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

test('stable preview shows agreed translations early even in final-only mode',async()=>{
 const {nodes,message}=await overlay({finalOnly:true,stablePreview:true,displayMode:'zh'});
 send(message,{type:'partial',phase:'asr',seq:2,original:'We should',translation:''});
 assert.equal(nodes.get('.translated').textContent,'');
 send(message,{type:'partial',phase:'stable',seq:2,original:'We should wait',translation:'我們應該等'});
 assert.equal(nodes.get('.translated').textContent,'我們應該等');
 send(message,{type:'final',seq:2,original:'We should wait for the team.',translation:'我們應該等隊友。'});
 assert.equal(nodes.get('.translated').textContent,'我們應該等隊友。');
});

test('a fresh final stays readable before the next stable preview replaces it',async()=>{
 const {nodes,message,advance}=await overlay({finalOnly:true,stablePreview:true,displayMode:'zh',holdMs:0});
 send(message,{type:'final',seq:1,original:'Hi',translation:'你好'});
 send(message,{type:'partial',phase:'stable',seq:2,original:'Next one',translation:'下一句'});
 assert.equal(nodes.get('.translated').textContent,'你好');
 advance(1199);assert.equal(nodes.get('.translated').textContent,'你好');
 advance(1);assert.equal(nodes.get('.translated').textContent,'下一句');
});

test('a newer final cancels a pending stable preview',async()=>{
 const {nodes,message,advance}=await overlay({finalOnly:true,stablePreview:true,displayMode:'zh',holdMs:0});
 send(message,{type:'final',seq:1,original:'Hi',translation:'你好'});
 send(message,{type:'partial',phase:'stable',seq:2,original:'Next',translation:'下一'});
 advance(500);
 send(message,{type:'final',seq:2,original:'Next one.',translation:'下一句。'});
 advance(3000);assert.equal(nodes.get('.translated').textContent,'下一句。');
});

test('without stable preview, final-only mode still hides every preview',async()=>{
 const {nodes,message,advance}=await overlay({finalOnly:true,displayMode:'zh'});
 send(message,{type:'partial',phase:'stable',seq:2,original:'We should wait',translation:'我們應該等'});
 advance(200);assert.equal(nodes.get('.translated').textContent,'');
});

test('stable preview setting is saved',async()=>{
 const {nodes,getSaved}=await overlay({});
 nodes.get('.stable-option').onchange({target:{checked:true}});
 assert.equal(getSaved().stablePreview,true);
});
