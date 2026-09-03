/* Shared by the page and dependency-free Node tests. No parsing lives here. */
(function (root) {
  const clone = (value) => JSON.parse(JSON.stringify(value));

  class EditorState {
    constructor() { this.current = null; this.draft = null; this.dirty = false; this.busy = false; }
    reset() { this.current = null; this.draft = null; this.dirty = false; }
    accept(result) {
      this.current = clone(result);
      this.draft = clone(result.schedule);
      for (const key of ['category_styles','key_date_overrides','footnote_styles','note_style']) this.draft[key] ??= {};
      this.draft.key_dates ??= [];
      this.draft.additional_info ??= '';
      this.draft.credits ??= result.defaults.credits || '';
      this.dirty = false;
    }
    edit(change) {
      if (this.busy) throw new Error('Editor is busy.');
      change(this.draft);
      this.dirty = true;
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
