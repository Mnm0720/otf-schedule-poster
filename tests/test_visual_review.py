from scripts.review_visuals import assess_metrics, review_html, classify_findings


def test_contrast_uses_actual_text_size_and_reports_missing_fonts_and_clipping():
    metrics = {'texts': [
        {'text':'Lift More','size':14,'weight':700,'ratio':3.48,'family':'Barlow'},
        {'text':'Large title','size':30,'weight':700,'ratio':3.48,'family':'Barlow'},
        {'text':'Tiny note','size':9,'weight':400,'ratio':7,'family':'Barlow'}],
        'missing_fonts':['Inter'],'overflow':['Long workout'],'clipped':['Bottom credits']}
    metrics['font_errors']=['BrokenFont']
    issues = assess_metrics(metrics)
    assert any('Lift More' in i and 'contrast' in i for i in issues)
    assert not any('Large title' in i for i in issues)
    assert any('Tiny note' in i and 'size' in i for i in issues)
    assert any('Inter' in i for i in issues)
    assert any('BrokenFont' in i for i in issues)
    assert any('Long workout' in i for i in issues)
    assert any('Bottom credits' in i for i in issues)


def test_review_page_escapes_untrusted_findings_and_references_every_layout():
    page = review_html([{'layout':'full','image':'poster.png','issues':['<img src=x onerror=alert(1)>']},
                        {'layout':'phone','image':'phone.png','issues':[]},
                        {'layout':'social','image':'social.png','issues':[]}])
    assert '<img src=x' not in page and '&lt;img src=x' in page
    assert all(name in page for name in ('poster.png','phone.png','social.png'))


def test_classic_readability_findings_stay_visible_without_hiding_technical_errors():
    findings=['Text contrast 3.48:1 below 4.5:1: Lift More',
              'Text size 10.8px below 11px: Caption','Clipped content: Workout',
              'Failed font: Barlow']
    errors,warnings=classify_findings({'visual_style':'classic'},findings)
    assert errors==findings[2:] and warnings==findings[:2]
    assert classify_findings({'visual_style':'other'},findings)==(findings,[])
    assert classify_findings({'visual_style':'classic'},['Missing font: Inter'])==([],['Missing font: Inter'])
