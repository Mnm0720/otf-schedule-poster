const {test} = require('node:test');
const assert = require('node:assert/strict');
const {EditorState, calendarCells, validateDraft} = require('../web/editor-state.js');

function response() {
  return {html: 'old poster', slug: '2026-09', days: 30, defaults: {
    notes: ['Automatic note'], footnotes: [{icon:'groups', lead:'Automatic', text:'Body'}],
  }, schedule: {year:2026, month:9, theme:'Theme', subtitle:'Monthly Schedule Poster',
    notes:[], footnotes:[], events:[], source_url:'keep me',
    days: Array.from({length:30}, (_, i) => ({day:i+1, repeat_of:null, three_g:false,
      note:'Keep this note', entries:[{category:'std', title:'', raw:'source'}]}))}};
}

test('draft edits never mutate the last rendered schedule or unrelated data', () => {
  const result = response();
  const s = new EditorState(); s.accept(result);
  s.edit(d => { d.days[0].entries[0].category = 'bench'; d.days[0].entries[0].title = 'My row';
    d.days[1].repeat_of = 1; d.days[0].three_g = true; });
  assert.equal(result.schedule.days[0].entries[0].category, 'std');
  assert.equal(s.draft.days[0].entries[0].raw, 'source');
  assert.equal(s.draft.source_url, 'keep me');
  assert.equal(s.draft.days[0].note, 'Keep this note');
  assert.equal(s.dirty, true); assert.equal(s.canDownload, false);
});

test('render failure retains draft; success updates export and clears dirty state', () => {
  const s = new EditorState(); s.accept(response());
  s.edit(d => d.subtitle = 'Edited');
  assert.equal(s.begin(), true); assert.equal(s.begin(), false);
  assert.throws(() => s.edit(d => d.theme = 'Race'), /busy/i);
  s.finish();
  assert.equal(s.current.html, 'old poster'); assert.equal(s.draft.subtitle, 'Edited');
  assert.equal(s.canDownload, false);
  s.accept({...response(), html:'new poster', schedule:s.draft});
  assert.equal(s.current.html, 'new poster'); assert.equal(s.canDownload, true);
});

test('automatic/custom copy preserves structured icons and restores defaults', () => {
  const s = new EditorState(); s.accept(response());
  s.setAutomatic('notes', false); s.setAutomatic('footnotes', false);
  assert.deepEqual(s.draft.notes, ['Automatic note']);
  s.edit(d => { d.footnotes[0].text = 'Edited body'; });
  assert.equal(s.draft.footnotes[0].icon, 'groups');
  assert.equal(s.current.defaults.footnotes[0].text, 'Body');
  s.setAutomatic('notes', true); assert.deepEqual(s.draft.notes, []);
});

test('calendar covers leap February and Sunday-first six-week months', () => {
  const feb = calendarCells(2028, 2);
  assert.equal(feb.filter(Boolean).length, 29); assert.equal(feb[2], 1);
  const aug = calendarCells(2026, 8);
  assert.equal(aug.length, 42); assert.equal(aug[6], 1); assert.equal(aug[36], 31);
});

test('repeat and event validation catches invalid ranges but permits clearing', () => {
  const d = response().schedule;
  d.days[0].repeat_of = 1;
  d.events = [{name:'Oops', start:12, end:3}];
  assert.match(validateDraft(d).join(' '), /repeat/i);
  assert.match(validateDraft(d).join(' '), /Event/);
  d.days[0].repeat_of = null;
  d.events = [{name:'Month event', start:1, end:30}];
  assert.deepEqual(validateDraft(d), []);
  for (const value of [0, 31, 1.5, '', NaN]) {
    d.events[0].end = value; assert.ok(validateDraft(d).length);
  }
});
