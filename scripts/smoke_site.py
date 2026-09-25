#!/usr/bin/env python3
"""Exercise the built GitHub project site with real Chromium and Pyodide.

Run after building: python scripts/smoke_site.py --site site
Requires the repository's Playwright dependency and its Chromium installation.
The temporary browser profile never opens or modifies a user's browser/drafts.
"""
from __future__ import annotations

import argparse
import base64
import functools
import http.server
import json
import re
import shutil
import struct
import tempfile
import threading
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
AXE_URL = "https://cdn.jsdelivr.net/npm/axe-core@4.10.3/axe.min.js"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def check_accessibility(page):
    if not page.evaluate("Boolean(globalThis.axe)"):
        page.add_script_tag(url=AXE_URL)
    result = page.evaluate("""async () => {
      const result = await axe.run({exclude:[['#preview']]}, {runOnly: {type:'tag', values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}});
      return result.violations.map(v => ({id:v.id, impact:v.impact, nodes:v.nodes.map(n=>n.target)}));
    }""")
    assert not result, json.dumps(result, indent=2)


def smoke(site: Path):
    with tempfile.TemporaryDirectory(prefix="otf-pages-smoke-") as temporary:
        root = Path(temporary)
        shutil.copytree(site, root / "otf-schedule-poster")
        handler = functools.partial(QuietHandler, directory=str(root))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                context = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, accept_downloads=True)
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                base = f"http://127.0.0.1:{server.server_port}/otf-schedule-poster/"
                measurements = {}
                start = time.perf_counter()
                page.goto(base)
                expect(page.locator("#go")).to_be_enabled(timeout=120000)
                measurements["cold_start_seconds"] = round(time.perf_counter() - start, 2)
                assert page.evaluate("typeof loadPyodide") == "undefined", "Python must run in a worker"
                assert page.evaluate("typeof PDFLib") == "undefined", "PDF support must load only when requested"
                assert page.evaluate("typeof htmlToImage") == "undefined", "image support must load only when requested"
                check_accessibility(page)
                page.locator("#src").fill((ROOT / "schedules/raw/2026-09.txt").read_text(encoding="utf-8"))
                start = time.perf_counter()
                page.locator("#go").click()
                expect(page.locator("#editorWrap")).to_be_visible(timeout=60000)
                expect(page.locator("#exportBtn")).to_be_enabled()
                measurements["generate_seconds"] = round(time.perf_counter() - start, 2)
                page.locator("#titleSection > summary").click()
                page.get_by_label("Poster subtitle", exact=True).fill("Mobile moderator smoke test")
                expect(page.locator("#exportBtn")).to_be_disabled()
                start = time.perf_counter()
                page.reload()
                expect(page.locator("#editorWrap")).to_be_visible(timeout=120000)
                measurements["warm_start_and_restore_seconds"] = round(time.perf_counter() - start, 2)
                if not page.locator("#titleSection").evaluate("node => node.open"):
                    page.locator("#titleSection > summary").click()
                expect(page.get_by_label("Poster subtitle", exact=True)).to_have_value("Mobile moderator smoke test")
                expect(page.locator("#exportBtn")).to_be_disabled()
                page.locator("#regenerate").click()
                expect(page.locator("#exportBtn")).to_be_enabled(timeout=60000)
                expect(page.frame_locator("#preview").locator(".poster")).to_contain_text("Mobile moderator smoke test")

                for width in (320, 390, 768, 1440):
                    page.set_viewport_size({"width": width, "height": 900})
                    page.wait_for_timeout(150)
                    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), f"Page overflow at {width}px"
                    metrics = page.locator("#regenerate").evaluate("node => ({height:node.getBoundingClientRect().height,font:parseFloat(getComputedStyle(node).fontSize)})")
                    assert metrics["height"] >= 44 and metrics["font"] >= 16, metrics
                page.set_viewport_size({"width": 390, "height": 844})
                check_accessibility(page)

                for kind, suffix in (("png", ".png"), ("pdf", ".pdf")):
                    page.locator("#exportFormat").select_option(kind)
                    with page.expect_download(timeout=120000) as download_event:
                        page.locator("#exportBtn").click()
                    download = download_event.value
                    assert download.suggested_filename.endswith(suffix), download.suggested_filename
                    target = root / ("poster" + suffix)
                    download.save_as(target)
                    payload = target.read_bytes()
                    if kind == "png":
                        assert payload[:8] == b"\x89PNG\r\n\x1a\n"
                        width, height = struct.unpack(">II", payload[16:24])
                        assert width == 2400 and height > 1000, (width, height)
                        assert page.evaluate("typeof PDFLib") == "undefined", "PNG must not load PDF support"
                    else:
                        assert payload.startswith(b"%PDF-")
                        pages = page.evaluate("""async value => {
                          const bytes=Uint8Array.from(atob(value),c=>c.charCodeAt(0));
                          return (await PDFLib.PDFDocument.load(bytes)).getPageCount();
                        }""", base64.b64encode(payload).decode("ascii"))
                        assert pages == 1, f"Expected single-page A4 PDF, got {pages}"
                    expect(page.locator("#lastDownload")).to_be_visible()
                assert not errors, errors
                # New profile: a failed startup must preserve the user's paste.
                retry_context = browser.new_context(viewport={"width": 320, "height": 700})
                retry_page = retry_context.new_page()
                bundle_pattern = re.compile(r".*/bundle\.[0-9a-f]{12}\.json$")
                retry_context.route(bundle_pattern, lambda route: route.fulfill(status=503, body="Unavailable"))
                retry_page.goto(base)
                retry_page.locator("#src").fill("Keep this pasted thread while retrying")
                expect(retry_page.locator("#retryBoot")).to_be_visible(timeout=120000)
                retry_context.unroute(bundle_pattern)
                retry_page.locator("#retryBoot").click()
                expect(retry_page.locator("#go")).to_be_enabled(timeout=120000)
                expect(retry_page.locator("#src")).to_have_value("Keep this pasted thread while retrying")
                retry_context.close()
                print("Headless CI timings (not representative phone/production measurements): " + json.dumps(measurements))
                context.close()
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    print("Built-site smoke passed: real worker/Pyodide, retry, restoration, mobile layout, editor accessibility (poster artwork excluded), PNG and PDF.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, default=ROOT / "site")
    args = parser.parse_args()
    smoke(args.site.resolve())
