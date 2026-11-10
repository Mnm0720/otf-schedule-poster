"""Bounded full-post RSS collection and historical parser replay."""
import hashlib
import json
from pathlib import Path

import pytest

from scripts import collect_months as corpus

URL = "https://www.reddit.com/r/orangetheory/comments/abc123/january_2025_monthly_highlights/"
FEED_URL = "https://www.reddit.com/r/orangetheory/search.rss?q=monthly&restrict_sr=on"
BODY = ('<h1>Welcome to the January 2025 Monthly Thread!</h1>'
        '<p>Key Dates for The Month</p><ul>'
        '<li><strong>January 2 (Thursday)</strong>: 1 Mile; benchmark.</li>'
        '<li>Run/Rows on 1/3, 1/19.</li>'
        '<li>Repeat templates are as follows: 1/19 = 1/3.</li></ul>'
        '<p>Resources for New Members and Everyone Else</p>')


def atom(*, title='January 2025 Monthly Highlights', url=URL, body=BODY, tag='content'):
    import html
    return (f'<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
            f'<id>t3_abc123</id><title>{html.escape(title)}</title>'
            f'<link rel="alternate" href="{url}"/><author><name>/u/mod</name></author>'
            f'<published>2025-01-01T00:00:00Z</published><updated>2025-01-02T00:00:00Z</updated>'
            f'<{tag} type="html">{html.escape(body)}</{tag}></entry></feed>').encode()


def test_atom_preserves_title_month_structure_and_provenance():
    posts = corpus.parse_feed(atom(), feed_url=FEED_URL)
    assert len(posts) == 1
    post = posts[0]
    assert post['month'] == '2025-01' and post['source_url'] == URL
    assert post['title'] == 'January 2025 Monthly Highlights'
    assert post['author'] == '/u/mod' and post['published'] == '2025-01-01T00:00:00Z'
    assert post['html'] == BODY and post['method'] == 'reddit-atom'
    assert '# Welcome to the January 2025 Monthly Thread!' in post['text']
    assert '* January 2 (Thursday): 1 Mile; benchmark.' in post['text']
    assert '* Run/Rows on 1/3, 1/19.' in post['text']
    assert post['sha256'] == hashlib.sha256(post['text'].encode()).hexdigest()


def test_rss_content_encoded_and_linebreaks_are_full_posts():
    import html
    blob = ('<rss xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><item>'
            '<title>January 2025 - Monthly Post</title><link>' + URL + '</link>'
            '<content:encoded>' + html.escape(BODY.replace('</li>', '<br/>Keep this note</li>'))
            + '</content:encoded></item></channel></rss>').encode()
    posts = corpus.parse_feed(blob, feed_url=FEED_URL)
    assert posts[0]['method'] == 'reddit-rss'
    assert 'Keep this note' in posts[0]['text']


@pytest.mark.parametrize('blob,message', [
    (b'<feed>', 'XML'),
    (b'<!DOCTYPE feed [<!ENTITY x "bad">]><feed/>', 'DTD'),
    (b'x' * (2 * 1024 * 1024 + 1), '2 MiB'),
], ids=['malformed', 'dtd', 'oversized'])
def test_invalid_xml_is_rejected(blob, message):
    with pytest.raises(ValueError, match=message):
        corpus.parse_feed(blob, feed_url=FEED_URL)


@pytest.mark.parametrize('url', ['https://evil.test/r/orangetheory/comments/abc123/x/',
                               'https://www.reddit.com/r/other/comments/abc123/x/'])
def test_wrong_post_origin_is_rejected(url):
    with pytest.raises(ValueError, match='orangetheory'):
        corpus.parse_feed(atom(url=url), feed_url=FEED_URL)


def test_summary_snippets_are_rejected_and_other_titles_ignored():
    with pytest.raises(ValueError, match='full'):
        corpus.parse_feed(atom(tag='summary'), feed_url=FEED_URL)
    assert corpus.parse_feed(atom(title='Daily Workout January 2025'), feed_url=FEED_URL) == []


def test_duplicate_months_cannot_choose_a_post_silently():
    one = atom().decode()
    second = one.replace('abc123', 'def456').split('<entry>')[1].split('</entry>')[0]
    with pytest.raises(ValueError, match='ambiguous'):
        corpus.parse_feed(one.replace('</feed>', '<entry>' + second + '</entry></feed>').encode(), feed_url=FEED_URL)


def test_explicit_post_id_resolves_month_ambiguity_and_missing_target_is_empty():
    one = atom().decode()
    second = one.replace('abc123', 'def456').split('<entry>')[1].split('</entry>')[0]
    blob = one.replace('</feed>', '<entry>' + second + '</entry></feed>').encode()
    assert corpus.parse_feed(blob, feed_url=FEED_URL, source_url=URL)[0]['source_url'] == URL
    assert corpus.parse_feed(blob, feed_url=FEED_URL, source_url=URL.replace('abc123', 'missing')) == []


def test_configured_user_agent_is_used_without_printing_credentials(monkeypatch):
    import io
    seen = []
    class Response(io.BytesIO):
        headers = {'Content-Type': 'application/atom+xml; charset=UTF-8'}
    class Opener:
        def open(self, request, timeout):
            seen.append(request)
            return Response(atom())
    monkeypatch.setenv('REDDIT_USER_AGENT', 'test-approved-reader/1.0')
    monkeypatch.setattr(corpus, 'build_opener', lambda *args: Opener())
    assert corpus.fetch_feed(FEED_URL) == atom()
    assert seen[0].get_header('User-agent') == 'test-approved-reader/1.0'


@pytest.mark.parametrize('slug', ['2024-06', '2025-12'])
def test_real_source_month_cannot_be_relabelled_as_a_different_fixture(tmp_path, slug):
    original = Path(__file__).parent / 'fixtures/monthly' / (slug + '.json')
    post = json.loads(original.read_text(encoding='utf-8'))
    post['month'] = '2023-01'
    corpus.save_post(post, tmp_path)
    report = corpus.replay_corpus(tmp_path)
    assert report['results'][0]['status'] == 'error'
    assert 'expected 2023-01' in report['results'][0]['error']


def test_saved_sources_are_idempotent_and_changed_source_needs_review(tmp_path):
    post = corpus.parse_feed(atom(), feed_url=FEED_URL)[0]
    path = corpus.save_post(post, tmp_path)
    before = path.read_bytes()
    assert corpus.save_post(post, tmp_path) == path and path.read_bytes() == before
    changed = {**post, 'text': post['text'] + '\nchanged', 'sha256': 'new'}
    with pytest.raises(ValueError, match='changed'):
        corpus.save_post(changed, tmp_path)
    assert path.read_bytes() == before


def test_replay_records_real_parser_failures_without_changing_sources(tmp_path):
    post = corpus.parse_feed(atom(), feed_url=FEED_URL)[0]
    good = corpus.save_post(post, tmp_path)
    bad = {**post, 'month': '2024-01', 'title': 'January 2024 Monthly Highlights',
           'text': 'January 2024 Monthly Highlights\nNo recognizable workout data here.'}
    corpus.save_post(bad, tmp_path)
    before = good.read_bytes()
    report = corpus.replay_corpus(tmp_path)
    assert report['months'] == 2 and report['years'] == {'2024': 1, '2025': 1}
    rows = {row['month']: row for row in report['results']}
    assert rows['2025-01']['recognized_days'] and rows['2025-01']['status'] == 'clean'
    assert rows['2024-01']['status'] == 'error'
    assert good.read_bytes() == before


def test_html_conversion_preserves_decimals_unicode_and_escaped_text():
    html = '<h2>Key Dates</h2><ul><li><b>November 5</b>: .25 Mile; benchmark.<br>3G-style &amp; more</li></ul>'
    text = corpus.html_to_markdown(html)
    assert '## Key Dates' in text and '* November 5: .25 Mile; benchmark.' in text
    assert '3G-style & more' in text
    assert '<b>' not in text


def test_tampered_and_corrupt_fixtures_are_reported_without_aborting_other_months(tmp_path):
    post = corpus.parse_feed(atom(), feed_url=FEED_URL)[0]
    path = corpus.save_post(post, tmp_path)
    post['text'] += '\nTampered after collection.'
    path.write_text(json.dumps(post), encoding='utf-8')
    (tmp_path / '2024-01.json').write_text('{broken', encoding='utf-8')
    report = corpus.replay_corpus(tmp_path)
    assert report['months'] == 2 and report['errors'] == 2
    assert all(row.get('error') for row in report['results'])
    assert any('hash' in row['error'].lower() for row in report['results'])


def test_real_corpus_has_unique_complete_sources_and_exact_month_provenance():
    fixture_dir = Path(__file__).parent / 'fixtures/monthly'
    posts = [json.loads(path.read_text(encoding='utf-8')) for path in fixture_dir.glob('20??-??.json')]
    assert len(posts) >= 40
    assert len({post['sha256'] for post in posts}) == len(posts)
    assert {post['month'][:4] for post in posts} >= {'2020', '2021', '2022', '2023', '2024', '2025', '2026'}
    for post in posts:
        assert len(post['html']) > 1000 and len(post['text']) > 1000
        assert post['sha256'] == hashlib.sha256(post['text'].encode()).hexdigest()
        assert post['source_url'].startswith('https://www.reddit.com/r/orangetheory/comments/')
        assert post['title'] in post['text'] and post['published']


def test_html_report_escapes_source_text_and_rejects_script_links():
    report = {'months': 1, 'years': {'2025': 1}, 'clean': 0, 'review_required': 1, 'errors': 0,
              'results': [{'month': '2025-01', 'status': 'review-required',
                           'source_url': 'javascript:alert(1)', 'recognized_days': [2], 'inferred_days': [1, 3],
                           'parser_warnings': ['<img src=x onerror=alert(1)>'],
                           'validation': [('warning', 'Check "source" & dates')],
                           'unknown_templates': [], 'unparsed': []}]}
    html = corpus.report_html(report)
    assert '<img src=x' not in html and '&lt;img src=x onerror=alert(1)&gt;' in html
    assert 'href="javascript:' not in html
    assert 'Check &quot;source&quot; &amp; dates' in html
    assert '2025-01' in html and 'review-required' in html
