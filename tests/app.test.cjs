const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const {Document} = require('./dom.cjs');

async function app(storageMap=new Map(), bundle={files:{}, examples:{}}) {
  const document = new Document();
  const iframe = document.getElementById('preview');
  iframe.contentDocument = {querySelector:() => null, fonts:{status:'loaded'}};
  Object.defineProperty(iframe, 'srcdoc', {get() { return this.source; }, set(value) {
    this.source = value; queueMicrotask(() => this.onload?.());
  }});
  const calls = []; const errors = []; let fail = false;
  const schedule = {year:2026, month:9, subtitle:'Monthly Schedule Poster', theme:'', tagline:'',
    notes:[], footnotes:[], events:[], days:Array.from({length:30}, (_,i) =>
      ({day:i+1, entries:[{category:'std', title:''}], repeat_of:null, three_g:false}))};
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
    loadPyodide:async () => ({FS:{mkdir(){}, writeFile(){}}, loadPackage:async () => {},
      pyimport:() => ({install:async () => {}, destroy(){}}), runPython(){},
      globals:{get(name) {
        const fn = (...args) => {
          calls.push({name, args}); if (fail) throw new Error('Test render failure');
          const draft = name === 'regenerate' ? JSON.parse(args[0]) : schedule;
          return JSON.stringify({html:`<p>${draft.subtitle}</p>`, slug:'2026-09', days:30,
            schedule:draft, categories:[{key:'std', label:'Standard'}],
            defaults:{notes:['Auto'], footnotes:[]}, errors:[], notes:''});
        }; fn.destroy = () => {}; return fn;
      }}}),
  });
  for (const name of ['editor-state.js','editor.js','workspace.js','app.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../web', name), 'utf8'), context);
  }
  await new Promise(resolve => setTimeout(resolve, 0));
  const api = vm.runInContext('({generate, regenerate, editorState, els, editor, doExport})', context);
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
 assert.equal(doc.getElementById('undo').textContent,'Undo','a pending edit alone creates no undo step');
 assert.equal(doc.getElementById('undo').disabled,true);
 await a.regenerate();
 assert.equal(doc.getElementById('undo').textContent,'Undo: subtitle');
 assert.equal(doc.getElementById('undo').disabled,false);
 await doc.getElementById('undo').onclick();
 assert.equal(doc.getElementById('undo').textContent,'Undo');
 assert.equal(doc.getElementById('redo').disabled,false);
 assert.equal(doc.getElementById('redo').textContent,'Redo: subtitle');
});

test('png export shows a confirmation with the exact filename and quick actions',async()=>{
 const a=await app();
 a.els.preview.contentDocument.querySelector=()=>({offsetWidth:1200,offsetHeight:1800});
 a.context.htmlToImage={toPng:async()=> 'data:image/png;base64,x'};
 await a.generate();
 a.context.document.getElementById('exportFormat').value='png';
 await a.doExport();
 const confirm=a.context.document.getElementById('exportConfirm');
 assert.equal(confirm.hidden,false,'#exportConfirm should be visible after export');
 assert.ok(confirm.textContent.includes('otf_2026-09.png'),'confirmation should name the exact file: '+confirm.textContent);
 assert.ok(confirm.textContent.includes('Open'),'confirmation should mention Open');
 assert.ok(/again/i.test(confirm.textContent),'confirmation should mention "again"');
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
