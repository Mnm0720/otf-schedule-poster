# Browser schedule and poster-copy editor

## Scope and contract

Keep paste → generate → download as the fast path. After a successful generation,
show an editor below the poster backed by a separate in-memory copy of
`Month.to_dict()`. Regenerate reconstructs `Month.from_dict()` and calls the same
`render_html()` as the CLI; it must never parse the original paste again.
The existing GitHub Pages build and Python category registry remain authoritative.

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
5. Editing marks the preview as out of date and disables both downloads until a
   successful regeneration. Regeneration updates preview, dimensions, report, and
   both exports together. Failed regeneration retains the draft and last preview.
   Controls cannot launch overlapping renders or edits during rendering/export.
6. Invalid repeats (self/future/missing source) and event ranges (outside month,
   reversed, fractional, or blank dates) block regeneration with useful errors.
   Existing repeat-template mismatches and unknown categories remain warnings.
7. Generating a new paste replaces the draft only on success. If there are pending
   edits, require confirmation before replacing them. Cancel/failure preserves
   those edits. Loading example text alone does not discard the editor.
8. All controls have labels, feedback is announced, keyboard focus remains usable,
   and user copy is rendered as text, not injected HTML. No persistence or accounts.
9. The header keeps a dark charcoal background and contrasting text in either color
   scheme. Main text and editable fields are at least 16px; secondary labels are
   at least 14px. Links and buttons have readable contrast and touch targets of
   at least 44px in height. The entire checkbox label is a touch target.
10. At 320px, 390px, 768px, and desktop widths, the page fits without horizontal
    scrolling. Phone day cards and copy fields use a single column. Section links
    reach paste, poster, days, copy, and help; generated sections appear in navigation
    only after generation. A day picker replaces the form with the requested day.
    Sticky navigation must not cover the destination or keyboard focus.
11. The poster preview defaults to fit-to-width. A full-size view lets people read
    the fixed-width print layout by scrolling inside the preview without widening
    the page. Switching views does not change the generated HTML or export size.

## Responsive/readability regression

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
