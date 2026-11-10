# Trustworthy import review

## Acceptance contract

- Historical monthly formats use the thread reader: Monthly Highlights,
  Calendar Intel and plain monthly headers with a Key Dates section. Strip
  Markdown heading markers before section detection and stop old Key Dates
  sections before unrelated community prose. Never attach that prose to the
  last dated workout.
- Key Dates accept named/abbreviated months, ordinals, numeric month/day dates,
  inclusive `through`/`to` ranges and explicit Benchmark/Signature suffixes from
  older posts. Clearly named multi-day events remain events even without a
  semicolon kind; ranges crossing months are clipped to the displayed month and
  carry an explicit source-scope review warning. Untyped or uncertain single-day
  information is preserved as a day note with a review warning. Ambiguous
  `and/or` and alternative studio dates warn instead of guessing.
- Category lists can omit `on`, and `days`/`templates` suffixes do not create new
  workout types. Unsupported verbs and EDIT/NOTE prose stay out of the workout
  registry. Prefix 3G lists, `are all 3G`, and explicit 3G-format wording retain
  their dates. Conditional repeat prose stays a note requiring review, rather
  than a fixed repeat link. Explicit no-60-minute-repeat guidance is valid even
  when independent Tread/Strength 50 templates repeat.
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
- Key Date descriptions saying `3G style template` or `3G-style template` mark
  that date as 3G, alongside the existing `3G only` wording. Explicit non-repeat
  date lists such as November's `11/27 and 11/30 are NOT designated as repeat
  templates` remain visible as day notes and do not produce a false malformed
  repeat warning. Invalid dates and contradictory repeat claims still warn.
  Preserve the November 2026 `.25 Mile` benchmark, all three benchmarks, Member
  Choice, Strength in Numbers, category dates, ten repeats, and header theme.
- Exclusion wording (`except`/`excluding`) and Key Dates missing their workout
  kind produce source review warnings; never claim those lines were read fully.
  Key Date ranges may omit a repeated month (`October 24-31`). Other recognizable
  date-led Key Date lines with unsupported syntax produce a review warning instead
  of silently disappearing.
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

- November 10, 2026: 23 of the first 24 historical source regressions failed
  before fixes; the remaining case correctly flagged May 2026's invalid future
  repeat. Additional red cases exposed an EDIT note becoming a workout type,
  a fake month 16 from `September 16/17`, an ignored ordinal `and/or` date and a
  silently dropped conditional repeat. All 27 historical cases now pass.
  The 40-month RSS corpus improves from 13 clean / 25 review / 2 errors to
  21 clean / 18 review / 1 upstream source error. Reviews remain explicit for
  uncertain or untyped key dates and clipped event scope, rather than inventing
  certainty or hiding source mistakes. See [historical corpus](historical-corpus.md).
- November 10, 2026: five output/regeneration cases failed when replayed against
  the pre-change parser in an isolated subprocess, all exposing the lost November
  23 3G flag. They now pass across full/phone/social posters, ICS and regeneration
  without reparsing. The real Chrome/Pyodide smoke passed for the bundled November
  example, all five key dates, `.25 Mile`, November 23's 3G flag, November 27/30's
  explicit non-repeat notes, subtitle editing and downloaded ICS. The complete
  smoke also passed October events, recovery, responsive editor layouts,
  accessibility checks, PNG and PDF. Inspected full/social November images had no
  detected calendar text overflow. These were local desktop-browser checks.
- November 10, 2026: the real November fixture first reproduced six failures
  (59 existing/passing cases): the signature's `3G style` wording lost its flag,
  and explicit non-repeat dates produced a false incomplete-repeat warning.
  The fix preserves November 23's 3G flag, November 27/30's explicit notes, all
  three benchmark titles (including `.25 Mile`), the header theme, every daily
  category, and all ten repeat links. Invalid/contradictory non-repeat dates warn.
- Four further red cases reproduced silently dropped shorthand Key Date ranges
  and unsupported date-led syntax. Inclusive shorthand ranges now import; other
  malformed recognizable Key Dates warn. Existing standalone 3G lists remain
  warning-free. Green focused verification: `python -m pytest -q
  tests/test_thread.py tests/test_parse.py tests/test_unknown_types.py
  tests/test_validation.py tests/test_browser_bridge.py tests/test_event_calendar.py`
  passes 139 tests.
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
