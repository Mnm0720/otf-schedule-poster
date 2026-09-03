"""Icons and fonts, fetched once and cached on disk.

Everything is inlined into the generated HTML so a rendered poster is a single
self-contained file that opens correctly with no network. The caches live under
``assets/`` and are committed, which also makes CI runs hermetic and
byte-reproducible.
"""
from __future__ import annotations

import base64
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICON_DIR = ROOT / "assets" / "icons"
FONT_DIR = ROOT / "assets" / "fonts"

ICON_CDN = "https://cdn.jsdelivr.net/npm/@material-symbols/svg-500/rounded/{}-fill.svg"

# Google Fonts CSS endpoint. A modern UA gets woff2 back.
FONT_CSS_URL = (
    "https://fonts.googleapis.com/css2"
    "?family=Anton"
    "&family=Barlow+Condensed:wght@500;600;700"
    "&family=Barlow:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500;1,600"
    "&display=block"
)
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

# Every icon the poster can reference. Pre-declared so `fetch-assets` can warm
# the cache in one go rather than discovering them mid-render.
ICON_NAMES = (
    "sprint", "fitness_center", "exercise", "check_circle", "calendar_month",
    "equalizer", "autorenew", "menu_book", "groups", "cyclone", "bolt",
    "star", "flag", "local_fire_department", "filter_hdr", "local_cafe",
    "military_tech",
)


class AssetError(RuntimeError):
    pass


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


# ---------------------------------------------------------------- icons ----
def icon_body(name: str, *, allow_fetch: bool = True) -> str:
    """The inner markup of a Material Symbols glyph, cached under assets/icons."""
    f = ICON_DIR / f"{name}.svg"
    if not f.exists():
        if not allow_fetch:
            raise AssetError(
                f"icon {name!r} is not cached and fetching is disabled; "
                f"run `python -m otfposter fetch-assets`"
            )
        ICON_DIR.mkdir(parents=True, exist_ok=True)
        try:
            f.write_bytes(_get(ICON_CDN.format(name)))
        except Exception as exc:  # network, 404, ...
            raise AssetError(f"could not fetch icon {name!r}: {exc}") from exc
    body = f.read_text(encoding="utf-8")
    return re.sub(r"^<svg[^>]*>|</svg>\s*$", "", body).strip()


def make_icon_fn(allow_fetch: bool = True):
    """Return the ``icon()`` helper exposed to the Jinja template."""
    from markupsafe import Markup

    def icon(name: str, cls: str = "", color: str = "") -> Markup:
        c = f' class="{cls}"' if cls else ""
        st = f' style="color:{color}"' if color else ""
        return Markup(
            f'<svg viewBox="0 -960 960 960" fill="currentColor" '
            f'xmlns="http://www.w3.org/2000/svg"{c}{st}>'
            f"{icon_body(name, allow_fetch=allow_fetch)}</svg>"
        )

    return icon


# ---------------------------------------------------------------- fonts ----
def font_css(*, allow_fetch: bool = True) -> str:
    """@font-face rules with the woff2 payloads inlined as data: URIs."""
    css_file = FONT_DIR / "fonts.css"
    if not css_file.exists():
        if not allow_fetch:
            return _FALLBACK_FONT_CSS
        try:
            _download_fonts()
        except Exception as exc:
            print(f"warning: falling back to system fonts ({exc})")
            return _FALLBACK_FONT_CSS

    css = css_file.read_text(encoding="utf-8")

    def inline(m: re.Match) -> str:
        path = FONT_DIR / m.group(1)
        if not path.exists():
            return m.group(0)
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"url(data:font/woff2;base64,{b64}) format('woff2')"

    return re.sub(r"url\((?:'|\")?([\w.\-]+\.woff2)(?:'|\")?\)\s*format\(['\"]woff2['\"]\)",
                  inline, css)


# Google serves one @font-face per (family, style, weight, subset). The poster
# is English, so only these subsets are worth carrying.
KEEP_SUBSETS = ("latin",)


def _download_fonts() -> None:
    """Fetch the Google Fonts CSS and every woff2 it points at."""
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    css = _keep_subsets(_get(FONT_CSS_URL).decode("utf-8"))
    urls = re.findall(r"url\((https://fonts\.gstatic\.com/[^)]+\.woff2)\)", css)
    if not urls:
        raise AssetError("Google Fonts returned no woff2 URLs")
    for url in dict.fromkeys(urls):
        name = _font_filename(url)
        target = FONT_DIR / name
        if not target.exists():
            target.write_bytes(_get(url))
        css = css.replace(url, name)
    (FONT_DIR / "fonts.css").write_text(css, encoding="utf-8")


def _keep_subsets(css: str) -> str:
    """Drop @font-face blocks for subsets the poster will never render."""
    blocks = re.split(r"(?=/\*\s*[\w\-\[\]]+\s*\*/)", css)
    kept = [
        b for b in blocks
        if not b.strip().startswith("/*")
        or (re.match(r"/\*\s*([\w\-\[\]]+)\s*\*/", b.strip()) or [None, ""])[1]
        in KEEP_SUBSETS
    ]
    out = "".join(kept)
    return out if "@font-face" in out else css


def _font_filename(url: str) -> str:
    """A stable, collision-free local name for a gstatic woff2 URL.

    The full stem is kept: Google's hashes differ only in their tail for faces
    of the same family, so truncating them silently aliases (say) Barlow
    italic onto Barlow roman.
    """
    parts = url.rstrip("/").split("/")
    stem = parts[-1].removesuffix(".woff2")
    family = parts[-3] if len(parts) >= 3 else "font"
    version = parts[-2] if len(parts) >= 2 else "v0"
    return f"{family}-{version}-{stem}.woff2"


_FALLBACK_FONT_CSS = """
/* Fonts unavailable at build time -- the poster will use system fallbacks. */
"""


def warm_cache() -> None:
    """Populate assets/ so later renders (and CI) need no network."""
    for name in ICON_NAMES:
        icon_body(name)
    _download_fonts()
