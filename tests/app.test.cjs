const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const {Document} = require('./dom.cjs');

async function app(storageMap=new Map()) {
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
    fetch:async () => ({ok:true, json:async () => ({files:{}, examples:{}})}),
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
  const api = vm.runInContext('({generate, regenerate, editorState, els, editor})', context);
  api.els.src.value = 'A pasted thread';
  return {...api, context, calls, errors, setFailure(value) { fail = value; }};
}

test('generate → edit → regenerate updates preview and both downloads without parsing twice', async () => {
  const a = await app();
  assert.equal(a.context.document.getElementById('navDays').hidden, true);
  await a.generate();
  for (const id of ['navPoster', 'navDays']) {
    assert.equal(a.context.document.getElementById(id).hidden, false);
  }
  assert.equal(a.els.png.disabled, false); assert.equal(a.els.html.disabled, false);
  a.editor.change(d => { d.subtitle = 'Edited subtitle'; });
  assert.equal(a.els.png.disabled, true); assert.equal(a.els.html.disabled, true);
  await a.regenerate();
  assert.deepEqual(a.calls.map(c => c.name), ['generate','regenerate']);
  assert.equal(a.els.preview.srcdoc, '<p>Edited subtitle</p>');
  assert.equal(a.editorState.current.html, a.els.preview.srcdoc);
  assert.equal(a.els.png.disabled, false); assert.equal(a.els.html.disabled, false);
});

test('autosave restores pending edits after reopening and restart keeps the saved poster',async()=>{
 const storage=new Map(); const a=await app(storage); await a.generate();
 a.editor.change(d=>{d.subtitle='Pending across refresh';});
 const saved=[...storage.entries()].find(([k])=>k.startsWith('otf-draft:'));
 assert.ok(saved);assert.equal(JSON.parse(saved[1]).state.draft.subtitle,'Pending across refresh');
 const b=await app(storage);await new Promise(resolve=>setTimeout(resolve,80));
 assert.equal(b.editorState.draft.subtitle,'Pending across refresh');assert.equal(b.editorState.dirty,true);
 b.context.document.getElementById('undo').onclick();assert.equal(b.editorState.draft.subtitle,'Monthly Schedule Poster');
 b.context.document.getElementById('redo').onclick();assert.equal(b.editorState.draft.subtitle,'Pending across refresh');
 b.context.document.getElementById('restartConfirm').onclick();
 assert.ok(storage.has(saved[0]));assert.equal(storage.has('otf-active'),false);
});

test('failed regeneration and cancelled restart preserve pending edits and preview', async () => {
  const a = await app(); await a.generate(); const original = a.els.preview.srcdoc;
  a.editor.change(d => { d.subtitle = 'Keep edits'; });
  a.setFailure(true); await a.regenerate();
  assert.equal(a.editorState.draft.subtitle, 'Keep edits');
  assert.equal(a.els.preview.srcdoc, original); assert.equal(a.els.html.disabled, true);
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
  assert.equal(a.els.go.disabled, false); assert.equal(a.els.png.disabled, true);
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

test('downloads also provide an open-file link for preview or saving manually',async()=>{
 const a=await app();await a.generate();a.els.html.onclick();
 const link=a.context.document.getElementById('lastDownload');
 assert.equal(link.hidden,false);assert.match(link.href,/^blob:/);assert.match(link.textContent,/otf_2026-09.html/);
});
