"""Guards on the browser build.

The site runs the real package under Pyodide, which means a module added to
otfposter/ but not to the bundle breaks the site at runtime with an ImportError
that nothing else would catch.
"""
import json
from pathlib import Path

import pytest

from scripts.build_site import PY_MODULES, ROOT

PKG = ROOT / "otfposter"

# cli.py is the only module the browser never touches -- it is argparse and
# filesystem plumbing for the command line.
BROWSER_EXEMPT = {"cli.py", "__main__.py"}


def test_bundle_lists_every_module_the_browser_could_import():
    on_disk = {p.name for p in PKG.glob("*.py")} - BROWSER_EXEMPT
    missing = on_disk - set(PY_MODULES)
    assert not missing, (
        f"new module(s) {sorted(missing)} are not in build_site.PY_MODULES, "
        f"so the Pages site would fail to import them"
    )


def test_bundle_does_not_list_modules_that_no_longer_exist():
    on_disk = {p.name for p in PKG.glob("*.py")}
    stale = set(PY_MODULES) - on_disk
    assert not stale, f"build_site.PY_MODULES references missing file(s): {sorted(stale)}"


def test_browser_entry_points_do_not_need_playwright():
    """render_html must stay importable without a browser installed.

    Playwright is imported inside render_png(); if it ever moves to module
    scope, the Pages build breaks.
    """
    source = (PKG / "render.py").read_text(encoding="utf-8")
    top_level = [ln for ln in source.splitlines()
                 if ln.startswith(("import ", "from ")) and "playwright" in ln]
    assert not top_level, f"playwright imported at module scope: {top_level}"


def test_web_assets_exist():
    for name in ("index.html", "app.js", "style.css"):
        assert (ROOT / "web" / name).exists(), f"web/{name} is missing"


@pytest.mark.skipif(not (ROOT / "assets" / "icons").exists(),
                    reason="assets not fetched")
def test_site_builds_and_bundle_is_self_contained():
    from scripts.build_site import build

    site = build()
    bundle = json.loads((site / "bundle.json").read_text(encoding="utf-8"))
    files = bundle["files"]

    assert "otfposter/templates/poster.html.j2" in files
    for name in PY_MODULES:
        assert f"otfposter/{name}" in files

    # Fonts must be pre-inlined: the browser has no filesystem to read .woff2
    # from and no network access at render time.
    css = files["assets/fonts/fonts.css"]
    assert "data:font/woff2;base64," in css
    assert ".woff2)" not in css

    assert bundle["examples"], "no example months bundled"
