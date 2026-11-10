# Monthly source checks

## Acceptance contract

- Fetch-only checks run with the Python standard library before installing browser
  dependencies. Restore the previous state and review artifacts across workflow
  runs; skip rendering only when schedule semantics, generator/assets, canonical
  edits and requested export options match and the prior artifacts still exist.
  Pin each verified monthly URL and check the next month from the 25th onward.
- `--source-mode auto` reads complete public RSS when OAuth credentials are absent,
  and approved API access when configured. Explicit `rss`/`api` and saved `--feed-file`
  inputs remain available. RSS uses the shared collector's bounded XML reader,
  exact month/post verification and full-body checks; preserve original feed HTML
  and label the converted text format in provenance. Current/next checks reuse a
  single feed response. Changed parser findings or recognized/inferred dates force
  review even when the resulting schedule semantics did not change.
- Approved Reddit applications may supply client ID/secret for application-only
  tokens, or additionally an authorized refresh token. Obtain fresh access tokens
  at run time, bound retries/rate waits, and keep the bearer-token/paste fallbacks.
  Report authentication, rate limiting and not-yet-published source separately.
  No API approval or credentials are created automatically.
- Compare the previous imported source, new import and edited canonical schedule.
  Preserve manual appearance and schedule changes; apply upstream edits to
  untouched fields. Conflicts retain the edited value and require review. A missing
  import baseline cannot be replaced by a guess based solely on edited JSON.
  Baselines are distinct from edited schedules and are staged with optional PRs.
- Report semantic date/workout/repeat/event changes and source timestamps. Visual
  checks run after changed HTML is generated and can block ready status. Summaries
  and review artifacts remain available for failures. Optional draft PR creation
  is dispatch-only and disabled by default; it uses a separate job with scoped
  write permissions, and never merges, publishes to Reddit or deploys directly.

- `python scripts/check_monthly.py --month YYYY-MM` discovers the exact monthly
  r/orangetheory thread. `--url` selects a specific thread; `--input` reads a
  saved paste without network access. An explicit source/header month must match
  the requested year and month. Ambiguous, removed, empty, wrong-subreddit and
  wrong-month posts fail instead of substituting another month's schedule.
- Requests use bounded JSON reads, a timeout and descriptive user agent.
  Optional `REDDIT_ACCESS_TOKEN` enables bearer authentication against Reddit's
  OAuth host. Access failures explain the saved-paste fallback; tokens are never
  persisted or printed. Redirects cannot send credentials to another host.
- Outputs go beneath `build/monthly/YYYY-MM/<source-hash>/`; `--out` replaces
  the root before the month/hash namespaces. Keep original text, provenance, candidate JSON, a diff against the
  saved month, and machine/human-readable reports. Never change canonical
  schedules, raw sources or accepted posters. Rechecking identical text selects
  the same source directory; changed text selects a different directory.
- Parser notes, unknown workout types and validation warnings produce a nonzero
  `review-required` result with artifacts retained. No recognized schedule dates
  is an error, even if the parser inferred Standard days. Validation errors block
  all rendering. A clean candidate gets full/phone/social HTML and ICS;
  warning-only candidates get those preview artifacts marked for review in the
  reports. Optional `--png` renders the full poster with the installed browser,
  with `--browser-channel chrome` available for local Chrome.
- Retrieval and parse failures retain diagnostic reports and return nonzero.
  Public posting, canonical-file updates and site publication are separate work.
- The read-only `Check monthly post` workflow runs daily at 14:17 UTC after it
  reaches the default branch, or on manual dispatch. It determines the current
  month in America/New_York, accepts an explicit month/post URL, and passes all
  inputs through environment variables. Diagnostics upload even after failure.
  `Build poster` reviews committed raw sources independently of saved JSON, so
  a raw-only month also gets a preview without replacing an edited schedule.

## Verification

- Integrated November 10 check: 350 Python tests and 85 Node tests passed; all six
  saved schedules passed strict validation. The complete Chrome smoke passed real
  Pyodide, icon rendering, cross-month style reuse/default recovery, saved-draft
  recovery, mobile accessibility checks, PNG/PDF/ICS exports and October events.
- A live public RSS fetch returned the verified November post, then a dependency-
  free fetch stage and Chrome resume produced a clean visual review. Rechecking
  the cached feed returned `unchanged` and reused the reviewed artifacts. Clean
  November full/phone/social exports and the 40-month replay report are preserved
  under `out/2026-11-revised/` and `out/historical-corpus.html`. Original accepted
  poster files remain unchanged. Hosted Actions execution is tracked separately.

- November 10, 2026 follow-up: the incremental-update red run initially failed
  because the state helper did not exist; implementation brought the focused suite
  to 39 passes. Frozen RSS, stdlib-only subprocess, authentication, rate-limit,
  staging and path-safety checks then brought it to 52 passes. A further red test
  reproduced a new invalid-date warning being hidden by an unchanged schedule
  fingerprint; including parser findings and provenance day arrays fixes that
  case. Final importer/update suite: 53 passed. The cached complete November feed
  also passed `python -S` fetch-only, resume with Chrome, and actual full/phone/social
  visual checks. No approved API credentials, hosted artifact restoration or draft
  PR write has been exercised; those require the documented account/repository setup.
- Final review reproduced a missing `index.html` when whitespace-only source edits
  reused cached visual exports in a new source-hash directory. The visual artifact
  requirements/copy list now includes the self-contained review page. The focused
  behavioral regression failed before that change; all 54 importer/update cases
  pass afterward.

- November 10, 2026: the first frozen-fixture run failed during collection because
  the importer did not exist. After implementation, all 20 initial behavioral
  cases passed. Follow-up failure-hygiene tests exposed stale successful exports
  after a failed recheck and uncaught screenshot errors. The checker now clears
  only its named disposable outputs before rechecking and records screenshot
  failures in its diagnostic report. All 29 importer cases pass, including bounded
  HTTP reads, malformed/login responses, bearer destination and non-persistence,
  source verification, month-isolated idempotent source hashes, redirect rejection,
  malformed API field recovery, warning/error gates, and offline
  canonical-file preservation. No live Reddit or hosted workflow success is
  inferred from those fixture tests.
- Combined local verification: 238 Python tests and 77 Node tests passed; all six
  saved schedules passed strict validation and all six raw posts returned `ready`
  through the isolated review runner. The static build bundled six examples.
  The real November saved-source command generated HTML, ICS and PNG successfully
  in Chrome. An actual anonymous network fetch returned HTTP 403 and retained its
  diagnostic report. No workflow was pushed, activated or verified on GitHub.
