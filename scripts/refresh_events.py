#!/usr/bin/env python3
"""Check public company and calendar sources and stage event evidence for maintainer review.

Never treats a news publication date as a confirmed event date. Never modifies
reviewed events automatically. No dependencies or licensed feed credentials.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
MONTH = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
DATE = re.compile(r'\b(?:' + MONTH + r'\.?\s+\d{1,2},?\s+20\d{2}|20\d{2}-\d{2}-\d{2})\b', re.I)
RELEVANT = re.compile(r'earnings|financial results|conference|summit|investor day|capital markets|GTC|re:Invent|Ignite|OCP|AI World|Cloudflare Connect|initial public offering|IPO', re.I)

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

def extract_published_estimate(html, url, as_of=None):
    """Read explicitly labeled provider estimates; never infer a date or confirmation."""
    parser = PageText()
    parser.feed(html)
    text = ' '.join(parser.parts)
    host = urlsplit(url).hostname
    match = None
    if host == 'www.marketbeat.com':
        match = re.search(r"(?:next earnings date is estimated for|estimated earnings date is)\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(" + MONTH + r"\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+20\d{2})", text, re.I)
    elif host == 'stockanalysis.com':
        match = re.search(r'Est\. Earnings\s+(' + MONTH + r'\.?\s+\d{1,2},?\s+20\d{2})', text, re.I)
    elif host == 'markets.ft.markitdigital.com':
        match = re.search(r'next earnings announcement is expected on\s+(' + MONTH + r'\.?\s+\d{1,2},?\s+20\d{2})', text, re.I)
    if not match:
        return None
    value = re.sub(r'(\d)(?:st|nd|rd|th)\b', r'\1', match.group(1), flags=re.I).replace(',', '').replace('.', '')
    parsed = None
    for fmt in ['%B %d %Y', '%b %d %Y']:
        try:
            parsed = datetime.strptime(value, fmt).date()
            break
        except ValueError:
            pass
    if not parsed or parsed < (as_of or date.today()):
        return None
    return {'date': parsed.isoformat(), 'sourceUrl': url,
            'status': 'estimated', 'reviewStatus': 'needs_review',
            'basis': 'Explicitly published provider estimate; not a company confirmation.'}

def check_source(item):
    url, names = item
    try:
        request = Request(url, headers={'User-Agent': 'CatalystResearchCalendar/1.0 (public event-source checks)'})
        with urlopen(request, timeout=20) as response:
            html = response.read(5_000_001)
            if len(html) > 5_000_000:
                return {'url': url, 'companies': names, 'status': 'too_large', 'candidates': []}
            content_type = response.headers.get('Content-Type', '').lower()
            text = html.decode(response.headers.get_content_charset() or 'utf-8', errors='replace')
            if 'json' in content_type:
                try:
                    payload = json.loads(text)
                except ValueError:
                    return {'url': url, 'companies': names, 'status': 'invalid_json', 'candidates': []}
                event = payload.get('eventInfo', {}) if isinstance(payload, dict) else {}
                candidates = []
                if event.get('date'):
                    candidates.append({'dateText': event['date'], 'evidence': ' | '.join(str(event.get(k,'')) for k in ['name','date','time']), 'status': 'needs_review', 'warning': 'Official structured metadata; verify event type and whether this is a call time.'})
                return {'url': url, 'companies': names, 'status': 'retrieved', 'format': 'json', 'candidates': candidates}
            if 'html' not in content_type:
                return {'url': url, 'companies': names, 'status': 'unsupported_format', 'candidates': []}
        return {'url': url, 'companies': names, 'status': 'retrieved', 'publishedEstimate': extract_published_estimate(text, url), 'candidates': extract_candidates(text)}
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
    for event in data['events']:
        for evidence in event.get('sources', []):
            ids = sources.setdefault(evidence['url'], [])
            for ticker in event['companies']:
                if ticker not in ids:
                    ids.append(ticker)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(check_source, sources.items()))
    success = sum(r['status'] == 'retrieved' for r in results)
    report = {'checkedAt': datetime.now(timezone.utc).isoformat(),
              'successfulSources': success, 'totalSources': len(results),
              'note': 'Published estimates are staged separately and remain unconfirmed. Retrieval is not date verification. JavaScript-only pages may return no candidates. Reviewed events remain unchanged.',
              'sources': results}
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix('.tmp')
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    temp.replace(output)
    count = sum(len(r['candidates']) for r in results)
    print(f'{success}/{len(results)} public sources retrieved; {count} evidence candidates staged in {output}.')
    print('No event dates were automatically confirmed or changed. Review evidence in Codex.')
    return 0 if success else 1

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'data/source-checks.json')
    parser.add_argument('--workers', type=int, choices=range(1, 9), default=4)
    args = parser.parse_args()
    raise SystemExit(run(args.output, args.workers))
