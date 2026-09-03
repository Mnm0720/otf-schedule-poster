# OTF Schedule Poster

Paste the monthly r/orangetheory thread in, get a printable schedule poster out.

![Example poster](out/otf_2026-09.png)

Schedule data comes from the monthly template threads on
[r/orangetheory](https://www.reddit.com/r/orangetheory/), curated by the
subreddit mods. This is an unofficial fan tool, not affiliated with
Orangetheory Fitness.

---

## Use it in your browser — no install, no account

**→ https://mnm0720.github.io/otf-schedule-poster/**

Paste the thread, hit Generate, download the PNG. Nothing is uploaded: the page
runs the *actual* Python package via [Pyodide](https://pyodide.org/), so the
parsing happens on your machine.

That is not a reimplementation. `scripts/build_site.py` bundles the same `.py`
files and Jinja template that CI uses, and the browser writes them into
Pyodide's filesystem. Verified byte-for-byte: for all four months in
`schedules/raw/`, the HTML the browser produces has the same SHA-256 as the HTML
the command line produces.

The rest of this README is for working on the tool itself.

---

## Quick start

```bash
pip install -e ".[dev]" && python -m playwright install chromium
```

Copy the whole monthly thread — headers, prose, links, all of it — and pipe it in:

```bash
python -m otfposter build - < month.txt
```

That writes:

| File | What it is |
| --- | --- |
| `schedules/2026-09.json` | the structured schedule — **the source of truth** |
| `schedules/raw/2026-09.txt` | the paste it came from |
| `out/otf_2026-09.html` | a standalone HTML poster (fonts and icons inlined) |
| `out/otf_2026-09.png` | the 2400px-wide poster image |

## Generating a poster from GitHub Actions

**Actions → Build poster → Run workflow**, paste the thread into the
`schedule_text` box, run. The poster is attached to the run as an artifact.

Note this route needs **write access** to the repo — GitHub only shows "Run
workflow" to collaborators. For everyone else, the Pages site above is the way
in.

Workflows never push to the repo: posters exist as run artifacts, and the Pages
site is built and deployed straight from `main` without committing build output.

## What it reads

The monthly threads describe a month **by category, not day by day**, so the
schedule is assembled by inverting those lists. Four things are read; the rest
of the post is ignored.

**1. The month and theme**, from the title and the prose:

```
Welcome to the September 2026 Monthly Thread!
... for September it is Rhythm & Routine.
```

**2. Key Dates** — signatures, benchmarks, specialties, and events:

```
* September 8 (Tuesday): 1000 Meter Row; benchmark. See our wiki for details.
* September 18 (Friday): OTF Foundations; signature. ...
* August 1 (Saturday) - August 31 (Monday): Marathon Month; event. ...
* August 27 (Thursday): PSL; specialty. This is a 3G only template, ...
```

Single days become pills on the calendar. Date ranges become an event ribbon.
"3G only" marks the day with a `3G` badge.

**3. The category lists**:

```
* Run/Rows on 9/3, 9/5, 9/8 (benchmark), 9/13, 9/19, 9/21, 9/29.
* Lift More templates on 9/2, 9/7, 9/10, 9/12, ...
* Minibands on 9/12, 9/28.
```

The parentheticals (`(benchmark)`, `(signature)`) are cross-references to Key
Dates, not extra templates, so they're read for corroboration and otherwise
ignored. **Any day no category names is a Standard template.**

**4. The repeat map**:

```
* Repeat templates are as follows: 9/16 = 9/1, 9/17 = 9/2, 9/19 = 9/3, ...
* 10/24 and 10/31 are 3G style templates, meaning that even if your class ...
```

Nothing is silently dropped: an unrecognised category label is reported, and
`--strict` turns any such report into a non-zero exit.

### The day-list format

For hand-written months, a plain day list is also accepted and detected
automatically:

```
9/1 - Standard
9/2 - Lift More + Elevation Gain
9/8 - Benchmark: 1000 Meter Row + Run/Row
9/16 - Standard (repeat of 9/1)
9/15 - Lift More (not a repeat)
```

Separators between templates are `+`, `,`, `&`, `;`, `and`. Note `/` is *not*
one — it lives inside `Run/Row`.

## Editing after parsing

The parse is a starting point. If a month has a quirk, edit
`schedules/YYYY-MM.json` and re-render:

```bash
python -m otfposter render --month 2026-09
```

The JSON also carries the poster's copy — `theme`, `tagline`, `notes`,
`footnotes`, `strength_split`, `events`. Leave them out and sensible values are
derived from the schedule.

## Commands

| Command | What it does |
| --- | --- |
| `build <file>` | parse a paste **and** render the poster (the usual one) |
| `parse <file>` | paste → `schedules/YYYY-MM.json` only |
| `render [json…]` | schedule JSON → HTML + PNG (all months if none given) |
| `validate [json…]` | check schedules without rendering |
| `fetch-assets` | refresh the cached icons and fonts under `assets/` |

Plus `python scripts/build_site.py`, which assembles `site/` for GitHub Pages.

Useful flags: `--strict`, `--offline`, `--html-only` (skip the browser),
`--scale N` (pixel density, default 2), `--theme`, `--tagline`, `--out DIR`.

## What gets checked

`validate` catches the ways a paste goes wrong:

- every day of the month is present, and none fall outside it
- every `repeat of N` points at a real, *earlier* day
- nothing repeats a day that is itself a repeat
- **a repeat day carries its source day's templates** — the strong one; see below
- unrecognised template names are surfaced (they render grey rather than vanish)

Errors fail the build; warnings only fail under `--strict`.

That fourth rule is not a convention someone hoped for — it holds across all 45
repeat pairs in the four months in `schedules/raw/`. So when `8/20 = 8/8` but
8/20 lists Lift More and 8/8 lists Lift More + Minibands, a category line got
lost in the paste, and you hear about it.

Named workouts are excluded from that comparison: a signature lands *on top of*
whatever template the day was already running, so 8/7 (Catch Me If You Can +
Run/Row) still counts as a Run/Row day.

## Adding a new template type

One entry in [`otfposter/categories.py`](otfposter/categories.py) — colour,
blurb, and the spellings to accept:

```python
Category(
    "sled", "Sled Push", "#8D6E63",
    "Weighted sled work for lower-body power.",
    aliases=("sled push", "sled", "weighted sled"),
    order=85,
),
```

Pill colour, highlights row, and the legend all follow. Nothing else changes.
`order` also sets the order pills stack within a day.

## How it fits together

```
monthly thread ──▶ thread.py ──┐
                               ├──▶ Month (schedules/*.json) ──▶ derive.py ──▶ poster.html.j2 ──▶ PNG
day list      ──▶ parse.py  ───┘         │                          │
                                    validate.py          highlights, repeat map,
                                                      key dates, legend, notes
```

The day list is the only thing anyone edits. Everything the poster says *about*
the month is computed in `derive.py`.

## Design notes

- **The rendered HTML is standalone.** Fonts (woff2) and icons (SVG) are cached
  under `assets/` and inlined as data URIs, so a poster opens correctly offline
  and CI needs no network. `--offline` makes a missing asset an error rather
  than a silent fetch.
- **Fonts are asserted, not assumed.** `document.fonts.status` reads `'loaded'`
  even when zero faces registered, so the renderer checks `document.fonts.size`
  too — otherwise a CSS mistake silently ships a poster in system fallbacks.
- **"Not a repeat" is suppressed when the cycle is loose.** Oct 2025 repeats
  only 7 of its last 20 days; labelling the other 13 "not a repeat" would mark
  most of the calendar and say nothing. Below 60% coverage the label is dropped
  and the notes say how many days repeat instead.
- **The browser runs the real package, not a copy of it.** A JavaScript
  reimplementation of the parser would be far lighter than shipping Pyodide,
  but the parser is the part of this project with all the subtle behaviour and
  all the tests, and a second copy would drift silently. `tests/test_site.py`
  fails the build if a new module isn't bundled, or if Playwright ever moves to
  module scope in `render.py` (the browser has no browser to drive).
- **Rules the poster asserts are not always checkable.** The threads say
  templates never repeat inside a Mon–Sun week, and an early version validated
  it — but it flagged four false positives on real months, because two days can
  both be "Low Bench" without being the same workout. The claim stayed as poster
  copy; the check was dropped.

## Licence

MIT — see [LICENSE](LICENSE). Anton and Barlow are used under the SIL Open Font
License; Material Symbols under Apache 2.0.
