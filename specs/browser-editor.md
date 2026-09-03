# Browser schedule and poster-copy editor

## Scope and contract

Keep paste → generate → download as the fast path. After a successful generation,
show an editor below the poster backed by a separate in-memory copy of
`Month.to_dict()`. Regenerate reconstructs `Month.from_dict()` and calls the same
`render_html()` as the CLI; it must never parse the original paste again.
The existing GitHub Pages build and Python category registry remain authoritative.

## Acceptance criteria

1. Every day of the parsed month appears in a Sunday-first calendar on wide screens
   and dated cards on narrow screens, including February and six-week months.
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
- Final local checks: 75 Python tests and 11 Node tests pass; all four stored
  schedules validate; the static build includes the bridge and both editor files.
- CI and the GitHub Pages build run editor tests before publication.
- The Node tests exercise form handlers and application flow using a small DOM
  adapter and mocked Pyodide. Actual browser startup, layout, and PNG export have
  not been exercised by these automated checks.
