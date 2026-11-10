"""Standard-library state, semantic comparisons and conservative monthly merges."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import shutil

VERSION = 1
_ABSENT = object()


def normalized(value):
    if isinstance(value, dict):
        return {key: normalized(item) for key, item in value.items()
                if key not in {'raw', 'source_url'}}
    if isinstance(value, list):
        return [normalized(item) for item in value]
    return value


def semantic_hash(value):
    return hashlib.sha256(json.dumps(normalized(value), sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest() if Path(path).is_file() else ''


def generator_hash(root):
    root = Path(root)
    paths = set((root / 'otfposter').rglob('*.py')) | set((root / 'otfposter/templates').rglob('*'))
    paths |= set((root / 'assets').rglob('*'))
    paths |= {root / 'scripts' / name for name in ('check_monthly.py', 'monthly_state.py', 'review_visuals.py')}
    digest = hashlib.sha256()
    for path in sorted(p for p in paths if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def fingerprint(imported, canonical, generator, options):
    return semantic_hash({'imported': imported, 'canonical': canonical,
                          'generator': generator, 'options': options})


def load_state(root, slug):
    path = Path(root) / f'{slug}.json'
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('version') != VERSION:
        raise ValueError('Monthly state is unsupported or corrupt; preserve it and retry with a new --state-root.')
    return data


def save_state(root, slug, data):
    path = Path(root) / f'{slug}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps({'version': VERSION, **data}, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def months_to_check(today: date, next_month='auto'):
    result = [(today.year, today.month)]
    if next_month == 'on' or (next_month == 'auto' and today.day >= 25):
        result.append((today.year + (today.month == 12), today.month % 12 + 1))
    return result


def _keyed(values, key):
    if not all(isinstance(item, dict) and key in item for item in values):
        return None
    result = {item[key]: item for item in values}
    return result if len(result) == len(values) else None


def merge_schedule(base, incoming, edited):
    """Preserve edited values on conflicts; never infer a base from edited JSON."""
    if edited is None:
        return deepcopy(incoming), []
    if base is None:
        return deepcopy(edited), [{'path': 'schedule', 'message':
            'No trusted imported baseline is available; saved schedule retained for review.'}]
    conflicts = []

    def clone(value):
        return _ABSENT if value is _ABSENT else deepcopy(value)

    def merge(old, new, manual, path):
        if manual == old:
            return clone(new)
        if new == old or manual == new:
            return clone(manual)
        if all(isinstance(value, dict) for value in (old, new, manual)):
            result = {}
            for key in sorted(set(old) | set(new) | set(manual)):
                item = merge(old.get(key, _ABSENT), new.get(key, _ABSENT),
                             manual.get(key, _ABSENT), path + '.' + str(key))
                if item is not _ABSENT:
                    result[key] = item
            return result
        if all(isinstance(value, list) for value in (old, new, manual)):
            key = {'days': 'day', 'events': 'name', 'entries': 'category'}.get(path.split('.')[-1])
            maps = [_keyed(value, key) for value in (old, new, manual)] if key else []
            if maps and all(value is not None for value in maps):
                joined = merge(*maps, path)
                order = list(dict.fromkeys([item[key] for item in new + manual]))
                return [joined[item] for item in order if item in joined]
        conflicts.append({'path': path.lstrip('.'), 'message':
                          'Source and saved poster changed this field differently; saved value retained.'})
        return clone(manual)

    return merge(base, incoming, edited, ''), conflicts


def _workouts(day):
    return ' + '.join(str(entry.get('title') or entry.get('category'))
                      for entry in day.get('entries', [])) or 'none'


def semantic_changes(old, new):
    if old is None:
        return ['First imported schedule; no earlier imported source for comparison.']
    changes = []
    month = new.get('month', '?')
    before = {value['day']: value for value in old.get('days', [])}
    after = {value['day']: value for value in new.get('days', [])}
    for number in sorted(set(before) | set(after)):
        first, second = before.get(number, {}), after.get(number, {})
        if _workouts(first) != _workouts(second):
            changes.append(f'{month}/{number}: workouts {_workouts(first)} → {_workouts(second)}.')
        if first.get('three_g', False) != second.get('three_g', False):
            changes.append(f'{month}/{number}: 3G {"added" if second.get("three_g") else "removed"}.')
        if first.get('repeat_of') != second.get('repeat_of'):
            changes.append(f'{month}/{number}: Repeat of {first.get("repeat_of") or "none"} → '
                           f'{second.get("repeat_of") or "none"}.')
        if first.get('note', '') != second.get('note', ''):
            changes.append(f'{month}/{number}: day note changed.')
    before_events = {value['name']: value for value in old.get('events', [])}
    after_events = {value['name']: value for value in new.get('events', [])}
    for name in sorted(set(before_events) | set(after_events)):
        first, second = before_events.get(name), after_events.get(name)
        if first != second:
            span = lambda value: f'{month}/{value["start"]}–{month}/{value["end"]}' if value else 'none'
            changes.append(f'{name}: event dates {span(first)} → {span(second)}.')
    for key, label in (('theme', 'Theme'), ('tagline', 'Tagline'), ('strength_split', 'Strength split'),
                       ('notes', 'Monthly notes'), ('footnotes', 'Monthly guidance')):
        if normalized(old.get(key)) != normalized(new.get(key)):
            changes.append(f'{label} changed.')
    return changes


def stage_pull_request(manifest_path, destination):
    """Create a reviewable patch tree; no git, API calls or repository writes."""
    manifest_path, destination = Path(manifest_path), Path(destination)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    allowed = manifest_path.parent.resolve()
    months, summaries = [], []
    for item in manifest['checks']:
        directory = Path(item['directory']).resolve()
        if not directory.is_relative_to(allowed):
            raise ValueError('Review path is outside the manifest artifact root.')
        report = json.loads((directory / 'report.json').read_text(encoding='utf-8'))
        healthy = report['status'] == 'ready' or (
            report['status'] == 'unchanged' and report.get('review_status') == 'ready')
        if not healthy or report.get('conflicts'):
            continue
        slug = report['month']
        import re
        if not re.fullmatch(r'20\d{2}-(?:0[1-9]|1[0-2])', slug):
            raise ValueError('Review month is invalid.')
        for source, relative in [('candidate.json', f'schedules/{slug}.json'),
                                 ('imported.json', f'schedules/baselines/{slug}.json'),
                                 ('source.txt', f'schedules/raw/{slug}.txt')]:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(directory / source, target)
        months.append(slug)
        summaries += [f'### {slug}', '', 'Source: ' + report.get('source', {}).get('url', ''), '']
        summaries += ['- ' + value for value in report.get('semantic_changes', [])]
    destination.mkdir(parents=True, exist_ok=True)
    body = ['Update monthly schedules from verified sources while preserving saved poster edits.', '',
            'Review source, changed dates and preview artifacts before merging. No Reddit post was submitted.', '']
    (destination / 'pull-request.md').write_text('\n'.join(body + summaries) + '\n', encoding='utf-8')
    return months


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Stage accepted monthly review files for an optional draft PR.')
    parser.add_argument('--stage-pr', required=True, type=Path, help='Completed review manifest')
    parser.add_argument('--destination', type=Path, default=Path('build/monthly-pr'))
    arguments = parser.parse_args()
    print('Staged months: ' + ', '.join(stage_pull_request(arguments.stage_pr, arguments.destination)))
