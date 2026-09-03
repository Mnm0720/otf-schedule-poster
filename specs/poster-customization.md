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
- Show every built-in and month-local custom workout type with a legend toggle and color control.
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
Month schema version 2 also stores `custom_categories` (per-key label and default
color), `additional_info`, and `credits`. The migration, storage, and history
contracts are in [saved workspaces](saved-workspaces.md#data-and-recovery-contract).

## Additional information and attribution

- Explain beneath Key Dates that Benchmark, Signature, and Specialty workouts,
  events, and applicable non-repeat-day callouts are added automatically. Derive
  the workout names from the existing category registry so this stays accurate.
- Append two independent, initially collapsed editor sections after Events:
  Additional info, then Credits & team. Both accept multiline plain text, mark
  the draft dirty, and update the poster/exports only after regeneration.
- Additional info defaults to an empty string. Whitespace-only text produces no
  poster section, heading, or reserved space. Nonempty text appears below the
  existing poster content, retaining line breaks and wrapping long words.
- Credits & team follows Additional info at the bottom of the poster. Its default
  is `Image: u/MnM0720` followed on a new line by `Modsquad: u/lookie4dacookie,
  u/jenniferlynn5454, u/pantherluna, and u/Rizzah319`. Display these as profile links
  in the HTML export and readable text in PNG. Allow editing, clearing to hide,
  and explicitly restoring the default. Escape all user text; link only recognized
  `u/username` mentions to a constructed HTTPS Reddit profile URL.
- Store `additional_info` and `credits` in Month JSON. Older schedules lacking the
  fields receive defaults; existing custom or explicitly empty values survive
  round trips. Keep the defaults in Python, not a separate JavaScript copy.
- Restart closes the new editor sections and returns to the initial defaults.
  Persistence and backups now follow [saved workspaces](saved-workspaces.md);
  restart keeps saved posters while clearing the active editing session.

## Simplified editing flow

- After the first successful generation, hide the source inputs and disable
  Generate. Examples and the saved-poster library remain above the source area;
  example buttons only load text before generation. Place PNG/HTML downloads and
  the additional format controls before View full size in the Poster section.
  Offer Restart from text beside Generate. Confirm that restarting clears current
  customizations, including regenerated edits, while retaining saved posters.
  Follow the saved-workspaces safeguards when saving fails. Cancel preserves everything;
  confirm clears the preview/draft/selections, shows the original paste, and enables
  Generate. A failed initial generation keeps the text available to correct.
- Before the daily schedule, provide a collapsed Poster title & theme section for
  theme, tagline, and subtitle. Below the daily editor, give Key Dates, Workout
  Types, Strength & Tread 50 notes, Monthly notes, and Events separate collapsed
  sections. Initialize them closed; preserve the user's expanded sections during
  regeneration. Restart closes them for the next poster.
- Select one Key Date by its description. Put Description first in its form, then
  date links and styling. Adding selects a new entry with a default description
  (`New key date`, numbered if needed) and the selected schedule date. Renaming
  updates the dropdown immediately; switching entries preserves unsaved changes.
  Hiding/removing an entry selects a remaining entry or shows an empty state.
- Replace icon-name dropdowns everywhere with visual pickers using the actual
  cached SVGs. Show the current icon and a grid of available icons, with accessible
  names and selected states. Keyboard users can choose an icon and return to the
  picker control. No user text is treated as SVG markup.
- Rename Checklist notes to Strength & Tread 50 notes. Remove the highlights list
  and its heading from the editor; retain the automatically derived panel in the
  poster. Put a short explanation of the date links and regeneration beneath Edit
  your schedule. Rename Workout Types & Highlights to Workout Types.
- Keep phone layouts readable, with 44px controls, no page overflow, and clear
  section labels. Editing alone does not update the preview or enable stale exports.

## Verification

The records below describe each earlier implementation stage. The
[saved-workspaces verification](saved-workspaces.md#verification-2026-09-03) records
the latest combined suites and browser checks.

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

### Simplified flow verification, 2026-09-03

- Red: eight Node cases and two Python cases failed against the previous UI,
  covering restart safeguards, section structure, entry selection, visual icons,
  and removal of the duplicate highlights list. Two restart cases also failed
  before the explicit dialog was added. All pass after implementation.
- A focused regression caught keyboard focus being lost after hiding the final
  Key Date; focus now moves to Add key date when the picker is empty.
- Green: 101 Python tests and 20 Node tests pass; all four stored schedules validate
  and the static build succeeds. Static structure checks complement the Node DOM
  adapter, checking initial collapse, section order, and download placement.
- Actual browser: successful generation hides text inputs, disables Generate,
  and reveals downloads before View full size. All six optional sections initially
  remain closed. Title settings precede the daily schedule. Expanded sections
  remain open after regeneration.
- Added `Studio celebration`, linked it to days 5, 12, and 19, chose a teal star,
  switched entries, and regenerated. The dropdown retained the description and
  selected entry; the preview contained the linked dates. The new subtitle and
  monthly-note icon also appeared after regeneration.
- Actual SVG icon grid and selected artwork visually checked on desktop and phone.
  At 320px and 390px, document width matched client width (305px and 375px), with
  no overflowing editor controls. The 320px restart dialog fits and defaults focus
  to Keep editing.
- Actual popup: Keep editing preserved a regenerated subtitle and preview.
  Confirming restart hid the old preview/editor, cleared customizations, retained
  the original paste, closed all sections, enabled Generate, and focused the text.
  Tests also cover failed regeneration, failed initial parsing, and blocked
  overlapping actions. The original user tab was not modified.

### Additional info and credits verification, 2026-09-03

- Red: eight Python cases (including the expanded structure check) and two Node
  cases failed before the new model fields, footer rendering, and controls existed.
- Green: 108 Python tests and 22 Node tests pass. All four saved schedules validate;
  the static build succeeds. Older schedule JSON receives defaults, custom values
  round-trip, and explicitly empty credit text remains empty.
- Actual browser: default Additional info is absent from the poster; the credit
  block contains the requested Image/Modsquad text and five Reddit profile links.
  Editing multiline Additional info disables stale downloads; regeneration places
  it below the existing panels and above Credits & team.
- Inspected the downloaded 2400×4110 PNG: the complete poster, both extra text
  lines, credit names, and readable profile labels appear without clipping.
- At 390px and 320px, document/client widths match at 375px and 305px; footer text
  controls use 16px text and stay inside the page. New editor sections start closed.
- Clearing both text fields with the keyboard and regenerating removes both poster
  sections. Restore default credits brings back the requested attribution while
  Additional info stays hidden. The original user tab was not modified.
