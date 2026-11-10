# Rendered poster review

## Acceptance criteria

- Review full, phone and social HTML in an isolated Playwright browser. Wait for
  fonts, use the compact export's fitting rule, and save all three actual PNGs.
- Audit visible text for contrast, missing requested fonts, effective text size,
  horizontal overflow and content clipped by the poster. Text labels accompany
  decorative workout artwork. Errors block a clean visual result.
- A self-contained review page and contact-sheet PNG show all exports and their
  findings. Machine-readable `visual-report.json` retains per-layout dimensions,
  metrics and failures. A failed review still leaves inspectable artifacts.
- Fresh source changes are expected to change screenshots. Compare fixed monthly
  fixtures for deterministic rendering; do not reject valid monthly source edits
  solely because they differ from the last month's pixels.

## Verification

- Initial red: the review module did not exist. Unit checks then passed for size,
  contrast, clipping, fonts and report escaping. An actual review of the original
  November images found 47 issues, including low-contrast text and missing Inter.
  Redesigned November clean/reference and six-week August passed in Chrome across
  full/phone/social outputs, with cached calendar artwork visible.
- Independent review reproduced a corrupt WOFF2 registering as a FontFace with
  `status=error` while the first audit passed. The audit now considers only loaded
  faces and explicitly reports failed faces; its regression failed before the fix
  and passes afterward. Fixed-fixture checks remain independent of expected
  changes in new monthly schedule content.
