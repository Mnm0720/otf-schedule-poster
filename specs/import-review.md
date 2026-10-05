# Trustworthy import review

## Acceptance contract

- Category date lists accept inclusive numeric ranges (`9/3-9/5`, `9/3-5`,
  typographic dashes, and `to`/`through`). Both endpoints and every intervening date are included.
  A colon after a category is also accepted. Unknown labels retain their dates,
  raw text, and separate month-local workout types.
- Invalid dates, reversed ranges, out-of-month schedule dates, and recognizable
  workout lines with unsupported wording produce actionable source warnings.
  Ordinary unrelated prose remains ignored. Invalid lines never attach workouts
  to the previous date. Valid neighboring dates remain usable.
- Standalone 3G date lists accept optional parenthesized weekdays after each
  numeric date, including `10/26 (Monday) and 10/31 (Saturday) are 3G style
  templates`. Keep bare-date lists working and report invalid/out-of-month dates
  with either form. The October 2026 thread preserves both benchmarks, every
  workout/equipment date, all six repeat links, its theme, and the Hell Week range.
- Exclusion wording (`except`/`excluding`) and Key Dates missing their workout
  kind produce source review warnings; never claim those lines were read fully.
  Verb-bearing prose such as `Members are meeting on 9/9` is ignored, while a
  recognizable workout prefix with unsupported wording receives a warning.
- Thread dates with no explicit workout retain the useful Standard default.
  Import provenance reports `recognizedDays` and `inferredDays` separately; a
  repeat reference or month-long event does not imply explicit workout recognition.
- The Python browser bridge returns `issues` with `severity`, `message`, `source`
  (`import` or `validation`), and optional `day`/`control` navigation hints.
  Initial validation errors retain an editable schedule and preview; the UI blocks
  all finished export formats until corrected. Existing invalid-edited-schedule
  rejection is retained. Source warnings remain available as original import
  review, distinct from the current schedule validation.
- Initial generation returns `importSummary` with the two day arrays. Regeneration
  only reconstructs `Month` and renders; it returns current validation issues,
  empty `parseNotes`, and `importSummary: null`, allowing the UI to retain original
  import provenance while clearing validation issues that have been corrected.
- `restore(schedule_json)` reconstructs and renders the saved Month without
  reparsing source. Like initial generation, it returns schedule validation errors
  instead of rejecting an already-rendered draft, so an initial invalid repeat
  remains editable after refresh/import. Schema, customization, and event checks
  remain mandatory; `regenerate` and finished exports still reject blocking errors.

## Verification

- October 4, 2026: added the supplied October thread as a fifth fixture and
  checked its complete daily entries, theme, two benchmarks, six repeat links,
  Hell Week event range, and recognized/inferred-day provenance. The red thread
  run failed five cases (51 passed): both real 3G flags were missing, weekday
  captions could lose either/all dates, and invalid captioned dates were ignored.
  Accepting optional captions in the 3G list preserves existing bare-date behavior
  and the date validator. Green: `python -m pytest -q tests/test_thread.py
  tests/test_parse.py tests/test_browser_bridge.py tests/test_unknown_types.py`
  passes 94 tests, including invalid and out-of-month 3G warning coverage.
- September 23, 2026: the first targeted run failed 16 new behavioral cases
  before implementation (54 existing cases passed). This covered the lost middle
  day, colon lists, invalid dates, unsupported category wording, explicit Standard
  provenance, invalid-day attachment to the previous day, and structured bridge
  review data. A second red run reproduced two additional gaps: partially read
  lists/repeat maps and invalid 3G dates.
- Green: `python -m pytest -q tests/test_thread.py tests/test_parse.py
  tests/test_browser_bridge.py tests/test_unknown_types.py` passes 76 tests.
  The four real monthly-thread fixtures still parse cleanly, match their known
  schedules, and validate. `python -m otfposter validate` reports all four saved
  schedules as valid.
- The initial full Python run during parallel UI/build implementation had 137
  passing tests and three in-progress site/UI structure failures; final combined
  verification is recorded by the owning implementation after integration.
- Follow-up edge review first reproduced ten failing cases for textual ranges,
  exclusions, prose, missing Key Date kinds, and reopening invalid initial previews.
  After the bounded parser fixes and `restore` entry point, the same focused command
  passes 86 tests. A restore test disables the parser and verifies identical saved
  preview/schedule/errors; finished export remains blocked. Unsupported schemas,
  malformed colors, and invalid events still fail restore. Stored schedules still
  all validate.
