#!/usr/bin/env python3
"""Assemble the static site that runs the poster generator in the browser.

The browser runs the *real* ``otfposter`` package under Pyodide rather than a
JavaScript reimplementation. That matters: the parser is the part of this
project with all the subtle behaviour and all the tests, and a second copy of
it would drift silently. Here the site and CI parse identically by construction.

What this script produces in ``site/``::

    index.html  app.js  style.css   copied from web/
    bundle.json                     every .py, the Jinja template, and the
                                    assets, as one JSON blob the page writes
                                    into Pyodide's virtual filesystem

Fonts are inlined into ``fonts.css`` here, at build time, so the browser never
needs the .woff2 files (or any network access) to render a poster.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from otfposter import assets  # noqa: E402

WEB = ROOT / "web"
SITE = ROOT / "site"

# Sources the browser needs. render.py is included but only render_html() is
# called there -- its Playwright import is lazy, inside render_png().
PY_MODULES = [
    "__init__.py", "assets.py", "categories.py", "derive.py", "models.py",
    "parse.py", "render.py", "thread.py", "validate.py",
]


def build() -> Path:
    if not (ROOT / "assets" / "icons").exists():
        raise SystemExit("assets/ is empty -- run `python -m otfposter fetch-assets` first")

    files: dict[str, str] = {}

    for name in PY_MODULES:
        files[f"otfposter/{name}"] = (ROOT / "otfposter" / name).read_text(encoding="utf-8")
    files["otfposter/templates/poster.html.j2"] = (
        ROOT / "otfposter" / "templates" / "poster.html.j2"
    ).read_text(encoding="utf-8")

    # Pre-inline the fonts: fonts.css arrives already carrying data: URIs, so
    # assets.font_css() finds nothing left to substitute and returns it as-is.
    files["assets/fonts/fonts.css"] = assets.font_css(allow_fetch=True)

    for svg in sorted((ROOT / "assets" / "icons").glob("*.svg")):
        files[f"assets/icons/{svg.name}"] = svg.read_text(encoding="utf-8")

    # A couple of real months so the page has something to demo with.
    examples = {}
    for raw in sorted((ROOT / "schedules" / "raw").glob("*.txt")):
        examples[raw.stem] = raw.read_text(encoding="utf-8")

    SITE.mkdir(exist_ok=True)
    for item in WEB.iterdir():
        shutil.copy2(item, SITE / item.name)

    payload = {"files": files, "examples": examples}
    (SITE / "bundle.json").write_text(json.dumps(payload), encoding="utf-8")
    # Pages will not serve a directory containing a Jekyll-hostile name.
    (SITE / ".nojekyll").write_text("", encoding="utf-8")

    kb = (SITE / "bundle.json").stat().st_size / 1024
    print(f"site/ built: {len(files)} files bundled, "
          f"{len(examples)} examples, bundle.json {kb:.0f} KB")
    return SITE


if __name__ == "__main__":
    build()
