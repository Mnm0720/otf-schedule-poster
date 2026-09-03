"""Month -> standalone HTML -> PNG."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import Markup

from . import assets
from .derive import build_context
from .models import Month

TEMPLATE_DIR = Path(__file__).parent / "templates"


def render_html(m: Month, *, allow_fetch: bool = True) -> str:
    from .validate import customization_errors
    errors = customization_errors(m)
    if errors:
        raise ValueError('\n'.join(message for _, message in errors))
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    tpl = env.get_template("poster.html.j2")
    ctx = build_context(m)
    ctx["icon"] = assets.make_icon_fn(allow_fetch=allow_fetch)
    # Markup, not a plain str: autoescaping would turn the quotes in the
    # @font-face rules into entities and the browser would drop every face.
    ctx["font_css"] = Markup(assets.font_css(allow_fetch=allow_fetch))
    return tpl.render(**ctx)


def render_png(html_path: Path, png_path: Path, *, scale: int = 2, width: int = 1200) -> tuple[int, int]:
    """Screenshot the poster. Returns the (width, height) of the CSS box."""
    from playwright.sync_api import sync_playwright

    png_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": width, "height": 1700},
            device_scale_factor=scale,
        )
        page.goto(html_path.resolve().as_uri())
        # Fonts are inlined as data: URIs, so this resolves without network.
        page.wait_for_function("document.fonts.status === 'loaded'", timeout=30_000)
        # fonts.status is trivially 'loaded' when no faces registered at all,
        # which would quietly render the whole poster in fallback faces.
        if page.evaluate("document.fonts.size") == 0:
            print("warning: no web fonts registered -- poster will use system "
                  "fallbacks; run `python -m otfposter fetch-assets`")
        poster = page.locator(".poster")
        poster.wait_for(state="visible")
        box = poster.bounding_box()
        height = int(box["height"]) + 1
        page.set_viewport_size({"width": width, "height": height})
        poster.screenshot(path=str(png_path))
        browser.close()
    return width, height


def build(m: Month, out_dir: Path, *, scale: int = 2, allow_fetch: bool = True,
          png: bool = True) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"otf_{m.slug}.html"
    html_path.write_text(render_html(m, allow_fetch=allow_fetch), encoding="utf-8")
    made = {"html": html_path}
    if png:
        png_path = out_dir / f"otf_{m.slug}.png"
        render_png(html_path, png_path, scale=scale)
        made["png"] = png_path
    return made
