# GitHub Pages runtime and release contract

## Acceptance criteria

- Keep the static, account-free GitHub Pages architecture and the actual Python
  parser/renderer. Parsing and rendering execute in a standard Web Worker so
  loading and generating do not block the editor's main thread on phones.
- Initialize the pinned Pyodide 0.26.2 runtime while fetching the local bundle.
  Load its included `jinja2` package directly, without installing packages through
  micropip. Display meaningful startup stages without promising a fixed duration.
- Check bundle HTTP responses, metadata, and paths. Bound network/startup waits;
  failures leave pasted text and saved drafts untouched. Retrying starts a fresh
  worker. Bridge exceptions remain actionable and do not destroy a healthy worker.
  A worker crash or render timeout exposes Retry without discarding the current
  in-memory draft, including when browser storage is unavailable.
- Load pinned image/PDF export libraries only when requested. Share concurrent
  requests and permit retry after failure. The user's existing export selection
  and PNG recommendation remain unchanged.
- Build with cached fonts/icons only; missing assets fail explicitly. Fingerprint
  local JavaScript, CSS, worker, and Python bundle URLs, and version the bridge
  protocol. All references work under the project-site subdirectory.
- Pin release Python dependencies, include dependency/test manifests in Pages
  trigger paths, and run actual built-site browser smoke checks before publishing.
  Browser checks cover real Pyodide, edit/update, refresh/restore, mobile overflow,
  PNG and single-page PDF downloads, and axe checks of editor controls (the poster
  artwork iframe is excluded). Report cold/warm timings as CI measurements, not
  representative phone or production-network benchmarks.
- An optional `--audit` local build provides an accessibility-check button for
  manual browser QA. Normal builds omit that page and its development-only tools.
- No new backend, service worker, paid service, automatic publishing, or changes
  to the default export workflow.

## Verification record

Implementation uses spec-first regression tests. Runtime unit tests isolate the
worker transport and package loader; these do not claim real-browser evidence.
The built-site Playwright smoke runs in CI against `/otf-schedule-poster/`.
It also covers October 2026 event labels, captioned 3G dates, and event edits in
real Pyodide. Local runs can pass `--browser-channel chrome` or `msedge` when an
installed browser is available instead of Playwright's downloaded Chromium.

### September 23, 2026 implementation

- Red: the new runtime test failed because `runtime.js` was absent; three build
  regressions failed before fingerprint/metadata/offline-asset support existed.
- Green: all six runtime transport/loader regressions and all eight static build
  tests pass. The build verifies deterministic asset names and complete local
  font payloads; Python syntax checks cover the build and CI smoke script.
- Release dependencies are pinned in `requirements-pages.lock`. CI and Pages run
  the built-site smoke before publication. Its actual Chromium execution is a
  separate CI check, not claimed by these unit/syntax results.
- An additional red/green regression covers render-time worker loss: errors mark
  the runtime unavailable, expose retry, and leave ordinary validation failures
  on a healthy worker. The optional local axe page is explicitly excluded from
  normal builds and has a build regression protecting that boundary.
