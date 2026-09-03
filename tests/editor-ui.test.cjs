const {test} = require('node:test');
const assert = require('node:assert/strict');
const {Document, all, labelled} = require('./dom.cjs');
const {EditorState} = require('../web/editor-state.js');
const {ScheduleEditor} = require('../web/editor.js');

function setup() {
  const doc = new Document();
  const state = new EditorState();
  state.accept({categories:[{key:'std', label:'Standard'}, {key:'bench', label:'Benchmark', titled:true}],
    defaults:{notes:['Automatic'], footnotes:[{icon:'groups', lead:'Default', text:'Default body'}]},
    schedule:{year:2026, month:9, theme:'Original', tagline:'', subtitle:'Monthly Schedule Poster',
      notes:[], footnotes:[], events:[{name:'Existing', start:1, end:30, kind:'special'}],
      days:Array.from({length:30}, (_,i) => ({day:i+1, repeat_of:null, three_g:false,
        note:'Keep', entries:[{category:'std', title:'', raw:'Original'}]}))}});
  const editor = new ScheduleEditor(doc, state, () => {});
  editor.render();
  return {doc, state, editor};
}

test('day controls retain metadata and edit independent entries, repeats and 3G', () => {
  const {doc, state} = setup(); const grid = doc.getElementById('calendarEditor');
  const cat = labelled(grid, 'Day 2 template 1'); cat.value = 'bench'; cat.onchange();
  const title = labelled(grid, 'Day 2 workout title 1'); title.value = 'My benchmark'; title.oninput();
  const repeat = labelled(grid, 'Day 2 repeat of'); repeat.value = '1'; repeat.onchange();
  const three = labelled(grid, 'Day 2 3G'); three.checked = true; three.onchange();
  assert.deepEqual(state.draft.days[1], {day:2, entries:[{category:'bench', title:'My benchmark', raw:'Original'}],
    note:'Keep', repeat_of:1, three_g:true});
  assert.equal(labelled(grid, 'Day 1 repeat of').children.length, 1);
  labelled(grid, 'Day 2 add template').onclick();
  assert.equal(state.draft.days[1].entries.length, 2);
  labelled(grid, 'Day 2 remove template 1').onclick();
  assert.equal(state.draft.days[1].entries.length, 1);
  labelled(grid, 'Day 2 remove template 1').onclick();
  assert.equal(state.draft.days[1].entries.length, 0);
  labelled(grid, 'Day 2 add template').onclick();
  assert.equal(state.draft.days[1].entries[0].category, 'std');
});

test('copy controls seed defaults, edit events and preserve their kind', () => {
  const {doc, state} = setup();
  const copy = doc.getElementById('copyEditor');
  const theme = labelled(copy, 'Poster theme'); theme.value = 'Changed'; theme.oninput();
  const auto = labelled(copy, 'Automatic footnotes'); auto.checked = false; auto.onchange();
  const text = labelled(copy, 'Footnote 1 text'); text.value = '<b>Plain text</b>'; text.oninput();
  assert.equal(state.draft.footnotes[0].icon, 'groups');
  const name = labelled(copy, 'Event 1 name'); name.value = 'Renamed'; name.oninput();
  assert.equal(state.draft.events[0].kind, 'special');
  const end = labelled(copy, 'Event 1 end day'); end.value = ''; end.oninput();
  assert.equal(state.draft.events[0].end, '');
  assert.equal(state.draft.theme, 'Changed');
  assert.equal(state.draft.footnotes[0].text, '<b>Plain text</b>');
  assert.ok(all(copy).every(e => !e.innerHTML));
  labelled(copy, 'Remove event 1').onclick();
  labelled(copy, 'Add event').onclick();
  assert.deepEqual(state.draft.events, [{name:'', start:1, end:30, kind:'event'}]);
});
