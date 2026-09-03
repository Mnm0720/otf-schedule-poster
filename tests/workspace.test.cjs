const {test}=require('node:test');
const assert=require('node:assert/strict');
const {EditorState}=require('../web/editor-state.js');
const schedule=()=>({year:2026,month:9,subtitle:'Original',theme:'',events:[],notes:[],footnotes:[],days:[{day:1,entries:[{category:'std'}],repeat_of:null}]});
const result=d=>({schedule:d,defaults:{credits:'Default'},categories:[]});

test('undo and redo survive regeneration; reset section preserves other edits and is undoable',()=>{
 const s=new EditorState(); s.accept(result(schedule()));
 s.edit(d=>{d.subtitle='Changed';}); s.edit(d=>{d.credits='Team';});
 s.accept(result(s.draft)); s.undo(); assert.equal(s.draft.credits,'Default');
 assert.equal(s.draft.subtitle,'Changed'); assert.equal(s.dirty,true);
 s.redo(); assert.equal(s.draft.credits,'Team'); assert.equal(s.dirty,false);
 s.resetSection('title'); assert.equal(s.draft.subtitle,'Original'); assert.equal(s.draft.credits,'Team');
 s.undo(); assert.equal(s.draft.subtitle,'Changed');
 s.edit(d=>{d.theme='New branch';}); assert.equal(s.canRedo,false);
});
test('snapshot restores pending changes, original baseline, and history',()=>{
 const s=new EditorState();s.accept(result(schedule()));s.edit(d=>{d.subtitle='Pending';});
 const snapshot=s.snapshot(); const restored=new EditorState();restored.accept(result(snapshot.rendered));restored.restore(snapshot);
 assert.equal(restored.draft.subtitle,'Pending');assert.equal(restored.dirty,true);
 restored.undo();assert.equal(restored.draft.subtitle,'Original');
});

test('restoring older JSON fills day defaults and retains promoted custom type choices',()=>{
 const s=new EditorState(),data=schedule();
 data.custom_categories={custom_abc:{label:'New class',color:'#123456'}};
 data.days[0].entries=[{category:'custom_abc',title:'New class'}];s.accept(result(data));
 const old={year:2026,month:9,days:[{day:1,entries:[{category:'unknown',title:'New class'}]}]};
 s.restore({draft:old,rendered:old,initial:old,past:[],future:[]});
 assert.equal(s.draft.days[0].repeat_of,null);assert.equal(s.draft.days[0].entries[0].category,'custom_abc');
});

test('draft storage roundtrips, preserves corrupt data, and supports versioned backups',()=>{
 const {DraftStore,decodeBackup}=require('../web/workspace.js');
 const map=new Map(); const storage={get length(){return map.size},key:i=>[...map.keys()][i],getItem:k=>map.get(k)??null,setItem:(k,v)=>map.set(k,v),removeItem:k=>map.delete(k)};
 const store=new DraftStore(storage);const s=new EditorState();s.accept(result(schedule()));
 store.save({id:'a',name:'September',source:'Original paste',state:s.snapshot()});
 assert.equal(store.list()[0].name,'September');assert.equal(store.load('a').source,'Original paste');
 assert.equal(decodeBackup(JSON.stringify(store.load('a'))).state.draft.month,9);
 map.set('otf-draft:a','broken');assert.throws(()=>store.load('a'),/read|invalid|JSON/i);
 assert.throws(()=>store.save({id:'a',state:s.snapshot()}));assert.equal(map.get('otf-draft:a'),'broken');
 assert.throws(()=>decodeBackup(JSON.stringify({version:99})),/version/i);
});
test('share links roundtrip Unicode editable data and reject oversized input',async()=>{
 const {encodeShare,decodeShare}=require('../web/workspace.js');
 const data={version:1,name:'Équipe 🧡',schedule:schedule()};
 const encoded=await encodeShare(data);assert.deepEqual(await decodeShare(encoded),data);
 await assert.rejects(decodeShare('x'.repeat(20001)),/large/i);
});

test('storage failures are surfaced and another tab cannot overwrite a newer draft',()=>{
 const {DraftStore}=require('../web/workspace.js');
 const map=new Map();const storage={getItem:k=>map.get(k)??null,setItem:(k,v)=>map.set(k,v)};
 const first=new DraftStore(storage),second=new DraftStore(storage),s=new EditorState();s.accept(result(schedule()));
 const doc={id:'a',name:'First',state:s.snapshot()};first.save(doc);second.load('a');
 first.save({...doc,name:'Newer'});
 assert.throws(()=>second.save({...doc,name:'Stale'}),/another tab/i);
 assert.equal(first.load('a').name,'Newer');
 const broken=new DraftStore({getItem:()=>null,setItem(){throw new Error('Quota exceeded');}});
 assert.throws(()=>broken.save(doc),/Quota/);
});

test('the ungenerated paste and month override survive a reload',()=>{
 const {DraftStore}=require('../web/workspace.js');const map=new Map();
 const storage={getItem:k=>map.get(k)??null,setItem:(k,v)=>map.set(k,v)};
 const first=new DraftStore(storage);first.saveSource('My unfinished thread','2026-09');
 assert.deepEqual(new DraftStore(storage).readSource(),{version:1,text:'My unfinished thread',month:'2026-09'});
});
