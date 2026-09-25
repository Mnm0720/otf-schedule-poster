# Moderator usability and GitHub Pages review

Reviewed September 23, 2026. The findings below record the original assessment.
The accepted application changes have since been implemented locally, except the
Reddit-specific download default, which the user excluded. The existing PNG
recommendation and format choices are unchanged.

Implementation includes the mobile editing workflow, import diagnostics, recovery
and save feedback, actionable download controls, worker-based Python execution,
on-demand export libraries, reproducible static assets, and built-site CI checks.
See the [current verification record](../specs/browser-editor.md#september-23-2026-moderator-and-mobile-update)
for passing tests, actual browser checks, and remaining device/user-study limits.

## Recommendation

Keep the static GitHub Pages architecture and the shared Python parser. Prioritize trustworthy schedule imports, recoverable editing, visible save feedback, and clear next actions. The intended users are occasional, potentially nontechnical Reddit moderators. Design for comfortable reading and low reliance on memory; age alone is not a measure of technical skill.

The existing application already provides local drafts, backup/import, snapshot sharing, collapsed optional settings, stale-preview export protection, and responsive forms. Build on these features.

## Confirmed problems to address first

### 1. A date range can silently produce an incorrect schedule

Reproduction:

```text
Welcome to the September 2026 Monthly Thread!
Key Dates for The Month
* Run/Rows on 9/3-9/5.
* Repeat templates are as follows: 9/16 = 9/1.
```

The Python bridge assigns Run/Row to September 3 and 5, but assigns Standard to September 4. It returns no errors or notes. Substituting `Run/Rows on 9/31.` or `Run/Rows: 9/3, 9/4, 9/5.` also silently loses the workouts in this input.

Cause: [thread.py](../otfposter/thread.py), lines 72-75 and 224-247, extracts isolated dates, skips unmatched lines and out-of-month dates, then fills unnamed days with Standard.

**Change:** support inclusive ranges, report invalid dates, and identify recognizable schedule lines that were not understood. Preserve the useful Standard default, but identify which days were inferred. Show a concise import summary with links to affected dates. Do not imply that every day was explicitly recognized just because the calendar has 30 entries.

**Acceptance:** the range includes September 3, 4 and 5; September 31 gets an actionable warning; a recognizable but unsupported category line cannot produce “Rendered cleanly.” Unrelated prose remains harmless.

### 2. Initial validation errors still allow a finished download

The real browser reproduced this with:

```text
September 2026
9/1 - Standard (repeat of 9/2)
9/2 - Standard
```

The report states that September 1 repeats a future date, but Download remains enabled. PNG, HTML and PDF export from the preview without the validation used by other exports.

Cause: [bridge.py](../web/bridge.py), lines 47-53, returns errors on initial generation; [editor-state.js](../web/editor-state.js), line 89, ignores them when computing download eligibility; [app.js](../web/app.js), lines 409-431, has different validation paths by format.

**Change:** use one export eligibility rule for all finished formats. Keep the editable draft and backup available. Put a “Fix September 1” action beside the error, selecting that date and focusing its repeat control.

**Acceptance:** every finished format stays unavailable until blocking errors are corrected and the preview is updated. Warnings are distinguished from blocking errors.

### 3. Undo can discard the latest unsent-to-preview edits

State/controller probes verified: initial version A → update to B → type pending edit C → Undo → Redo returns B. C is absent from the resulting history snapshot.

This follows the current regeneration-only history specification; it is a product decision to revise, not an accidental violation of that specification. See [editor-state.js](../web/editor-state.js), lines 48-63, [app.js](../web/app.js), lines 338-343, and [saved-workspaces.md](../specs/saved-workspaces.md).

**Change:** make pending edits recoverable before navigating history. If history remains based on rendered versions, label controls “Previous version” and “Next version.” Explicitly distinguish reverting a version from discarding current edits.

**Acceptance:** C remains recoverable after history navigation and refresh. A failed render must not irreversibly consume history.

### 4. Save success and failure feedback is normally hidden

`saveLocal()` and `savePaste()` write success and failure messages into `#saveStatus`, inside the usually closed Saved Drafts dialog. The visible draft indicator says “loaded” or “Poster generated from text,” which does not communicate current save health. A browser check confirmed “Saved on this device.” existed but had no visible box.

See [app.js](../web/app.js), lines 91-99, 288-297 and 345-348, and [index.html](../web/index.html), the Saved Drafts dialog.

**Change:** keep a persistent save status beside the active draft name: “Saved in this browser,” “Saving…,” or “Not saved: download a backup.” Separately display whether the preview includes the latest edits. Do not claim autosave succeeded when storage is unavailable or full.

**Acceptance:** storage-denied, quota and multi-tab conflict messages are visible without opening a dialog; the backup action remains available.

### 5. Failed draft loading can disable recovery controls

A controller probe forced a saved-draft regeneration failure. The current editor survived, but the dialog closed and Saved Drafts became disabled. `openDocument()` returns without an explicit success result, while its callers unconditionally mark loading complete. See [app.js](../web/app.js), lines 313-325, 357-363 and 373-378.

**Change:** return a success result; close the dialog only on success. Also reconsider the specified one-load-per-session restriction. Keeping Saved Drafts available with save-before-switch protection makes comparisons and handoffs easier.

**Acceptance:** failed load/import preserves the active poster, keeps the picker usable, and permits retry or another selection.

### 6. Important controls are smaller than the project's stated target

The real browser measured Undo, Redo and Regenerate at **34px high with 13px text**, and preview status at **12px**, including at 390px viewport width. [style.css](../web/style.css), lines 165-166, overrides the otherwise larger controls. [browser-editor.md](../specs/browser-editor.md) calls for 44px control height, 16px main text and 14px secondary text.

**Change:** restore those project targets for the sticky action bar; verify that wrapping and sticky bars do not cover keyboard focus. This is a project readability regression, not by itself proof of a WCAG AA failure: WCAG 2.2 AA target-size minimum is 24px with exceptions.

The new how-to block also has no corresponding `.how-to*` styling, so its ordered list uses default outside markers and lacks the intended card spacing. Style it consistently and check narrow widths and zoom.

### 7. Suggested download actions are not actionable

[app.js](../web/app.js), lines 448-450, writes “Open file · Download again · Share editable copy” as plain text into a paragraph. Those words are not controls, although an actual file link exists elsewhere.

**Change:** use real links/buttons in that confirmation, or show only the filename and confirmation. Verify actions by clicking them in tests.

## Proposed moderator workflow

Use three clear stages: **Paste thread → Review and edit → Download for Reddit**. Keep the existing quick path for clean input; do not force a lengthy wizard.

- Show the detected month prominently before download. Use a friendly month/year control for corrections, and keep the original text accessible for reference without requiring a reset.
- Make the main action “Update preview,” with nearby text such as “Changes saved in this browser; preview needs updating.” Successful update should offer a direct route to Download.
- Put schedule editing before backup/sharing and visual customization. Keep theme, colors, icons and credits optional and collapsed.
- Retain the single-day form. Add Previous/Next date buttons and a compact review list showing workouts, edited dates, inferred defaults and issues. A desktop split view can reduce scrolling; phones should retain a simple stacked layout.
- Explain that “Repeat of” records a relationship and does not copy or synchronize workouts. If needed, provide a separate explicit “Copy workouts from this day” action.
- **Excluded by user request:** make “Download image for Reddit” the default and move the other formats under additional formats. The existing download choices are preserved.
- Keep “Share editable copy” and local-save explanations. Copies are not live collaboration, and browser drafts do not automatically follow users to another computer.
- Replace parser-focused Help with a short task guide: where to copy the thread, check a date, correct an issue, update the preview, download, recover a draft and hand off a copy. Keep syntax details in an advanced section.

Validate the wording with a few actual moderators completing those tasks without coaching. Record wrong turns, uncertainty, recovery success and whether the final poster matches their intended changes. These are design proposals, not observed user-study results.

## GitHub Pages improvements

The site already uses relative local asset paths, a static build, `.nojekyll`, and an Actions deployment. The application bundle is **464,800 bytes, about 454 KiB**. Embedded font CSS accounts for approximately 72% of that bundle and supports standalone exports. This size excludes the external Python runtime and libraries.

1. **Recoverable startup:** replace “Loading Python runtime (one-off, ~10s)” with user-facing progress. Add Retry, bounded network failures and HTTP status checks while preserving pasted text. Current startup catches failures but provides no retry action ([app.js](../web/app.js), lines 112-152). Do not promise a load time without representative cold/warm measurements.
2. **Remove unnecessary startup work:** use the pinned Pyodide runtime's built-in `loadPackage("jinja2")`, which includes its MarkupSafe dependency, instead of first loading micropip and installing packages. Fetch the local bundle concurrently with runtime initialization. Verify compatibility in the real browser.
3. **Load export libraries when needed:** defer `pdf-lib` until PDF export, and load image export support on demand or after the editor is ready. Both are currently blocking scripts before `app.js` ([index.html](../web/index.html), lines 256-263). The PDF script alone is about 525 KB decoded; this is not its compressed network transfer size.
4. **Measure UI responsiveness:** Python bridge calls currently execute on the main thread. If slow-device measurements justify it, move Python parsing/rendering into a standard Web Worker. Keep the existing Python implementation; preview DOM and image export remain on the main thread. Workers do not require a backend.
5. **Reduce image-export memory:** use the existing `html-to-image.toBlob()` API instead of PNG data URL → fetch → Blob conversions ([app.js](../web/app.js), lines 419-421 and 442-444), with null-result handling.
6. **Make releases reproducible:** fingerprint assets/bundle references, add bundle compatibility metadata, require cached assets during release builds, and include dependency manifests in Pages trigger paths. The build currently permits font fetching; deployment dependencies are not fully locked.
7. **Test the built site before publishing:** use the existing Playwright dependency to smoke-test under `/otf-schedule-poster/`, matching the project-site base path. Exercise actual Pyodide startup, edit/update, refresh/restore and downloaded PNG/PDF output. Add axe-core accessibility checks plus manual keyboard/zoom review. Current Node tests mock the runtime and iframe; the PDF test exercises an unused pagination helper rather than the actual single-page export.

Existing solutions checked: the current Python/Pyodide architecture, standard Web Workers, the already used html-to-image API, Playwright, axe-core and Lighthouse. They cover the proposed work without a backend, new UI framework, or paid service. Add an offline service worker only if offline use becomes a requirement; cache lifecycle complexity is not needed for the first improvement pass.

## Implementation order and acceptance

1. **Correctness and recovery:** parser diagnostics, consistent export validation, recoverable pending edits, visible save status, failed-load recovery. Update specs and add failing behavioral regressions before implementation.
2. **Moderator workflow:** clear stages, “Update preview,” date review/navigation, straightforward download/handoff, readable controls. Test keyboard-only operation, 200% zoom, 320/390/768px and desktop layouts, including errors and long labels.
3. **Pages delivery:** package-loading simplification, lazy export dependencies, profiling, asset revisions and real-browser CI. Measure cold/warm startup and generation on representative devices before and after changes.

## Verification performed for this review

- 118 Python tests passed.
- 41 Node tests passed.
- All four stored schedules validated.
- Static site build succeeded: 31 bundled files, four examples, about 454 KiB bundle.
- Actual local browser: loaded Pyodide, generated September, edited a workout title, updated the preview and verified the new title appeared.
- Actual local browser: no page-level horizontal overflow at 320px or 390px for the tested editor; confirmed small action-bar controls and hidden save feedback.
- Actual local browser: invalid initial repeat reported an error while Download remained enabled.
- Isolated Python/Node probes: silent category/range parsing, pending-edit loss and failed-draft-load behavior described above.

This review did not measure production cold/warm transfer performance, test every browser/export format, conduct a full accessibility audit, or run moderator usability sessions. No application changes were deployed.

## References

- [W3C target size guidance](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html)
- [W3C error suggestions](https://www.w3.org/WAI/WCAG22/Understanding/error-suggestion.html)
- [Pyodide 0.26.2 package loading](https://pyodide.org/en/0.26.2/usage/loading-packages.html)
- [Packages included in Pyodide 0.26.2](https://pyodide.org/en/0.26.2/usage/packages-in-pyodide.html)
- [Pyodide Web Workers](https://pyodide.org/en/0.26.2/usage/webworker.html)
- [html-to-image APIs](https://github.com/bubkoo/html-to-image)
- [GitHub Pages custom workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [axe-core](https://github.com/dequelabs/axe-core)
- [Lighthouse](https://developer.chrome.com/docs/lighthouse/overview)
