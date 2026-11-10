# Historical monthly-post corpus

## Acceptance contract

- Collect public r/orangetheory monthly posts from a bounded Atom/RSS feed, with
  an offline feed-file option. Preserve full post HTML and readable heading/list
  structure, exact title/month/year, canonical URL, author, publication/update
  timestamps, retrieval method and content hash. Accept historical Monthly
  Highlights titles as well as Monthly Thread/Post. Never invent missing dates.
- Reject unsupported hosts, wrong-subreddit links, summaries/snippets, malformed
  or oversized XML, DTD/entity declarations, and ambiguous duplicate months.
  Honor access/rate-limit failures and retain a saved-feed workflow.
- Store historical fixtures outside shipped example sources and canonical
  schedules. Repeated identical collection is idempotent; a different post or
  changed body cannot silently replace an existing fixture.
- Replay every fixture through the actual parser and validator. Record imported
  dates, inferred days, unknown types, warnings, exceptions and validation issues
  in a machine-readable report with year/month coverage. A saved source is not
  proof of a clean or semantically complete import.
- Write an HTML report beside each JSON report, with coverage, a month index,
  original-source links and every diagnostic. Escape retrieved text and validate
  source-link destinations before creating clickable links.
- Validate HTML conversion with old heading/list/line-break formats and exercise
  network-independent feed parsing, source verification, hashing and replay.
- An exact source URL filters by Reddit post ID before checking duplicate-month
  ambiguity. `REDDIT_USER_AGENT` can identify an approved reader. Empty discovery,
  corrupt fixture JSON, changed text/HTML hashes and mismatched source months are
  explicit failures; one corrupt fixture must not stop the remaining replay.

## Collected evidence

- November 10, 2026: the public Reddit `search.rss` endpoint returned HTTP 200
  and a complete 684,784-byte Atom feed with 80 entries. The saved feed is at
  `build/historical-corpus/monthly-search.atom`. The corpus contains 40 distinct
  full posts: every month from January 2024 through November 2026, plus March and
  October 2020, February 2021, May 2022 and September 2023. Fixtures retain full
  HTML, converted text, source URLs, authors, timestamps and both content hashes.
  They are intentionally outside `schedules/raw/`, so historical posts are not
  shipped as editor examples or accepted schedules.
- The generic subreddit RSS endpoint and a separate 2019 search returned HTTP
  429. Those requests were not retried. Web browsing could not consume Atom's
  content type, while direct public RSS retrieval worked. No OAuth credentials
  or paid service was needed for the successful collection.

## Verification

- Initial collection tests failed at import because the collector did not exist.
  The collector now passes 19 cases covering Atom and RSS full content, HTML
  structure, bounds/DTD rejection, URL validation, ambiguity, explicit IDs,
  configured user agents, idempotence, wrong-month real sources, corrupt/tampered
  fixtures and complete unique corpus provenance. The HTML report's initial
  injection case failed because no HTML renderer existed; it now confirms that
  source HTML is escaped and script URLs cannot become links.
- The untouched initial replay at `build/historical-corpus/before.json` recorded
  13 clean months, 25 requiring review and 2 errors. After parser fixes,
  `build/historical-corpus/after.json` records 21 clean months, 18 requiring review
  and one source error. Every collected month now parses with its correct month.
  Review results retain ambiguous or untyped historical notes, month-clipped
  events, a custom Medicine Ball type and source repeat mismatches. The May 2026
  post explicitly says `5/12 = 5/29`; this invalid future repeat remains an error
  and is never silently swapped.
- Remaining causes overlap across months: 10 sources need review of clipped
  cross-month event scope; 7 have untyped or uncertain Key Dates; 2 contain
  ambiguous/conditional dates; 1 has a preserved custom Medicine Ball type.
  Source validation warnings occur in 5 months (including the one error month),
  covering repeat-category mismatches, a duplicate repeat source and that custom
  equipment type. These are not 18 remaining parser crashes.
- The replay command returns nonzero when any source needs review or has an error.
  That is a diagnostic result, separate from regression-test success. Collection
  and parser tests do not establish that every original source is correct or
  that every studio followed its schedule.
