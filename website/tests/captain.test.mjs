import test from 'node:test';
import assert from 'node:assert/strict';
import {createCompanion} from '../dist/companion.mjs';

const flush=()=>new Promise(resolve=>setImmediate(resolve));
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const state=(id,awaiting=true)=>({captain:{id,name:'Captain '+id},messages:[{role:'captain',text:'Conversation '+id,created:1}],checkin:awaiting?{id:'check-'+id,status:'awaiting'}:null});
function setup(t,handler){
  class Element {
    constructor(){this.dataset={};this.textContent='';this.innerHTML='';this.value='';this.disabled=false;this.hidden=true;this.open=false;this.events={};}
    replaceChildren(){this.innerHTML='';}
    showModal(){this.open=true;}
    close(){this.open=false;this.events.close?.();}
    addEventListener(name,fn){this.events[name]=fn;}
    querySelectorAll(selector){return selector.includes('#captain-send')?[...actions,el('#captain-send')]:actions;}
  }
  const elements=new Map(),el=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
  const actions=['all_good','need_help','unsafe','status'].map((name,i)=>{const node=el(i===0?'#captain-good':'#'+name);node.dataset.captainAction=name;return node;});
  const doc={hidden:false,querySelector:el,addEventListener(){}};
  let timer,user={id:'rider'},calls=[];
  const previous={document:globalThis.document,setInterval:globalThis.setInterval,clearInterval:globalThis.clearInterval};
  globalThis.document=doc;globalThis.setInterval=fn=>{timer=fn;return 1;};globalThis.clearInterval=()=>{};
  t.after(()=>Object.assign(globalThis,previous));
  const api={request:(path,method,body)=>{calls.push({path,method,body});return path==='/v1/captain/checkins'?Promise.resolve({checkins:[]}):handler(path,method,body);}};
  const companion=createCompanion({api,getUser:()=>user,getView:()=> 'trips',openSOS(){},toast(){}});
  companion.sessionChanged();
  return {companion,el,actions,calls,tick:()=>timer(),logout:()=>{user=null;companion.sessionChanged();}};
}

test('switching Captains discards the previous ride response and stale check-in',async t=>{
  const a=deferred(),b=deferred();
  const x=setup(t,path=>path.includes('/A/')?a.promise:b.promise);
  const first=x.companion.open('A'),second=x.companion.open('B');
  assert.equal(x.el('#captain-good').dataset.checkin,'');
  b.resolve(state('B'));await second;a.resolve(state('A'));await first;
  assert.equal(x.el('#captain-name').textContent,'Captain B');
  assert.equal(x.el('#captain-good').dataset.checkin,'check-B');
});

test('failed old Captain request does not place an error in the new chat',async t=>{
  const a=deferred();const x=setup(t,path=>path.includes('/A/')?a.promise:Promise.resolve(state('B')));
  const first=x.companion.open('A');await x.companion.open('B');a.reject(Error('Old error'));await first;
  assert.equal(x.el('#captain-error').textContent,'');
});

test('quick check-in reply supplies its ID and disables All good after answer',async t=>{
  let answered=false;
  const x=setup(t,(path,method)=>{if(method==='POST')answered=true;return Promise.resolve(state('A',!answered));});
  await x.companion.open('A');x.actions[0].onclick();await flush();
  const sent=x.calls.find(c=>c.method==='POST');
  assert.equal(sent.body.checkin_id,'check-A');assert.equal(sent.body.action,'all_good');
  assert.match(sent.body.request_id,/^[a-f0-9-]{36}$/);assert.equal(x.el('#captain-good').disabled,true);
});

test('a slow pre-send GET cannot overwrite the answered state',async t=>{
  const old=deferred();let gets=0,answered=false;
  const x=setup(t,(path,method)=>{if(method==='POST'){answered=true;return Promise.resolve(state('A',false));}if(++gets===2)return old.promise;return Promise.resolve(state('A',!answered));});
  await x.companion.open('A');x.tick();x.actions[0].onclick();await flush();
  old.resolve(state('A',true));await flush();
  assert.equal(x.el('#captain-good').dataset.checkin,'');assert.equal(x.el('#captain-good').disabled,true);
});

test('help on a newly opened chat never reuses the old ride check-in',async t=>{
  const b=deferred();const x=setup(t,(path,method)=>method==='POST'?Promise.resolve(state('B',false)):path.includes('/B/')?b.promise:Promise.resolve(state('A')));
  await x.companion.open('A');const opening=x.companion.open('B');x.actions[1].onclick();await flush();
  const sent=x.calls.find(c=>c.method==='POST');assert.match(sent.path,/\/B\/captain\/messages$/);assert.equal(sent.body.checkin_id,undefined);
  b.resolve(state('B',false));await opening;await flush();
});

test('logout clears private history and ignores an in-flight response',async t=>{
  const pending=deferred();const x=setup(t,()=>pending.promise);const opening=x.companion.open('A');x.logout();pending.resolve(state('A'));await opening;
  assert.equal(x.el('#captain-messages').innerHTML,'');assert.equal(x.el('#captain-dialog').open,false);
});
