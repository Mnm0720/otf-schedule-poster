# Appearance presets

## Acceptance criteria

- Month JSON has an additive `appearance` object. At the user's request, missing
  settings restore the original reference design, with calendar icons off.
  Only supported layout/density values and boolean section/icon settings render.
- Appearance controls participate in dirty state, regeneration, undo, backups,
  sharing and section reset. Applying a layout sets its documented section choices.
- Save named local style presets containing appearance, built-in category colors
  and visibility, note/icon styles and credits. Never carry dates, workouts, theme,
  events, repeat links or date-linked Key Dates into another month.
- Saving, applying, importing and exporting a preset are explicit actions. An
  optional default applies to newly generated posters only, never restored drafts.
  Corrupt/newer preset stores are retained and reported; a storage failure does not
  erase the draft or claim a save succeeded. Export remains available for recovery.
- Presets are separate from saved poster drafts, require no account, and work on
  GitHub Pages. Applying a preset preserves all schedule and source metadata.

## Verification

- Initial red: nine model cases failed because appearance was absent/unvalidated;
  the Node preset suite could not import its module. Green: nine model cases and
  three pure preset/storage cases passed after implementation.
- A second red exposed the missing browser generation parameter and two missing
  appearance/preset form behaviors. Green: all ten model/bridge cases and the
  editor/application regressions pass, including cross-month field isolation,
  corrupt-store preservation and failed saves. Real-browser verification follows
  after integration with the redesigned templates and historical parser fixes.
- Independent real Chrome checks passed saving a named default, downloading its
  date-free JSON and actual PNG, applying it to a new month, retaining changed
  draft choices on refresh, and opening expanded controls at 320/390px with no
  page overflow or tested axe violations. Follow-up red/green regressions fixed
  restart failing to collapse Appearance and a corrupt style-store message
  masking a generation failure.
- A rejected default with an unknown icon/type previously prevented generation
  before recovery controls appeared. Two Python cases and a Node application
  case reproduced this. Style validation now identifies preset-only failures;
  generation retries once with the built-in style, keeps the saved preset and
  exposes recovery controls. Ordinary parser failures retain their own messages.
  The built-site smoke exercises this recovery too.
