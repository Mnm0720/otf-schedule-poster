# OTF Schedule Poster

Turn the monthly Orangetheory template post into a printable PNG schedule poster.

Paste the month's template list in, get this out:

![Example poster](out/otf_2026-09.png)

The schedule data comes from the monthly template posts on
[r/orangetheory](https://www.reddit.com/r/orangetheory/) (typically posted by
[u/Rizzah319](https://www.reddit.com/user/Rizzah319/)). This repo is an
unofficial fan tool and is not affiliated with Orangetheory Fitness.

---

## Quick start

```bash
pip install -e ".[dev]" && python -m playwright install chromium
```

Then paste a month in:

```bash
python -m otfposter build schedules/raw/2026-09.txt --theme "Rhythm & Routine"
```

That writes three things:

| File | What it is |
| --- | --- |
| `schedules/2026-09.json` | the structured schedule — **the source of truth** |
| `out/otf_2026-09.html` | a standalone HTML poster (fonts and icons inlined) |
| `out/otf_2026-09.png` | the 2400px-wide poster image |

You can also pipe it in:

```bash
pbpaste | python -m otfposter build - --month 2026-10
```

## Generating a poster from GitHub (no local setup)

Go to **Actions → Build poster → Run workflow**, paste the month's post into the
`schedule_text` box, and run it. The poster is attached to the run as an
artifact and (unless you untick `commit`) committed back to `out/`.

Pull requests that touch `schedules/` render a preview artifact without
committing, so you can eyeball a month before it lands.

## The paste format

The parser is deliberately forgiving — it looks for "a date, then some template
names" and ignores prose around it. All of these work:

```
9/1 - Standard
9/2 — Lift More + Elevation Gain
09/03: Run/Row
Sept 4 - Low Bench
9/8 - Benchmark: 1000 Meter Row + Run/Row
9/16 - Standard (repeat of 9/1)
9/15 - Lift More (not a repeat)
9/17 - repeat of 9/2            # inherits 9/2's templates
```

or a date header with its templates underneath:

```
Tuesday, September 1
  Standard
  Lift More
```

Details:

- **Separators between templates**: `+`, `,`, `&`, `;`, `and`, `·`, `|`.
  Note `/` is *not* one — it lives inside `Run/Row`.
- **Named workouts**: `Signature: <name>`, `Benchmark: <name>`,
  `Specialty: <name>` keep their name on the pill.
- **The month** is read from a line like `September 2026`. If the post doesn't
  say, pass `--month 2026-09`.
- Anything the parser can't place is printed as a note; nothing is silently
  dropped. Use `--strict` to turn those notes into a non-zero exit.

## Editing after parsing

The parse is a starting point, not a straitjacket. If a month has a quirk,
edit `schedules/YYYY-MM.json` by hand and re-render:

```bash
python -m otfposter render --month 2026-09
```

The JSON also carries the poster's copy — `theme`, `tagline`, `notes`,
`footnotes`, `strength_split`. Leave them out and sensible values are derived
from the schedule itself.

## Commands

| Command | What it does |
| --- | --- |
| `build <file>` | parse a paste **and** render the poster (the usual one) |
| `parse <file>` | paste → `schedules/YYYY-MM.json` only |
| `render [json…]` | schedule JSON → HTML + PNG (all months if none given) |
| `validate [json…]` | check schedules without rendering |
| `fetch-assets` | refresh the cached icons and fonts under `assets/` |

Useful flags: `--strict`, `--offline`, `--html-only` (skip the browser),
`--scale N` (pixel density, default 2), `--out DIR`.

## What gets checked

`validate` encodes the rules the poster itself asserts, so a typo in the paste
fails the build instead of quietly producing a wrong poster:

- every day of the month is present, and none fall outside it
- every `repeat of N` points at a real, *earlier* day
- nothing repeats a day that is itself a repeat
- no template set recurs inside the same Monday–Sunday week
- unrecognised template names are surfaced (they render grey rather than vanish)

Errors fail the build; warnings only fail under `--strict`.

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

The pill colour, the highlights row, and the legend at the bottom of the poster
all follow from that. Nothing else needs touching.

## How it fits together

```
raw paste ──▶ parse.py ──▶ Month (schedules/*.json) ──▶ derive.py ──▶ poster.html.j2 ──▶ PNG
                              │                            │
                         validate.py            highlights, repeat map,
                                                key dates, legend, notes
```

The day list is the only thing anyone edits. Everything the poster says *about*
the month — which dates are Run/Rows, what repeats what, which days aren't
repeats, how many bonus templates the month has — is computed in `derive.py`.

## Design notes

- **The rendered HTML is standalone.** Fonts (woff2) and icons (SVG) are cached
  under `assets/` and inlined as data URIs, so a poster opens correctly offline
  and CI needs no network at render time. `--offline` makes a missing asset an
  error rather than a silent fetch.
- **Fonts are asserted, not assumed.** `document.fonts.status` is `'loaded'`
  even when zero faces registered, so the renderer checks `document.fonts.size`
  too — otherwise a CSS mistake silently ships a poster in system fallbacks.

## Licence

MIT — see [LICENSE](LICENSE). Anton and Barlow are used under the SIL Open Font
License; Material Symbols under Apache 2.0.
