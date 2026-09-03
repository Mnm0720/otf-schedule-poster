# Date selection and linked poster customization

## Behavior

- Replace the full editor calendar with a date dropdown and exactly one day form.
  Initially select day 1; changing dates preserves edits without marking the draft
  dirty. Keep the selected date after regeneration and reset it for a new month.
- Keep copy, events, Key Dates, and Workout Types independently accessible below
  the selected day. Preserve the existing mobile sizes and section navigation.
- Key Dates from workouts/events/non-repeat days remain derived. Expose overrides
  for their text, linked date(s), icon, and color; only edited properties override
  the source. Allow adding/removing custom entries and hiding/restoring automatic
  entries. Accept date lists and inclusive ranges, e.g. `8, 18, 24-31`, within the
  current month. The printed heading is derived from those date links.
- Template & Equipment Highlights always derive their dates/types from the edited
  schedule. They have no independent date editor. Refresh after regeneration.
- Show every registered workout type with a legend toggle and color control.
  Unless explicitly overridden, the toggle follows whether the month uses that
  type. Manual choices persist; a reset restores automatic selections. Toggles
  affect the Workout Types legend only, never delete schedule data/highlights.
- A type color applies to its calendar pills, highlight markers/text, legend, and
  linked Key Date icons (unless that key date has its own color override). Choose
  contrasting black/white text for custom pill colors. Never mutate the shared
  Python category registry or leak settings between months.
- Key Dates and each monthly footnote support an icon from the cached icon catalog
  and a color picker. Automatic footnote text continues to follow the schedule
  when only its style is changed. Also expose icon/color for the checklist notes.
- Round-trip all settings through Month JSON. Existing schedule files still load.
  Validate dates, category keys, hex colors, and cached icon names before rendering.
  Invalid settings preserve the draft and disable stale exports. Escape user copy.

## Data contract

Month adds `category_styles` (per-key color/optional visibility), `key_dates`
(additional linked rows), `key_date_overrides` (sparse patches keyed by derived row
ID), `footnote_styles` (sparse patches keyed by automatic note ID), and `note_style`
(checklist icon/color). Defaults are empty. The Python renderer owns derivation;
the browser receives current defaults and the registries from its Python bridge.

## Verification

Verified locally on 2026-09-02:

- Red: 16 new Python cases failed before the model/render changes. The UI tests
  first exposed the missing date selection, linked-date controls, type toggles,
  and automatic-note styles. Implemented each behavior and reran focused suites.
- Two additional regressions failed before their fixes: switching an automatic
  monthly note to custom text lost an unsaved icon/color choice, and selecting
  exactly four legend types left a blank grid column. Both now pass.
- Green: all 98 Python tests and 18 Node tests pass. All four saved schedules
  validate and the static site builds successfully. Node tests use a DOM adapter
  and mocked runtime; the browser results below use the actual Pyodide bundle.
- In an isolated browser tab, generated September and confirmed exactly one day
  form. Edited day 8, switched to day 1, then returned to day 8 without losing the
  title or 3G change. Regeneration retained the selected date.
- Added a custom Key Date for `3, 7, 9`, changed linked entry icons/colors, selected
  Specialty and deselected Standard in the legend, and changed Run/Row/Benchmark
  colors. Preview and export reflected the edits; Standard workouts remained in
  the calendar. Named workout changes updated Key Dates automatically.
- Adding Run/Row to day 1 refreshed highlights to include `9/1`. A 3G edit changed
  the automatic monthly note to include `9/8` while retaining its flag icon and
  chosen red color. The benchmark's custom purple propagated to its calendar pill,
  highlight, legend, and linked Key Date icon.
- At 320/390/768/1440px viewport widths, document/client widths both measured
  305/375/753/1425px, respectively: no page overflow. Date controls use 16px text.
  Phone Key Dates and workout controls stack in one column; desktop columns expand.
  Screenshots of the phone date/key-date forms and desktop workout controls checked.
- Downloaded and inspected the actual 2400×3656 PNG: complete poster, linked dates,
  updated highlights, custom icons/colors, and selected legend entries present.
  Original user tab and its draft stayed untouched.

CI and Pages run both suites before publishing. Commits use Mnm0720 as author and
committer, with no co-author trailers.
