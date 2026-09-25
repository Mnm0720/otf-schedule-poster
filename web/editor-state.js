/* Shared by the page and dependency-free Node tests. No parsing lives here. */
(function (root) {
  const clone = (value) => JSON.parse(JSON.stringify(value));
  const comparable = (value) => JSON.stringify(value,(_,item)=>item && typeof item==='object' && !Array.isArray(item)
    ? Object.fromEntries(Object.keys(item).sort().map(key=>[key,item[key]])) : item);

  class EditorState {
    constructor() { this.busy = false; this.reset(); }
    reset() { this.current = null; this.draft = null; this.dirty = false; this.initial=null; this.past=[]; this.future=[]; this.pastLabels=[]; this.futureLabels=[]; this.pastPending=[]; this.futurePending=[]; this.currentIsPending=false; this.rendered=null; this.importReview=null; }
    accept(result, opts = {}) {
      if (opts.checkpoint && this.rendered) {
        const label=this._describeChange(this.rendered, result.schedule);
        if (this.currentIsPending && comparable(this.past.at(-1))===comparable(this.rendered)) {
          this.pastLabels[this.past.length-1]=label;
        } else this._pushVersion('past',this.rendered,label,Boolean(this.current.errors?.length));
        this.future = []; this.futureLabels = []; this.futurePending = [];
      }
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
      this.currentIsPending = false;
    }
    _describeChange(before, after) {
      if (before.theme !== after.theme) return 'theme';
      if (before.tagline !== after.tagline) return 'tagline';
      if (before.subtitle !== after.subtitle) return 'subtitle';
      if (comparable(before.days) !== comparable(after.days)) return 'schedule';
      if (comparable(before.key_dates) !== comparable(after.key_dates)) return 'key dates';
      if (comparable(before.key_date_overrides) !== comparable(after.key_date_overrides)) return 'key dates';
      if (comparable(before.category_styles) !== comparable(after.category_styles)) return 'workout types';
      if (comparable(before.notes) !== comparable(after.notes) || comparable(before.note_style) !== comparable(after.note_style)) return 'notes';
      if (comparable(before.footnotes) !== comparable(after.footnotes) || comparable(before.footnote_styles) !== comparable(after.footnote_styles)) return 'monthly notes';
      if (comparable(before.events) !== comparable(after.events)) return 'events';
      if (before.additional_info !== after.additional_info) return 'additional info';
      if (before.credits !== after.credits) return 'credits';
      return 'edit';
    }
    edit(change) {
      if (this.busy) throw new Error('Editor is busy.');
      const before=clone(this.draft);
      try { change(this.draft); } catch (err) { this.draft=before; throw err; }
      this.updateDirty();
    }
    updateDirty() { this.dirty=comparable(this.draft)!==comparable(this.rendered); }
    get canUndo() { return !this.busy && this.past.length>0; }
    get canRedo() { return !this.busy && this.future.length>0; }
    get undoLabel() { return this.pastLabels.length ? this.pastLabels[this.pastLabels.length-1] : ''; }
    get redoLabel() { return this.futureLabels.length ? this.futureLabels[this.futureLabels.length-1] : ''; }
    _pushVersion(stack, schedule, label, pending) {
      this[stack].push(clone(schedule));
      this[`${stack}Labels`].push(label);
      this[`${stack}Pending`].push(pending);
      if(this[stack].length>100) {
        this[stack].shift(); this[`${stack}Labels`].shift(); this[`${stack}Pending`].shift();
      }
    }
    _moveVersion(from, to) {
      const target=this[from].pop(), label=this[`${from}Labels`].pop()||'';
      const pending=this[`${from}Pending`].pop()===true;
      const pendingLabel=`pending ${this._describeChange(this.rendered,this.draft)}`;
      if(this.currentIsPending) this._pushVersion(to,this.draft,label,true);
      else if(this.dirty) {
        // Keep the rendered version as well as the pending work, in travel order.
        if(from==='past') {
          this._pushVersion(to,this.draft,pendingLabel,true);
          this._pushVersion(to,this.rendered,label,false);
        } else {
          this._pushVersion(to,this.rendered,pendingLabel,false);
          this._pushVersion(to,this.draft,label,true);
        }
      } else this._pushVersion(to,this.rendered,label,false);
      this.draft=target;
      this.currentIsPending=pending;
      this.updateDirty();
      // Pending versions can be invalid: restore the form without rendering them.
      return {pending};
    }
    undo() { if(this.canUndo)return this._moveVersion('past','future'); }
    redo() { if(this.canRedo)return this._moveVersion('future','past'); }
    resetSection(section) {
      const keys={title:['theme','tagline','subtitle'],schedule:['days'],keyDates:['key_dates','key_date_overrides'],
        workouts:['category_styles'],notes:['notes','note_style'],monthlyNotes:['footnotes','footnote_styles'],
        events:['events'],additionalInfo:['additional_info'],credits:['credits']}[section];
      if(!keys)throw new Error('Unknown section');
      this.edit(d=>{for(const key of keys){if(key in this.initial)d[key]=clone(this.initial[key]);else delete d[key];}});
    }
    snapshot() { return clone({draft:this.draft,initial:this.initial,rendered:this.rendered,past:this.past,future:this.future,
      pastLabels:this.pastLabels,futureLabels:this.futureLabels,pastPending:this.pastPending,futurePending:this.futurePending,
      currentIsPending:this.currentIsPending,importReview:this.importReview}); }
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
      for(const key of ['past','future']) {
        this[`${key}Labels`]=this[key].map((_,i)=>typeof snapshot[`${key}Labels`]?.[i]==='string'?snapshot[`${key}Labels`][i]:'');
        this[`${key}Pending`]=this[key].map((_,i)=>snapshot[`${key}Pending`]?.[i]===true);
      }
      this.currentIsPending=snapshot.currentIsPending===true;
      this.importReview=snapshot.importReview?clone(snapshot.importReview):null;
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
    get canDownload() { return Boolean(this.current) && !this.current.errors?.length && !this.dirty && !this.busy; }
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
