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
  Show save, share, import, and export failure messages, disable stale poster and
  calendar exports, and preserve drafts
  during render/network failures. Storage and sharing content is untrusted data.

## Data and recovery contract

- `web/workspace.js` stores workspace envelope version 1 with `id`, `name`,
  `source`, `updatedAt`, and `state`. State contains `draft`, `rendered`, `initial`,
  `past`, and `future`; all schedule snapshots use the Month JSON contract.
  `otf-draft:<id>` holds each saved poster, `otf-active` identifies the last active
  poster, and `otf-source` separately saves an unfinished paste and month override.
- Month schema version 2 includes `custom_categories`. Older Month JSON and plain
  schedule imports receive current defaults; versions newer than supported are
  rejected. Unreadable local entries remain listed with a raw backup action.
- Save edits before regeneration, preserving pending invalid values. Restore the
  last rendered schedule through Python, then overlay the saved draft and history.
  Do not reparse the source or show a pending edit as already rendered. Keep at most
  100 undo snapshots. Regeneration does not discard history or change the initial
  reset baseline.
- Reject saves when stored data changed since it was read. When another tab changes
  the active poster, preserve the current editor as a separate local copy. Report
  storage failures and keep draft download available; no browser-only design can
  guarantee recovery after site data is cleared.
- Restart confirms clearing the active editor while keeping saved posters. If
  autosave was already unavailable, warn to download a backup before discarding.
  If a previously successful save fails at confirmation, abort restart and leave
  the editor open. Successful restart restores the source paste and clears the
  active selection, preview, and history without deleting library entries.
- JSON draft backups include source text and history. Shared links contain the
  current draft and last rendered schedule, use the shared draft as the recipient's
  reset baseline, and omit source text and past/future history. Opening either an
  imported file or link creates a separate local copy. Sending updates requires a
  new link/file; there is no shared server state on GitHub Pages.
- Gzip snapshots use URL-safe base64 in the fragment. Emitted encoded snapshots
  are limited to 12,000 characters; input is capped at 20,000 encoded characters.
  JSON input is capped at 2,000,000 characters; imported files and decompression
  are also capped at 2,000,000 bytes.
  Offer draft files when links exceed the limit. Validate versions and schedule
  structure before restoring; escape imported poster text as for local edits.
- PNG, HTML, PDF, phone/social images, and ICS use the last successfully rendered
  schedule and are disabled while busy or dirty. Draft backup and sharing can
  preserve pending edits. PDF uses A4 pages and favors section/row boundaries;
  overlong blocks still retain every pixel. Compact images include the calendar,
  color key, events, and credits; full poster/PDF retains detailed notes.

Each section's Reset restores only these fields from `initial` and is undoable:

| Section | Month fields restored |
| --- | --- |
| Poster title & theme | `theme`, `tagline`, `subtitle` |
| Edit your schedule | `days` |
| Key Dates | `key_dates`, `key_date_overrides` |
| Workout Types | `category_styles` |
| Strength & Tread 50 notes | `notes`, `note_style` |
| Monthly notes | `footnotes`, `footnote_styles` |
| Events | `events` |
| Additional info | `additional_info` |
| Credits & team | `credits` |

Resetting Workout Types restores color/visibility choices and preserves the custom
type registry and daily entries. Resetting the schedule restores the month's days
without removing unrelated copy or style overrides.

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
