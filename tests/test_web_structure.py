"""The static page structure is not represented by the Node DOM adapter."""
from html.parser import HTMLParser
from pathlib import Path


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.nodes = []

    def handle_starttag(self, tag, attrs):
        self.nodes.append((tag, dict(attrs)))


def test_customization_sections_start_collapsed_and_titles_precede_schedule():
    page = Page()
    page.feed((Path(__file__).resolve().parents[1] / 'web/index.html').read_text(encoding='utf-8'))
    ids = [attrs.get('id') for _, attrs in page.nodes]
    sections = ['titleSection', 'keyDateSection', 'workoutSection', 'notesSection', 'monthlyNotesSection', 'eventsSection', 'additionalInfoSection', 'creditsSection']
    for section in sections:
        tag, attrs = next((tag, attrs) for tag, attrs in page.nodes if attrs.get('id') == section)
        assert tag == 'details' and 'open' not in attrs
    assert ids.index('headingEditor') < ids.index('calendarEditor')
    assert ids.index('previewWrap') < ids.index('png') < ids.index('html') < ids.index('previewZoom')
    assert ids.index('go') < ids.index('restart') < ids.index('previewWrap')
    assert 'sourceInputs' in ids
    assert ids.index('eventsSection') < ids.index('additionalInfoSection') < ids.index('creditsSection')
    assert ids.index('examples') < ids.index('savedPicker') < ids.index('sourceInputs') < ids.index('src')


def test_restart_popup_explains_loss_and_defaults_to_keep_editing():
    html = (Path(__file__).resolve().parents[1] / 'web/index.html').read_text(encoding='utf-8')
    page = Page(); page.feed(html)
    dialog = next(attrs for tag, attrs in page.nodes if tag == 'dialog')
    assert dialog['id'] == 'restartDialog'
    cancel = next(attrs for _, attrs in page.nodes if attrs.get('id') == 'restartCancel')
    assert 'autofocus' in cancel
    assert 'remove all customizations' in html
    assert 'including changes already applied' in html
