const {test}=require('node:test');
const assert=require('node:assert/strict');
const {EditorState}=require('../web/editor-state.js');
const schedule=()=>({year:2026,month:9,subtitle:'Original',theme:'',events:[],notes:[],footnotes:[],days:[{day:1,entries:[{category:'std',title:''}],repeat_of:null,three_g:false,note:''}]});
const result=d=>({schedule:d,defaults:{credits:'Default'},categories:[]});

test('undo and redo checkpoint only at regenerate, not per edit or reset',()=>{
 const s=new EditorState(); s.accept(result(schedule()));
 assert.equal(s.canUndo,false);

 s.edit(d=>{d.subtitle='Changed';}); s.edit(d=>{d.credits='Team';});
 assert.equal(s.canUndo,false,'pending edits are not individually undoable');

 s.accept(result(s.draft),{checkpoint:true}); // simulates hitting Regenerate
 assert.equal(s.canUndo,true); assert.equal(s.dirty,false);

 s.resetSection('title'); // pending, not checkpointed on its own
 assert.equal(s.draft.subtitle,'Original'); assert.equal(s.draft.credits,'Team');
 assert.equal(s.past.length,1);

 s.accept(result(s.draft),{checkpoint:true}); // regenerate again
 assert.equal(s.past.length,2);

 s.undo();
 assert.equal(s.draft.subtitle,'Changed'); assert.equal(s.draft.credits,'Team'); assert.equal(s.dirty,true);
 s.accept(result(s.draft),{checkpoint:false}); // app's silent re-render to sync the preview
 assert.equal(s.dirty,false);

 s.undo();
 assert.equal(s.draft.subtitle,'Original'); assert.equal(s.draft.credits,'Default');
 s.accept(result(s.draft),{checkpoint:false});

 s.redo(); assert.equal(s.draft.subtitle,'Changed'); assert.equal(s.draft.credits,'Team');
 s.accept(result(s.draft),{checkpoint:false});

 s.edit(d=>{d.theme='New branch';});
 s.accept(result(s.draft),{checkpoint:true});
 assert.equal(s.canRedo,false,'a fresh regenerate clears the redo stack');
});
test('snapshot restores pending changes, original baseline, and history',()=>{
 const s=new EditorState();s.accept(result(schedule()));
 s.edit(d=>{d.subtitle='Checkpoint 1';});
 s.accept(result(s.draft),{checkpoint:true});
 s.edit(d=>{d.subtitle='Pending';});
 const snapshot=s.snapshot(); const restored=new EditorState();restored.accept(result(snapshot.rendered));restored.restore(snapshot);
 assert.equal(restored.draft.subtitle,'Pending');assert.equal(restored.dirty,true);
 restored.undo();assert.equal(restored.draft.subtitle,'Original');
});

test('previous version preserves invalid pending edits for recovery through next version',()=>{
 const s=new EditorState();s.accept(result(schedule()));
 s.edit(d=>{d.subtitle='Checkpoint';});s.accept(result(s.draft),{checkpoint:true});
 s.edit(d=>{d.events=[{name:'Unfinished',start:15,end:2}];});
 assert.deepEqual(s.undo(),{pending:false});
 assert.equal(s.draft.subtitle,'Original');
 s.accept(result(s.draft));
 assert.deepEqual(s.redo(),{pending:false});
 assert.equal(s.draft.subtitle,'Checkpoint');s.accept(result(s.draft));
 assert.deepEqual(s.redo(),{pending:true});
 assert.equal(s.draft.events[0].end,2);
 assert.equal(s.rendered.events.length,0);
 assert.equal(s.dirty,true);assert.equal(s.canDownload,false);
 assert.deepEqual(s.undo(),{pending:false});
 assert.equal(s.draft.subtitle,'Checkpoint');assert.deepEqual(s.draft.events,[]);
 s.accept(result(s.draft));
 assert.deepEqual(s.redo(),{pending:true});
 assert.equal(s.draft.events[0].end,2);
});

test('next version preserves edits made while reviewing an older version',()=>{
 const s=new EditorState();s.accept(result(schedule()));
 s.edit(d=>{d.subtitle='Checkpoint';});s.accept(result(s.draft),{checkpoint:true});
 s.undo();s.accept(result(s.draft));
 s.edit(d=>{d.theme='Pending older version';});
 assert.deepEqual(s.redo(),{pending:false});s.accept(result(s.draft));
 assert.equal(s.draft.subtitle,'Checkpoint');
 assert.deepEqual(s.undo(),{pending:true});
 assert.equal(s.draft.theme,'Pending older version');
 assert.equal(s.draft.subtitle,'Original');assert.equal(s.dirty,true);
 assert.deepEqual(s.undo(),{pending:false});
 assert.equal(s.draft.subtitle,'Original');assert.equal(s.draft.theme,'');
});

test('the original invalid schedule remains recoverable after its first correction',()=>{
 const s=new EditorState(),initial=schedule();initial.days[0].repeat_of=2;
 s.accept({...result(initial),errors:['Day 1 repeats a later day.']});
 s.edit(d=>{d.days[0].repeat_of=null;});s.accept({...result(s.draft),errors:[]},{checkpoint:true});
 assert.deepEqual(s.undo(),{pending:true});
 assert.equal(s.draft.days[0].repeat_of,2);
 assert.equal(s.rendered.days[0].repeat_of,null);
 assert.equal(s.canDownload,false);
});

test('draft backups retain descriptive history, pending versions, and source review',()=>{
 const {decodeBackup}=require('../web/workspace.js');
 const s=new EditorState();s.accept(result(schedule()));
 s.importReview={issues:[{severity:'warning',message:'Check this line.',day:1,control:'day',source:'9/1 custom workout'}],summary:{recognizedDays:[1],inferredDays:[2,3]}};
 s.edit(d=>{d.subtitle='Checkpoint';});s.accept(result(s.draft),{checkpoint:true});
 s.edit(d=>{d.events=[{name:'Pending',start:9,end:1}];});s.undo();s.accept(result(s.draft));
 const saved=decodeBackup(JSON.stringify({version:1,state:s.snapshot()}));
 const restored=new EditorState();restored.accept(result(saved.state.rendered));restored.restore(saved.state);
 assert.equal(restored.redoLabel,'subtitle');
 assert.deepEqual(restored.importReview,s.importReview);
 restored.redo();restored.accept(result(restored.draft));
 assert.match(restored.redoLabel,/pending.*events/i);
 assert.deepEqual(restored.redo(),{pending:true});assert.equal(restored.draft.events[0].end,1);
 const pending=restored.snapshot();restored.accept(result(schedule()));restored.restore(pending);
 assert.equal(restored.currentIsPending,true);
 assert.deepEqual(restored.undo(),{pending:false});assert.deepEqual(restored.draft.events,[]);
});

test('history remains bounded and older draft metadata migrates safely',()=>{
 const {decodeBackup}=require('../web/workspace.js');
 const s=new EditorState();s.accept(result(schedule()));
 for(let i=0;i<105;i++){s.edit(d=>{d.subtitle=`Version ${i}`;});s.accept(result(s.draft),{checkpoint:true});}
 assert.equal(s.past.length,100);assert.equal(s.pastLabels.length,100);
 s.undo();s.accept(result(s.draft));s.edit(d=>{d.theme='Pending at history limit';});s.redo();s.accept(result(s.draft));
 assert.equal(s.past.length,100);assert.equal(s.pastLabels.length,100);assert.equal(s.pastPending.length,100);
 for(let i=0;i<100;i++){s.undo();s.accept(result(s.draft));}
 s.edit(d=>{d.subtitle='Pending';});s.redo();
 assert.ok(s.past.length<=100);assert.ok(s.future.length<=100);
 const state={draft:schedule(),rendered:schedule(),initial:schedule(),past:[schedule()],future:[]};
 const old=decodeBackup(JSON.stringify({version:1,state}));
 const restored=new EditorState();restored.accept(result(schedule()));restored.restore(old.state);
 assert.equal(restored.undoLabel,'');assert.equal(restored.currentIsPending,false);assert.equal(restored.importReview,null);
 const malformed={...state,pastLabels:['subtitle','excess'],pastPending:['unsafe'],currentIsPending:'true',importReview:{issues:[{severity:'warning',message:'Kept',day:500,control:3,source:{}}],summary:{recognizedDays:[1,1,500,'2',3],inferredDays:-2}}};
 const cleaned=decodeBackup(JSON.stringify({version:1,state:malformed})).state;
 assert.deepEqual(cleaned.pastLabels,['subtitle']);assert.deepEqual(cleaned.pastPending,[false]);
 assert.equal(cleaned.currentIsPending,false);assert.equal(cleaned.importReview.issues[0].day,undefined);
 assert.equal(cleaned.importReview.issues[0].control,undefined);assert.equal(cleaned.importReview.issues[0].source,undefined);
 assert.deepEqual(cleaned.importReview.summary.recognizedDays,[1,3]);
 assert.deepEqual(cleaned.importReview.summary.inferredDays,[]);
});

test('a failed navigation can restore both pending edits and all history metadata',()=>{
 const s=new EditorState();s.accept(result(schedule()));
 s.edit(d=>{d.subtitle='Updated';});s.accept(result(s.draft),{checkpoint:true});
 s.edit(d=>{d.theme='Pending';});
 const before=s.snapshot();s.undo();
 s.restore(before); // the controller rolls back when rendering the target fails
 assert.deepEqual(s.snapshot(),before);
 assert.equal(s.draft.theme,'Pending');assert.equal(s.current.schedule.subtitle,'Updated');
 assert.equal(s.canDownload,false);
});

test('restored object property order does not create false pending edits',()=>{
 const s=new EditorState();const data=schedule();
 data.category_styles={std:{color:'#123456',visible:true},bench:{visible:true,color:'#654321'}};
 s.accept(result(data));const saved=s.snapshot();
 saved.draft.category_styles={bench:{color:'#654321',visible:true},std:{visible:true,color:'#123456'}};
 s.restore(saved);
 assert.equal(s.dirty,false);assert.equal(s.canDownload,true);
 const updated=JSON.parse(JSON.stringify(saved.rendered));updated.credits='Updated team';
 s.edit(d=>{d.credits='Updated team';});s.accept(result(updated),{checkpoint:true});
 assert.equal(s.undoLabel,'credits');
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
