#!/usr/bin/env python3
"""Fetch or read a monthly post and write isolated, non-publishing review files."""
from __future__ import annotations

import argparse
import base64
import calendar
from dataclasses import dataclass
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from otfposter import validate  # noqa: E402
from otfposter.models import Month  # noqa: E402
from otfposter.parse import parse  # noqa: E402
from scripts import monthly_state as state  # noqa: E402

MAX_RESPONSE = 2 * 1024 * 1024
USER_AGENT = 'python:otf-schedule-poster:0.1 (monthly schedule review; read-only)'
MONTH_NAMES = {name.lower(): number for number in range(1, 13)
               for name in (calendar.month_name[number], calendar.month_abbr[number])}
MONTH_NAMES['sept'] = 9
MONTH_HINT = re.compile(r'\b(' + '|'.join(sorted(MONTH_NAMES, key=len, reverse=True))
                        + r')\.?\s+(20\d{2})\b', re.I)


@dataclass(frozen=True)
class ReviewResult:
    directory: Path
    status: str
    exit_code: int


class NotPublished(ValueError):
    """No matching source has been published yet."""


class AuthenticationRequired(RuntimeError):
    """Approved renewable credentials need setup or reauthorization."""


def month_hint(text: str) -> tuple[int, int] | None:
    match = MONTH_HINT.search(text)
    return (int(match[2]), MONTH_NAMES[match[1].lower()]) if match else None


def canonical_url(url: str) -> str:
    """Accept a normal HTTPS post link, never an arbitrary network destination."""
    parts = urlsplit(url)
    if (parts.scheme != 'https' or parts.hostname not in
            {'reddit.com', 'www.reddit.com', 'old.reddit.com', 'oauth.reddit.com'}
            or parts.username or parts.password or parts.port not in (None, 443)):
        raise ValueError('Use an HTTPS r/orangetheory Reddit post URL.')
    match = re.fullmatch(r'/r/orangetheory/comments/([a-z0-9]+)(?:/[^/]+)?/?', parts.path, re.I)
    if not match:
        raise ValueError('Use an r/orangetheory post URL, including its comments/post ID.')
    path = parts.path.rstrip('/') + '/'
    return 'https://www.reddit.com' + path


def _monthly_title(title: str, year: int, month: int) -> bool:
    return bool(isinstance(title, str) and month_hint(title) == (year, month)
                and re.search(r'\bmonthly\s+(?:thread|post|highlights)\b', title, re.I))


def _posts(payload) -> list[dict]:
    if isinstance(payload, list):
        if not payload:
            raise ValueError('Reddit returned an empty response.')
        payload = payload[0]
    if not isinstance(payload, dict) or not isinstance(payload.get('data'), dict):
        raise ValueError('Reddit returned malformed listing JSON.')
    children = payload['data'].get('children')
    if not isinstance(children, list):
        raise ValueError('Reddit returned malformed listing children.')
    return [child['data'] for child in children if isinstance(child, dict)
            and child.get('kind') == 't3' and isinstance(child.get('data'), dict)]


def select_post(payload, year: int, month: int) -> dict:
    posts = _posts(payload)
    if any(not isinstance(p.get('subreddit'), str) or not isinstance(p.get('title'), str) for p in posts):
        raise ValueError('Reddit returned malformed post fields.')
    candidates = {p.get('id'): p for p in posts
                  if isinstance(p.get('subreddit'), str) and p['subreddit'].lower() == 'orangetheory'
                  and _monthly_title(p.get('title', ''), year, month)}
    if not candidates:
        raise NotPublished(f'No {calendar.month_name[month]} {year} monthly post found. '
                         'Use --url to select the exact thread, or --input with a saved paste.')
    if len(candidates) != 1:
        raise ValueError('Monthly post discovery is ambiguous; use --url with the intended thread.')
    return next(iter(candidates.values()))


def verify_post(post: dict, year: int, month: int) -> dict:
    if not isinstance(post.get('subreddit'), str) or post['subreddit'].lower() != 'orangetheory':
        raise ValueError('Source is not from r/orangetheory.')
    if not _monthly_title(post.get('title', ''), year, month):
        raise ValueError('Source title month/year does not match the requested monthly post.')
    body = post.get('selftext')
    if (post.get('is_self') is not True or not isinstance(body, str)
            or not body.strip() or body.strip().lower() in {'[removed]', '[deleted]'}):
        raise ValueError('Monthly post is empty, removed, deleted, or is not a text post.')
    if not isinstance(post.get('id'), str) or not re.fullmatch('[a-z0-9]+', post['id']):
        raise ValueError('Source post ID is missing or invalid.')
    url = canonical_url('https://www.reddit.com' + post.get('permalink', ''))
    if urlsplit(url).path.split('/')[4].lower() != post['id'].lower():
        raise ValueError('Source permalink does not match its post ID.')
    body_month = month_hint(body[:400])
    if body_month and body_month != (year, month):
        raise ValueError('Source body month/year differs from its title.')
    return post


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Reddit redirected the request; use --input with a saved paste.')


def _open_json(request):
    opener = build_opener(_NoRedirect())
    for attempt in range(3):
        try:
            with opener.open(request, timeout=30) as response:
                content_type = response.headers.get('Content-Type', '').split(';')[0].strip()
                if content_type != 'application/json':
                    raise ValueError('Reddit returned a login/block page instead of JSON. Use --input.')
                raw = response.read(MAX_RESPONSE + 1)
            break
        except HTTPError as error:
            if error.code not in (429, 502, 503, 504) or attempt == 2:
                raise
            try:
                wait = float(error.headers.get('Retry-After', 2 ** attempt))
            except (ValueError, TypeError, AttributeError):
                wait = 2 ** attempt
            if not 0 <= wait <= 30:
                raise
            time.sleep(wait)
    if len(raw) > MAX_RESPONSE:
        raise ValueError('Reddit response exceeded the 2 MiB limit. Use --input.')
    try:
        return json.loads(raw.decode('utf-8'))
    except (ValueError, UnicodeError):
        raise ValueError('Reddit returned invalid JSON. Use --input with a saved paste.') from None


def obtain_access_token(*, exchange=None):
    """Renew credentials for an already approved app; never persist tokens."""
    client = os.environ.get('REDDIT_CLIENT_ID', '').strip()
    secret = os.environ.get('REDDIT_CLIENT_SECRET', '').strip()
    refresh = os.environ.get('REDDIT_REFRESH_TOKEN', '').strip()
    if not client and not secret and not refresh:
        return os.environ.get('REDDIT_ACCESS_TOKEN', '').strip()
    if not client or not secret:
        raise AuthenticationRequired('Renewable Reddit authentication requires approved REDDIT_CLIENT_ID '
                           'and REDDIT_CLIENT_SECRET. Keep --input available.')
    fields = {'grant_type': 'refresh_token', 'refresh_token': refresh} if refresh else {'grant_type': 'client_credentials'}
    authorization = base64.b64encode((client + ':' + secret).encode()).decode()
    request = Request('https://www.reddit.com/api/v1/access_token',
                      data=urlencode(fields).encode(), headers={
                          'Authorization': 'Basic ' + authorization,
                          'User-Agent': os.environ.get('REDDIT_USER_AGENT', '').strip() or USER_AGENT,
                          'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'})
    try:
        payload = (exchange or _open_json)(request)
    except HTTPError as error:
        if error.code in (400, 401, 403):
            raise AuthenticationRequired('Reddit token renewal was rejected; verify app approval '
                                         'and authorized credentials. Use --input.') from None
        raise
    if not isinstance(payload, dict) or not isinstance(payload.get('access_token'), str):
        raise AuthenticationRequired('Reddit token renewal failed; check app approval and authorized credentials. Use --input.')
    return payload['access_token']


def request_json(url: str):
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.hostname != 'www.reddit.com':
        raise ValueError('Unsupported Reddit request destination.')
    token = obtain_access_token()
    headers = {'User-Agent': os.environ.get('REDDIT_USER_AGENT', '').strip() or USER_AGENT, 'Accept': 'application/json'}
    if token:
        url = 'https://oauth.reddit.com' + parts.path + ('?' + parts.query if parts.query else '')
        headers['Authorization'] = 'Bearer ' + token
    return _open_json(Request(url, headers=headers))


def fetch_source(year: int, month: int, *, source_url=None, fetch_json=None,
                 source_mode='auto', fetch_feed=None, feed_file=None) -> tuple[str, dict]:
    credentials = any(os.environ.get(name, '').strip() for name in
                      ('REDDIT_ACCESS_TOKEN', 'REDDIT_CLIENT_ID', 'REDDIT_CLIENT_SECRET', 'REDDIT_REFRESH_TOKEN'))
    rss = source_mode == 'rss' or (source_mode == 'auto' and not credentials and fetch_json is None)
    if feed_file or rss:
        from scripts.collect_months import DEFAULT_FEED, fetch_feed as get_feed, parse_feed
        slug = f'{year:04d}-{month:02d}'
        if feed_file:
            path = Path(feed_file)
            if path.stat().st_size > MAX_RESPONSE:
                raise ValueError('Saved RSS feed exceeds the 2 MiB limit.')
            blob = path.read_bytes()
        else:
            blob = (fetch_feed or get_feed)(DEFAULT_FEED)
        posts = parse_feed(blob, feed_url=DEFAULT_FEED, start_month=slug, end_month=slug,
                           source_url=source_url)
        if not posts:
            raise NotPublished(f'No {slug} monthly post found in the public RSS feed. '
                               'Use --input for a saved paste, or --source-mode api with approved credentials.')
        if len(posts) != 1:
            raise ValueError('RSS monthly post discovery is ambiguous; select --url explicitly.')
        post = posts[0]
        url = canonical_url(post['source_url'])
        if source_url and urlsplit(url).path.split('/')[4] != urlsplit(canonical_url(source_url)).path.split('/')[4]:
            raise ValueError('RSS source does not match the requested post ID.')
        if not _monthly_title(post['title'], year, month):
            raise ValueError('RSS source title month/year does not match the request.')
        return post['text'], {'url': url, 'post_id': urlsplit(url).path.split('/')[4], 'title': post['title'],
            'method': post['method'], 'published': post['published'], 'updated': post['updated'],
            'feed_url': post['feed_url'], 'body_format': 'feed HTML converted to text', '_source_html': post['html']}
    fetch = fetch_json or request_json
    if source_url:
        url = canonical_url(source_url)
    else:
        query = urlencode({'q': f'title:"{calendar.month_name[month]} {year}"',
                           'restrict_sr': 'on', 'sort': 'new', 'limit': 100,
                           'raw_json': 1, 'type': 'link'})
        selected = select_post(fetch('https://www.reddit.com/r/orangetheory/search.json?' + query),
                               year, month)
        url = canonical_url('https://www.reddit.com' + selected.get('permalink', ''))
    payload = _posts(fetch(url.rstrip('/') + '.json?raw_json=1&limit=1'))
    if len(payload) != 1:
        raise ValueError('Reddit did not return exactly one source post.')
    post = verify_post(payload[0], year, month)
    verified_url = canonical_url('https://www.reddit.com' + post['permalink'])
    if urlsplit(url).path.split('/')[4].lower() != post['id'].lower():
        raise ValueError('Returned post ID does not match the selected source URL.')
    raw = post['title'].strip() + '\n\n' + post['selftext']
    return raw, {'url': verified_url, 'post_id': post['id'], 'title': post['title'],
                 'created_utc': post.get('created_utc'), 'edited_utc': post.get('edited') or None,
                 'method': 'reddit-json'}


def _save_report(directory: Path, report: dict) -> ReviewResult:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    lines = [f'# {report["month"]}: {report["status"]}', '',
             'Review artifacts only. Canonical schedules and accepted posters were not changed.', '']
    if report.get('source', {}).get('url'):
        lines += ['Source: ' + report['source']['url'], '']
    updated = report.get('source', {}).get('updated') or report.get('source', {}).get('edited_utc')
    if updated:
        lines += ['Source updated: ' + str(updated), '']
    lines += ['## Schedule changes', ''] + ['- ' + item for item in report.get('semantic_changes', [])]
    if report.get('conflicts'):
        lines += ['', '## Manual edits requiring review', '']
        lines += ['- ' + item['path'] + ': ' + item['message'] for item in report['conflicts']]
    for issue in report['issues']:
        lines.append(f'- {issue["severity"]}: {issue["message"]}')
    if not report['issues']:
        lines.append('No parser or validation issues detected. Review the preview against the source.')
    lines += ['', 'Recognized schedule dates: ' + ', '.join(map(str, report.get('recognized_days', []))),
              'Inferred Standard dates: ' + ', '.join(map(str, report.get('inferred_days', []))), '']
    (directory / 'report.md').write_text('\n'.join(lines), encoding='utf-8')
    healthy = report['status'] in {'ready', 'changed', 'not-published'} or (
        report['status'] == 'unchanged' and report.get('review_status', 'ready') == 'ready')
    return ReviewResult(directory, report['status'], 0 if healthy else 1)


def _render_png(html_path, png_path, browser_channel):
    try:
        from otfposter import render
        if browser_channel is None:
            return render.render_png(html_path, png_path)
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel=browser_channel)
            page = browser.new_page(viewport={'width': 1200, 'height': 1700}, device_scale_factor=2)
            page.goto(html_path.resolve().as_uri())
            page.evaluate('document.fonts.ready')
            page.locator('.poster').screenshot(path=str(png_path))
            browser.close()
    except Exception:
        raise RuntimeError('PNG screenshot failed. Check the installed Playwright browser '
                           'or use --browser-channel chrome; review HTML remains available.') from None


def _write_exports(candidate, directory, *, png=False, browser_channel=None, visual_check=False):
    from otfposter import exports, render
    (directory / 'poster.html').write_text(render.render_html(candidate, allow_fetch=False), encoding='utf-8')
    for layout in ('phone', 'social'):
        (directory / f'{layout}.html').write_text(exports.compact_html(candidate, layout)['html'], encoding='utf-8')
    (directory / 'calendar.ics').write_bytes(exports.calendar_file(candidate).encode('utf-8'))
    if visual_check:
        from scripts.review_visuals import run_visual_review
        visual = run_visual_review(directory, browser_channel=browser_channel)
        if visual.get('errors') or visual.get('status') in {'error', 'failed'}:
            raise RuntimeError('Visual review found issues; inspect visual-report.json and the contact sheet.')
    elif png:
        _render_png(directory / 'poster.html', directory / 'poster.png', browser_channel)


def _trusted_baseline(slug, previous):
    path = ROOT / 'schedules/baselines' / f'{slug}.json'
    if path.exists():
        return Month.load(path).to_dict()
    if previous.get('merge_base'):
        return previous['merge_base']
    raw = ROOT / 'schedules/raw' / f'{slug}.txt'
    if raw.exists():
        imported, report = parse(raw.read_text(encoding='utf-8'))
        if imported.slug == slug and report.clean and report.recognized_days and not validate.check(imported):
            return imported.to_dict()
    return None


def _generated_files(directory):
    for name in ('candidate.json', 'imported.json', 'changes.diff', 'poster.html', 'phone.html',
                 'social.html', 'calendar.ics', 'poster.png', 'phone.png', 'social.png',
                 'contact-sheet.png', 'index.html', 'visual-report.json', 'report.json', 'report.md'):
        (directory / name).unlink(missing_ok=True)


def run_review(*, year: int, month: int, output: Path, input_path: Path | None = None,
               source_url: str | None = None, fetch_json=None, png: bool = False,
               browser_channel: str | None = None, state_root: Path | None = None,
               fetch_only: bool = False, visual_check: bool = False, source_meta=None,
               source_mode='auto', fetch_feed=None, feed_file=None) -> ReviewResult:
    slug = f'{year:04d}-{month:02d}'
    # The requested month remains a namespace even when callers share --out.
    review_root = Path(output) / slug
    now = datetime.now(timezone.utc)
    directory = review_root / ('error-' + now.strftime('%Y%m%dT%H%M%S%fZ'))
    report = {'month': slug, 'status': 'error', 'checked_at': now.isoformat(), 'source': {},
              'issues': [], 'recognized_days': [], 'inferred_days': [], 'conflicts': [], 'semantic_changes': []}
    prepared = False
    try:
        previous = state.load_state(state_root, slug) if state_root else {}
        if previous.get('review_path') and not (Path(output) / previous['review_path']).resolve().is_relative_to(Path(output).resolve()):
            raise ValueError('Cached review path is outside the review output root; preserve state and use a new --state-root.')
        if input_path is not None:
            path = Path(input_path)
            if path.stat().st_size > MAX_RESPONSE:
                raise ValueError('Saved paste exceeds the 2 MiB limit.')
            text = path.read_text(encoding='utf-8-sig')
            source = source_meta or {'method': 'saved-paste', 'url': canonical_url(source_url) if source_url else ''}
        else:
            text, source = fetch_source(year, month, source_url=source_url or previous.get('pinned_url'),
                fetch_json=fetch_json, source_mode=source_mode, fetch_feed=fetch_feed, feed_file=feed_file)
        digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
        directory = review_root / digest[:16]
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'source.txt').write_text(text, encoding='utf-8')
        if '_source_html' in source:
            original_html = source.pop('_source_html')
            (directory / 'source-original.html').write_text(original_html, encoding='utf-8')
            source['html_sha256'] = hashlib.sha256(original_html.encode('utf-8')).hexdigest()
        source.update(sha256=digest, retrieved_at=now.isoformat())
        report['source'] = source
        (directory / 'provenance.json').write_text(json.dumps(source, indent=2) + '\n', encoding='utf-8')
        if state_root and source.get('url'):
            previous.update(pinned_url=source['url'], checked_at=now.isoformat())
            state.save_state(state_root, slug, previous)
        header = '\n'.join(text.strip().splitlines()[:3])
        if month_hint(header) != (year, month):
            raise ValueError('Saved/source header month/year does not match the requested month; '
                             'include the original monthly post title.')
        imported, parsed = parse(text)
        if (imported.year, imported.month) != (year, month):
            raise ValueError('Parsed month/year does not match the requested month.')
        imported.source_url = source.get('url', '')
        canonical = ROOT / 'schedules' / f'{slug}.json'
        saved = Month.load(canonical).to_dict() if canonical.exists() else None
        base = _trusted_baseline(slug, previous)
        incoming = imported.to_dict()
        merged, conflicts = state.merge_schedule(base, incoming, saved)
        candidate = Month.from_dict(merged)
        report['conflicts'] = conflicts
        report['semantic_changes'] = state.semantic_changes(previous.get('last_import') or base, incoming)
        options = {'png': png, 'visual_check': visual_check, 'canonical_sha': state.file_hash(canonical),
                   'origin': source.get('url', ''), 'parser_findings': {
                       'clean': parsed.clean, 'notes': parsed.render(),
                       'recognized_days': parsed.recognized_days, 'inferred_days': parsed.inferred_days}}
        signature = state.fingerprint(incoming, saved, state.generator_hash(ROOT), options)
        report['fingerprint'] = signature
        prior_directory = Path(output) / previous.get('review_path', '__missing__')
        required = ['candidate.json', 'imported.json', 'poster.html', 'phone.html', 'social.html', 'calendar.ics']
        if png:
            required += ['poster.png']
        if visual_check:
            required += ['visual-report.json', 'contact-sheet.png', 'phone.png', 'social.png', 'index.html']
        if (state_root and signature == previous.get('fingerprint')
                and previous.get('review_status') in {'ready', 'review-required'}
                and all((prior_directory / name).is_file() for name in required)):
            if prior_directory.resolve() != directory.resolve():
                for name in required:
                    shutil.copy2(prior_directory / name, directory / name)
            report.update(status='unchanged', review_status=previous['review_status'],
                          issues=previous.get('issues', []), recognized_days=parsed.recognized_days,
                          inferred_days=parsed.inferred_days)
            previous.update(source_sha=digest, checked_at=now.isoformat(), review_path=str(directory.relative_to(output)))
            state.save_state(state_root, slug, previous)
            return _save_report(directory, report)
        _generated_files(directory)
        prepared = True
        imported.save(directory / 'imported.json')
        candidate.save(directory / 'candidate.json')
        original = canonical.read_text(encoding='utf-8') if canonical.exists() else ''
        candidate_json = (directory / 'candidate.json').read_text(encoding='utf-8')
        (directory / 'changes.diff').write_text(''.join(difflib.unified_diff(
            original.splitlines(keepends=True), candidate_json.splitlines(keepends=True),
            fromfile=f'saved/{slug}.json', tofile='candidate.json')), encoding='utf-8')
        report['recognized_days'] = parsed.recognized_days
        report['inferred_days'] = parsed.inferred_days
        if not parsed.recognized_days:
            raise ValueError('No recognized schedule dates; inferred Standard days cannot establish a schedule.')
        if not parsed.clean:
            report['issues'].append({'severity': 'warning', 'source': 'parser', 'message': parsed.render().strip()})
        issues = validate.check(candidate)
        report['issues'].extend({'severity': severity, 'source': 'validation', 'message': message}
                                for severity, message in issues)
        if conflicts:
            report['issues'].append({'severity': 'warning', 'source': 'merge',
                                     'message': f'{len(conflicts)} conflicting manual/source edits require review.'})
        if validate.has_errors(issues):
            return _save_report(directory, report)
        if fetch_only:
            report['status'] = 'changed'
            pending = {'year': year, 'month': month, 'output': str(Path(output).resolve()),
                       'state_root': str(Path(state_root).resolve()) if state_root else None,
                       'source': source, 'png': png, 'visual_check': visual_check}
            (directory / 'pending.json').write_text(json.dumps(pending, indent=2) + '\n', encoding='utf-8')
            return _save_report(directory, report)
        _write_exports(candidate, directory, png=png, browser_channel=browser_channel, visual_check=visual_check)
        report['status'] = 'review-required' if report['issues'] else 'ready'
        if state_root:
            state.save_state(state_root, slug, {'fingerprint': signature, 'review_status': report['status'],
                'review_path': str(directory.relative_to(output)), 'pinned_url': source.get('url', ''),
                'source_sha': digest, 'checked_at': now.isoformat(), 'last_import': incoming,
                'merge_base': base, 'issues': report['issues'], 'last_candidate': candidate.to_dict()})
    except NotPublished as error:
        report['status'] = 'not-published'
        report['issues'].append({'severity': 'info', 'message': str(error)})
    except AuthenticationRequired as error:
        report['status'] = 'authentication-required'
        report['issues'].append({'severity': 'error', 'message': str(error)})
    except HTTPError as error:
        report['status'] = 'authentication-required' if error.code in (401, 403) else 'rate-limited' if error.code == 429 else 'error'
        report['issues'].append({'severity': 'error', 'message':
            f'Reddit HTTP {error.code}; verify approved app credentials/access or retry after rate limiting. '
            'Use --input with a saved monthly post paste.'})
    except URLError:
        report['issues'].append({'severity': 'error', 'message':
            'Could not reach Reddit. Use --input with a saved monthly post paste.'})
    except (ValueError, OSError, TypeError, KeyError, RuntimeError, AttributeError) as error:
        # Credential values never belong in a report, including upstream errors.
        message = str(error)
        for name in ('REDDIT_ACCESS_TOKEN', 'REDDIT_CLIENT_SECRET', 'REDDIT_REFRESH_TOKEN'):
            secret = os.environ.get(name, '')
            if secret:
                message = message.replace(secret, '[redacted]')
        report['issues'].append({'severity': 'error', 'message': message})
    if not prepared:
        _generated_files(directory)
    return _save_report(directory, report)


def resume_review(directory, *, png=None, browser_channel=None, visual_check=None):
    directory = Path(directory)
    pending = json.loads((directory / 'pending.json').read_text(encoding='utf-8'))
    return run_review(year=pending['year'], month=pending['month'], output=Path(pending['output']),
        input_path=directory / 'source.txt', source_meta=pending['source'],
        state_root=Path(pending['state_root']) if pending.get('state_root') else None,
        png=pending['png'] if png is None else png,
        visual_check=pending['visual_check'] if visual_check is None else visual_check,
        browser_channel=browser_channel)


def _month(value):
    if not re.fullmatch(r'20\d{2}-(?:0[1-9]|1[0-2])', value):
        raise argparse.ArgumentTypeError('Use YYYY-MM, for example 2026-11.')
    return tuple(map(int, value.split('-')))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--month', type=_month, help='Exact source month; default current America/New_York month')
    parser.add_argument('--url', help='Exact monthly Reddit post URL')
    parser.add_argument('--source-mode', choices=['auto', 'rss', 'api'], default='auto',
                        help='auto uses public RSS without OAuth credentials, otherwise approved API access')
    parser.add_argument('--feed-file', type=Path, help='Saved complete RSS/Atom feed for offline checks')
    parser.add_argument('--input', type=Path, help='Saved original post text; skips all network requests')
    parser.add_argument('--out', type=Path, help='Review root; month/hash appended (default: build/monthly)')
    parser.add_argument('--png', action='store_true', help='Also screenshot the full poster')
    parser.add_argument('--browser-channel', help='Installed Playwright browser channel, e.g. chrome')
    parser.add_argument('--state-root', type=Path, default=ROOT / 'build/monthly-state', help='Persistent state root')
    parser.add_argument('--fetch-only', action='store_true', help='Fetch/compare without rendering or browser dependencies')
    parser.add_argument('--resume', type=Path, help='Finish one pending directory or every pending check in a manifest')
    parser.add_argument('--visual-check', action='store_true', help='Render all formats and audit actual layout')
    parser.add_argument('--check-next-month', choices=['auto', 'on', 'off'], default='off',
                        help='Also check next month; auto enables this from the 25th')
    args = parser.parse_args(argv)
    output = args.out or ROOT / 'build/monthly'
    results = []
    if args.resume:
        if args.resume.is_file():
            manifest = json.loads(args.resume.read_text(encoding='utf-8'))
            for item in manifest['checks']:
                directory = Path(item['directory'])
                results.append(resume_review(directory, browser_channel=args.browser_channel)
                               if item['status'] == 'changed' else ReviewResult(directory, item['status'], item['exit_code']))
        else:
            results = [resume_review(args.resume, browser_channel=args.browser_channel)]
    else:
        from datetime import date
        if args.month:
            today = date.today()
        else:
            from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
            try:
                today = datetime.now(ZoneInfo('America/New_York')).date()
            except ZoneInfoNotFoundError:
                parser.error('America/New_York timezone data is unavailable; pass --month YYYY-MM.')
        if args.month:
            year, month = args.month
            selected = date(year, month, today.day if (year, month) == (today.year, today.month) else 1)
        else:
            selected = today
        if args.input and args.check_next_month != 'off':
            parser.error('--input reads one month; use --check-next-month off.')
        feed_cache = {}
        def shared_feed(url):
            if url not in feed_cache:
                from scripts.collect_months import fetch_feed
                for attempt in range(3):
                    try:
                        feed_cache[url] = fetch_feed(url)
                        break
                    except HTTPError as error:
                        if error.code != 429 or attempt == 2:
                            raise
                        try:
                            wait = float(error.headers.get('Retry-After', 2 ** attempt))
                        except (ValueError, TypeError, AttributeError):
                            wait = 2 ** attempt
                        if not 0 <= wait <= 30:
                            raise
                        time.sleep(wait)
            return feed_cache[url]
        for year, month in state.months_to_check(selected, args.check_next_month):
            results.append(run_review(year=year, month=month, output=output,
                input_path=args.input, source_url=args.url if (year, month) == (selected.year, selected.month) else None,
                png=args.png, browser_channel=args.browser_channel, state_root=args.state_root,
                fetch_only=args.fetch_only, visual_check=args.visual_check,
                source_mode=args.source_mode, fetch_feed=shared_feed, feed_file=args.feed_file))
    checks = []
    for result in results:
        report = json.loads((result.directory / 'report.json').read_text(encoding='utf-8'))
        checks.append({'directory': str(result.directory.resolve()), 'status': result.status,
                       'exit_code': result.exit_code, 'month': report['month']})
        print(f'{result.status}: {result.directory / "report.md"}')
    output.mkdir(parents=True, exist_ok=True)
    manifest = output / 'manifest.json'
    manifest.write_text(json.dumps({'version': 1, 'checks': checks}, indent=2) + '\n', encoding='utf-8')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as handle:
            handle.write('changed=' + str(any(item['status'] == 'changed' for item in checks)).lower() + '\n')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as handle:
            for result in results:
                handle.write((result.directory / 'report.md').read_text(encoding='utf-8') + '\n\n')
            handle.write('Download the **monthly-post-review** artifact for preview images and source evidence.\n')
    return max((result.exit_code for result in results), default=0)


if __name__ == '__main__':
    raise SystemExit(main())
