/* Shared by the page and dependency-free Node tests. No parsing lives here. */
(function (root) {
  const clone = (value) => JSON.parse(JSON.stringify(value));

  class EditorState {
    constructor() { this.busy = false; this.reset(); }
    reset() { this.current = null; this.draft = null; this.dirty = false; this.initial=null; this.past=[]; this.future=[]; this.rendered=null; }
    accept(result) {
      this.current = clone(result);
      this.draft = clone(result.schedule);
      for (const key of ['category_styles','key_date_overrides','footnote_styles','note_style']) this.draft[key] ??= {};
      this.draft.key_dates ??= [];
      this.draft.additional_info ??= '';
      this.draft.credits ??= result.defaults.credits || '';
      this.draft.custom_categories ??= {};
      this.initial ??= clone(this.draft);
      this.rendered = clone(this.draft);
      this.dirty = false;
    }
    edit(change) {
      if (this.busy) throw new Error('Editor is busy.');
      const before=clone(this.draft);
      try { change(this.draft); } catch (err) { this.draft=before; throw err; }
      if (JSON.stringify(before)===JSON.stringify(this.draft)) return;
      this.past.push(before); if(this.past.length>100)this.past.shift(); this.future=[];
      this.updateDirty();
    }
    updateDirty() { this.dirty=JSON.stringify(this.draft)!==JSON.stringify(this.rendered); }
    get canUndo() { return !this.busy && this.past.length>0; }
    get canRedo() { return !this.busy && this.future.length>0; }
    undo() { if(!this.canUndo)return;this.future.push(clone(this.draft));this.draft=this.past.pop();this.updateDirty(); }
    redo() { if(!this.canRedo)return;this.past.push(clone(this.draft));this.draft=this.future.pop();this.updateDirty(); }
    resetSection(section) {
      const keys={title:['theme','tagline','subtitle'],schedule:['days'],keyDates:['key_dates','key_date_overrides'],
        workouts:['category_styles'],notes:['notes','note_style'],monthlyNotes:['footnotes','footnote_styles'],
        events:['events'],additionalInfo:['additional_info'],credits:['credits']}[section];
      if(!keys)throw new Error('Unknown section');
      this.edit(d=>{for(const key of keys){if(key in this.initial)d[key]=clone(this.initial[key]);else delete d[key];}});
    }
    snapshot() { return clone({draft:this.draft,initial:this.initial,rendered:this.rendered,past:this.past,future:this.future}); }
    restore(snapshot) {
      const defaults=clone(this.draft), normalize=d=>{
        const value={...clone(defaults),...clone(d),schema_version:defaults.schema_version};
        value.custom_categories={...defaults.custom_categories,...d.custom_categories};
        value.days=value.days.map(day=>({...{repeat_of:null,note:'',three_g:false},...day,entries:day.entries.map(entry=>{
          const e={title:'',...entry};
          if(e.category==='unknown'){
            const known=Object.entries(value.custom_categories).find(([,type])=>type.label.toLowerCase()===(e.title||e.raw||'Other').toLowerCase());
            if(known)e.category=known[0];
          }return e;
        })}));
        return value;
      };
      for(const key of ['draft','initial','rendered'])this[key]=normalize(snapshot[key]);
      for(const key of ['past','future'])this[key]=snapshot[key].map(normalize);
      this.updateDirty();
    }
    setAutomatic(key, automatic) {
      this.edit(d => {
        const defaults = key === 'footnotes' ? this.current.defaults[key].map(note =>
          ({...note, ...d.footnote_styles[note.id]})) : this.current.defaults[key];
        d[key] = automatic ? [] : clone(d[key].length ? d[key] : defaults);
      });
    }
    begin() { if (this.busy) return false; this.busy = true; return true; }
    finish() { this.busy = false; }
    get canDownload() { return Boolean(this.current) && !this.dirty && !this.busy; }
  }

  function calendarCells(year, month) {
    const first = new Date(Date.UTC(year, month - 1, 1)).getUTCDay();
    const length = new Date(Date.UTC(year, month, 0)).getUTCDate();
    const cells = Array(first).fill(null);
    for (let day = 1; day <= length; day++) cells.push(day);
    while (cells.length % 7) cells.push(null);
    return cells;
  }

  function validateDraft(draft) {
    const errors = [];
    const length = new Date(Date.UTC(draft.year, draft.month, 0)).getUTCDate();
    for (const day of draft.days) {
      if (day.repeat_of !== null && (!Number.isInteger(day.repeat_of) || day.repeat_of >= day.day ||
          !draft.days.some(source => source.day === day.repeat_of))) {
        errors.push(`Day ${day.day}: repeat source must be an earlier day in this month.`);
      }
    }
    for (const [index, event] of draft.events.entries()) {
      if (!event.name.trim()) errors.push(`Event ${index + 1}: enter a name.`);
      if (!Number.isInteger(event.start) || !Number.isInteger(event.end) ||
          event.start < 1 || event.end > length || event.start > event.end) {
        errors.push(`Event ${index + 1}: choose start/end days between 1 and ${length}, in order.`);
      }
    }
    const linked = (row, label, required) => {
      if ((required || 'days' in row) && (!Array.isArray(row.days) || !row.days.length ||
          row.days.some(d => !Number.isInteger(d) || d < 1 || d > length))) {
        errors.push(`${label}: choose date numbers between 1 and ${length}, e.g. 8, 18, 24-28.`);
      }
      if (required && !row.detail?.trim()) errors.push(`${label}: enter a description.`);
    };
    (draft.key_dates || []).forEach((row,i) => linked(row, `Key Date ${i+1}`, true));
    Object.values(draft.key_date_overrides || {}).forEach(row => linked(row, 'Key Date', false));
    return errors;
  }

  function parseDayList(text, length) {
    if (!text.trim()) return [];
    const days = new Set();
    for (const part of text.split(',')) {
      const match = part.trim().match(/^(\d+)(?:\s*-\s*(\d+))?$/);
      if (!match) return null;
      const first = Number(match[1]), last = Number(match[2] || match[1]);
      if (first < 1 || last > length || first > last) return null;
      for (let day = first; day <= last; day++) days.add(day);
    }
    return [...days].sort((a,b) => a-b);
  }

  const api = {EditorState, calendarCells, validateDraft, parseDayList};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.OTFEditor = api;
})(globalThis);
