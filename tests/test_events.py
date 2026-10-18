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
        self.assertTrue({'ASML','LRCX','005930.KS','000660.KS','MU','2454.TW','AMZN','GOOGL','ANTHROPIC','CRWV','NBIS'} <= self.companies.keys())

    def test_dates_have_honest_precision_and_provenance(self):
        ids = set()
        for event in self.data['events']:
            with self.subTest(event=event['id']):
                self.assertNotIn(event['id'], ids)
                ids.add(event['id'])
                self.assertTrue(event['companies'] or event.get('organizer'))
                self.assertTrue(set(event['companies']) <= self.companies.keys())
                self.assertIn(event['status'], ['confirmed','estimated','reported','unannounced'])
                self.assertTrue(event['basis'])
                self.assertTrue(event['importance'])
                self.assertEqual(urlsplit(event['sourceUrl']).scheme, 'https')
                if event['date']:
                    date.fromisoformat(event['date'])
                    self.assertIsNone(event['window'])
                    datetime.fromisoformat(event['sourceCheckedAt'])
                    self.assertTrue(event['sources'])
                    if event['endDate']:
                        self.assertGreaterEqual(date.fromisoformat(event['endDate']),date.fromisoformat(event['date']))
                if event['status'] == 'confirmed':
                    date.fromisoformat(event['date'])
                    self.assertIsNone(event['window'])
                    self.assertIsNotNone(datetime.fromisoformat(event['verifiedAt']))
                    self.assertTrue(event['sourceLabel'])
                    if event['endDate']:
                        self.assertGreaterEqual(date.fromisoformat(event['endDate']),date.fromisoformat(event['date']))
                elif event['status'] == 'estimated':
                    self.assertTrue(event['date'] or event.get('timingWindow'))
                    self.assertIsNone(event['window'])
                    self.assertTrue(any(source['kind']=='estimate' for source in event['sources']) or (event.get('estimateKind')=='reported-target' and any(source['kind']=='report' for source in event['sources'])))
                    self.assertIsNone(event['verifiedAt'])
                    self.assertIsNone(event['time'])
                elif event['status'] == 'reported':
                    self.assertIsNotNone(event['date'])
                    self.assertIsNone(event['verifiedAt'])
                    self.assertTrue(any(source['kind']=='report' for source in event['sources']))
                else:
                    self.assertIsNone(event['date'])
                    self.assertIsNone(event['window'])

    def test_no_duplicate_confirmed_and_estimated_month(self):
        confirmed = {(c,e['date'][:7]) for e in self.data['events'] if e['type']=='Earnings' and e['status']=='confirmed' for c in e['companies']}
        estimated = {(c,(e['date'] or e['window'])[:7]) for e in self.data['events'] if e['type']=='Earnings' and e['status']=='estimated' for c in e['companies']}
        self.assertFalse(confirmed & estimated)

    def test_coverage_has_sourced_earnings_history(self):
        for ticker, company in self.companies.items():
            if not company['coverage']:
                continue
            earnings=[e for e in self.data['events'] if e['type']=='Earnings' and ticker in e['companies'] and e['date']]
            self.assertTrue(earnings,ticker)
            self.assertTrue(all(e['sourceCheckedAt'] and e['sources'] and e['window'] is None for e in earnings))
        # The weekly report flags missing next dates rather than inventing a day
        # to satisfy a completeness assertion when no provider publishes one.
        self.assertFalse(any(e.get('window') for e in self.data['events']), 'Unsourced month placeholders must not return')

    def test_each_event_exposes_valid_evidence(self):
        for event in self.data['events']:
            self.assertTrue(event['sourceLabel'])
            self.assertTrue(event['sources'])
            for evidence in event['sources']:
                self.assertEqual(urlsplit(evidence['url']).scheme,'https')
                self.assertTrue(evidence['label'])
        for ticker in ['CRWV','NBIS']:
            self.assertTrue(any(e['type']=='Earnings' and ticker in e['companies'] for e in self.data['events']))

    def test_normalized_times_have_source_zones_and_real_endpoints(self):
        from zoneinfo import ZoneInfo
        for event in self.data['events']:
            if not event.get('startAt'):
                continue
            start=datetime.fromisoformat(event['startAt'].replace('Z','+00:00'))
            source_zone=ZoneInfo(event['sourceTimeZone'])
            self.assertEqual(start.astimezone(source_zone).date().isoformat(),event['date'])
            self.assertIn(event['timeCertainty'],['verified','reported'])
            self.assertTrue(event['timeCheckedAt'])
            if event.get('endAt'):
                self.assertGreater(datetime.fromisoformat(event['endAt'].replace('Z','+00:00')),start)
        for event in self.data['events']:
            if event['status']=='estimated':
                self.assertFalse(event.get('startAt'), 'Do not invent a clock time for an estimate')
            if event.get('startAt'):
                self.assertTrue(event.get('time'), 'Normalized instants need published clock wording')

    def test_windows_never_assert_exact_event_dates(self):
        events={e['id']:e for e in self.data['events']}
        for event in self.data['events']:
            window=event.get('timingWindow')
            if not window:
                continue
            self.assertIsNone(event['date'])
            self.assertIsNone(event['endDate'])
            self.assertIsNone(event['verifiedAt'])
            self.assertNotEqual(event['status'],'confirmed')
            self.assertGreaterEqual(date.fromisoformat(window['end']),date.fromisoformat(window['start']))
            self.assertIn(window['precision'],['week','month','quarter','year'])
            self.assertTrue(window['label'])
        self.assertEqual(events['mit-ai-2026']['companies'],[])
        self.assertEqual(events['mit-ai-2026']['organizer'],'MIT AI Conference')
        self.assertEqual(events['oracle-ai-world-2025']['date'],'2025-10-13')

    def test_current_editions_are_not_undated_watch_items(self):
        events={e['id']:e for e in self.data['events']}
        self.assertEqual(events['anthropic-investor']['date'],'2026-10-14')
        self.assertIn(events['anthropic-investor']['status'],['reported','confirmed'])
        self.assertEqual(events['ocp']['date'],'2026-10-12')
        self.assertEqual(events['ocp']['endDate'],'2026-10-15')
        self.assertEqual(events['anthropic-ipo']['type'],'IPO watch', 'Do not confuse investor day with listing')

    def test_oracle_ai_world_sessions_remain_in_the_conference(self):
        oracle_events=[e for e in self.data['events'] if e['id'].startswith('oracle-ai-world-')]
        self.assertTrue(oracle_events)
        editions=set()
        for event in oracle_events:
            self.assertEqual(event['type'],'Conference', 'Show keynotes in the conference brief, not separate cards')
            self.assertNotIn(event['date'][:4],editions, 'Only one Oracle AI World event per edition')
            editions.add(event['date'][:4])
        current=next(e for e in oracle_events if e['id']=='oracle-ai-world-2026')
        self.assertIn('Clay Magouyrk',current['basis'])
        self.assertEqual(sum(s['url']=='https://www.oracle.com/ai-world/keynotes/' for s in current['sources']),1)

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

    def test_conference_schedules_are_staged_for_review(self):
        for title in ['MIT AI Conference 2026','Cloudflare Connect 2026','Oracle AI World 2026']:
            rows=refresh.extract_candidates(f'<h1>{title}</h1><p>October 17, 2026</p>')
            self.assertEqual(len(rows),1,title)
            self.assertEqual(rows[0]['status'],'needs_review')

    def test_scripts_and_irrelevant_dates_are_ignored(self):
        html = '<script>October 1, 2026 earnings</script><p>December 4, 2026</p><p>Dividend payment</p>'
        self.assertEqual(refresh.extract_candidates(html),[])

class ProviderEstimateTests(unittest.TestCase):
    def test_marketbeat_explicit_date_remains_estimated(self):
        row=refresh.extract_published_estimate('<p>NVIDIA has not confirmed its next earnings publication date, but the company estimated earnings date is Wednesday, November 18th, 2026 based on past dates.</p>', 'https://www.marketbeat.com/stocks/NASDAQ/NVDA/earnings/',date(2026,10,15))
        self.assertEqual(row['date'],'2026-11-18')
        self.assertEqual(row['status'],'estimated')
        self.assertEqual(row['reviewStatus'],'needs_review')

    def test_stale_or_unlabeled_dates_do_not_become_estimates(self):
        self.assertIsNone(refresh.extract_published_estimate('<p>Earnings Date Sep 10, 2026</p>','https://stockanalysis.com/stocks/orcl/',date(2026,10,15)))
        self.assertIsNone(refresh.extract_published_estimate('<p>Est. Earnings Sep 10, 2026</p>','https://stockanalysis.com/stocks/orcl/',date(2026,10,15)))
        self.assertIsNone(refresh.extract_published_estimate('<p>Published Nov 18, 2026</p>','https://www.marketbeat.com/stocks/NASDAQ/NVDA/earnings/',date(2026,10,15)))

    def test_stockanalysis_and_ft_labeled_estimates(self):
        row=refresh.extract_published_estimate('<p>Est. Earnings</p><p>Nov 24, 2026</p>','https://stockanalysis.com/stocks/wday/',date(2026,10,15))
        self.assertEqual(row['date'],'2026-11-24')
        row=refresh.extract_published_estimate('<p>The next earnings announcement is expected on Oct 29, 2026.</p>','https://markets.ft.markitdigital.com/data/equities/tearsheet/forecasts?s=2454:TAI',date(2026,10,15))
        self.assertEqual(row['date'],'2026-10-29')

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
