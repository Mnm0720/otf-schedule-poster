const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const {Document} = require('./dom.cjs');

async function app(storageMap=new Map(), bundle={files:{}, examples:{}}, startup={}) {
  const document = new Document();
  const iframe = document.getElementById('preview');
  iframe.contentDocument = {querySelector:() => null, fonts:{status:'loaded'}};
  Object.defineProperty(iframe, 'srcdoc', {get() { return this.source; }, set(value) {
    this.source = value; queueMicrotask(() => this.onload?.());
  }});
  const calls = []; const errors = []; let fail = false;
  const schedule = {year:2026, month:9, subtitle:'Monthly Schedule Poster', theme:'', tagline:'',
    notes:[], footnotes:[], events:[], days:Array.from({length:30}, (_,i) =>
      ({day:i+1, entries:[{category:'std', title:''}], repeat_of:null, three_g:false, note:''}))};
  const context = vm.createContext({document, console:{error:error => errors.push(error)}, setTimeout, clearTimeout, Blob, URL,
    crypto:require('node:crypto').webcrypto,
    localStorage:{get length(){return storageMap.size},key:i=>[...storageMap.keys()][i],getItem:k=>storageMap.get(k)??null,setItem:(k,v)=>storageMap.set(k,v),removeItem:k=>storageMap.delete(k)},
    location:{hash:'',href:'https://example.test/'},history:{replaceState(){}},
    confirm:() => true, addEventListener:() => {},
    ResizeObserver:class { observe() {} },
    fetch:async (url) => {
      if (typeof url === 'string' && url.startsWith('data:')) {
        return { ok: true, json: async () => bundle, blob: async () => new Blob(['png'], { type: 'image/png' }) };
      }
      return { ok: true, json: async () => bundle };
    },
    OTFRuntime:{createRuntime:()=>({initialize:startup.initialize||(async()=>({examples:bundle.examples})),execute:async(name,args)=>{
      calls.push({name,args});if(fail)throw fail===true?new Error('Test render failure'):fail;
      const draft=name==='regenerate'||name==='restore'?JSON.parse(args[0]):schedule;
      return JSON.stringify({html:`<p>${draft.subtitle}</p>`,slug:'2026-09',days:30,schedule:draft,
        categories:[{key:'std',label:'Standard'}],defaults:{notes:['Auto'],footnotes:[]},errors:[],notes:'',...(startup.response?.(name,draft)||{})});
    }}),loadExportLibrary:async name=>name==='image'?context.htmlToImage:context.PDFLib},
  });
  for (const name of ['editor-state.js','editor.js','workspace.js','app.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../web', name), 'utf8'), context);
  }
  await new Promise(resolve => setTimeout(resolve, 0));
  const api = vm.runInContext('({generate, regenerate, editorState, els, editor, doExport, openDocument, draftDocument, historyChange, boot, runtime})', context);
  api.els.src.value = 'A pasted thread';
  return {...api, context, calls, errors, setFailure(value) { fail = value; }};
}

test('generate → edit → regenerate updates preview and download without parsing twice', async () => {
  const a = await app();
  assert.equal(a.context.document.getElementById('navDays').hidden, true);
  await a.generate();
  for (const id of ['navPoster', 'navDays']) {
    assert.equal(a.context.document.getElementById(id).hidden, false);
  }
  assert.equal(a.context.document.getElementById('exportBtn').disabled, false);
  a.editor.change(d => { d.subtitle = 'Edited subtitle'; });
  assert.equal(a.context.document.getElementById('exportBtn').disabled, true);
  await a.regenerate();
  assert.deepEqual(a.calls.map(c => c.name), ['generate','regenerate']);
  assert.equal(a.els.preview.srcdoc, '<p>Edited subtitle</p>');
  assert.equal(a.editorState.current.html, a.els.preview.srcdoc);
  assert.equal(a.context.document.getElementById('exportBtn').disabled, false);
});

test('autosave restores pending edits after reopening and restart keeps the saved poster',async()=>{
 const storage=new Map(); const a=await app(storage); await a.generate();
 a.editor.change(d=>{d.subtitle='Regenerated once';});
 await a.regenerate();
 a.editor.change(d=>{d.subtitle='Pending across refresh';});
 const saved=[...storage.entries()].find(([k])=>k.startsWith('otf-draft:'));
 assert.ok(saved);assert.equal(JSON.parse(saved[1]).state.draft.subtitle,'Pending across refresh');
 const b=await app(storage);await new Promise(resolve=>setTimeout(resolve,80));
 assert.equal(b.editorState.draft.subtitle,'Pending across refresh');assert.equal(b.editorState.dirty,true);
 await b.context.document.getElementById('undo').onclick();
 assert.equal(b.editorState.draft.subtitle,'Monthly Schedule Poster');assert.equal(b.editorState.dirty,false);
 await b.context.document.getElementById('redo').onclick();
 assert.equal(b.editorState.draft.subtitle,'Regenerated once');assert.equal(b.editorState.dirty,false);
 b.context.document.getElementById('restartConfirm').onclick();
 assert.ok(storage.has(saved[0]));assert.equal(storage.has('otf-active'),false);
});

test('failed regeneration and cancelled restart preserve pending edits and preview', async () => {
  const a = await app(); await a.generate(); const original = a.els.preview.srcdoc;
  a.editor.change(d => { d.subtitle = 'Keep edits'; });
  a.setFailure(true); await a.regenerate();
  assert.equal(a.editorState.draft.subtitle, 'Keep edits');
  assert.equal(a.els.preview.srcdoc, original); assert.equal(a.context.document.getElementById('exportBtn').disabled, true);
  assert.match(a.els.editStatus.textContent, /Could not regenerate/);
  a.context.document.getElementById('restart').onclick();
  assert.equal(a.context.document.getElementById('restartDialog').open, true);
  a.context.document.getElementById('restartCancel').onclick();
  await a.generate(); assert.equal(a.calls.length, 2);
  assert.equal(a.editorState.draft.subtitle, 'Keep edits');
  assert.equal(a.els.preview.srcdoc, original);
});

test('source is hidden after success and only confirmed restart permits a fresh generation', async () => {
  const a = await app(); const doc = a.context.document;
  await a.generate();
  assert.equal(doc.getElementById('sourceInputs').hidden, true);
  assert.equal(a.els.go.disabled, true);
  await a.generate(); assert.equal(a.calls.length, 1);
  a.editor.change(d => { d.subtitle = 'Already saved edit'; }); await a.regenerate();
  doc.getElementById('restart').onclick();
  assert.equal(doc.getElementById('restartDialog').open,true);
  doc.getElementById('restartCancel').onclick();
  assert.equal(a.editorState.draft.subtitle, 'Already saved edit');
  assert.equal(doc.getElementById('restartDialog').open,false);
  doc.getElementById('restart').onclick();
  doc.getElementById('restartConfirm').onclick();
  assert.equal(doc.getElementById('restartDialog').open,false);
  assert.equal(a.editorState.draft, null); assert.equal(a.editorState.current, null);
  assert.equal(doc.getElementById('sourceInputs').hidden, false);
  assert.equal(a.els.previewWrap.hidden, true);
  assert.equal(a.els.go.disabled, false); assert.equal(doc.getElementById('exportBtn').disabled, true);
  assert.equal(a.els.src.value, 'A pasted thread');
  a.setFailure(true); await a.generate();
  assert.equal(a.editorState.draft, null); assert.equal(a.els.go.disabled, false);
  assert.equal(doc.getElementById('sourceInputs').hidden, false);
  a.setFailure(false); await a.generate();
  assert.equal(a.editorState.draft.subtitle, 'Monthly Schedule Poster');
  assert.equal(a.editorState.dirty, false);
});

test('invalid events block rendering and overlapping requests are ignored', async () => {
  const a = await app(); await a.generate();
  a.editorState.begin();
  a.context.document.getElementById('restart').onclick();
  assert.ok(a.editorState.draft); a.editorState.finish();
  a.editor.change(d => { d.events.push({name:'Invalid', start:5, end:2}); });
  await a.regenerate(); assert.equal(a.calls.length, 1);
  a.editor.change(d => { d.events = []; });
  await Promise.all([a.regenerate(), a.regenerate()]);
  assert.equal(a.calls.length, 2); assert.equal(a.editorState.busy, false);
});

test('full-size preview is readable without changing the exported poster', async () => {
  const a = await app(); await a.generate();
  a.els.stage.clientWidth = 320;
  a.els.preview.contentDocument.querySelector = () => ({offsetHeight:1800});
  const toggle = a.context.document.getElementById('previewZoom');
  assert.equal(typeof toggle.onclick, 'function');
  toggle.onclick();
  assert.equal(a.els.preview.style.transform, 'scale(1)');
  assert.equal(toggle.textContent, 'Fit to width');
  toggle.onclick();
  assert.equal(a.els.preview.style.transform, `scale(${320 / 1200})`);
  assert.equal(a.editorState.dirty, false);
  assert.equal(a.editorState.current.html, '<p>Monthly Schedule Poster</p>');
});

test('examples are hidden after generation',async()=>{
 const a=await app();
 assert.equal(a.context.document.getElementById('examplesWrap').hidden,false);
 await a.generate();
 assert.equal(a.context.document.getElementById('examplesWrap').hidden,true);
});

test('generate with empty text shows human-friendly status copy', async () => {
  const a = await app();
  a.els.src.value = '   \n  ';
  await a.generate();
  assert.match(a.els.status.textContent, /Paste the monthly thread first\. Copy the whole Reddit post/);
  assert.match(a.els.status.textContent, /category lists/);
  assert.equal(a.calls.length, 0, 'no generate call should be made for empty text');
});

test('inline paste hint under #src and Month hint mentions wrong', () => {
  const html = fs.readFileSync(path.join(__dirname, '../web/index.html'), 'utf8');
  const fieldsetMatch = html.match(/<fieldset id="sourceInputs"[\s\S]*?<\/fieldset>/);
  assert.ok(fieldsetMatch, 'sourceInputs fieldset not found');
  const fieldset = fieldsetMatch[0];
  const afterTextarea = fieldset.split('</textarea>')[1] || '';
  const beforeMonth = afterTextarea.split('<div class="row">')[0] || afterTextarea;
  assert.match(beforeMonth, /<p class="hint">/,
    'no hint <p> found between textarea and Month row');
  assert.match(beforeMonth, /Copy the entire Reddit post/,
    'hint text should mention copying the entire Reddit post');
  assert.match(beforeMonth, /links|Links|extra text/i,
    'hint should reassure that extra text is fine');
  const monthLabel = fieldset.match(/<label for="month"[^>]*>[\s\S]*?<\/label>/);
  assert.ok(monthLabel, 'Month <label> not found in sourceInputs fieldset');
  assert.match(monthLabel[0], /wrong/, 'Month hint should mention “wrong”');
});

test('renderPoster keeps Could-not-parse prefix for unexpected errors', async () => {
  const a = await app();
  a.setFailure(true);
  await a.generate();
  assert.match(a.els.status.textContent, /Could not parse that: Test render failure/);
  assert.equal(a.els.report.hidden, false, 'report box should be visible on error');
});

test('undo/redo buttons only checkpoint at regenerate and show action descriptions',async()=>{
 const a=await app();await a.generate();
 const doc=a.context.document;
 a.editor.change(d=>{d.subtitle='Changed';});
 assert.equal(doc.getElementById('undo').textContent,'Previous version','a pending edit alone creates no prior rendered version');
 assert.equal(doc.getElementById('undo').disabled,true);
 await a.regenerate();
 assert.equal(doc.getElementById('undo')['aria-label'],'Previous version: subtitle');
 assert.equal(doc.getElementById('undo').disabled,false);
 await doc.getElementById('undo').onclick();
 assert.equal(doc.getElementById('undo').textContent,'Previous version');
 assert.equal(doc.getElementById('redo').disabled,false);
 assert.equal(doc.getElementById('redo')['aria-label'],'Next version: subtitle');
});

test('png export shows a confirmation with the exact filename and quick actions',async()=>{
 const a=await app();
 a.els.preview.contentDocument.querySelector=()=>({offsetWidth:1200,offsetHeight:1800});
 let exports=0;a.context.htmlToImage={toBlob:async()=>{exports++;return new Blob(['png'],{type:'image/png'});}};
 await a.generate();
 a.context.document.getElementById('exportFormat').value='png';
 await a.doExport();
 const confirm=a.context.document.getElementById('exportConfirm');
 assert.equal(confirm.hidden,false,'#exportConfirm should be visible after export');
 assert.ok(confirm.textContent.includes('otf_2026-09.png'),'confirmation should name the exact file: '+confirm.textContent);
 assert.ok(confirm.textContent.includes('Open'),'confirmation should mention Open');
 assert.equal(a.context.document.getElementById('exportActions').hidden,false);
 await a.context.document.getElementById('exportAgain').onclick();assert.equal(exports,2);
 let shared=false;a.context.document.getElementById('shareDraft').onclick=()=>{shared=true;};a.context.document.getElementById('exportShare').onclick();assert.equal(shared,true);
});

test('examples label says to hit Generate and clicking loads text without generating',async()=>{
 const a=await app(new Map(),{files:{},examples:{'2026-08':'sample thread text'}});
 const html=fs.readFileSync(path.join(__dirname,'../web/index.html'),'utf8');
 const wrapMatch=html.match(/<div class="examples" id="examplesWrap">[\s\S]*?<\/div>/);
 assert.ok(wrapMatch,'examplesWrap not found');
 const span=wrapMatch[0].match(/<span>([\s\S]*?)<\/span>/);
 assert.ok(span,'label span not found in examplesWrap');
 assert.ok(span[1].includes('then hit Generate'),'label should say "then hit Generate": '+span[1]);
 const examples=a.context.document.getElementById('examples');
 const btn=examples.children[0];
 assert.ok(btn,'no example button rendered');
 btn.onclick();
 assert.equal(a.els.src.value,'sample thread text','clicking should load the example text into #src');
 assert.equal(a.calls.length,0,'clicking an example must NOT call generate');
});

test('saved drafts dialog wording',()=>{
 const html=fs.readFileSync(path.join(__dirname,'../web/index.html'),'utf8');
 const dlg=html.match(/<dialog id="draftsDialog"[\s\S]*?<\/dialog>/);
 assert.ok(dlg,'draftsDialog not found');
 const p=dlg[0].match(/<p class="hint">([\s\S]*?)<\/p>/);
 assert.ok(p,'hint paragraph not found in draftsDialog');
 assert.ok(p[1].includes('Saved in this browser'),'drafts dialog should say "Saved in this browser": '+p[1]);
 assert.ok(p[1].includes('Download a backup'),'drafts dialog should mention "Download a backup": '+p[1]);
});

test('how-to strip lists four steps with Copy, Paste, Generate, Download',()=>{
 const html=fs.readFileSync(path.join(__dirname,'../web/index.html'),'utf8');
 const ol=html.match(/<ol class="how-to"[\s\S]*?<\/ol>/);
 assert.ok(ol,'<ol class="how-to"> not found');
 const items=[...ol[0].matchAll(/<li>([\s\S]*?)<\/li>/g)];
 assert.equal(items.length,4,'how-to should have exactly 4 steps, got '+items.length);
 const text=items.map(m=>m[1]).join(' ');
 assert.ok(text.includes('Copy'),'step should mention Copy');
 assert.ok(text.includes('Paste'),'step should mention Paste');
 assert.ok(text.includes('Generate'),'step should mention Generate');
 assert.ok(text.includes('Download'),'step should mention Download');
});

test('save failures remain visible beside the editor with backup available',async()=>{
 const a=await app(); await a.generate();
 a.context.localStorage.setItem=()=>{throw new Error('Storage full');};
 a.editor.change(d=>{d.subtitle='Keep this unsaved edit';});
 const doc=a.context.document;
 assert.match(doc.getElementById('autosaveStatus').textContent,/Not saved.*Storage full/);
 assert.equal(doc.getElementById('backupDraft').disabled,false);
 assert.equal(doc.getElementById('emergencyBackup').hidden,false);
 assert.match(a.els.editStatus.textContent,/Not saved/);
 assert.equal(doc.getElementById('draftsDialog').open,undefined);
});

test('the download panel explains why pending edits cannot be downloaded',async()=>{
 const a=await app();await a.generate();const notice=a.context.document.getElementById('previewNeedsUpdate');
 assert.equal(notice.hidden,true);
 a.editor.change(d=>{d.subtitle='Pending';});assert.equal(notice.hidden,false);
 await a.regenerate();assert.equal(notice.hidden,true);
});

test('failed draft load keeps picker open and permits retry and later switching',async()=>{
 const a=await app();await a.generate();const doc=a.context.document;
 const stored=a.draftDocument(); stored.id='other';stored.name='Other poster';stored.state.rendered.subtitle='Other';stored.state.draft.subtitle='Other';
 a.context.localStorage.setItem('otf-draft:other',JSON.stringify(stored));
 doc.getElementById('openDrafts').onclick();doc.getElementById('savedPicker').value='other';
 a.setFailure(true);await doc.getElementById('openSaved').onclick();
 assert.equal(doc.getElementById('draftsDialog').open,true);
 assert.equal(doc.getElementById('openDrafts').disabled,false);
 assert.equal(a.editorState.draft.subtitle,'Monthly Schedule Poster');
 a.setFailure(false);await doc.getElementById('openSaved').onclick();
 assert.equal(doc.getElementById('draftsDialog').open,false);
 assert.equal(a.editorState.draft.subtitle,'Other');
 assert.equal(doc.getElementById('openDrafts').disabled,false);
});

test('failed version render preserves pending edits and history',async()=>{
 const a=await app();await a.generate();a.editor.change(d=>{d.subtitle='Version B';});await a.regenerate();
 a.editor.change(d=>{d.subtitle='Pending C';});const before=JSON.stringify(a.editorState.snapshot());
 a.setFailure(true);await a.historyChange('undo');
 assert.deepEqual(JSON.parse(JSON.stringify(a.editorState.snapshot())),JSON.parse(before));
 assert.match(a.els.editStatus.textContent,/Could not/);
});

test('validation issues select the affected date and focus its repeat control',async()=>{
 const a=await app();await a.generate();a.editor.change(d=>{d.days[2].repeat_of=4;});await a.regenerate();
 const issue=a.context.document.getElementById('issueList').children[0];
 assert.ok(issue,'validation issue is visible beside editor');
 issue.children.find(e=>e.tagName==='button').onclick();
 assert.equal(a.editor.selectedDay,3);
 assert.equal(a.editor.repeatControl.focused,true);
});

test('original source is available for reference without restarting',async()=>{
 const a=await app();await a.generate();
 assert.equal(a.context.document.getElementById('sourceReference').value,'A pasted thread');
 assert.equal(a.context.document.getElementById('sourceReferenceSection').hidden,false);
});

test('late render failure restores the previous preview, pending edits, and history',async()=>{
 const a=await app();await a.generate();a.editor.change(d=>{d.subtitle='Keep pending edit';});
 const before=JSON.stringify(a.editorState.snapshot()),preview=a.els.preview.srcdoc;
 a.els.preview.contentDocument.fonts={status:'loading',get ready(){return Promise.reject(new Error('Fonts failed'));}};
 await a.regenerate();
 assert.equal(a.els.preview.srcdoc,preview);
 assert.deepEqual(JSON.parse(JSON.stringify(a.editorState.snapshot())),JSON.parse(before));
 assert.equal(a.context.document.getElementById('exportBtn').disabled,true);
 assert.match(a.els.status.textContent,/Fonts failed/);
});

test('a late failure opening another draft preserves the active draft and preview',async()=>{
 const a=await app();await a.generate();const original=a.draftDocument(),preview=a.els.preview.srcdoc;
 const other=JSON.parse(JSON.stringify(original));other.id='other';other.name='Other';other.state.rendered.subtitle='Different';other.state.draft.subtitle='Different';
 a.els.preview.contentDocument.fonts={status:'loading',get ready(){return Promise.reject(new Error('Fonts failed'));}};
 assert.equal(await a.openDocument(other),false);
 assert.equal(a.els.preview.srcdoc,preview);
 assert.equal(a.draftDocument().id,original.id);assert.equal(a.editorState.draft.subtitle,original.state.draft.subtitle);
});

test('deleting the active saved draft shows unsaved status until editing saves another copy',async()=>{
 const storage=new Map(),a=await app(storage);await a.generate();const doc=a.context.document;
 doc.getElementById('openDrafts').onclick();const deletedId=doc.getElementById('savedPicker').value;
 doc.getElementById('deleteSaved').onclick();doc.getElementById('deleteConfirm').onclick();
 assert.match(doc.getElementById('autosaveStatus').textContent,/Not saved.*deleted/);
 assert.equal(storage.has('otf-draft:'+deletedId),false);
 a.editor.change(d=>{d.subtitle='Saved again';});
 assert.match(doc.getElementById('autosaveStatus').textContent,/Saved in this browser/);
 assert.notEqual(a.draftDocument().id,deletedId);
});

test('opening a draft with invalid pending edits immediately shows their errors',async()=>{
 const a=await app();await a.generate();const saved=a.draftDocument();
 saved.state.draft.days[2].repeat_of=4;
 assert.equal(await a.openDocument(saved),true);
 assert.equal(a.editorState.dirty,true);
 const issues=a.context.document.getElementById('issueList').children;
 assert.ok(issues.some(li=>li.children[0].textContent.includes('Day 3')));
 assert.match(a.els.status.textContent,/pending.*error/i);
 assert.equal(a.context.document.getElementById('exportBtn').disabled,true);
});

test('a fresh invalid saved poster restores through non-strict rendering with exports blocked',async()=>{
 const response=(name,draft)=>({errors:['Day 1 repeats a future date.'],issues:[{severity:'error',day:1,control:'repeat',message:'Day 1 repeats a future date.'}]});
 const a=await app(new Map(),{examples:{}},{response});await a.generate();const saved=a.draftDocument();
 saved.state.draft.days[0].repeat_of=saved.state.rendered.days[0].repeat_of=2;
 assert.equal(await a.openDocument(saved),true);
 assert.equal(a.calls.at(-1).name,'restore');
 assert.equal(a.editorState.draft.days[0].repeat_of,2);
 assert.equal(a.context.document.getElementById('exportBtn').disabled,true);
});

test('runtime retry retains unsaved pending edits and history instead of reloading saved data',async()=>{
 const a=await app();await a.generate();a.editor.change(d=>{d.subtitle='Version B';});await a.regenerate();
 a.context.localStorage.setItem=()=>{throw new Error('Storage denied');};
 a.editor.change(d=>{d.subtitle='Unsaved C';});const before=JSON.stringify(a.editorState.snapshot());
 const failure=new Error('Editor runtime stopped. Retry loading.');failure.runtimeUnavailable=true;a.setFailure(failure);
 await a.regenerate();
 const doc=a.context.document;
 assert.equal(doc.getElementById('retryBoot').hidden,false);
 assert.equal(doc.getElementById('regenerate').disabled,true);assert.equal(doc.getElementById('undo').disabled,true);
 assert.equal(doc.getElementById('backupDraft').disabled,false);
 a.setFailure(false);await a.boot();
 assert.deepEqual(JSON.parse(JSON.stringify(a.editorState.snapshot())),JSON.parse(before));
 assert.equal(doc.getElementById('regenerate').disabled,false);
 assert.equal(doc.getElementById('retryBoot').hidden,true);
 assert.match(doc.getElementById('autosaveStatus').textContent,/Not saved/);
});

test('text entered while startup runs takes precedence over restoring an older active draft',async()=>{
 const storage=new Map(),first=await app(storage);await first.generate();
 let complete;const loaded=new Promise(resolve=>{complete=resolve;});
 const a=await app(storage,{examples:{}},{initialize:()=>loaded});
 a.els.src.value='New moderator thread';a.els.src.oninput();complete({examples:{}});
 await new Promise(resolve=>setTimeout(resolve,80));
 assert.equal(a.editorState.current,null);
 assert.equal(a.els.src.value,'New moderator thread');
 assert.equal(a.context.document.getElementById('sourceInputs').hidden,false);
});

test('paste storage failure stays visible after delayed startup finishes',async()=>{
 let complete;const loaded=new Promise(resolve=>{complete=resolve;});
 const a=await app(new Map(),{examples:{}},{initialize:()=>loaded});
 a.context.localStorage.setItem=()=>{throw new Error('Storage denied');};
 a.els.src.value='Unsaved moderator thread';a.els.src.oninput();
 const feedback=a.context.document.getElementById('draftStatus');
 assert.match(feedback.textContent,/Thread text could not be saved: Storage denied/);
 complete({examples:{}});
 await new Promise(resolve=>setTimeout(resolve,10));
 assert.equal(a.els.go.disabled,false);
 assert.match(feedback.textContent,/Thread text could not be saved: Storage denied/);
 assert.equal(a.els.src.value,'Unsaved moderator thread');
});

test('repeated draft switches keep each pending draft, source, and baseline separate',async()=>{
 const storage=new Map(),a=await app(storage);await a.generate();const first=a.draftDocument();
 const second=JSON.parse(JSON.stringify(first));second.id='';second.name='Second';second.source='Second thread';
 second.state.draft.subtitle=second.state.rendered.subtitle=second.state.initial.subtitle='Second baseline';
 assert.equal(await a.openDocument(second,true),true);
 const secondId=a.draftDocument().id;
 a.editor.change(d=>{d.subtitle='Second pending';});
 assert.equal(await a.openDocument(first),true);a.editor.change(d=>{d.subtitle='First pending';});
 assert.equal(await a.openDocument(JSON.parse(storage.get('otf-draft:'+secondId))),true);
 assert.equal(a.editorState.draft.subtitle,'Second pending');assert.equal(a.editorState.initial.subtitle,'Second baseline');
 assert.equal(a.els.src.value,'Second thread');
 assert.equal(await a.openDocument(JSON.parse(storage.get('otf-draft:'+first.id))),true);
 assert.equal(a.editorState.draft.subtitle,'First pending');assert.equal(a.editorState.initial.subtitle,'Monthly Schedule Poster');
 assert.equal(a.els.src.value,'A pasted thread');
});
