#!/usr/bin/env python3
"""Collect full public monthly posts from Reddit RSS and replay parser coverage."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
from html import escape
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from otfposter.parse import parse  # noqa: E402
from otfposter import validate  # noqa: E402
from scripts.check_monthly import canonical_url, month_hint, _NoRedirect  # noqa: E402

MAX_FEED_BYTES = 2 * 1024 * 1024
DEFAULT_FEED = 'https://www.reddit.com/r/orangetheory/search.rss?' + urlencode({
    'q': 'flair:"Monthly Posts"', 'restrict_sr': 'on', 'sort': 'new', 'limit': 100})
ATOM = '{http://www.w3.org/2005/Atom}'
CONTENT = '{http://purl.org/rss/1.0/modules/content/}'


class _Markdown(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if self.hidden:
            return
        if re.fullmatch('h[1-6]', tag):
            self.parts.append('\n\n' + '#' * int(tag[1]) + ' ')
        elif tag == 'li':
            self.parts.append('\n* ')
        elif tag in ('p', 'div', 'blockquote', 'tr'):
            self.parts.append('\n')
        elif tag == 'br':
            self.parts.append('\n')
        elif tag in ('td', 'th'):
            self.parts.append(' | ')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
            return
        if not self.hidden and (tag in ('li', 'p', 'div', 'tr') or re.fullmatch('h[1-6]', tag)):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def html_to_markdown(html: str) -> str:
    parser = _Markdown()
    parser.feed(html)
    lines = [re.sub(r'[\t \xa0]+', ' ', line).strip() for line in ''.join(parser.parts).splitlines()]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()


def _feed_url(url):
    parts = urlsplit(url)
    if (parts.scheme != 'https' or parts.hostname != 'www.reddit.com'
            or parts.username or parts.password or parts.port not in (None, 443)
            or parts.path not in ('/r/orangetheory/search.rss', '/r/orangetheory/.rss')):
        raise ValueError('Use an HTTPS www.reddit.com/r/orangetheory RSS URL.')
    return url


def fetch_feed(url: str) -> bytes:
    _feed_url(url)
    request = Request(url, headers={
        'User-Agent': (os.environ.get('REDDIT_USER_AGENT', '').strip()
                       or 'otf-schedule-poster/0.1 (historical parser fixtures; read-only)'),
        'Accept': 'application/atom+xml, application/rss+xml, application/xml'})
    with build_opener(_NoRedirect()).open(request, timeout=30) as response:
        content_type = response.headers.get('Content-Type', '').split(';')[0].strip().lower()
        if content_type not in ('application/atom+xml', 'application/rss+xml', 'application/xml', 'text/xml'):
            raise ValueError('RSS returned a non-XML login/block page. Use --feed-file.')
        body = response.read(MAX_FEED_BYTES + 1)
    if len(body) > MAX_FEED_BYTES:
        raise ValueError('RSS exceeds the 2 MiB limit.')
    return body


def parse_feed(blob: bytes, *, feed_url: str, start_month='2000-01', end_month='2099-12',
               source_url=None) -> list[dict]:
    _feed_url(feed_url)
    selected_id = urlsplit(canonical_url(source_url)).path.split('/')[4] if source_url else None
    if len(blob) > MAX_FEED_BYTES:
        raise ValueError('RSS exceeds the 2 MiB limit.')
    if b'\x00' in blob:
        raise ValueError('RSS must be UTF-8 XML; DTD/entity declarations are not supported.')
    if re.search(br'<!\s*(?:DOCTYPE|ENTITY)\b', blob, re.I):
        raise ValueError('DTD/entity declarations are not supported in feeds.')
    try:
        root = ET.fromstring(blob)
    except ET.ParseError as error:
        raise ValueError('Malformed RSS/Atom XML.') from error
    if root.tag == ATOM + 'feed':
        entries, prefix, method = root.findall(ATOM + 'entry'), ATOM, 'reddit-atom'
    elif root.tag == 'rss':
        entries, prefix, method = root.findall('./channel/item'), '', 'reddit-rss'
    else:
        raise ValueError('XML is not an Atom or RSS feed.')
    if len(entries) > 200:
        raise ValueError('RSS has too many entries; limit discovery to 200.')
    posts = {}
    for entry in entries:
        title = entry.findtext(prefix + 'title', '')
        hint = month_hint(title)
        if not hint or not re.search(r'\bmonthly\s+(?:thread|post|highlights)\b', title, re.I):
            continue
        year, month = hint
        slug = f'{year:04d}-{month:02d}'
        if not start_month <= slug <= end_month:
            continue
        if prefix:
            link = next((node.attrib.get('href', '') for node in entry.findall(ATOM + 'link')
                         if node.attrib.get('rel', 'alternate') == 'alternate'), '')
            body = entry.findtext(ATOM + 'content', '')
            author = entry.findtext(ATOM + 'author/' + ATOM + 'name', '')
        else:
            link = entry.findtext('link', '')
            body = entry.findtext(CONTENT + 'encoded', '')
            author = entry.findtext('author', '')
        url = canonical_url(link)
        if selected_id and urlsplit(url).path.split('/')[4] != selected_id:
            continue
        if not body or len(body.strip()) < 120:
            raise ValueError(f'{slug} RSS entry does not contain a full post; fetch the canonical post instead.')
        text = title + '\n\n' + html_to_markdown(body) + '\n'
        post = {'month': slug, 'title': title, 'source_url': url, 'author': author,
                'published': entry.findtext(prefix + 'published', entry.findtext('pubDate', '')),
                'updated': entry.findtext(prefix + 'updated', ''),
                'feed_url': feed_url, 'method': method, 'html': body, 'text': text,
                'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
                'html_sha256': hashlib.sha256(body.encode('utf-8')).hexdigest(),
                'retrieved_at': datetime.now(timezone.utc).isoformat()}
        if slug in posts and posts[slug]['source_url'] != url:
            raise ValueError(f'{slug} has ambiguous monthly posts in this feed.')
        posts[slug] = post
    return sorted(posts.values(), key=lambda post: post['month'])


def save_post(post: dict, output: Path) -> Path:
    slug = post['month']
    if not re.fullmatch(r'20\d{2}-(?:0[1-9]|1[0-2])', slug):
        raise ValueError('Invalid fixture month.')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    path = output / f'{slug}.json'
    if path.exists():
        previous = json.loads(path.read_text(encoding='utf-8'))
        if (previous['sha256'] != post['sha256'] or previous['source_url'] != post['source_url']
                or previous['html'] != post['html']):
            raise ValueError(f'{slug} source changed; inspect it before replacing the fixture.')
        return path
    path.write_text(json.dumps(post, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return path


def replay_corpus(directory: Path) -> dict:
    rows = []
    years = {}
    for path in sorted(Path(directory).glob('20??-??.json')):
        slug = path.stem
        row = {'month': slug, 'source_url': '', 'method': '',
               'status': 'error', 'recognized_days': [], 'inferred_days': [],
               'unknown_templates': [], 'parser_warnings': [], 'validation': []}
        years[slug[:4]] = years.get(slug[:4], 0) + 1
        try:
            post = json.loads(path.read_text(encoding='utf-8'))
            row.update(source_url=post['source_url'], method=post['method'])
            if post['month'] != slug:
                raise ValueError('Fixture filename and recorded month do not match.')
            digest = hashlib.sha256(post['text'].encode('utf-8')).hexdigest()
            if post['sha256'] != digest:
                raise ValueError('Fixture text hash differs from the collected source.')
            if post.get('html_sha256') and post['html_sha256'] != hashlib.sha256(post['html'].encode('utf-8')).hexdigest():
                raise ValueError('Fixture HTML hash differs from the collected source.')
            month, parsed = parse(post['text'])
            if month.slug != slug:
                raise ValueError(f'Parsed {month.slug}, expected {slug}.')
            row.update(recognized_days=parsed.recognized_days, inferred_days=parsed.inferred_days,
                       unknown_templates=parsed.unknown_templates, parser_warnings=parsed.warnings,
                       unparsed=parsed.unparsed, validation=validate.check(month))
            if not parsed.recognized_days:
                raise ValueError('No recognized workout dates; inferred Standard days cannot establish coverage.')
            row['status'] = ('error' if validate.has_errors(row['validation']) else
                             'clean' if parsed.clean and not row['validation'] else 'review-required')
        except (ValueError, TypeError, KeyError, AttributeError, OSError) as error:
            row['error'] = str(error)
        rows.append(row)
    return {'months': len(rows), 'years': years, 'clean': sum(row['status'] == 'clean' for row in rows),
            'review_required': sum(row['status'] == 'review-required' for row in rows),
            'errors': sum(row['status'] == 'error' for row in rows), 'results': rows}


def report_html(report: dict) -> str:
    """Make a portable, escaped review report with links to the original posts."""
    def text(value):
        return escape(str(value), quote=True)

    coverage = ''.join(f'<tr><td>{text(year)}</td><td>{count}</td></tr>'
                       for year, count in sorted(report['years'].items()))
    index = []
    details = []
    for number, row in enumerate(report['results']):
        slug, status = text(row['month']), text(row['status'])
        identifier = f'month-{number}'
        source = row.get('source_url', '')
        try:
            source = canonical_url(source)
            source_link = f'<a href="{text(source)}" rel="noopener noreferrer">Original Reddit post</a>'
        except ValueError:
            source_link = '<span>Source URL unavailable or invalid</span>'
        recognized, inferred = row.get('recognized_days', []), row.get('inferred_days', [])
        index.append(f'<tr><td><a href="#{identifier}">{slug}</a></td><td>{status}</td>'
                     f'<td>{len(recognized)}</td><td>{len(inferred)}</td><td>{source_link}</td></tr>')
        issues = []
        if row.get('error'):
            issues.append(('error', row['error']))
        issues.extend(('import warning', warning) for warning in row.get('parser_warnings', []))
        issues.extend((severity, message) for severity, message in row.get('validation', []))
        issues.extend(('unknown workout', f'Line {line}: {label}')
                      for line, label in row.get('unknown_templates', []))
        issues.extend(('unparsed line', f'Line {line}: {value}') for line, value in row.get('unparsed', []))
        issue_html = ('<ul>' + ''.join(f'<li><strong>{text(kind)}:</strong> {text(message)}</li>'
                                      for kind, message in issues) + '</ul>' if issues
                      else '<p>No parser or validation issues detected.</p>')
        details.append(f'<section id="{identifier}"><h2>{slug} <span>{status}</span></h2>'
                       f'<p>{source_link}</p><p><strong>Recognized workout dates:</strong> '
                       f'{text(", ".join(map(str, recognized)) or "None")}</p>'
                       f'<p><strong>Inferred Standard dates:</strong> '
                       f'{text(", ".join(map(str, inferred)) or "None")}</p>{issue_html}</section>')
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Historical OTF source review</title><style>'
            'body{font:16px/1.5 system-ui,sans-serif;margin:0;color:#202833;background:#f4f5f7}'
            'header{background:#202833;color:white;padding:28px max(20px,calc((100% - 1100px)/2))}'
            'main{max-width:1100px;margin:24px auto;padding:0 20px}h1{margin:0;font-size:30px}'
            'h2{font-size:22px}h2 span{font-size:15px;font-weight:400}a{color:#1558a5}'
            'table{border-collapse:collapse;background:white;width:100%;font-size:15px}'
            'th,td{text-align:left;padding:10px;border-bottom:1px solid #dce0e6}'
            '.table-wrap{overflow:auto}section{background:white;padding:20px;margin:18px 0;'
            'border:1px solid #dce0e6;border-radius:8px;scroll-margin-top:12px}'
            'li{margin-bottom:10px;overflow-wrap:anywhere}.coverage{max-width:350px}'
            '</style></head><body><header><h1>Historical monthly source review</h1>'
            f'<p>{report["months"]} months: {report["clean"]} clean, '
            f'{report["review_required"]} requiring review, {report["errors"]} with errors.</p></header>'
            '<main><p>Recognized dates have explicit workout entries. Inferred Standard dates '
            'fill gaps in the source. A clean import still needs comparison with its original post.</p>'
            '<h2>Coverage</h2><table class="coverage"><thead><tr><th>Year</th><th>Months</th></tr>'
            f'</thead><tbody>{coverage}</tbody></table><h2>Month index</h2><div class="table-wrap">'
            '<table><thead><tr><th>Month</th><th>Result</th><th>Recognized</th><th>Inferred</th>'
            f'<th>Source</th></tr></thead><tbody>{"".join(index)}</tbody></table></div>'
            + ''.join(details) + '</main></body></html>')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--feed-url', default=DEFAULT_FEED)
    parser.add_argument('--feed-file', type=Path, help='Use cached complete RSS/Atom XML without network access')
    parser.add_argument('--out', type=Path, default=ROOT / 'tests/fixtures/monthly')
    parser.add_argument('--replay-only', action='store_true')
    parser.add_argument('--start-month', default='2000-01')
    parser.add_argument('--end-month', default='2099-12')
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--report', type=Path, default=ROOT / 'build/historical-corpus/report.json')
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.limit <= 100:
            raise ValueError('--limit must be between 1 and 100.')
        if any(not re.fullmatch(r'20\d{2}-(?:0[1-9]|1[0-2])', value)
               for value in (args.start_month, args.end_month)) or args.start_month > args.end_month:
            raise ValueError('Use an ordered YYYY-MM range for --start-month and --end-month.')
        if not args.replay_only:
            if args.feed_file:
                if args.feed_file.stat().st_size > MAX_FEED_BYTES:
                    raise ValueError('RSS exceeds the 2 MiB limit.')
                blob = args.feed_file.read_bytes()
            else:
                blob = fetch_feed(args.feed_url)
            posts = parse_feed(blob, feed_url=args.feed_url, start_month=args.start_month,
                               end_month=args.end_month)[-args.limit:]
            if not posts:
                raise ValueError('No full monthly posts match the requested feed/range.')
            for post in posts:
                save_post(post, args.out)
        report = replay_corpus(args.out)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        args.report.with_suffix('.html').write_text(report_html(report), encoding='utf-8')
        print(json.dumps({key: value for key, value in report.items() if key != 'results'}))
        print(f'Replay report: {args.report}')
        return 0 if report['months'] and not report['errors'] and not report['review_required'] else 1
    except (ValueError, OSError, KeyError) as error:
        print(f'Collection failed: {error}. Respect access/rate limits; use --feed-file for a saved feed.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
