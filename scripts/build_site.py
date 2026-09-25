#!/usr/bin/env python3
"""Assemble the static site that runs the poster generator in the browser.

The browser runs the *real* ``otfposter`` package under Pyodide rather than a
JavaScript reimplementation. That matters: the parser is the part of this
project with all the subtle behaviour and all the tests, and a second copy of
it would drift silently. Here the site and CI parse identically by construction.

What this script produces in ``site/``::

    index.html                      references fingerprinted scripts/styles
    bundle.<hash>.json              every .py, the Jinja template, and the
                                    assets, as one JSON blob the page writes
                                    into Pyodide's virtual filesystem

Fonts are inlined into ``fonts.css`` here, at build time, so the browser never
needs the .woff2 files (or any network access) to render a poster.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
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
    "parse.py", "render.py", "thread.py", "validate.py", "exports.py",
]


def build(output: Path | None = None, *, audit: bool = False) -> Path:
    site = output or SITE
    if not (ROOT / "assets" / "icons").exists():
        raise SystemExit("assets/ is empty -- run `python -m otfposter fetch-assets` first")
    for name in assets.ICON_NAMES:
        if not (assets.ICON_DIR / f"{name}.svg").is_file():
            raise SystemExit(f"Cached icon {name!r} is missing; run `python -m otfposter fetch-assets` before building")
    font_source = assets.FONT_DIR / "fonts.css"
    if not font_source.is_file():
        raise SystemExit("Cached font CSS is missing; run `python -m otfposter fetch-assets` before building")
    font_css = assets.font_css(allow_fetch=False)
    font_urls = re.findall(r"url\(([^)]+)\)", font_css)
    if not font_urls or any(not value.strip("\"'").startswith("data:font/woff2;base64,") for value in font_urls):
        raise SystemExit("Cached fonts are incomplete; run `python -m otfposter fetch-assets` before building")

    files: dict[str, str] = {}

    for name in PY_MODULES:
        files[f"otfposter/{name}"] = (ROOT / "otfposter" / name).read_text(encoding="utf-8")
    files["browser_bridge.py"] = (WEB / "bridge.py").read_text(encoding="utf-8")
    files["otfposter/templates/poster.html.j2"] = (
        ROOT / "otfposter" / "templates" / "poster.html.j2"
    ).read_text(encoding="utf-8")
    files['otfposter/templates/compact.html.j2'] = (ROOT / 'otfposter/templates/compact.html.j2').read_text(encoding='utf-8')

    # Pre-inline the fonts: fonts.css arrives already carrying data: URIs, so
    # assets.font_css() finds nothing left to substitute and returns it as-is.
    files["assets/fonts/fonts.css"] = font_css

    for svg in sorted((ROOT / "assets" / "icons").glob("*.svg")):
        files[f"assets/icons/{svg.name}"] = svg.read_text(encoding="utf-8")

    # A couple of real months so the page has something to demo with.
    examples = {}
    for raw in sorted((ROOT / "schedules" / "raw").glob("*.txt")):
        examples[raw.stem] = raw.read_text(encoding="utf-8")

    site.mkdir(parents=True, exist_ok=True)
    manifest = {"protocol": 1, "assets": {}}

    def write_asset(name: str, data: bytes) -> str:
        path = Path(name)
        digest = hashlib.sha256(data).hexdigest()[:12]
        target = f"{path.stem}.{digest}{path.suffix}"
        (site / target).write_bytes(data)
        manifest["assets"][name] = target
        return target

    payload = {"schemaVersion": 1, "bridgeVersion": 1, "files": files, "examples": examples}
    bundle_name = write_asset("bundle.json", json.dumps(payload, sort_keys=True).encode("utf-8"))
    for item in sorted(WEB.iterdir()):
        if item.suffix in {".js", ".css"}:
            write_asset(item.name, item.read_bytes())
    page = (WEB / "index.html").read_text(encoding="utf-8")
    for original, target in manifest["assets"].items():
        page = page.replace(f'src="{original}"', f'src="{target}"')
        page = page.replace(f'href="{original}"', f'href="{target}"')
    config = {"protocol": 1, "bundleUrl": bundle_name,
              "workerUrl": manifest["assets"]["runtime-worker.js"]}
    # Relative URLs preserve GitHub project sites such as /otf-schedule-poster/.
    page = page.replace("</head>", f"<script>globalThis.OTF_BUILD={json.dumps(config)};</script>\n</head>")
    (site / "index.html").write_text(page, encoding="utf-8")
    (site / "asset-manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")
    audit_page = site / "audit.html"
    if audit:
        audit_page.write_bytes((ROOT / "scripts" / "audit_site.html").read_bytes())
    else:
        audit_page.unlink(missing_ok=True)
    # Pages will not serve a directory containing a Jekyll-hostile name.
    (site / ".nojekyll").write_text("", encoding="utf-8")

    kb = (site / bundle_name).stat().st_size / 1024
    print(f"site/ built: {len(files)} files bundled, "
          f"{len(examples)} examples, Python bundle {kb:.0f} KB")
    return site


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=SITE)
    parser.add_argument("--audit", action="store_true", help="Include a local-only editor accessibility audit page")
    args = parser.parse_args()
    build(args.output, audit=args.audit)
