"""Monthly checks use frozen source/API responses, never a live network."""
import json
import io
from pathlib import Path
from urllib.error import HTTPError

import pytest

from scripts import check_monthly as monthly


ROOT = Path(__file__).resolve().parents[1]
TEXT = (ROOT / 'schedules/raw/2026-10.txt').read_text(encoding='utf-8')
URL = 'https://www.reddit.com/r/orangetheory/comments/abc123/october_2026_monthly_thread/'


def post(**overrides):
    data = dict(id='abc123', title='October 2026 - Monthly Thread',
                subreddit='orangetheory', selftext=TEXT, is_self=True,
                permalink='/r/orangetheory/comments/abc123/october_2026_monthly_thread/',
                created_utc=1790812800, edited=False)
    data.update(overrides)
    return data


def listing(*posts):
    return {'kind': 'Listing', 'data': {'children': [{'kind': 't3', 'data': p} for p in posts]}}


def test_discovery_excludes_other_years_and_daily_threads():
    payload = listing(post(title='October 2025 - Monthly Thread'),
                      post(title='Daily Workout October 2026'), post())
    assert monthly.select_post(payload, 2026, 10)['id'] == 'abc123'


def test_discovery_rejects_ambiguity_and_missing_posts():
    with pytest.raises(ValueError, match='ambiguous'):
        monthly.select_post(listing(post(), post(id='def456')), 2026, 10)
    with pytest.raises(ValueError, match='No.*monthly'):
        monthly.select_post(listing(post(title='November 2026 - Monthly Thread')), 2026, 10)


@pytest.mark.parametrize('changes', [dict(subreddit='other'), dict(title='October 2025 - Monthly Thread'),
                                      dict(selftext='[removed]'), dict(selftext=''), dict(is_self=False)])
def test_rejects_unusable_or_wrong_source(changes):
    with pytest.raises(ValueError):
        monthly.verify_post(post(**changes), 2026, 10)


@pytest.mark.parametrize('url', ['https://evil.test/r/orangetheory/comments/abc123/',
                               'https://www.reddit.com/r/other/comments/abc123/',
                               'https://www.reddit.com@evil.test/r/orangetheory/comments/abc123/',
                               'http://www.reddit.com/r/orangetheory/comments/abc123/'])
def test_url_validation(url):
    with pytest.raises(ValueError):
        monthly.canonical_url(url)


def test_offline_review_preserves_source_and_canonical_files(tmp_path):
    source = tmp_path / 'paste.txt'; source.write_text(TEXT, encoding='utf-8')
    before = (ROOT / 'schedules/2026-10.json').read_bytes()
    result = monthly.run_review(year=2026, month=10, output=tmp_path / 'reviews',
                                input_path=source, source_url=URL)
    assert result.status == 'ready' and result.exit_code == 0
    assert (ROOT / 'schedules/2026-10.json').read_bytes() == before
    assert (result.directory / 'source.txt').read_text(encoding='utf-8') == TEXT
    candidate = json.loads((result.directory / 'candidate.json').read_text())
    assert candidate['source_url'] == URL
    assert URL in (result.directory / 'poster.html').read_text(encoding='utf-8')
    for name in ('phone.html', 'social.html', 'calendar.ics', 'changes.diff', 'report.md'):
        assert (result.directory / name).exists()
    report = json.loads((result.directory / 'report.json').read_text())
    assert report['source']['sha256'] and report['recognized_days'] and report['inferred_days']
    again = monthly.run_review(year=2026, month=10, output=tmp_path / 'reviews', input_path=source)
    assert again.directory == result.directory
    source.write_text(TEXT + '\nUpdated source.\n', encoding='utf-8')
    changed = monthly.run_review(year=2026, month=10, output=tmp_path / 'reviews', input_path=source)
    assert changed.directory != result.directory


def test_offline_month_mismatch_is_not_overridden(tmp_path):
    source = tmp_path / 'paste.txt'; source.write_text(TEXT, encoding='utf-8')
    result = monthly.run_review(year=2026, month=11, output=tmp_path / 'reviews', input_path=source)
    assert result.exit_code != 0 and result.status == 'error'
    assert 'month' in (result.directory / 'report.md').read_text().lower()
    assert not (result.directory / 'poster.html').exists()


def test_unknown_workout_requires_review_and_keeps_preview(tmp_path):
    source = tmp_path / 'paste.txt'
    source.write_text(TEXT + '\n* Turbo Blocks on 10/1.\n', encoding='utf-8')
    result = monthly.run_review(year=2026, month=10, output=tmp_path / 'reviews', input_path=source)
    assert result.status == 'review-required' and result.exit_code != 0
    assert (result.directory / 'poster.html').exists()
    assert 'Turbo Blocks' in (result.directory / 'candidate.json').read_text()


def test_all_inferred_days_are_not_ready(tmp_path):
    source = tmp_path / 'paste.txt'
    source.write_text('October 2026 - Monthly Thread\nKey Dates for The Month\n'
                      'REGARDING STRENGTH 50\nNo schedule yet.', encoding='utf-8')
    result = monthly.run_review(year=2026, month=10, output=tmp_path / 'reviews', input_path=source)
    assert result.status == 'error' and result.exit_code != 0
    assert not (result.directory / 'poster.html').exists()


def test_validation_errors_block_rendering(tmp_path):
    source = tmp_path / 'paste.txt'
    source.write_text(TEXT + '\n* Repeat templates are as follows: 10/1 = 10/31.\n', encoding='utf-8')
    result = monthly.run_review(year=2026, month=10, output=tmp_path / 'reviews', input_path=source)
    assert result.status == 'error' and result.exit_code != 0
    assert (result.directory / 'candidate.json').exists()
    assert not (result.directory / 'poster.html').exists()


def test_discovery_fetches_selected_post_again(tmp_path):
    calls = []
    def fetch(url):
        calls.append(url)
        return listing(post()) if 'search.json' in url else [listing(post()), listing()]
    result = monthly.run_review(year=2026, month=10, output=tmp_path / 'reviews', fetch_json=fetch)
    assert result.status == 'ready'
    assert len(calls) == 2 and '/comments/abc123/' in calls[1]


@pytest.mark.parametrize('code', [403, 429])
def test_http_failure_retains_paste_fallback_diagnostics(tmp_path, code):
    def fetch(url):
        raise HTTPError(url, code, 'blocked', {}, None)
    result = monthly.run_review(year=2026, month=10, output=tmp_path / 'reviews', fetch_json=fetch)
    assert result.status == {403: 'authentication-required', 429: 'rate-limited'}[code] and result.exit_code != 0
    report = (result.directory / 'report.md').read_text()
    assert str(code) in report and '--input' in report


def test_cli_rejects_invalid_month_and_networkless_input_works(tmp_path):
    with pytest.raises(SystemExit):
        monthly.main(['--month', '2026-13'])
    source = tmp_path / 'paste.txt'; source.write_text(TEXT, encoding='utf-8')
    assert monthly.main(['--month', '2026-10', '--input', str(source), '--out', str(tmp_path / 'out')]) == 0


@pytest.mark.parametrize('content_type,body,message', [
    ('text/html', b'<html>Log in</html>', 'login/block'),
    ('application/json', b'not JSON', 'invalid JSON'),
    ('application/json', b'x' * (monthly.MAX_RESPONSE + 1), '2 MiB')], ids=['html-block', 'malformed', 'oversized'])
def test_http_boundary_rejects_block_pages_invalid_and_oversized_json(monkeypatch, content_type, body, message):
    class Response(io.BytesIO):
        headers = {'Content-Type': content_type}
    class Opener:
        def open(self, request, timeout):
            assert timeout == 30
            return Response(body)
    monkeypatch.setattr(monthly, 'build_opener', lambda *args: Opener())
    with pytest.raises(ValueError, match=message):
        monthly.request_json('https://www.reddit.com/r/orangetheory/search.json')


def test_bearer_is_sent_only_to_oauth_host_and_not_saved(tmp_path, monkeypatch):
    calls = []
    class Response(io.BytesIO):
        headers = {'Content-Type': 'application/json'}
    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            return Response(json.dumps([listing(post()), listing()]).encode())
    monkeypatch.setenv('REDDIT_ACCESS_TOKEN', 'secret-test-token')
    monkeypatch.setattr(monthly, 'build_opener', lambda *args: Opener())
    result = monthly.run_review(year=2026, month=10, output=tmp_path / 'reviews', source_url=URL)
    assert result.status == 'ready'
    assert calls[0].full_url.startswith('https://oauth.reddit.com/')
    assert calls[0].get_header('Authorization') == 'Bearer secret-test-token'
    assert all('secret-test-token' not in path.read_text(encoding='utf-8')
               for path in result.directory.iterdir() if path.is_file())


def test_failed_recheck_cannot_leave_previous_ready_exports(tmp_path, monkeypatch):
    source = tmp_path / 'paste.txt'; source.write_text(TEXT, encoding='utf-8')
    first = monthly.run_review(year=2026, month=10, output=tmp_path / 'reviews', input_path=source)
    assert (first.directory / 'poster.html').exists()
    monkeypatch.setattr(monthly.validate, 'check', lambda candidate: [('error', 'Newly detected invalid schedule')])
    second = monthly.run_review(year=2026, month=10, output=tmp_path / 'reviews', input_path=source)
    assert second.directory == first.directory and second.status == 'error'
    assert not (second.directory / 'poster.html').exists()


def test_png_failure_keeps_diagnostic_report(tmp_path, monkeypatch):
    source = tmp_path / 'paste.txt'; source.write_text(TEXT, encoding='utf-8')
    def fail(*args):
        raise RuntimeError('PNG browser unavailable')
    monkeypatch.setattr(monthly, '_render_png', fail)
    result = monthly.run_review(year=2026, month=10, output=tmp_path / 'reviews', input_path=source, png=True)
    assert result.status == 'error' and result.exit_code != 0
    assert 'PNG browser unavailable' in (result.directory / 'report.md').read_text()


def test_wrong_month_recheck_uses_separate_namespace(tmp_path):
    source = tmp_path / 'paste.txt'; source.write_text(TEXT, encoding='utf-8')
    first = monthly.run_review(year=2026, month=10, output=tmp_path / 'reviews', input_path=source)
    second = monthly.run_review(year=2026, month=11, output=tmp_path / 'reviews', input_path=source)
    assert first.directory != second.directory
    assert second.status == 'error' and (first.directory / 'poster.html').exists()


def test_malformed_api_fields_produce_report_instead_of_crashing(tmp_path):
    result = monthly.run_review(year=2026, month=10, output=tmp_path / 'reviews',
                                fetch_json=lambda url: listing(post(subreddit=17, title=[])))
    assert result.status == 'error'
    assert (result.directory / 'report.json').exists()


def test_redirect_cannot_forward_bearer_to_another_host():
    with pytest.raises(ValueError, match='redirected'):
        monthly._NoRedirect().redirect_request(None, None, 302, 'Found', {}, 'https://evil.test/')
