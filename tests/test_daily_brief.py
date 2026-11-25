import contextlib
from datetime import date
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('daily_brief', ROOT / 'scripts/daily_brief.py')
brief = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(brief)


def event(event_id, companies, day=None, **extra):
    base = {'id': event_id, 'companies': companies, 'title': event_id.replace('-', ' '), 'type': 'Earnings',
            'status': 'confirmed', 'window': None, 'date': day, 'endDate': None, 'time': None,
            'sourceUrl': f'https://example.com/{event_id}', 'sourceLabel': 'Company IR', 'basis': 'b', 'importance': 'i',
            'sources': [{'label': 'Company IR', 'url': f'https://example.com/{event_id}', 'kind': 'official'}]}
    base.update(extra)
    return base


DATA = {
    'companies': [
        {'id': 'NVDA', 'name': 'NVIDIA', 'coverage': True},
        {'id': 'MU', 'name': 'Micron', 'coverage': False},
    ],
    'events': [
        # 13:30 PST on Nov 24 is 05:30 HKT on Nov 25: it belongs to "today" in Hong Kong.
        event('nvda-call', ['NVDA'], '2026-11-24', startAt='2026-11-24T21:30:00Z', sourceTimeZone='America/Los_Angeles',
              time='13:30 PST', timeCertainty='verified'),
        event('mu-week', ['MU'], '2026-11-27'),
        event('mu-day-seven', ['MU'], '2026-12-02'),
        event('nvda-day-eight', ['NVDA'], '2026-12-03'),
        event('nvda-conference', ['NVDA'], '2026-11-30', endDate='2026-12-04', type='Conference'),
        event('mu-day-thirty', ['MU'], '2026-12-25'),
        event('mu-day-thirty-one', ['MU'], '2026-12-26'),
        event('mu-yesterday', ['MU'], '2026-11-24'),
        event('nvda-estimate', ['NVDA'], '2026-12-10', status='estimated', verifiedAt=None),
        event('mu-time-unverified', ['MU'], '2026-12-17', time='14:30 MST'),
        event('watch', ['MU'], None, status='unannounced'),
        event('<script>alert(1)</script>', ['NVDA'], '2026-12-05', sourceUrl='javascript:alert(1)'),
    ],
}
TODAY = date(2026, 11, 25)


class SectionTests(unittest.TestCase):
    def sections(self):
        return {key: [r['id'] for r in rows] for key, _l, _f, _t, rows in brief.build_rows(DATA, TODAY)}

    def test_windows_use_hong_kong_dates_and_do_not_overlap(self):
        sections = self.sections()
        self.assertEqual(sections['today'], ['nvda-call'])
        self.assertIn('mu-week', sections['week'])
        self.assertIn('mu-day-seven', sections['week'])
        self.assertIn('nvda-day-eight', sections['month'])
        self.assertIn('mu-day-thirty', sections['month'])
        flat = [i for ids in sections.values() for i in ids]
        self.assertEqual(len(flat), len(set(flat)), 'An event must appear in only one section')
        for excluded in ['mu-day-thirty-one', 'mu-yesterday', 'watch']:
            self.assertNotIn(excluded, flat)

    def test_multi_day_event_listed_once_in_earliest_window(self):
        sections = self.sections()
        self.assertIn('nvda-conference', sections['week'])
        self.assertNotIn('nvda-conference', sections['month'])

    def test_coverage_is_starred_and_others_are_not(self):
        rows = {r['id']: r for *_x, rs in brief.build_rows(DATA, TODAY) for r in rs}
        self.assertTrue(rows['nvda-call']['starred'])
        self.assertTrue(rows['nvda-estimate']['starred'])
        self.assertFalse(rows['mu-week']['starred'])

    def test_times_are_hong_kong_and_never_invented(self):
        rows = {r['id']: r for *_x, rs in brief.build_rows(DATA, TODAY) for r in rs}
        self.assertTrue(rows['nvda-call']['time'].startswith('05:30 HKT'))
        self.assertIn('13:30 PST', rows['nvda-call']['time'])
        self.assertEqual(rows['mu-week']['time'], 'Time not announced')
        self.assertEqual(rows['mu-time-unverified']['time'], 'Source time: 14:30 MST')
        self.assertEqual(rows['nvda-estimate']['statusLabel'], 'Estimate')


class ComposeTests(unittest.TestCase):
    def test_subject_counts_and_highlighting(self):
        subject, text, html = brief.compose(DATA, TODAY, 'unchanged', {}, brief.DEFAULT_SITE)
        self.assertIn('Wed 25 Nov 2026', subject)
        self.assertIn('Today 1', subject)
        self.assertIn('★', text)
        self.assertIn('TODAY — Wed 25 Nov', text)
        self.assertIn('NEXT 7 DAYS — Thu 26 Nov – Wed 2 Dec', text)
        self.assertIn('Thu 3 Dec – Fri 25 Dec', text)
        self.assertIn(brief.HIGHLIGHT_BG, html)
        self.assertIn('Coverage: ', text)

    def test_html_is_escaped_and_unsafe_links_dropped(self):
        _subject, text, html = brief.compose(DATA, TODAY, 'unchanged', {}, brief.DEFAULT_SITE)
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('javascript:', html)
        self.assertNotIn('javascript:', text)

    def test_report_sections_and_failure_wording(self):
        report = {'summary': 'Checked sources.', 'warnings': ['Adobe IR blocked.'],
                  'developments': [{'title': 'NVIDIA news', 'companies': ['NVDA'], 'sourceUrl': 'https://example.com/n'}],
                  'added': [{'title': 'New event', 'date': '2026-12-03', 'sourceUrl': 'https://example.com/a'}],
                  'to': ['attacker@example.com'], 'html': '<b>x</b>'}
        subject, text, html = brief.compose(DATA, TODAY, 'failed', report, brief.DEFAULT_SITE)
        self.assertIn('FAILED', subject)
        self.assertIn('calendar not updated', text)
        self.assertIn('★ NVIDIA news', text)
        self.assertIn('Adobe IR blocked.', html)
        self.assertIn('Added: New event', text)
        self.assertNotIn('attacker@example.com', text + html)
        _s, text, _h = brief.compose(DATA, TODAY, 'published', report, brief.DEFAULT_SITE)
        self.assertIn('with exceptions', text)

    def test_rejects_unknown_result_and_unsafe_site(self):
        with self.assertRaises(brief.BriefError):
            brief.compose(DATA, TODAY, 'great', {}, brief.DEFAULT_SITE)
        with self.assertRaises(brief.BriefError):
            brief.compose(DATA, TODAY, 'unchanged', {}, 'http://example.com')

    def test_real_dataset_composes(self):
        data = json.loads((ROOT / 'data/events.json').read_text())
        subject, text, html = brief.compose(data, TODAY, 'unchanged', {}, brief.DEFAULT_SITE)
        self.assertTrue(subject and text and html)


class Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return b'{"id":"accepted-message-id"}'


class DeliveryTests(unittest.TestCase):
    def run_main(self, environ):
        with tempfile.TemporaryDirectory() as directory:
            dataset = Path(directory) / 'events.json'
            dataset.write_text(json.dumps(DATA))
            with patch.object(brief, 'urlopen', return_value=Response()) as request, \
                    contextlib.redirect_stdout(io.StringIO()):
                code = brief.main(['--result', 'published', '--dataset', str(dataset), '--date', '2026-11-25'], environ)
        return code, request.call_args.args[0]

    def test_fixed_recipient_html_and_text(self):
        code, sent = self.run_main({'RESEND_API_KEY': 'secret-key', 'GLOBAL_TECH_EMAIL_FROM': 'Global Tech <brief@example.com>'})
        self.assertEqual(code, 0)
        payload = json.loads(sent.data)
        self.assertEqual(sent.full_url, 'https://api.resend.com/emails')
        self.assertEqual(payload['to'], ['hangyul.son@clsa.com'])
        self.assertEqual(payload['from'], 'Global Tech <brief@example.com>')
        self.assertIn('html', payload)
        self.assertIn('text', payload)
        self.assertNotIn('secret-key', payload['text'] + payload['html'])
        self.assertEqual(sent.get_header('Authorization'), 'Bearer secret-key')
        self.assertTrue(sent.get_header('Idempotency-key').startswith('global-tech-daily-'))

    def test_proxy_placeholder_when_key_is_injected_by_session(self):
        code, sent = self.run_main({})
        self.assertEqual(code, 0)
        self.assertEqual(sent.get_header('Authorization'), 'Bearer ' + brief.PROXY_PLACEHOLDER_KEY)
        self.assertEqual(json.loads(sent.data)['from'], 'Global Tech <onboarding@resend.dev>')

    def test_idempotency_is_per_day(self):
        self.assertEqual(brief.idempotency_key(TODAY, 'published'), brief.idempotency_key(TODAY, 'published'))
        self.assertNotEqual(brief.idempotency_key(TODAY, 'published'), brief.idempotency_key(date(2026, 11, 26), 'published'))
        self.assertNotEqual(brief.idempotency_key(TODAY, 'published'), brief.idempotency_key(TODAY, 'published', 'retry'))


if __name__ == '__main__':
    unittest.main()
