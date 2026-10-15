import importlib.util
import json
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('refresh', ROOT / 'scripts/refresh_events.py')
refresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh)

class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'data/events.json').read_text())
        self.companies = {c['id']: c for c in self.data['companies']}

    def test_exact_priority_universe(self):
        self.assertEqual({c['id'] for c in self.data['companies'] if c['coverage']},
                         {'TSM','NVDA','AMD','AVGO','MRVL','AAPL','MSFT','ORCL','CRM','NOW','ADBE','WDAY'})
        self.assertEqual(len(self.companies), len(self.data['companies']))
        self.assertTrue({'ASML','LRCX','005930.KS','000660.KS','MU','2454.TW','AMZN','GOOGL','META','ANTHROPIC'} <= self.companies.keys())

    def test_dates_have_honest_precision_and_provenance(self):
        ids = set()
        for event in self.data['events']:
            with self.subTest(event=event['id']):
                self.assertNotIn(event['id'], ids)
                ids.add(event['id'])
                self.assertTrue(event['companies'])
                self.assertTrue(set(event['companies']) <= self.companies.keys())
                self.assertIn(event['status'], ['confirmed','estimated','unannounced'])
                self.assertTrue(event['basis'])
                self.assertTrue(event['importance'])
                self.assertEqual(urlsplit(event['sourceUrl']).scheme, 'https')
                if event['status'] == 'confirmed':
                    date.fromisoformat(event['date'])
                    self.assertIsNone(event['window'])
                    self.assertIsNotNone(datetime.fromisoformat(event['verifiedAt']))
                    self.assertTrue(event['sourceLabel'])
                    if event['endDate']:
                        self.assertGreaterEqual(date.fromisoformat(event['endDate']),date.fromisoformat(event['date']))
                elif event['status'] == 'estimated':
                    self.assertRegex(event['window'], r'^20\d{2}-(0[1-9]|1[0-2])$')
                    self.assertIsNone(event['date'])
                    self.assertIsNone(event['verifiedAt'])
                    self.assertIsNone(event['time'])
                else:
                    self.assertIsNone(event['date'])
                    self.assertIsNone(event['window'])

    def test_no_duplicate_confirmed_and_estimated_month(self):
        confirmed = {(c,e['date'][:7]) for e in self.data['events'] if e['type']=='Earnings' and e['status']=='confirmed' for c in e['companies']}
        estimated = {(c,e['window']) for e in self.data['events'] if e['type']=='Earnings' and e['status']=='estimated' for c in e['companies']}
        self.assertFalse(confirmed & estimated)

    def test_source_report_does_not_claim_full_verification(self):
        report = json.loads((ROOT / 'data/source-checks.json').read_text())
        self.assertEqual(report['successfulSources'],sum(s['status']=='retrieved' for s in report['sources']))
        self.assertEqual(report['totalSources'],len(report['sources']))
        for source in report['sources']:
            for candidate in source['candidates']:
                self.assertEqual(candidate['status'],'needs_review')

class ExtractionTests(unittest.TestCase):
    def test_publication_date_only_stages_candidate(self):
        html = '<p>October 1, 2026</p><h2>Company to report earnings on November 3, 2026</h2>'
        rows = refresh.extract_candidates(html)
        self.assertEqual(len(rows),2)
        self.assertTrue(all(r['status']=='needs_review' for r in rows))
        self.assertTrue(all('publication date' in r['warning'] for r in rows))

    def test_scripts_and_irrelevant_dates_are_ignored(self):
        html = '<script>October 1, 2026 earnings</script><p>December 4, 2026</p><p>Dividend payment</p>'
        self.assertEqual(refresh.extract_candidates(html),[])

class LocalLinkTests(unittest.TestCase):
    def test_all_site_assets_and_navigation_resolve(self):
        class Links(HTMLParser):
            def __init__(self): super().__init__(); self.links=[]
            def handle_starttag(self, tag, attrs):
                self.links.extend(v for k,v in attrs if k in ('src','href') and v)
        pages = list(ROOT.glob('*.html')) + list((ROOT/'articles').glob('*.html'))
        for page in pages:
            parser = Links();parser.feed(page.read_text())
            for link in parser.links:
                url = urlsplit(link)
                if url.scheme or url.netloc or not url.path:
                    continue
                self.assertTrue((page.parent / unquote(url.path)).is_file(),f'{page.name}: {link}')

if __name__ == '__main__':
    unittest.main()
