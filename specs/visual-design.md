# Readable calendar-first poster design

## Acceptance contract

- New posters use a clean calendar-first layout with a restrained month/title
  header, larger dates and workout labels, and readable repeat annotations. Keep
  every calendar entry, event, 3G flag, day note, key date, Strength/Tread split,
  monthly note, additional information, and credit available in the full poster.
- `appearance` controls layout (`clean` or `reference`), density (`comfortable`
  or `compact`), calendar icons, marked-date ribbon, highlights, repeat map, and
  detailed workout guide. Clean defaults hide the duplicate ribbon, highlights,
  and guide; reference defaults restore those panels. Explicit visibility choices
  take precedence. Changing appearance never changes schedule data or custom copy.
- Calendar workout labels retain their complete text and use cached Material
  Symbols SVG icons for workout/equipment categories. Icons are decorative,
  hidden from assistive technology, and optional. One shared category-to-icon
  registry provides distinct equipment/format cues and a safe custom-type fallback.
  Benchmark icons depict timing or achievement rather than a coffee cup.
- Built-in and custom workout pill colors use the same linear sRGB contrast
  calculation, choosing black or white text with at least 4.5:1 contrast. Other
  normal-size poster text also meets 4.5:1 against its background. Preserve the
  user's chosen colors; do not alter shared category settings.
- Full, phone, and social layouts use the bundled Barlow family and consistent
  icon/3G conventions. Compact outputs keep their 1080px width and 1920/1350px
  heights, escape copy, wrap labels, and retain all dates and credits. Verify real
  layout/font loading/overflow separately from markup and contrast unit tests.
- Reuse the project's existing Material Symbols SVG system and cached fonts.
  [Google distributes these icons under Apache 2.0](https://developers.google.com/fonts/docs/material_symbols);
  no image generation or new
  runtime asset service is needed. Existing accepted output files are preserved.

## Verification

- November 10, 2026 red run: 17 failures and 10 passes reproduced insufficient
  contrast for six built-in category colors, inconsistent custom-color decisions,
  the missing compact font, absent semantic calendar icons, the coffee benchmark
  icon, and missing clean/reference visibility behavior.
- Green: the visual, November output, event calendar, customization, derivation,
  footer, export, and browser bridge suites passed all 128 cases after implementation. The guide
  column regression explicitly selects Reference so it still tests visible guide
  layout instead of passing because Clean hides that panel.
- Actual Chrome render reports for November Clean and Reference show zero visual
  issues across full, phone, and social outputs. Inspected both contact sheets;
  text labels and 3G badges accompany the icons. Barlow fonts loaded, every
  workout pill had cached SVG artwork, and no text was clipped or overflowed.
- An independent August 2026 check covered a six-week calendar, a month-long event,
  several named workouts, three-category days, and repeat annotations. All three
  actual outputs passed the same contrast, font, overflow, clipping, and missing
  artwork checks. Minimum rendered text sizes were 13px full, 14.93px phone, and
  11.74px social; fixed compact output dimensions remained 1080×1920/1350.
- These are desktop Chrome rendering checks, not physical mobile device testing.
  The accepted output files were retained; review captures are separate artifacts.
- Independent Chrome UI verification generated November, selected Reference /
  Compact / icons off, changed a workout color and credits, saved a named default
  style, regenerated, and downloaded the actual 2400×4400 PNG and style JSON.
  The inspected PNG preserved the full schedule and selected style. A fresh
  September poster inherited appearance/colors/credits while retaining September
  dates, workouts, and theme. Changing that draft back to Clean / Comfortable /
  icons on survived refresh independently of the saved default. Expanded
  Appearance controls had no horizontal overflow or tested axe violations at
  320px and 390px. All seven workflow checks passed with no browser errors.
