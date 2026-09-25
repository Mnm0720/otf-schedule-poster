"""The static page structure is not represented by the Node DOM adapter."""
from html.parser import HTMLParser
from pathlib import Path


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.nodes = []

    def handle_starttag(self, tag, attrs):
        self.nodes.append((tag, dict(attrs)))


def test_customization_sections_start_collapsed_and_schedule_precedes_styling():
    page = Page()
    page.feed((Path(__file__).resolve().parents[1] / 'web/index.html').read_text(encoding='utf-8'))
    ids = [attrs.get('id') for _, attrs in page.nodes]
    sections = ['titleSection', 'keyDateSection', 'workoutSection', 'notesSection', 'monthlyNotesSection', 'eventsSection', 'additionalInfoSection', 'creditsSection']
    for section in sections:
        tag, attrs = next((tag, attrs) for tag, attrs in page.nodes if attrs.get('id') == section)
        assert tag == 'details' and 'open' not in attrs
    assert ids.index('calendarEditor') < ids.index('headingEditor')
    assert ids.index('editorWrap') < ids.index('previewWrap')
    assert ids.index('calendarEditor') < ids.index('draftName')
    assert ids.index('previewWrap') < ids.index('exportFormat') < ids.index('exportBtn') < ids.index('previewZoom')
    assert ids.index('go') < ids.index('restart') < ids.index('previewWrap')
    assert 'sourceInputs' in ids
    assert ids.index('eventsSection') < ids.index('additionalInfoSection') < ids.index('creditsSection')
    # savedPicker now lives inside the drafts <dialog> (near end of body), so it
    # is no longer ordered before sourceInputs; assert the real source-panel order.
    assert ids.index('examples') < ids.index('sourceInputs') < ids.index('src')
    assert 'savedPicker' in ids


def test_mobile_workflow_has_save_feedback_navigation_and_real_export_actions():
    page = Page()
    page.feed((Path(__file__).resolve().parents[1] / 'web/index.html').read_text(encoding='utf-8'))
    ids = [attrs.get('id') for _, attrs in page.nodes]
    assert ids.index('autosaveStatus') < ids.index('calendarEditor') < ids.index('draftsDialog')
    for name in ['previousDay', 'nextDay', 'exportAgain', 'exportShare', 'retryBoot']:
        assert next(tag for tag, attrs in page.nodes if attrs.get('id') == name) == 'button'
    assert next(attrs for _, attrs in page.nodes if attrs.get('id') == 'month')['type'] == 'month'
    assert 'readonly' in next(attrs for _, attrs in page.nodes if attrs.get('id') == 'sourceReference')


def test_restart_popup_explains_loss_and_defaults_to_keep_editing():
    html = (Path(__file__).resolve().parents[1] / 'web/index.html').read_text(encoding='utf-8')
    page = Page(); page.feed(html)
    dialog = next(attrs for tag, attrs in page.nodes if tag == 'dialog')
    assert dialog['id'] == 'restartDialog'
    cancel = next(attrs for _, attrs in page.nodes if attrs.get('id') == 'restartCancel')
    assert 'autofocus' in cancel
    assert 'remove all customizations' in html
    assert 'including changes already applied' in html
