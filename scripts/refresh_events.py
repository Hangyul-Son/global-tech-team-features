#!/usr/bin/env python3
"""Check official sources and stage event evidence for maintainer review.

Never treats a news publication date as a confirmed event date. Never modifies
reviewed events automatically. No dependencies or licensed feed credentials.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
MONTH = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
DATE = re.compile(r'\b(?:' + MONTH + r'\.?\s+\d{1,2},?\s+20\d{2}|20\d{2}-\d{2}-\d{2})\b', re.I)
RELEVANT = re.compile(r'earnings|financial results|results.{0,20}conference|investor day|capital markets|GTC|re:Invent|Ignite|OCP|initial public offering|IPO|AI.{0,20}conference', re.I)

class PageText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self.skip += 1
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'):
            self.skip = max(0, self.skip - 1)
    def handle_data(self, text):
        if not self.skip and text.strip():
            self.parts.append(re.sub(r'\s+', ' ', text.strip()))

def extract_candidates(html):
    """Stage nearby date and event text; proximity alone does NOT confirm a date."""
    parser = PageText()
    parser.feed(html)
    lines = parser.parts
    candidates, seen = [], set()
    for i, line in enumerate(lines):
        if not DATE.search(line):
            continue
        context = ' | '.join(lines[max(0, i-2):i+5])[:1600]
        if not RELEVANT.search(context):
            continue
        key = (line, context)
        if key not in seen:
            seen.add(key)
            candidates.append({'dateText': line[:250], 'evidence': context,
                               'status': 'needs_review',
                               'warning': 'May be a publication date, past event, or fiscal period. Verify the actual event date before approval.'})
    return candidates

def check_source(item):
    url, names = item
    try:
        request = Request(url, headers={'User-Agent': 'CatalystResearchCalendar/1.0 (public event-source checks)'})
        with urlopen(request, timeout=20) as response:
            html = response.read(5_000_001)
            if len(html) > 5_000_000:
                return {'url': url, 'companies': names, 'status': 'too_large', 'candidates': []}
            if 'html' not in response.headers.get('Content-Type', '').lower():
                return {'url': url, 'companies': names, 'status': 'unsupported_format', 'candidates': []}
            text = html.decode(response.headers.get_content_charset() or 'utf-8', errors='replace')
        return {'url': url, 'companies': names, 'status': 'retrieved', 'candidates': extract_candidates(text)}
    except HTTPError as error:
        return {'url': url, 'companies': names, 'status': f'http_{error.code}', 'candidates': []}
    except (URLError, TimeoutError, OSError):
        return {'url': url, 'companies': names, 'status': 'connection_failed', 'candidates': []}

def run(output, workers=4):
    data = json.loads((ROOT / 'data/events.json').read_text())
    sources = {}
    for company in data['companies']:
        sources.setdefault(company['source'], []).append(company['id'])
    for event in data['events']:
        for name in event['companies']:
            ids = sources.setdefault(event['sourceUrl'], [])
            if name not in ids:
                ids.append(name)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(check_source, sources.items()))
    success = sum(r['status'] == 'retrieved' for r in results)
    report = {'checkedAt': datetime.now(timezone.utc).isoformat(),
              'successfulSources': success, 'totalSources': len(results),
              'note': 'Retrieval is not date verification. JavaScript-only pages may return no candidates. Reviewed events remain unchanged.',
              'sources': results}
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix('.tmp')
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    temp.replace(output)
    count = sum(len(r['candidates']) for r in results)
    print(f'{success}/{len(results)} official sources retrieved; {count} evidence candidates staged in {output}.')
    print('No event dates were automatically confirmed or changed. Review evidence in Codex.')
    return 0 if success else 1

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'data/source-checks.json')
    parser.add_argument('--workers', type=int, choices=range(1, 9), default=4)
    args = parser.parse_args()
    raise SystemExit(run(args.output, args.workers))
