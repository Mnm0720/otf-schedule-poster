"""Behavioral checks for incremental updates and edit-preserving review."""
import copy
import json
import io
from html import escape
import subprocess
import sys
from datetime import date
from pathlib import Path
from urllib.error import HTTPError

import pytest

from scripts import monthly_state as state
from scripts import check_monthly as monthly

ROOT = Path(__file__).resolve().parents[1]
TEXT = (ROOT / 'schedules/raw/2026-10.txt').read_text(encoding='utf-8')


def schedule():
    return {'year': 2026, 'month': 10, 'theme': 'Original', 'credits': 'Default',
            'days': [{'day': 1, 'entries': [{'category': 'runrow', 'title': '', 'raw': 'old prose'}],
                      'repeat_of': None, 'note': '', 'three_g': False}],
            'events': [{'name': 'Challenge', 'start': 4, 'end': 6}]}


def test_three_way_merge_preserves_manual_colors_and_changes_untouched_dates():
    base = schedule(); new = copy.deepcopy(base); edited = copy.deepcopy(base)
    edited['category_styles'] = {'runrow': {'color': '#112233'}}
    edited['credits'] = 'My team'
    new['days'][0]['three_g'] = True
    merged, conflicts = state.merge_schedule(base, new, edited)
    assert not conflicts
    assert merged['days'][0]['three_g'] and merged['credits'] == 'My team'
    assert merged['category_styles'] == edited['category_styles']


def test_three_way_conflicts_keep_manual_value():
    base = schedule(); new = copy.deepcopy(base); edited = copy.deepcopy(base)
    new['days'][0]['note'] = 'Upstream'; edited['days'][0]['note'] = 'Manual'
    merged, conflicts = state.merge_schedule(base, new, edited)
    assert merged['days'][0]['note'] == 'Manual'
    assert conflicts and 'days.1.note' in conflicts[0]['path']


def test_missing_baseline_does_not_overwrite_manual_schedule():
    new = schedule(); edited = copy.deepcopy(new); edited['theme'] = 'Manual'
    merged, conflicts = state.merge_schedule(None, new, edited)
    assert merged == edited and conflicts


def test_semantic_fingerprint_ignores_raw_prose_but_keeps_workouts():
    first = schedule(); second = copy.deepcopy(first)
    second['days'][0]['entries'][0]['raw'] = 'different prose'
    assert state.semantic_hash(first) == state.semantic_hash(second)
    second['days'][0]['three_g'] = True
    assert state.semantic_hash(first) != state.semantic_hash(second)


def test_semantic_summary_reports_workout_repeat_and_event_dates():
    old = schedule(); new = copy.deepcopy(old)
    new['days'][0]['three_g'] = True; new['days'][0]['repeat_of'] = 2
    new['events'][0]['end'] = 8
    changes = state.semantic_changes(old, new)
    assert any('10/1' in value and '3G' in value for value in changes)
    assert any('Repeat' in value for value in changes)
    assert any('Challenge' in value and '8' in value for value in changes)


def test_next_month_check_rolls_year_and_is_limited_to_month_end():
    assert state.months_to_check(date(2026, 12, 28)) == [(2026, 12), (2027, 1)]
    assert state.months_to_check(date(2026, 11, 10)) == [(2026, 11)]


def test_unchanged_source_skips_render_but_missing_artifact_rebuilds(tmp_path, monkeypatch):
    source = tmp_path / 'source.txt'; source.write_text(TEXT, encoding='utf-8')
    kwargs = dict(year=2026, month=10, output=tmp_path / 'out', input_path=source,
                  state_root=tmp_path / 'state')
    first = monthly.run_review(**kwargs)
    assert first.status == 'ready'
    monkeypatch.setattr(monthly, '_write_exports', lambda *a, **k: pytest.fail('unchanged source rendered'))
    second = monthly.run_review(**kwargs)
    assert second.status == 'unchanged'
    (second.directory / 'poster.html').unlink()
    called = []
    monkeypatch.setattr(monthly, '_write_exports', lambda *a, **k: called.append(True))
    monthly.run_review(**kwargs)
    assert called


def test_fetch_only_is_dependency_free_and_resume_uses_pending_source(tmp_path):
    source = tmp_path / 'source.txt'; source.write_text(TEXT, encoding='utf-8')
    result = monthly.run_review(year=2026, month=10, output=tmp_path / 'out', input_path=source,
                                state_root=tmp_path / 'state', fetch_only=True)
    assert result.status == 'changed'
    assert not (result.directory / 'poster.html').exists()
    resumed = monthly.resume_review(result.directory, png=False)
    assert resumed.status == 'ready'


def test_renewable_auth_uses_refresh_token_without_logging_secrets(monkeypatch):
    calls = []
    monkeypatch.setenv('REDDIT_CLIENT_ID', 'approved-app')
    monkeypatch.setenv('REDDIT_CLIENT_SECRET', 'client-secret')
    monkeypatch.setenv('REDDIT_REFRESH_TOKEN', 'refresh-secret')
    def token_exchange(request):
        calls.append(request)
        return {'access_token': 'fresh-access', 'expires_in': 3600}
    assert monthly.obtain_access_token(exchange=token_exchange) == 'fresh-access'
    assert b'grant_type=refresh_token' in calls[0].data
    assert b'refresh-secret' in calls[0].data
    assert calls[0].full_url == 'https://www.reddit.com/api/v1/access_token'


def test_state_does_not_contain_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv('REDDIT_ACCESS_TOKEN', 'never-persist-this')
    source = tmp_path / 'source.txt'; source.write_text(TEXT, encoding='utf-8')
    monthly.run_review(year=2026, month=10, output=tmp_path / 'out', input_path=source,
                       state_root=tmp_path / 'state')
    assert all('never-persist-this' not in p.read_text(encoding='utf-8')
               for p in (tmp_path / 'state').rglob('*.json'))


def feed():
    html = '<div>' + escape(TEXT) + '</div>'
    return ('<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
            '<title>October 2026 - Monthly Thread</title>'
            '<link href="https://www.reddit.com/r/orangetheory/comments/abc123/october_2026_monthly_thread/"/>'
            '<published>2026-10-01T08:00:00Z</published><updated>2026-10-09T09:00:00Z</updated>'
            '<content type="html">' + escape(html) + '</content></entry></feed>').encode()


def test_auto_mode_uses_full_rss_without_api_credentials(tmp_path, monkeypatch):
    for key in ('REDDIT_ACCESS_TOKEN', 'REDDIT_CLIENT_ID', 'REDDIT_CLIENT_SECRET', 'REDDIT_REFRESH_TOKEN'):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(monthly, 'request_json', lambda url: pytest.fail('RSS mode used JSON API'))
    result = monthly.run_review(year=2026, month=10, output=tmp_path / 'out', fetch_feed=lambda url: feed())
    assert result.status == 'ready'
    report = json.loads((result.directory / 'report.json').read_text())
    assert report['source']['method'] == 'reddit-atom'
    assert report['source']['updated'] == '2026-10-09T09:00:00Z'
    assert (result.directory / 'source-original.html').exists()


def test_pinned_rss_url_must_match_exact_post_id(tmp_path):
    result = monthly.run_review(year=2026, month=10, output=tmp_path / 'out', source_mode='rss',
        source_url='https://www.reddit.com/r/orangetheory/comments/wrongid/', fetch_feed=lambda url: feed())
    assert result.status == 'not-published'
    assert not (result.directory / 'candidate.json').exists()


def test_source_not_published_has_distinct_nonfailing_state(tmp_path):
    result = monthly.run_review(year=2026, month=11, output=tmp_path / 'out', source_mode='rss',
                                fetch_feed=lambda url: feed())
    assert result.status == 'not-published' and result.exit_code == 0


def test_fetch_only_runs_without_site_packages(tmp_path):
    source = tmp_path / 'source.txt'; source.write_text(TEXT, encoding='utf-8')
    result = subprocess.run([sys.executable, '-S', 'scripts/check_monthly.py', '--month', '2026-10',
        '--input', str(source), '--fetch-only', '--out', str(tmp_path / 'out'),
        '--state-root', str(tmp_path / 'state')], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert 'changed:' in result.stdout


def test_skip_fingerprint_changes_with_generator_and_manual_colors():
    original = schedule(); edited = copy.deepcopy(original)
    edited['category_styles'] = {'runrow': {'color': '#112233'}}
    first = state.fingerprint(original, original, 'generator1', {})
    assert first != state.fingerprint(original, original, 'generator2', {})
    assert first != state.fingerprint(original, edited, 'generator1', {})


def test_renewable_app_only_auth_needs_no_refresh_token(monkeypatch):
    monkeypatch.setenv('REDDIT_CLIENT_ID', 'approved-app')
    monkeypatch.setenv('REDDIT_CLIENT_SECRET', 'client-secret')
    monkeypatch.delenv('REDDIT_REFRESH_TOKEN', raising=False)
    requests = []
    def exchange(request):
        requests.append(request)
        return {'access_token': 'app-only'}
    assert monthly.obtain_access_token(exchange=exchange) == 'app-only'
    assert requests[0].data == b'grant_type=client_credentials'


def test_rate_limit_retry_respects_short_wait_and_is_bounded(monkeypatch):
    attempts, waits = [], []
    class Response(io.BytesIO):
        headers = {'Content-Type': 'application/json'}
    class Opener:
        def open(self, request, timeout):
            attempts.append(True)
            if len(attempts) < 3:
                raise HTTPError(request.full_url, 429, 'rate limit', {'Retry-After': '0.1'}, None)
            return Response(b'{}')
    monkeypatch.setattr(monthly, 'build_opener', lambda *a: Opener())
    monkeypatch.setattr(monthly.time, 'sleep', lambda wait: waits.append(wait))
    monkeypatch.delenv('REDDIT_CLIENT_ID', raising=False)
    monkeypatch.delenv('REDDIT_CLIENT_SECRET', raising=False)
    monkeypatch.delenv('REDDIT_REFRESH_TOKEN', raising=False)
    monthly.request_json('https://www.reddit.com/r/orangetheory/search.json')
    assert len(attempts) == 3 and waits == [0.1, 0.1]


def test_clean_review_stages_patch_and_independent_baseline(tmp_path):
    source = tmp_path / 'source.txt'; source.write_text(TEXT, encoding='utf-8')
    review = tmp_path / 'reviews'
    result = monthly.run_review(year=2026, month=10, output=review, input_path=source)
    manifest = review / 'manifest.json'
    manifest.write_text(json.dumps({'checks': [{'directory': str(result.directory)}]}))
    destination = tmp_path / 'patch'
    assert state.stage_pull_request(manifest, destination) == ['2026-10']
    assert (destination / 'schedules/2026-10.json').exists()
    assert (destination / 'schedules/baselines/2026-10.json').exists()
    assert (destination / 'schedules/raw/2026-10.txt').read_text(encoding='utf-8') == TEXT
    assert (destination / 'pull-request.md').exists()


def test_staging_rejects_artifact_paths_outside_review_root(tmp_path):
    review = tmp_path / 'reviews'; review.mkdir()
    manifest = review / 'manifest.json'
    manifest.write_text(json.dumps({'checks': [{'directory': str(tmp_path / 'outside')}]}))
    with pytest.raises(ValueError, match='outside'):
        state.stage_pull_request(manifest, tmp_path / 'patch')


def test_scheduled_workflow_keeps_writes_in_dispatch_only_job():
    source = (ROOT / '.github/workflows/monthly.yml').read_text()
    assert source.index('Fetch and compare') < source.index('Install pinned render')
    assert "if: steps.fetch.outputs.changed == 'true'" in source
    assert 'inputs.create_draft_pr' in source and 'draft: always-true' in source
    assert 'default: false' in source and 'actions: read' in source


def test_incomplete_renewable_credentials_are_an_authentication_state(tmp_path, monkeypatch):
    monkeypatch.setenv('REDDIT_CLIENT_ID', 'approved-app')
    monkeypatch.delenv('REDDIT_CLIENT_SECRET', raising=False)
    monkeypatch.delenv('REDDIT_ACCESS_TOKEN', raising=False)
    result = monthly.run_review(year=2026, month=10, output=tmp_path / 'out', source_mode='api')
    assert result.status == 'authentication-required'


def test_corrupt_cached_path_cannot_restore_external_files(tmp_path):
    source = tmp_path / 'source.txt'; source.write_text(TEXT, encoding='utf-8')
    root = tmp_path / 'state'; root.mkdir()
    (root / '2026-10.json').write_text(json.dumps({'version': 1, 'review_path': '../../outside'}))
    result = monthly.run_review(year=2026, month=10, output=tmp_path / 'out',
                                input_path=source, state_root=root)
    assert result.status == 'error'
    assert 'outside' in (result.directory / 'report.md').read_text()


def test_unchanged_review_reuses_clean_import_without_advancing_merge_base(tmp_path):
    source = tmp_path / 'source.txt'; source.write_text(TEXT, encoding='utf-8')
    kwargs = dict(year=2026, month=10, output=tmp_path / 'out', input_path=source, state_root=tmp_path / 'state')
    monthly.run_review(**kwargs)
    before = json.loads((tmp_path / 'state/2026-10.json').read_text())['merge_base']
    monthly.run_review(**kwargs)
    after = json.loads((tmp_path / 'state/2026-10.json').read_text())['merge_base']
    assert before == after


def test_new_parser_warning_cannot_hide_behind_same_schedule_fingerprint(tmp_path):
    source = tmp_path / 'source.txt'; source.write_text(TEXT, encoding='utf-8')
    kwargs = dict(year=2026, month=10, output=tmp_path / 'out', input_path=source, state_root=tmp_path / 'state')
    assert monthly.run_review(**kwargs).status == 'ready'
    source.write_text(TEXT + '\n* Run/Rows on 10/32.\n', encoding='utf-8')
    result = monthly.run_review(**kwargs)
    assert result.status == 'review-required' and result.exit_code != 0
    assert 'not a valid date' in (result.directory / 'report.md').read_text()


def test_semantic_unchanged_visual_review_keeps_self_contained_page(tmp_path, monkeypatch):
    source = tmp_path / 'source.txt'; source.write_text(TEXT, encoding='utf-8')
    def export(candidate, directory, **options):
        for name in ('poster.html', 'phone.html', 'social.html', 'calendar.ics', 'poster.png',
                     'phone.png', 'social.png', 'contact-sheet.png', 'visual-report.json'):
            (directory / name).write_text('{}', encoding='utf-8')
        (directory / 'index.html').write_text('<html>Self-contained visual review</html>', encoding='utf-8')
    monkeypatch.setattr(monthly, '_write_exports', export)
    kwargs = dict(year=2026, month=10, output=tmp_path / 'out', input_path=source,
                  state_root=tmp_path / 'state', png=True, visual_check=True)
    first = monthly.run_review(**kwargs)
    assert first.status == 'ready'
    source.write_text(TEXT + '\n\n', encoding='utf-8')
    second = monthly.run_review(**kwargs)
    assert second.status == 'unchanged' and second.directory != first.directory
    assert (second.directory / 'index.html').read_text(encoding='utf-8') == '<html>Self-contained visual review</html>'
