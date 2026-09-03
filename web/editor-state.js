/* Shared by the page and dependency-free Node tests. No parsing lives here. */
(function (root) {
  const clone = (value) => JSON.parse(JSON.stringify(value));

  class EditorState {
    constructor() { this.current = null; this.draft = null; this.dirty = false; this.busy = false; }
    accept(result) {
      this.current = clone(result);
      this.draft = clone(result.schedule);
      this.dirty = false;
    }
    edit(change) {
      if (this.busy) throw new Error('Editor is busy.');
      change(this.draft);
      this.dirty = true;
    }
    setAutomatic(key, automatic) {
      this.edit(d => { d[key] = automatic ? [] : clone(d[key].length ? d[key] : this.current.defaults[key]); });
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
    return errors;
  }

  const api = {EditorState, calendarCells, validateDraft};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.OTFEditor = api;
})(globalThis);
