"""Command line entry point: ``python -m otfposter <command>``."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import assets, render, validate
from .models import Month
from .parse import parse

ROOT = Path(__file__).resolve().parent.parent
SCHED_DIR = ROOT / "schedules"
RAW_DIR = SCHED_DIR / "raw"
OUT_DIR = ROOT / "out"


def _month_arg(value: str) -> tuple[int, int]:
    try:
        y, mo = value.split("-")
        return int(y), int(mo)
    except Exception:
        raise argparse.ArgumentTypeError("expected YYYY-MM, e.g. 2026-10")


def _read_text(args) -> str:
    if args.text:
        return args.text
    if args.input in (None, "-"):
        data = sys.stdin.read()
        if not data.strip():
            raise SystemExit("no input: pass a file, --text, or pipe the post on stdin")
        return data
    return Path(args.input).read_text(encoding="utf-8")


def _apply_meta(m: Month, args) -> Month:
    for field in ("theme", "tagline", "source_url", "subtitle"):
        val = getattr(args, field, None)
        if val:
            setattr(m, field, val)
    return m


def _emit_issues(m: Month, strict: bool) -> None:
    issues = validate.check(m)
    if issues:
        print(f"validation for {m.slug}:", file=sys.stderr)
        print(validate.report(issues), file=sys.stderr)
    if validate.has_errors(issues):
        raise SystemExit(f"{m.slug}: schedule has errors (see above)")
    if strict and issues:
        raise SystemExit(f"{m.slug}: --strict and the schedule has warnings")


# --------------------------------------------------------------- commands --
def cmd_parse(args) -> None:
    text = _read_text(args)
    ym = args.month or (None, None)
    m, report = parse(text, year=ym[0], month=ym[1])
    _apply_meta(m, args)

    if not report.clean:
        print(f"parser notes for {m.slug}:", file=sys.stderr)
        print(report.render(), file=sys.stderr)
    if args.strict and not report.clean:
        raise SystemExit("--strict and the parser could not read every line")

    _emit_issues(m, strict=False)
    out = Path(args.out) if args.out else SCHED_DIR / f"{m.slug}.json"
    m.save(out)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / f"{m.slug}.txt").write_text(text, encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({len(m.days)} days)")


def cmd_render(args) -> None:
    for path in _schedule_paths(args):
        m = Month.load(path)
        _apply_meta(m, args)
        _emit_issues(m, args.strict)
        made = render.build(
            m, Path(args.out or OUT_DIR),
            scale=args.scale, allow_fetch=not args.offline, png=not args.html_only,
        )
        for kind, p in made.items():
            print(f"{kind}: {p.relative_to(ROOT) if ROOT in p.parents else p}")


def cmd_build(args) -> None:
    """parse + render in one step -- the common path."""
    text = _read_text(args)
    ym = args.month or (None, None)
    m, report = parse(text, year=ym[0], month=ym[1])
    _apply_meta(m, args)

    if not report.clean:
        print(f"parser notes for {m.slug}:", file=sys.stderr)
        print(report.render(), file=sys.stderr)
    if args.strict and not report.clean:
        raise SystemExit("--strict and the parser could not read every line")

    # Validate before persisting: a rejected month must not leave a broken
    # schedule in schedules/ for the next `validate` run to trip over.
    _emit_issues(m, args.strict)
    m.save(SCHED_DIR / f"{m.slug}.json")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / f"{m.slug}.txt").write_text(text, encoding="utf-8")
    made = render.build(
        m, Path(args.out or OUT_DIR),
        scale=args.scale, allow_fetch=not args.offline, png=not args.html_only,
    )
    print(f"schedule: schedules/{m.slug}.json")
    for kind, p in made.items():
        print(f"{kind}: {p.relative_to(ROOT) if ROOT in p.parents else p}")


def cmd_validate(args) -> None:
    failed = False
    for path in _schedule_paths(args):
        m = Month.load(path)
        issues = validate.check(m)
        if issues:
            print(f"{m.slug}:")
            print(validate.report(issues))
            failed = failed or validate.has_errors(issues) or args.strict
        else:
            print(f"{m.slug}: ok")
    if failed:
        raise SystemExit(1)


def cmd_fetch_assets(_args) -> None:
    assets.warm_cache()
    icons = len(list(assets.ICON_DIR.glob("*.svg")))
    fonts = len(list(assets.FONT_DIR.glob("*.woff2")))
    print(f"cached {icons} icons and {fonts} font files under assets/")


def _schedule_paths(args) -> list[Path]:
    if args.schedule:
        return [Path(p) for p in args.schedule]
    if getattr(args, "month", None):
        y, mo = args.month
        return [SCHED_DIR / f"{y:04d}-{mo:02d}.json"]
    paths = sorted(SCHED_DIR.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9].json"))
    if not paths:
        raise SystemExit("no schedules found under schedules/")
    return paths


# ------------------------------------------------------------------ parser --
def _add_meta_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--theme", help="theme of the month, printed in the orange chip")
    p.add_argument("--tagline", help="italic line under the theme (inline HTML ok)")
    p.add_argument("--subtitle", help='overrides "Monthly Schedule Poster"')
    p.add_argument("--source-url", dest="source_url",
                   help="credit line at the foot of the poster")


def _add_render_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--out", help="output directory (default: out/)")
    p.add_argument("--scale", type=int, default=2,
                   help="device pixel ratio for the PNG (default: 2)")
    p.add_argument("--html-only", action="store_true",
                   help="skip the screenshot; no browser needed")
    p.add_argument("--offline", action="store_true",
                   help="fail rather than fetch missing icons/fonts")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="otfposter",
        description="Generate an OTF monthly schedule poster from a pasted template post.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("build", help="parse a pasted post and render the poster")
    p.add_argument("input", nargs="?", help="text file, or - for stdin")
    p.add_argument("--text", help="the post text, inline")
    p.add_argument("--month", type=_month_arg,
                   help="YYYY-MM; inferred from the text when omitted")
    p.add_argument("--strict", action="store_true",
                   help="fail on anything the parser or validator flags")
    _add_meta_args(p)
    _add_render_args(p)
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("parse", help="paste -> schedules/YYYY-MM.json, no rendering")
    p.add_argument("input", nargs="?", help="text file, or - for stdin")
    p.add_argument("--text", help="the post text, inline")
    p.add_argument("--month", type=_month_arg, help="YYYY-MM")
    p.add_argument("--out", help="output JSON path")
    p.add_argument("--strict", action="store_true")
    _add_meta_args(p)
    p.set_defaults(func=cmd_parse)

    p = sub.add_parser("render", help="schedules/*.json -> HTML + PNG")
    p.add_argument("schedule", nargs="*", help="schedule JSON paths (default: all)")
    p.add_argument("--month", type=_month_arg, help="YYYY-MM")
    p.add_argument("--strict", action="store_true")
    _add_meta_args(p)
    _add_render_args(p)
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("validate", help="check schedules without rendering")
    p.add_argument("schedule", nargs="*")
    p.add_argument("--month", type=_month_arg, help="YYYY-MM")
    p.add_argument("--strict", action="store_true",
                   help="treat warnings as failures")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("fetch-assets", help="warm the icon/font cache under assets/")
    p.set_defaults(func=cmd_fetch_assets)

    return ap


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
