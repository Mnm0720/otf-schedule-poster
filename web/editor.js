/* Form controls edit the Month JSON in place; the Python renderer owns all copy. */
(function (root) {
  const {parseDayList} = typeof module !== 'undefined' && module.exports
    ? require('./editor-state.js') : root.OTFEditor;
  const weekdays = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

  class ScheduleEditor {
    constructor(doc, state, changed) {
      this.doc = doc; this.state = state; this.changed = changed; this.serial = 0;
    }
    node(tag, text, cls) {
      const el = this.doc.createElement(tag);
      if (text !== undefined) el.textContent = text;
      if (cls) el.className = cls;
      return el;
    }
    change(fn) { this.state.edit(fn); this.changed(); }
    button(text, name, fn) {
      const b = this.node('button', text, 'small-button');
      b.type = 'button'; b.setAttribute('aria-label', name); b.onclick = fn;
      return b;
    }
    field(parent, label, name, value, update, type = 'text') {
      const wrap = this.node('div', undefined, 'editor-field');
      const input = this.node(type === 'textarea' ? 'textarea' : 'input');
      if (type !== 'textarea') input.type = type;
      input.id = `editor-field-${++this.serial}`;
      input.setAttribute('aria-label', name);
      input.value = value ?? '';
      if (type === 'number') { input.min = 1; input.max = this.state.draft.days.length; input.step = 1; }
      input.oninput = () => this.change(() => update(input.value));
      const caption = this.node('label', label); caption.htmlFor = input.id;
      wrap.append(caption, input); parent.append(wrap);
      return input;
    }
    checkbox(parent, text, name, checked, update) {
      const label = this.node('label', undefined, 'check-label');
      const input = this.node('input'); input.type = 'checkbox'; input.checked = checked;
      input.setAttribute('aria-label', name);
      input.onchange = () => update(input.checked);
      label.append(input, this.node('span', text)); parent.append(label);
      return input;
    }
    select(parent, label, name, options, value, update) {
      const wrap = this.node('div', undefined, 'editor-field');
      const select = this.node('select'); select.setAttribute('aria-label', name);
      select.id = `editor-field-${++this.serial}`;
      for (const [key, text] of options) {
        const option = this.node('option', text); option.value = String(key); select.append(option);
      }
      select.value = value == null ? '' : String(value);
      select.onchange = () => this.change(() => update(select.value));
      const caption = this.node('label', label); caption.htmlFor = select.id;
      wrap.append(caption, select); parent.append(wrap);
      return select;
    }
    render() {
      this.renderCalendar(); this.renderCopy(); this.renderKeyDates(); this.renderWorkoutTypes();
      this.doc.getElementById('editorWrap').hidden = false;
    }
    renderCalendar() {
      const grid = this.doc.getElementById('calendarEditor'); grid.replaceChildren();
      const m = this.state.draft;
      const month = `${m.year}-${m.month}`;
      if (this.selectionMonth !== month || !m.days.some(d => d.day === this.selectedDay)) this.selectedDay = m.days[0].day;
      this.selectionMonth = month;
      const jump = this.doc.getElementById('dayJump'); jump.replaceChildren();
      for (const day of m.days) {
        const weekday = weekdays[new Date(Date.UTC(m.year,m.month-1,day.day)).getUTCDay()];
        const option = this.node('option', `${m.month}/${day.day} · ${weekday}`); option.value = String(day.day); jump.append(option);
      }
      jump.value = String(this.selectedDay);
      const showDay = () => {
        grid.replaceChildren();
        const day = m.days.find(d => d.day === this.selectedDay);
        const card = this.node('fieldset', undefined, 'day-card'); card.id = `day-${day.day}`;
        grid.append(card); this.renderDay(card, day);
      };
      jump.onchange = () => {
        this.selectedDay = Number(jump.value); showDay();
      };
      showDay();
    }
    renderDay(card, day) {
      card.replaceChildren();
      const m = this.state.draft;
      const weekday = weekdays[new Date(Date.UTC(m.year, m.month - 1, day.day)).getUTCDay()];
      card.append(this.node('legend', `${m.month}/${day.day} · ${weekday.slice(0, 3)}`));
      day.entries.forEach((entry, index) => {
        const group = this.node('div', undefined, 'template-entry');
        const options = this.state.current.categories.map(c => [c.key, c.label]);
        if (!options.some(([key]) => key === entry.category)) options.push([entry.category, entry.category]);
        this.select(group, 'Template', `Day ${day.day} template ${index + 1}`, options, entry.category, value => {
          entry.category = value;
          this.renderWorkoutTypes();
        });
        // Keep each entry's own title, including unknown or custom regular templates.
        this.field(group, 'Workout title', `Day ${day.day} workout title ${index + 1}`, entry.title,
          value => { entry.title = value; });
        group.append(this.button('Remove', `Day ${day.day} remove template ${index + 1}`, () => {
          this.change(() => day.entries.splice(index, 1)); this.renderDay(card, day); this.renderWorkoutTypes();
          card.querySelectorAll('button')[0]?.focus();
        }));
        card.append(group);
      });
      const add = this.button('+ Template', `Day ${day.day} add template`, () => {
        this.change(() => day.entries.push({category:'std', title:''})); this.renderDay(card, day); this.renderWorkoutTypes();
        const selects = card.querySelectorAll('select'); selects[selects.length - 2]?.focus();
      });
      card.append(add);
      this.select(card, 'Repeat of', `Day ${day.day} repeat of`,
        [['', 'Not a repeat'], ...m.days.filter(d => d.day < day.day).map(d => [d.day, `${m.month}/${d.day}`])],
        day.repeat_of, value => { day.repeat_of = value ? Number(value) : null; });
      this.checkbox(card, '3G template', `Day ${day.day} 3G`, day.three_g,
        checked => this.change(() => { day.three_g = checked; }));
    }
    styleControls(parent, value, label, update, defaults = {}) {
      const row = this.node('div', undefined, 'style-controls');
      this.select(row, 'Icon', `${label} icon`, (this.state.current.icons || []).map(i => [i.key,i.label]),
        value.icon || defaults.icon || 'groups', icon => update('icon',icon));
      this.field(row, 'Color', `${label} color`, value.color || defaults.color || '#8A919B',
        color => update('color',color), 'color');
      parent.append(row);
    }
    renderWorkoutTypes() {
      const root = this.doc.getElementById('workoutTypesEditor'); root.replaceChildren();
      const m = this.state.draft;
      const used = new Set(m.days.flatMap(d => d.entries.map(e => e.category)));
      root.append(this.node('p','Selections start with the types used this month. Colors apply across the poster; toggles change the legend only.','hint'));
      const list = this.node('div', undefined, 'workout-types'); root.append(list);
      for (const cat of this.state.current.categories) {
        const row = this.node('div', undefined, 'type-setting');
        const settings = m.category_styles[cat.key] || {};
        const set = (key,value) => { (m.category_styles[cat.key] ??= {})[key] = value; };
        this.checkbox(row, cat.label, `Show ${cat.label} in workout types`, settings.visible ?? used.has(cat.key),
          checked => this.change(() => set('visible',checked)));
        this.field(row,'Color',`${cat.label} color`,settings.color || cat.color || '#8A919B', color => set('color',color),'color');
        list.append(row);
      }
      root.append(this.button('Use automatic selections','Use automatic workout selections',() => {
        this.change(() => { for (const settings of Object.values(m.category_styles)) delete settings.visible; });
        this.renderWorkoutTypes();
      }));
      root.append(this.button('Reset type colors','Reset workout colors',() => {
        this.change(() => { for (const settings of Object.values(m.category_styles)) delete settings.color; });
        this.renderWorkoutTypes();
      }));
      root.append(this.node('h3','Template & equipment highlights'));
      root.append(this.node('p','Dates are linked to your schedule. Regenerate to refresh the list below.','hint'));
      const highlights = this.node('ul',undefined,'automatic-copy');
      for (const row of this.state.current.highlights || []) highlights.append(this.node('li',`${row.label}: ${row.value}`));
      root.append(highlights);
    }
    renderKeyDates() {
      const root = this.doc.getElementById('keyDatesEditor'); root.replaceChildren();
      const m = this.state.draft;
      root.append(this.node('p','Workouts and events stay linked to the schedule. Customize a field to override it, or add your own dates. Regenerate to refresh linked rows.','hint'));
      const renderRow = (value,label,set,remove) => {
        const row = this.node('section',undefined,'copy-item');
        row.append(this.node('h3',label));
        this.field(row,'Date(s)',`${label} dates`,Array.isArray(value.days) ? value.days.join(', ') : value.days,
          input => set('days',parseDayList(input,m.days.length) ?? input));
        row.append(this.node('p','Day numbers or ranges, e.g. 8, 18, 24-28.','hint'));
        this.field(row,'Description',`${label} description`,value.detail,input => set('detail',input));
        this.styleControls(row,value,label,set,{icon:'flag',color:'#F4511E'});
        row.append(remove); root.append(row);
      };
      (this.state.current.defaults.key_dates || []).forEach((source,index) => {
        const label = `Key Date ${index+1}`;
        const patch = m.key_date_overrides[source.id] || {};
        if (patch.hidden) return;
        const set = (key,value) => { (m.key_date_overrides[source.id] ??= {})[key]=value; };
        renderRow({...source,...patch},label,set,this.button('Hide linked entry',`Hide ${label}`,() => {
          this.change(() => set('hidden',true)); this.renderKeyDates();
        }));
      });
      m.key_dates.forEach((row,index) => {
        const label = `Custom Key Date ${index+1}`;
        renderRow(row,label,(key,value) => { row[key]=value; },this.button('Remove entry',`Remove ${label}`,() => {
          this.change(() => m.key_dates.splice(index,1)); this.renderKeyDates();
        }));
      });
      root.append(this.button('+ Key date','Add key date',() => {
        this.change(() => m.key_dates.push({days:[this.selectedDay],detail:'',icon:'flag',color:'#F4511E'}));
        this.renderKeyDates();
      }));
      root.append(this.button('Restore linked entries','Restore linked key dates',() => {
        this.change(() => { m.key_date_overrides={}; }); this.renderKeyDates();
      }));
    }
    renderCopy() {
      const root = this.doc.getElementById('copyEditor'); root.replaceChildren();
      const m = this.state.draft;
      const headings = this.node('div', undefined, 'copy-headings');
      for (const key of ['theme', 'tagline', 'subtitle']) {
        this.field(headings, key[0].toUpperCase() + key.slice(1), `Poster ${key}`, m[key], value => { m[key] = value; });
      }
      root.append(headings);
      for (const key of ['notes', 'footnotes']) {
        const section = this.node('section', undefined, 'copy-section'); root.append(section);
        const renderSection = () => {
          section.replaceChildren();
          section.append(this.node('h3', key === 'notes' ? 'Checklist notes' : 'Monthly notes'));
          if (key === 'notes') this.styleControls(section,m.note_style,'Checklist notes',
            (key,value) => { m.note_style[key]=value; },{icon:'check_circle',color:'#F4511E'});
          const automatic = m[key].length === 0;
          const toggle = this.checkbox(section, 'Use automatic copy', `Automatic ${key}`, automatic, checked => {
            this.state.setAutomatic(key, checked); this.changed(); renderSection();
            section.querySelectorAll('input')[0]?.focus();
          });
          if (automatic) {
            const preview = this.node('ul', undefined, 'automatic-copy');
            for (const [index,item] of this.state.current.defaults[key].entries()) {
              const li = this.node('li', key === 'notes' ? item : `${item.lead} ${item.text}`);
              if (key === 'footnotes') {
                const id = item.id || String(index);
                this.styleControls(li,{...item,...m.footnote_styles[id]},`Monthly note ${index+1}`,
                  (key,value) => { (m.footnote_styles[id] ??= {})[key]=value; });
              }
              preview.append(li);
            }
            section.append(preview, this.node('p', 'Automatic copy updates when you regenerate.', 'hint'));
          } else if (key === 'notes') {
            this.field(section, 'One note per line', 'Poster notes', m.notes.join('\n'), value => {
              m.notes = value.split('\n').map(s => s.trim()).filter(Boolean);
              toggle.checked = m.notes.length === 0;
            }, 'textarea');
            section.append(this.node('p', 'Clear all notes to restore automatic copy.', 'hint'));
          } else {
            m.footnotes.forEach((item, index) => {
              const row = this.node('div', undefined, 'copy-item');
              this.field(row, 'Heading', `Footnote ${index + 1} heading`, item.lead, value => { item.lead = value; });
              this.field(row, 'Text', `Footnote ${index + 1} text`, item.text, value => { item.text = value; }, 'textarea');
              this.styleControls(row,item,`Monthly note ${index+1}`,(key,value) => { item[key]=value; });
              row.append(this.button('Remove footnote', `Remove footnote ${index + 1}`, () => {
                this.change(() => m.footnotes.splice(index, 1)); renderSection();
                section.querySelectorAll('input')[0]?.focus();
              }));
              section.append(row);
            });
            section.append(this.button('+ Footnote', 'Add footnote', () => {
              this.change(() => m.footnotes.push({icon:'groups', lead:'', text:''})); renderSection();
              const inputs = section.querySelectorAll('input[type="text"]'); inputs[inputs.length - 1]?.focus();
            }));
            section.append(this.node('p', 'Remove all footnotes to restore automatic copy.', 'hint'));
          }
        };
        renderSection();
      }
      const events = this.node('section', undefined, 'copy-section events'); root.append(events);
      const renderEvents = () => {
        events.replaceChildren(); events.append(this.node('h3', 'Events'));
        events.append(this.node('p', 'Add a day range for each event ribbon. Use day numbers within this month.', 'hint'));
        m.events.forEach((event, index) => {
          const row = this.node('div', undefined, 'event-item');
          this.field(row, 'Event name', `Event ${index + 1} name`, event.name, value => { event.name = value; });
          for (const key of ['start', 'end']) {
            this.field(row, `${key === 'start' ? 'Start' : 'End'} day`, `Event ${index + 1} ${key} day`, event[key],
              value => { event[key] = value === '' ? '' : Number(value); }, 'number');
          }
          row.append(this.button('Remove', `Remove event ${index + 1}`, () => {
            this.change(() => m.events.splice(index, 1)); renderEvents();
            events.querySelectorAll('button')[0]?.focus();
          }));
          events.append(row);
        });
        events.append(this.button('+ Event', 'Add event', () => {
          this.change(() => m.events.push({name:'', start:1, end:m.days.length, kind:'event'})); renderEvents();
          const inputs = events.querySelectorAll('input[type="text"]'); inputs[inputs.length - 1]?.focus();
        }));
      };
      renderEvents();
    }
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {ScheduleEditor};
  else root.ScheduleEditor = ScheduleEditor;
})(globalThis);
