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

test('keyboard controls clear captions, cycle modes and restore click-through',async()=>{
 const {nodes,message,getSaved}=await overlay({outline:true});
 message({target:'overlay',type:'final',seq:1,original:'Hi',translation:'你好'});
 message({target:'overlay',type:'clear-caption'});assert.equal(nodes.get('.translated').textContent,'');
 message({target:'overlay',type:'cycle-display'});assert.equal(getSaved().displayMode,'zh');
 message({target:'overlay',type:'toggle-through'});assert.equal(getSaved().clickThrough,true);
 assert.match(nodes.get('.box').className,/through/);assert.match(nodes.get('.box').className,/outline/);
 message({target:'overlay',type:'toggle-through'});assert.equal(getSaved().clickThrough,false);
});
test('automatic hold gives long captions more reading time and expires both',async()=>{
 const {nodes,message,advance}=await overlay({holdMs:-1});
 message({target:'overlay',type:'final',seq:1,original:'Hi',translation:'你好'});
 advance(2499);assert.equal(nodes.get('.translated').textContent,'你好');advance(1);assert.equal(nodes.get('.translated').textContent,'');
 message({target:'overlay',type:'final',seq:2,original:'long',translation:'字'.repeat(100)});
 advance(7999);assert.ok(nodes.get('.translated').textContent);advance(1);assert.equal(nodes.get('.translated').textContent,'');
});
test('three display modes hide the correct text and preserve selection during new captions',async()=>{
 const {nodes,message,getSaved}=await overlay();
 for(const [mode,hideSource,hideTranslation] of [['zh',true,false],['original',false,true],['both',false,false]]){
  nodes.get('.language').onchange({target:{value:mode}});
  message({target:'overlay',type:'partial',seq:1,original:'Hello / こんにちは',translation:'你好'});
  assert.equal(nodes.get('.original').hidden,hideSource);
  assert.equal(nodes.get('.translated').hidden,hideTranslation);
  assert.equal(getSaved().displayMode,mode);
 }
});

test('saved original mode reloads and legacy Chinese-only setting migrates',async()=>{
 for(const [saved,mode] of [[{displayMode:'original'},'original'],[{bilingual:false},'zh'],[{},'both']]){
  const {nodes}=await overlay(saved);
  assert.equal(nodes.get('.language').value,mode);
 }
});

test('final survives next partial and retry, expires on time, and is replaced by next final',async()=>{
 for(const displayMode of ['both','zh','original']){
  const {nodes,message,advance}=await overlay({displayMode,holdMs:3000});
  const send=(type,seq,translation)=>message({target:'overlay',type,seq,original:'source '+seq,translation});
  send('final',0,'old');advance(1000);send('partial',1,'new');advance(120);
  assert.equal(nodes.get('.translated').textContent,'old');
  message({target:'overlay',type:'status',text:'連線中斷，稍後重試'});
  send('final',0,'late');assert.equal(nodes.get('.translated').textContent,'old');
  advance(1879);assert.equal(nodes.get('.translated').textContent,'old');
  advance(1);assert.equal(nodes.get('.translated').textContent,'');assert.equal(nodes.get('.original').textContent,'');
  send('final',1,'done');send('final',2,'next');assert.equal(nodes.get('.translated').textContent,'next');
  message({target:'overlay',type:'status',clear:true,text:'換片'});assert.equal(nodes.get('.translated').textContent,'');
  send('partial',2,'draft');message({target:'overlay',type:'status',clearPartial:true,text:'failed'});
  assert.equal(nodes.get('.translated').textContent,'');
 }
});

test('background persists all valid display modes',async()=>{
 const listeners=[];let stored={};
 vm.runInNewContext(readFileSync(new URL('../extension/background.js',import.meta.url),'utf8'),{
  chrome:{action:{onClicked:{addListener(){}}},runtime:{onMessage:{addListener:fn=>listeners.push(fn)}},storage:{local:{set:async value=>{stored=value;},get:async()=>stored}}}
 });
 for(const displayMode of ['zh','original','both']){
  const reply=await new Promise(resolve=>listeners.at(-1)({target:'settings',type:'set',settings:{displayMode,holdMs:8000}},{},resolve));
  assert.equal(reply.ok,true);assert.equal(stored.mosaOverlaySettings.displayMode,displayMode);
  assert.equal(stored.mosaOverlaySettings.holdMs,8000);
 }
});

test('retains matching bilingual pair while next translation is pending without extending expiry',async()=>{
 const {nodes,message,advance}=await overlay({holdMs:5000});
 message({target:'overlay',type:'final',seq:0,original:'old source',translation:'舊譯文',speaker:1});
 advance(4000);
 message({target:'overlay',type:'partial',seq:1,phase:'asr',original:'new source',translation:''});
 advance(120);
 assert.equal(nodes.get('.original').textContent,'old source');
 assert.equal(nodes.get('.translated').textContent,'舊譯文');
 assert.match(nodes.get('.status').textContent,/正在翻譯下一句/);
 advance(880);assert.equal(nodes.get('.translated').textContent,'');
 message({target:'overlay',type:'partial',seq:1,original:'new source',translation:'新譯文'});
 advance(120);
 assert.equal(nodes.get('.original').textContent,'new source');
 assert.equal(nodes.get('.translated').textContent,'新譯文');
 nodes.get('.hold').onchange({target:{value:'0'}});advance(60000);
 assert.equal(nodes.get('.translated').textContent,'新譯文');
 nodes.get('.clear-caption').onclick();assert.equal(nodes.get('.translated').textContent,'');
});

test('hold preference and ASR selection restore on reload',async()=>{
 const {nodes,getSaved}=await overlay({holdMs:8000,asrMode:'stream-ja'});
 assert.equal(nodes.get('.hold').value,'8000');assert.equal(nodes.get('.asr').value,'stream-ja');
 nodes.get('.hold').onchange({target:{value:'2000'}});
 assert.equal(getSaved().holdMs,2000);
});

test('language lock mode persists',async()=>{
 const {nodes,message,getSaved}=await overlay();
 await nodes.get('.asr').onchange({target:{value:'stream-ko'}});
 assert.equal(getSaved().asrMode,'stream-ko');
});
