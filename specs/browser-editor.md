# Browser schedule and poster-copy editor

## Scope and contract

Keep paste → generate → download as the fast path. After a successful generation,
show the schedule editor before the preview on phones, and beside it on wide
screens, backed by a separate in-memory copy of
`Month.to_dict()`. Regenerate reconstructs `Month.from_dict()` and calls the same
`render_html()` as the CLI; it must never parse the original paste again.
The existing GitHub Pages build and Python category registry remain authoritative.
The persistence, sharing, history, and export extensions are specified in
[saved workspaces](saved-workspaces.md), which supersedes the original no-storage scope.

## Acceptance criteria

1. Every day of the parsed month is available in a date dropdown. Show exactly one
   selected day form, preserving edits when switching dates and keeping the selected
   date after regeneration. See [poster customization](poster-customization.md)
   for linked Key Dates, workout toggles, shared colors, and note icons.
2. Each day supports multiple template entries with category dropdowns, independent
   workout titles, add/remove actions, an optional earlier repeat source, and 3G.
   Preserve entry order, unknown entries, raw text, day notes, and unrelated month
   fields unless the user changes the corresponding value. Changing a repeat link
   does not silently copy or overwrite another day's templates.
3. Theme, tagline, subtitle, notes, footnotes (heading/body), and events
   (name/start/end) can be edited. Preserve existing footnote icons and event kinds.
   New footnotes use a bundled icon. Events may span one day or the whole month.
4. Notes and footnotes offer automatic/custom modes. Automatic mode leaves the
   stored list empty, deriving fresh copy on every render. Custom mode starts with
   the currently displayed defaults when there is no override. Empty custom lists
   restore automatic copy, matching the existing model. Subtitle initially reads
   “Monthly Schedule Poster” when no override exists.
5. Editing marks the preview as out of date and disables the unified Download button until a
   successful regeneration. Regeneration updates preview, dimensions, report, and
   the schedule used for all export formats (PNG, HTML, PDF, compact images, ICS)
   together. Draft backups and editable snapshots remain available with pending edits.
   Failed regeneration retains the draft and last preview.
   Controls cannot launch overlapping renders or edits during rendering/export.
6. Invalid repeats (self/future/missing source) and event ranges (outside month,
   reversed, fractional, or blank dates) block regeneration with useful errors.
   Existing repeat-template mismatches and unknown categories remain warnings.
7. After successful generation, hide source inputs, examples, and disable Generate.
   Previous/Next version controls appear in Earlier versions and recovery. Successful
   updates create checkpoints; navigating versions preserves pending edits as
   a recoverable version, including invalid drafts. Failed navigation restores
   the original draft and history. Labels survive refresh and backup/import.
   A unified format dropdown and Download button replace the separate PNG/HTML
   buttons. The poster preview is capped at 1080px wide.
   Restart from text opens a popup explaining that the current editing session will
   be cleared while saved drafts remain. Warn when autosave is unavailable; if a
   previously working save fails during confirmation, keep the editor open for
   backup. Cancel preserves the draft and preview; successful confirmation clears
   them and restores the original paste. Failed initial parsing keeps that text
   available to correct. Recovery details follow the saved-workspaces contract.
8. All controls have labels, feedback is announced, keyboard focus remains usable,
   and user copy is escaped; tagline supports attribute-free emphasis only. Local
   persistence and account-free sharing follow the saved-workspaces specification.
9. The header keeps a dark charcoal background and contrasting text in either color
   scheme. Main text and editable fields are at least 16px; secondary labels are
   at least 14px. Links and buttons have readable contrast and touch targets of
   at least 44px in height. The entire checkbox label is a touch target.
10. At 320px, 390px, 768px, and desktop widths, the page fits without horizontal
    scrolling. Phone day cards and copy fields use a single column. Section links
    reach Paste, Edit, Download, and Help; generated sections appear in navigation
    only after generation. A day picker replaces the form with the requested day.
    Sticky navigation must not cover the destination or keyboard focus.
11. The poster preview defaults to fit-to-width. A full-size view lets people read
    the fixed-width print layout by scrolling inside the preview without widening
    the page. Switching views does not change the generated HTML or export size.

## Responsive/readability regression

### Moderator workflow update, September 2026

- Use Paste thread, Review and edit, and Preview and download as visible stages.
  Preserve PNG (Recommended) and the existing format choices; do not introduce a
  Reddit-specific default. Optional styling and backup/sharing follow the schedule.
- Keep save health visible outside dialogs, separately from preview freshness.
  Failed saves provide a backup action, and failed draft loading keeps the picker
  available. Users can switch drafts repeatedly without restarting.
- Show the detected month prominently and provide a month picker before generation.
  Make the original source available read-only after generation without resetting.
- Add Previous/Next date controls and a collapsed month review with workouts,
  inferred Standard days, modified dates, and actionable validation issues.
  Selecting a review entry opens that day without losing pending edits.
- Explain repeat metadata versus copying. Copying workouts is an explicit action
  and preserves unrelated day fields; its pending change can be recovered through
  version history. Validation issues select the relevant day or open the relevant
  section and focus its field. Initial validation errors block every final export.
- Update preview is the primary edit action. The sticky mobile action bar uses
  controls at least 44px high and 16px type; secondary status is at least 14px.
  At 320/390/768px, long names, expanded settings, and validation messages must
  wrap without page overflow. Sticky bars must not obscure focused controls.
- Download confirmation includes real Open file, Download again, and Share editable
  copy controls. Help explains moderator tasks, with parser syntax kept secondary.
- Verify the built site using real Pyodide and actual mobile browser layouts, in
  addition to unit tests. Startup and asset delivery follow github-pages.md.

Before this change, actual browser checks at 390px found a dark-mode header with
`rgb(242,244,247)` behind white text, 13px paste text, 22px example buttons, and no
section navigation. Verify the corrected styles, navigation, generated editor,
regeneration, and exports in the real browser as well as the existing unit suites.

Historical responsive pass for the original calendar editor, verified on 2026-09-02
(the selected-date editor's current results are in the customization spec):

| Viewport width | Document width | Day columns | Input font | Example / editor buttons |
| --- | --- | --- | --- | --- |
| 320px | 305px | 1 | 16px | 44px high |
| 390px | 375px | 1 | 16px | 44px high |
| 768px | 753px | 3 | 16px | 44px high |
| 1440px | 1425px | 7 | 16px | 44px high |

- Actual dark-mode header is now `rgb(24,33,45)` with white text; its background
  is independent of the theme's text color. Desktop and mobile screenshots checked.
- Day-picker and section navigation regressions failed before implementation and
  passed afterward. Full-size preview likewise began with a failing test.
- Real browser: loaded September through Pyodide, jumped to day 23, edited its
  workout title and 3G flag, navigated to copy, changed subtitle, and regenerated.
  Pending edits disabled downloads; successful regeneration restored them.
- At 390px, full-size preview has 1200px scrollable content within a 304px region;
  document width stays 375px. Fit-to-width restores the scaled overview.
- Downloaded and inspected the actual 2400×3736 PNG: complete poster, edited copy
  and 3G flag present. Downloaded HTML also contains the edited subtitle and title.
- All 75 Python tests and 13 Node tests pass; saved schedules validate and the
  static build succeeds. Original user preview was preserved with pending edits;
  interaction tests used a separate tab and temporary viewport overrides were reset.

## TDD and verification

Write and run failing tests before each behavioral slice. Use Python tests for the
real parse/render bridge, round trips, validation, and derived panels. Use Node's
built-in test runner for immutable draft editing, calendar layout, default-copy
semantics, and render-state transitions. Run both suites in CI without requiring
a browser or network. Build the same static output used by GitHub Pages.

## Verification record

The original editor's historical record follows the current implementation checks.

### September 23, 2026 moderator and mobile update

- Red/green regressions cover actionable errors, invalid-export protection, save
  failures, pending-edit history, failed draft switching, and source references.
  Later red cases caught Key Date focus selecting the wrong custom entry, missing
  validation indicators in month review, and absent stale-preview guidance beside
  Download. Parser, history, and runtime evidence is recorded in their specifications.
- Combined local verification: 151 Python tests and 77 Node tests pass; all four
  stored schedules validate. The static project-path build succeeds with hashed
  assets and the real worker runtime.
- Real Chromium browser, served under `/otf-schedule-poster/`: generated a monthly
  thread, edited and updated a title, switched dates without losing edits, refreshed
  into the saved draft, and downloaded PNG and PDF. The inspected PNG was complete
  at 2400 by 3858 pixels. The actual PDF was confirmed as one A4 page with Poppler.
- Real browser recovery: an invalid future repeat blocked Download, survived
  refresh, and its issue action selected and focused the repeat field. Correcting
  it enabled export. A pending title remained recoverable through Previous/Next
  version and another refresh. The inclusive range assigned Run/Row to its middle day.
- No page overflow at 320, 390, 768, and 1440px viewport widths. Phone inputs use
  16px text or larger, action controls are at least 44px high, and the preview's
  full-size mode scrolls internally. Expanded optional settings were also checked.
  A keyboard focus check confirmed an optional control stayed above the sticky bar.
- The optional audit page reported zero axe violations with 28 rules passing on
  the generated mobile editor, including expanded optional sections. Poster artwork
  is excluded from this check; it is not a complete accessibility certification.
- These are desktop Chromium viewport checks, not physical iOS/Android testing.
  Actual 200% browser zoom was not verified because the embedded browser did not
  apply the shortcut. Moderator usability sessions and representative-device
  performance measurements remain follow-up validation. The CI smoke is configured
  but its hosted run has not occurred locally. No application changes were published.

### Original editor implementation

- Baseline: 63 Python tests passed before changes.
- Red: 12 bridge cases failed because the bridge did not exist; the state and UI
  suites failed on missing modules, and three application-flow cases failed on the
  missing regeneration entry point.
- Green: implemented the bridge, isolated draft state, and form controls. Adjusted
  the render assertion to respect the existing renderer's uppercase theme style.
- An additional regression test caught regeneration errors being replaced by the
  generic pending-edits message. Preserved the specific error beside the editor.
- Initial editor local checks: 75 Python tests and 11 Node tests pass; all four stored
  schedules validate; the static build includes the bridge and both editor files.
- CI and the GitHub Pages build run editor tests before publication.
- The Node tests exercise form handlers and application flow using a small DOM
  adapter and mocked Pyodide. Actual browser checks are recorded separately above.
