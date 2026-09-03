# Saved workspaces, editing history, sharing, and exports

## Acceptance contract

- Save every edit locally, including invalid pending edits and the original paste.
  Restore the last active draft after refresh without reparsing; named saved posters
  appear below examples and above the paste box. Opening another draft preserves
  the previous one. Restart starts a new draft and does not delete saved posters.
- Version the storage envelope separately from Month JSON. Preserve unsupported or
  corrupt storage without overwriting it; announce failures and offer JSON backup
  and import. Do not promise that browser data survives clearing site storage.
  Workspace envelope version 1 accepts old plain JSON; Month schema 2 records the
  custom workout registry so older builds reject newer schedules instead of silently
  stripping their customization. Imported missing day defaults are filled in.
- Undo/redo captures changes across sections and regeneration. New edits discard
  the redo branch. Reset each section to its initial generated/imported state,
  retaining unrelated settings; resets can be undone. Restore history with drafts.
- Unknown template lines retain all linked days, appear as distinct month-specific
  workout types and in template selectors/highlights/legend, receive deterministic
  distinct colors, and support color/visibility overrides without changing the global
  registry. Preserve raw text and warn to check spelling or notify the developer.
- Export the current rendered draft as printable PDF, a 1080×1920 calendar phone
  wallpaper, a 1080×1350 social calendar image, and an all-day .ics calendar. Full
  poster exports keep all information; compact layouts emphasize the calendar.
  Escape ICS text, fold UTF-8 lines, use stable event IDs and exclusive end dates.
- GitHub Pages only, per the user's hosting constraint: create compressed editable
  snapshot links with data in the URL fragment and JSON backup/import files. No
  login or uploads. Opening shared data creates a separate local copy, preserving
  existing drafts. State clearly that copies do not synchronize live: mods send an
  updated link/file back. Bound decoded size and reject unsupported versions; offer
  a file when a link would be too long. No infrastructure credentials or backend.
- Keep new controls labelled, keyboard usable, 44px touch targets, and responsive.
  Show save/sync failure messages, disable stale visual exports, and preserve drafts
  during render/network failures. Storage and sharing content is untrusted data.

## Verification

Write failing behavioral tests for each slice before implementation. Record results
after full Python/Node tests, schedule validation, static build and real-browser QA.

### Verification, 2026-09-03

- Red tests confirmed missing unknown categories/dates, persistence, history, shared
  links, exports, and schema migration before those implementations were added.
  Later regressions caught the misplaced saved picker, unsafe shared tagline HTML,
  literal emphasis markup in compact layouts, and stale-tab storage writes.
- Green: 114 Python tests and 33 Node tests pass. All four committed schedules
  validate and the static build includes 31 bundled files. CI and Pages run all
  `tests/*.test.cjs` suites. The OTF TDD skill was updated and validated.
- Actual Pyodide browser: generated September with `Minvdaibands` on days 2 and 5;
  both dates retained the type. Its legend checkbox, color input, and developer
  note appeared. Changed the subtitle before regeneration, closed the tab, reopened,
  and restored the pending edit with downloads disabled. Undo and redo survived;
  regeneration succeeded without reparsing.
- A 1.5 KB compressed link opened the pending edit as a separate saved copy, keeping
  the original poster. Restart retained both saved posters and restored the source
  form. Removed only those two named QA drafts afterward.
- Actual narrow browser viewport: 319px inner width / 304px client and document
  widths. Saved controls and custom types fit without page overflow; visual checks
  covered dropdowns, action buttons, color controls, and the developer note. The
  viewport override API did not change the measured width for desktop requests,
  so a new desktop-width browser pass was not claimed; temporary overrides reset.
- Phone and social HTML layouts from the same export renderer were opened and
  visually reviewed; all 30 dates and attribution were present at 1080×1920 and
  1080×1350. Dense compact layouts scale their content to fit during image export.
- PDF, phone, social, and ICS browser export handlers completed without errors.
  The browser policy blocked opening the generated PDF blob URL; that PDF's actual
  downloaded pages were not visually verified. Independently exercised the same
  PDF export function with real pdf-lib and a synthetic section fixture: two valid
  A4 pages, reopened with pdf-lib and rasterized with Poppler. Inspected both page
  images; section starts/ends were preserved with no clipping. Pure pagination
  tests cover complete pixel coverage and overlong blocks.
- ICS tests cover stable UIDs, month-end exclusive end dates, all-day events,
  Unicode line folding, escaping, and events. Implementation references:
  [RFC 5545](https://www.rfc-editor.org/rfc/rfc5545) and
  [pdf-lib API](https://pdf-lib.js.org/docs/api/classes/pdfdocument).
