#!/usr/bin/env python3
"""Render and audit the actual full, phone and social poster exports."""
from __future__ import annotations

import argparse
import base64
from html import escape
import json
from pathlib import Path


METRICS_SCRIPT = r"""() => {
 const poster=document.querySelector('.poster'), texts=[], missing=new Set(), clipped=new Set();
 const faces=[...document.fonts],fonts=new Set(faces.filter(f=>f.status==='loaded').map(f=>f.family.replace(/[\"']/g,'').toLowerCase()));
 const system=new Set(['arial','sans-serif','serif','monospace','system-ui','helvetica','verdana','impact']);
 const bounds=poster.getBoundingClientRect();
 const rgb=value=>{const m=value.match(/[\d.]+/g);return m ? m.map(Number) : [0,0,0,0];};
 const light=c=>c.slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
 const background=el=>{for(let node=el;node;node=node.parentElement){const c=rgb(getComputedStyle(node).backgroundColor);if(c.length===3||c[3]>=.99)return c;}return [255,255,255];};
 const walker=document.createTreeWalker(poster,NodeFilter.SHOW_TEXT);
 while(walker.nextNode()){
   const node=walker.currentNode,el=node.parentElement,text=node.textContent.trim();
   if(!text || ['SCRIPT','STYLE'].includes(el.tagName))continue;
   const style=getComputedStyle(el),range=document.createRange();range.selectNodeContents(node);
   const rect=range.getBoundingClientRect();
   if(!rect.width||!rect.height||style.visibility==='hidden'||style.display==='none')continue;
   let scale=1;for(let p=el;p&&p!==poster;p=p.parentElement){const t=getComputedStyle(p).transform;if(t!=='none')scale*=new DOMMatrix(t).a;}
   const size=parseFloat(style.fontSize)*scale,weight=parseInt(style.fontWeight)||400;
   const family=style.fontFamily.split(',')[0].trim().replace(/[\"']/g,'');
   if(!fonts.has(family.toLowerCase())&&!system.has(family.toLowerCase()))missing.add(family);
   const a=light(rgb(style.color)),b=light(background(el)),ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);
   texts.push({text:text.slice(0,100),size,weight,ratio,family});
   if(rect.left<bounds.left-2||rect.right>bounds.right+2||rect.bottom>bounds.bottom+2||rect.top<bounds.top-2)clipped.add(text.slice(0,100));
 }
 const overflow=[...poster.querySelectorAll('td,.pill,.event-label,.kd,.map')].filter(e=>e.scrollWidth>e.clientWidth+2).map(e=>e.textContent.trim().slice(0,100));
 const broken=[...poster.querySelectorAll('img')].filter(e=>!e.complete||!e.naturalWidth).map(e=>e.alt||e.src.slice(0,60));
 return {visual_style:poster.dataset.visualStyle||'',width:bounds.width,height:bounds.height,texts,missing_fonts:[...missing],font_errors:faces.filter(f=>f.status==='error').map(f=>f.family),overflow:[...new Set(overflow)],clipped:[...clipped],broken_images:broken,
   calendar_icons:poster.querySelectorAll('td .pill svg').length,loaded_fonts:[...fonts]};
}"""


def assess_metrics(metrics: dict) -> list[str]:
    issues = []
    for item in metrics.get('texts', []):
        large = item['size'] >= 24 or (item['size'] >= 18.667 and item['weight'] >= 700)
        minimum = 3 if large else 4.5
        if item['ratio'] + 1e-7 < minimum:
            issues.append(f"Text contrast {item['ratio']:.2f}:1 below {minimum}:1: {item['text']}")
        if item['size'] < 11:
            issues.append(f"Text size {item['size']:.1f}px below 11px: {item['text']}")
    for field, label in [('missing_fonts', 'Missing font'), ('font_errors', 'Failed font'), ('overflow', 'Horizontal overflow'),
                         ('clipped', 'Clipped content'), ('broken_images', 'Missing artwork')]:
        issues.extend(f'{label}: {value}' for value in metrics.get(field, []))
    return list(dict.fromkeys(issues))


def review_html(layouts: list[dict]) -> str:
    cards = []
    for item in layouts:
        issues = ''.join('<li>' + escape(issue) + '</li>' for issue in item['issues'])
        image = item.get('image_data') or item['image']
        cards.append(f'<section><h2>{escape(item["layout"].title())}</h2>'
                     f'<p>{len(item["issues"])} visual issues</p><ul>{issues}</ul>'
                     f'<img alt="{escape(item["layout"])} poster preview" src="{escape(image, quote=True)}"></section>')
    return ('<!doctype html><html><meta charset="utf-8"><title>Poster visual review</title>'
            '<style>*{box-sizing:border-box}body{margin:0;padding:28px;background:#edf0f3;color:#202732;'
            'font:16px Arial,sans-serif}h1{margin:0 0 20px}main{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}'
            'section{background:white;border:1px solid #ccd2d9;border-radius:12px;padding:16px;min-width:0}'
            'h2{margin:0 0 10px}li{overflow-wrap:anywhere}img{display:block;width:100%;height:auto;border:1px solid #ddd}'
            'p{color:#4c535d}</style><h1>Poster visual review</h1><main>' + ''.join(cards) + '</main></html>')


def classify_findings(metrics: dict, findings: list[str]) -> tuple[list[str], list[str]]:
    """Retain readability diagnostics for the user-requested original style."""
    if metrics.get('visual_style') != 'classic':
        return findings, []
    warnings = [value for value in findings if value.startswith(('Text contrast ', 'Text size '))
                or value == 'Missing font: Inter']  # Original compact stack has an Arial fallback.
    return [value for value in findings if value not in warnings], warnings


def run_visual_review(directory: Path, browser_channel: str | None = None) -> dict:
    from playwright.sync_api import sync_playwright
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    report = {'status': 'failed', 'errors': [], 'warnings': [], 'layouts': []}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel=browser_channel)
            try:
                for layout, html, image, width, scale in (
                    ('full', 'poster.html', 'poster.png', 1200, 2),
                    ('phone', 'phone.html', 'phone.png', 1080, 1),
                    ('social', 'social.html', 'social.png', 1080, 1)):
                    source = directory / html
                    if not source.is_file():
                        report['errors'].append(f'{layout}: missing {html}')
                        continue
                    page = browser.new_page(viewport={'width': width, 'height': 2000}, device_scale_factor=scale)
                    try:
                        page.goto(source.resolve().as_uri())
                        page.evaluate('document.fonts.ready')
                        if layout != 'full':
                            page.evaluate("""() => {
                              const node=document.querySelector('.poster'),content=document.querySelector('.compact-content');
                              if(!content)return;const style=getComputedStyle(node);
                              const available=node.clientHeight-parseFloat(style.paddingTop)-parseFloat(style.paddingBottom);
                              if(content.offsetHeight>available)content.style.transform=`scale(${available/content.offsetHeight})`;
                            }""")
                        metrics = page.evaluate(METRICS_SCRIPT)
                        issues = assess_metrics(metrics)
                        errors, warnings = classify_findings(metrics, issues)
                        page.locator('.poster').screenshot(path=str(directory / image))
                        item = {'layout': layout, 'image': image, 'issues': issues, 'errors': errors,
                                'warnings': warnings, 'metrics': metrics}
                        report['layouts'].append(item)
                        report['errors'].extend(f'{layout}: {issue}' for issue in errors)
                        report['warnings'].extend(f'{layout}: {issue}' for issue in warnings)
                    finally:
                        page.close()
                cards = [{**item, 'image_data': 'data:image/png;base64,' + base64.b64encode((directory / item['image']).read_bytes()).decode('ascii')}
                         for item in report['layouts']]
                (directory / 'index.html').write_text(review_html(cards), encoding='utf-8')
                page = browser.new_page(viewport={'width': 1600, 'height': 1000}, device_scale_factor=1)
                try:
                    page.goto((directory / 'index.html').resolve().as_uri())
                    page.screenshot(path=str(directory / 'contact-sheet.png'), full_page=True)
                finally:
                    page.close()
            finally:
                browser.close()
    except Exception as error:
        # Do not dump browser/network traces or environment values into artifacts.
        report['errors'].append('Visual review could not finish: ' + type(error).__name__)
    report['status'] = 'failed' if report['errors'] else 'passed'
    (directory / 'visual-report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--browser-channel', choices=('chrome', 'msedge'))
    args = parser.parse_args(argv)
    result = run_visual_review(args.directory, args.browser_channel)
    print(f'Visual review {result["status"]}: {args.directory / "visual-report.json"}')
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
