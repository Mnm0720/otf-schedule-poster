#!/usr/bin/env python3
"""Exercise the built GitHub project site with real Chromium and Pyodide.

Run after building: python scripts/smoke_site.py --site site
Requires the repository's Playwright dependency and its Chromium installation.
Use --browser-channel chrome or msedge to test with an installed browser instead.
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


def check_october_events(browser, base):
    """The October source must show Hell Week and captioned 3G dates in Pyodide."""
    context = browser.new_context(viewport={"width": 390, "height": 844})
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base)
        expect(page.locator("#go")).to_be_enabled(timeout=120000)
        page.locator("#src").fill((ROOT / "schedules/raw/2026-10.txt").read_text(encoding="utf-8"))
        page.locator("#go").click()
        expect(page.locator("#exportBtn")).to_be_enabled(timeout=60000)
        preview = page.frame_locator("#preview")
        expect(preview.locator(".cal .event-label")).to_have_count(8)
        for day in range(24, 32):
            cell = preview.locator(".dnum").filter(has_text=re.compile(rf"^{day}(?:3G)?$")).locator("..")
            expect(cell).to_contain_text("Hell Week")
            expect(cell).not_to_contain_text("Standard")
            expect(cell.locator(".g3")).to_have_count(1 if day in (26, 31) else 0)
        page.locator("#eventsSection > summary").click()
        page.get_by_label("Event 1 name", exact=True).fill("Updated event")
        page.get_by_label("Event 1 start day", exact=True).fill("25")
        page.get_by_label("Event 1 end day", exact=True).fill("27")
        expect(page.locator("#exportBtn")).to_be_disabled()
        page.locator("#regenerate").click()
        expect(page.locator("#exportBtn")).to_be_enabled(timeout=60000)
        expect(preview.locator(".cal .event-label")).to_have_count(3)
        expect(preview.locator(".cal")).not_to_contain_text("Hell Week")
        page.get_by_role("button", name="Remove event 1", exact=True).click()
        page.locator("#regenerate").click()
        expect(page.locator("#exportBtn")).to_be_enabled(timeout=60000)
        expect(preview.locator(".cal .event-label")).to_have_count(0)
        expect(preview.locator(".dnum").filter(has_text=re.compile(r"^24$")).locator("..")).to_contain_text("Standard")
        assert not errors, errors
    finally:
        context.close()


def check_november_source(browser, base):
    """Check the latest monthly example through real parsing, editing and ICS."""
    context = browser.new_context(viewport={"width": 390, "height": 844}, accept_downloads=True)
    try:
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base)
        expect(page.locator("#go")).to_be_enabled(timeout=120000)
        page.locator("#sampleSection > summary").click()
        page.locator("#examples").get_by_role("button", name="2026-11", exact=True).click()
        expect(page.locator("#src")).to_have_value(re.compile("November 2026 - Monthly Post"))
        page.locator("#go").click()
        expect(page.locator("#exportBtn")).to_be_enabled(timeout=60000)
        preview = page.frame_locator("#preview")

        def check_preview():
            expect(preview.locator(".theme")).to_contain_text("COMMUNITY & MOBILITY")
            for day, title in ((1, "Member Choice"), (5, ".25 Mile"), (13, "1 Mile"),
                               (17, "200 Meter row"), (23, "Strength in Numbers")):
                cell = preview.locator(".dnum").filter(has_text=re.compile(rf"^{day}(?:3G)?$")).locator("..")
                expect(cell).to_contain_text(title)
                expect(preview.locator(".kd").filter(has_text=title)).to_have_count(1)
            cell_23 = preview.locator(".dnum").filter(has_text=re.compile(r"^23(?:3G)?$")).locator("..")
            expect(cell_23.locator(".g3")).to_have_count(1)
            for day in (27, 30):
                cell = preview.locator(".dnum").filter(has_text=re.compile(rf"^{day}$")).locator("..")
                expect(cell).to_contain_text("Not a repeat")
                expect(cell).not_to_contain_text("Repeat of")

        check_preview()
        page.locator("#dayJump").select_option("23")
        expect(page.get_by_label("Day 23 3G", exact=True)).to_be_checked()
        for day in (27, 30):
            page.locator("#dayJump").select_option(str(day))
            expect(page.get_by_label(f"Day {day} repeat of", exact=True)).to_have_value("")
        page.locator("#titleSection > summary").click()
        page.get_by_label("Poster subtitle", exact=True).fill("November verified source")
        expect(page.locator("#exportBtn")).to_be_disabled()
        page.locator("#regenerate").click()
        expect(page.locator("#exportBtn")).to_be_enabled(timeout=60000)
        expect(preview.locator(".sub")).to_have_text("November verified source")
        check_preview()

        page.locator("#exportFormat").select_option("ics")
        with page.expect_download(timeout=60000) as download_event:
            page.locator("#exportBtn").click()
        download = download_event.value
        assert download.suggested_filename.endswith(".ics"), download.suggested_filename
        calendar = Path(download.path()).read_text(encoding="utf-8").replace("\n ", "")
        assert ".25 Mile" in calendar and "Strength in Numbers (3G)" in calendar
        for day in (27, 30):
            event = next(part for part in calendar.split("BEGIN:VEVENT")
                         if f"DTSTART;VALUE=DATE:202611{day}" in part)
            assert "Not a repeat" in event
            assert "Repeat of" not in event
        assert not errors, errors
    finally:
        context.close()


def check_appearance_presets(browser, base):
    """A style moves between months while dates and restored edits remain local."""
    context = browser.new_context(viewport={"width": 390, "height": 844}, accept_downloads=True)
    try:
        page = context.new_page()
        page.goto(base)
        expect(page.locator('#go')).to_be_enabled(timeout=120000)
        page.locator('#src').fill((ROOT / 'schedules/raw/2026-11.txt').read_text(encoding='utf-8'))
        page.locator('#go').click()
        expect(page.locator('#exportBtn')).to_be_enabled(timeout=60000)
        assert page.frame_locator('#preview').locator('td .pill svg').count() == 0
        page.locator('#appearanceSection > summary').click()
        page.get_by_label('Poster layout', exact=True).select_option('reference')
        page.get_by_label('Poster spacing', exact=True).select_option('compact')
        page.get_by_label('Show workout icons on calendar dates', exact=True).check()
        page.get_by_label('Show workout icons on calendar dates', exact=True).uncheck()
        page.locator('#workoutSection > summary').click()
        page.get_by_label('Run/Row color', exact=True).fill('#123456')
        page.locator('#creditsSection > summary').click()
        page.get_by_label('Credits & team', exact=True).fill('Image: Studio style smoke')
        page.get_by_label('Style preset name', exact=True).fill('Studio smoke')
        page.get_by_label('Use saved style for new posters', exact=True).check()
        page.get_by_role('button', name='Save style preset', exact=True).click()
        expect(page.locator('#presetStatus')).to_contain_text('saved')
        page.locator('#regenerate').click()
        expect(page.locator('#exportBtn')).to_be_enabled(timeout=60000)
        expect(page.frame_locator('#preview').locator('td .pill svg')).to_have_count(0)
        with page.expect_download() as download_event:
            page.get_by_role('button', name='Download style preset', exact=True).click()
        preset = json.loads(Path(download_event.value.path()).read_text(encoding='utf-8'))
        assert preset['settings']['credits'] == 'Image: Studio style smoke'
        assert not any(key in preset['settings'] for key in ('days', 'events', 'theme', 'key_dates'))
        page.locator('#restart').click()
        page.locator('#restartConfirm').click()
        page.locator('#src').fill((ROOT / 'schedules/raw/2026-09.txt').read_text(encoding='utf-8'))
        page.locator('#go').click()
        expect(page.locator('#exportBtn')).to_be_enabled(timeout=60000)
        values = page.evaluate('({month:editorState.draft.month,appearance:editorState.draft.appearance,credits:editorState.draft.credits,color:editorState.draft.category_styles.runrow.color})')
        assert values['month'] == 9 and values['appearance']['layout'] == 'reference'
        assert values['appearance']['calendar_icons'] is False
        assert values['credits'] == 'Image: Studio style smoke' and values['color'] == '#123456'
        page.locator('#appearanceSection > summary').click()
        page.get_by_label('Show workout icons on calendar dates', exact=True).check()
        page.locator('#regenerate').click()
        expect(page.locator('#exportBtn')).to_be_enabled(timeout=60000)
        page.reload()
        expect(page.locator('#editorWrap')).to_be_visible(timeout=120000)
        assert page.evaluate('editorState.draft.appearance.calendar_icons') is True
        page.locator('#appearanceSection > summary').click()
        for width in (320, 390):
            page.set_viewport_size({'width': width, 'height': 844})
            assert page.evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth'), f'Appearance overflow at {width}px'
        check_accessibility(page)
        # A broken imported default must never lock the user out of generation.
        page.evaluate("""() => {
          const key='otf-appearance-presets-v1',data=JSON.parse(localStorage.getItem(key));
          data.presets.push({version:1,name:'Unsupported old style',settings:{note_style:{icon:'not_cached'}}});
          data.defaultName='Unsupported old style';localStorage.setItem(key,JSON.stringify(data));
        }""")
        page.locator('#restart').click()
        page.locator('#restartConfirm').click()
        page.locator('#go').click()
        expect(page.locator('#exportBtn')).to_be_enabled(timeout=60000)
        expect(page.locator('#status')).to_contain_text('saved style could not be applied')
        page.locator('#appearanceSection > summary').click()
        page.get_by_role('button',name='Clear default style preset',exact=True).click()
        expect(page.locator('#presetStatus')).to_contain_text('built-in style')
    finally:
        context.close()


def smoke(site: Path, browser_channel=None):
    with tempfile.TemporaryDirectory(prefix="otf-pages-smoke-") as temporary:
        root = Path(temporary)
        shutil.copytree(site, root / "otf-schedule-poster")
        handler = functools.partial(QuietHandler, directory=str(root))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel=browser_channel)
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
                check_october_events(browser, base)
                check_november_source(browser, base)
                check_appearance_presets(browser, base)
                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    print("Built-site smoke passed: real worker/Pyodide, October events/3G/regeneration, November key dates/3G/nonrepeats/ICS, reusable styles across months, retry, restoration, mobile layout, editor accessibility (poster artwork excluded), PNG and PDF.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, default=ROOT / "site")
    parser.add_argument("--browser-channel", choices=("chrome", "msedge"),
                        help="Use an installed browser instead of Playwright's downloaded Chromium.")
    args = parser.parse_args()
    smoke(args.site.resolve(), args.browser_channel)
