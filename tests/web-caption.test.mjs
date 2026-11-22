import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import {CaptionState} from '../web/engine.js';

test('web replaces previous captions and expires stalled partials and finals',()=>{
 const nodes=new Map(),timers=new Map();let now=0,id=0;
 const get=key=>{if(!nodes.has(key))nodes.set(key,{textContent:'',value:'both',style:{},addEventListener(){}});return nodes.get(key);};
 const context=vm.createContext({
  CaptionState,document:{getElementById:get},window:{addEventListener(){}},localStorage:{getItem(){return null;}},
  fetch:async()=>({json:async()=>({ready:true})}),setInterval(){},
  setTimeout(fn,ms){timers.set(++id,{fn,at:now+ms});return id;},clearTimeout(id){timers.delete(id);}
 });
 vm.runInContext(readFileSync(new URL('../web/app.js',import.meta.url),'utf8').replace(/^import .*\r?\n/,''),context);
 get('holdMs').onchange({target:{value:'3000'}});
 const advance=ms=>{now+=ms;for(const [id,t] of timers)if(t.at<=now){timers.delete(id);t.fn();}};
 const send=(type,seq,translation)=>context.receive({type,seq,translation,original:'source',transport_model_ms:1});
 send('final',0,'old');advance(1000);send('partial',1,'new');advance(500);
 assert.equal(get('translation').textContent,'new');
 send('final',0,'late');assert.equal(get('translation').textContent,'new');
 advance(1000);assert.equal(get('translation').textContent,'new');
 send('final',1,'done');advance(2999);assert.equal(get('translation').textContent,'done');
 advance(1);assert.equal(get('translation').textContent,'');
 send('partial',2,'draft');context.receive({type:'status',clearPartial:true,text:'failed'});
 assert.equal(get('translation').textContent,'');
 assert.match(get('log').textContent,/done/);
 send('final',3,'paired');advance(1000);
 context.receive({type:'partial',seq:4,phase:'asr',original:'next source',translation:''});
 assert.equal(get('translation').textContent,'paired');assert.equal(get('original').textContent,'source');
 advance(2000);assert.equal(get('translation').textContent,'');
 context.receive({type:'partial',seq:4,original:'next source',translation:'next translation'});
 assert.equal(get('original').textContent,'next source');
 get('holdMs').onchange({target:{value:'0'}});advance(60000);
 assert.equal(get('translation').textContent,'next translation');
 context.clear();assert.equal(get('translation').textContent,'');
});
