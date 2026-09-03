const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const {Document} = require('./dom.cjs');

async function app() {
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
  for (const name of ['editor-state.js','editor.js','app.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../web', name), 'utf8'), context);
  }
  await new Promise(resolve => setTimeout(resolve, 0));
  const api = vm.runInContext('({generate, regenerate, editorState, els, editor})', context);
  api.els.src.value = 'A pasted thread';
  return {...api, context, calls, errors, setFailure(value) { fail = value; }};
}

test('generate → edit → regenerate updates preview and both downloads without parsing twice', async () => {
  const a = await app(); await a.generate();
  assert.equal(a.els.png.disabled, false); assert.equal(a.els.html.disabled, false);
  a.editor.change(d => { d.subtitle = 'Edited subtitle'; });
  assert.equal(a.els.png.disabled, true); assert.equal(a.els.html.disabled, true);
  await a.regenerate();
  assert.deepEqual(a.calls.map(c => c.name), ['generate','regenerate']);
  assert.equal(a.els.preview.srcdoc, '<p>Edited subtitle</p>');
  assert.equal(a.editorState.current.html, a.els.preview.srcdoc);
  assert.equal(a.els.png.disabled, false); assert.equal(a.els.html.disabled, false);
});

test('failed regeneration and cancelled new parsing preserve pending edits and preview', async () => {
  const a = await app(); await a.generate(); const original = a.els.preview.srcdoc;
  a.editor.change(d => { d.subtitle = 'Keep edits'; });
  a.setFailure(true); await a.regenerate();
  assert.equal(a.editorState.draft.subtitle, 'Keep edits');
  assert.equal(a.els.preview.srcdoc, original); assert.equal(a.els.html.disabled, true);
  assert.match(a.els.editStatus.textContent, /Could not regenerate/);
  a.context.confirm = () => false;
  await a.generate(); assert.equal(a.calls.length, 2);
  assert.equal(a.editorState.draft.subtitle, 'Keep edits');
});

test('failed new parsing keeps the existing draft and allows a later successful replacement', async () => {
  const a = await app(); await a.generate();
  a.editor.change(d => { d.subtitle = 'Retain me'; });
  a.setFailure(true); await a.generate();
  assert.equal(a.editorState.draft.subtitle, 'Retain me');
  assert.equal(a.editorState.dirty, true); assert.equal(a.els.go.disabled, false);
  a.setFailure(false); await a.generate();
  assert.equal(a.editorState.draft.subtitle, 'Monthly Schedule Poster');
  assert.equal(a.editorState.dirty, false);
});

test('invalid events block rendering and overlapping requests are ignored', async () => {
  const a = await app(); await a.generate();
  a.editor.change(d => { d.events.push({name:'Invalid', start:5, end:2}); });
  await a.regenerate(); assert.equal(a.calls.length, 1);
  a.editor.change(d => { d.events = []; });
  await Promise.all([a.regenerate(), a.regenerate()]);
  assert.equal(a.calls.length, 2); assert.equal(a.editorState.busy, false);
});
