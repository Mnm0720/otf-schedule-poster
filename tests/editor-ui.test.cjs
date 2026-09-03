const {test} = require('node:test');
const assert = require('node:assert/strict');
const {Document, all, labelled} = require('./dom.cjs');
const {EditorState} = require('../web/editor-state.js');
const {ScheduleEditor} = require('../web/editor.js');

function setup() {
  const doc = new Document();
  const state = new EditorState();
  state.accept({categories:[{key:'std', label:'Standard',color:'#E4E7EB'}, {key:'bench', label:'Benchmark', titled:true,color:'#1A3A6B'}],
    icons:[{key:'groups',label:'Groups'},{key:'bolt',label:'Bolt'},{key:'flag',label:'Flag'},{key:'check_circle',label:'Check Circle'}],
    defaults:{notes:['Automatic'], footnotes:[{id:'three_g',icon:'groups',color:'#8A919B',lead:'Default',text:'Default body'}],
      key_dates:[{id:'workout:8:bench:0',days:[8],detail:'Benchmark: Row',icon:'flag',color:'#1A3A6B'}]},
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
  const jump = doc.getElementById('dayJump'); jump.value = '2'; jump.onchange();
  const cat = labelled(grid, 'Day 2 template 1'); cat.value = 'bench'; cat.onchange();
  const title = labelled(grid, 'Day 2 workout title 1'); title.value = 'My benchmark'; title.oninput();
  const repeat = labelled(grid, 'Day 2 repeat of'); repeat.value = '1'; repeat.onchange();
  const three = labelled(grid, 'Day 2 3G'); three.checked = true; three.onchange();
  assert.deepEqual(state.draft.days[1], {day:2, entries:[{category:'bench', title:'My benchmark', raw:'Original'}],
    note:'Keep', repeat_of:1, three_g:true});
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

test('the date dropdown shows only its selected day and preserves edits when switching', () => {
  const {doc, state, editor} = setup();
  const jump = doc.getElementById('dayJump');
  assert.equal(jump.children.length, 30);
  assert.equal(doc.getElementById('calendarEditor').children.length, 1);
  jump.value = '23'; jump.onchange();
  assert.equal(state.dirty, false);
  const grid = doc.getElementById('calendarEditor');
  assert.equal(grid.children.length, 1); assert.equal(grid.children[0].id, 'day-23');
  const title = labelled(grid,'Day 23 workout title 1'); title.value='Keep me'; title.oninput();
  jump.value='8'; jump.onchange(); jump.value='23'; jump.onchange();
  assert.equal(labelled(grid,'Day 23 workout title 1').value,'Keep me');
  editor.render();
  assert.equal(doc.getElementById('dayJump').value, '23');
  state.draft.month=10; editor.render();
  assert.equal(doc.getElementById('dayJump').value, '1');
});

test('workout legend defaults follow schedule edits and manual toggles retain colors', () => {
  const {doc,state} = setup(); const types=doc.getElementById('workoutTypesEditor');
  assert.equal(labelled(types,'Show Standard in workout types').checked,true);
  assert.equal(labelled(types,'Show Benchmark in workout types').checked,false);
  const category=labelled(doc.getElementById('calendarEditor'),'Day 1 template 1');
  category.value='bench'; category.onchange();
  assert.equal(labelled(types,'Show Benchmark in workout types').checked,true);
  const toggle=labelled(types,'Show Benchmark in workout types'); toggle.checked=false; toggle.onchange();
  const color=labelled(types,'Benchmark color'); color.value='#123456'; color.oninput();
  assert.deepEqual(state.draft.category_styles.bench,{visible:false,color:'#123456'});
  labelled(types,'Use automatic workout selections').onclick();
  assert.deepEqual(state.draft.category_styles.bench,{color:'#123456'});
});

test('key-date overrides are sparse and new rows support date lists and styles', () => {
  const {doc,state}=setup(); const dates=doc.getElementById('keyDatesEditor');
  const icon=labelled(dates,'Key Date 1 icon'); icon.value='bolt'; icon.onchange();
  assert.deepEqual(state.draft.key_date_overrides,{'workout:8:bench:0':{icon:'bolt'}});
  labelled(dates,'Add key date').onclick();
  const links=labelled(dates,'Custom Key Date 1 dates'); links.value='2, 8-10'; links.oninput();
  const text=labelled(dates,'Custom Key Date 1 description'); text.value='Studio event'; text.oninput();
  assert.deepEqual(state.draft.key_dates[0].days,[2,8,9,10]);
  assert.equal(state.draft.key_dates[0].detail,'Studio event');
  labelled(dates,'Hide Key Date 1').onclick();
  assert.equal(state.draft.key_date_overrides['workout:8:bench:0'].hidden,true);
});

test('automatic monthly-note styling does not convert derived text to custom copy', () => {
  const {doc,state}=setup(); const copy=doc.getElementById('copyEditor');
  const color=labelled(copy,'Monthly note 1 color'); color.value='#123456'; color.oninput();
  const icon=labelled(copy,'Monthly note 1 icon'); icon.value='bolt'; icon.onchange();
  assert.deepEqual(state.draft.footnotes,[]);
  assert.deepEqual(state.draft.footnote_styles.three_g,{color:'#123456',icon:'bolt'});
});
