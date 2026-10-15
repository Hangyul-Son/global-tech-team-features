"""Offline safety checks for the scheduled, source-grounded calendar updater."""
from copy import deepcopy
from datetime import datetime, timezone
import contextlib
from email.message import Message
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('weekly_refresh', ROOT / 'scripts/weekly_refresh.py')
weekly = importlib.util.module_from_spec(SPEC)
sys.path.insert(0, str(ROOT / 'scripts'))
try:
    SPEC.loader.exec_module(weekly)
finally:
    sys.path.remove(str(ROOT / 'scripts'))


class WeeklyRefreshTests(unittest.TestCase):
    def setUp(self):
        # Match the scripts/ import path used by the actual CLI, including
        # preflight's lazy import of the sender validator.
        paths = patch.object(sys, 'path', [str(ROOT / 'scripts'), *sys.path])
        paths.start()
        self.addCleanup(paths.stop)
        # A test must never reach DNS, public evidence pages or a billable API.
        for target in ['urlopen', 'build_opener']:
            blocker = patch.object(weekly, target, side_effect=AssertionError('Unexpected network access in unit test'))
            blocker.start()
            self.addCleanup(blocker.stop)
        dns = patch.object(weekly.socket, 'getaddrinfo', side_effect=AssertionError('Unexpected DNS in unit test'))
        dns.start()
        self.addCleanup(dns.stop)
        self.current = json.loads((ROOT / 'data/events.json').read_text())
        self.now = datetime(2026, 10, 18, 2, tzinfo=timezone.utc)
        self.url = 'https://investor.nvidia.com/news/earnings-announcement'
        self.quote = 'NVIDIA will report its third-quarter 2026 financial results on November 18, 2026. This is the confirmed earnings announcement.'
        self.event = {
            'id': 'NVDA-2026-11-earnings', 'title': 'NVIDIA Q3 earnings',
            'companies': ['NVDA'], 'organizer': None, 'type': 'Earnings',
            'status': 'confirmed', 'date': '2026-11-18', 'endDate': None,
            'timingWindow': None, 'time': None, 'startAt': None, 'endAt': None,
            'sourceTimeZone': None, 'timeCertainty': None, 'sourceUrl': self.url,
            'sourceLabel': 'NVIDIA investor relations', 'basis': self.quote,
            'importance': 'AI accelerator demand and guidance.', 'dateConflict': None,
            'estimateKind': None,
            'sources': [{'url': self.url, 'label': 'NVIDIA investor relations', 'kind': 'official'}],
        }
        self.change = {'event': self.event, 'evidence': [
            {'url': self.url, 'quote': self.quote, 'supports': ['identity', 'date', 'status']}
        ]}
        self.fetcher = Mock(return_value=self.quote)

    def validate(self, change=None, current=None, searched=None):
        return weekly.validate_change(change or self.change, current or self.current,
                                      searched if searched is not None else {self.url},
                                      self.now, fetcher=self.fetcher)

    def test_approved_changes_preserve_original_twelve_and_all_history(self):
        original = deepcopy(self.current)
        proposal = self.validate()
        held = deepcopy(proposal)
        held['event']['id'] = 'held-event'
        result, added, updated = weekly.apply_approved(self.current, [proposal, held], {self.event['id']}, self.now, [])
        self.assertEqual(self.current, original, 'Applying changes must not mutate the input snapshot')
        self.assertEqual(result['companies'], original['companies'])
        self.assertEqual({c['id'] for c in result['companies'] if c['coverage']}, weekly.COVERAGE)
        after = {e['id']: e for e in result['events']}
        for event in original['events']:
            if event['id'] != self.event['id']:
                self.assertEqual(after[event['id']], event)
        self.assertNotIn('held-event', after)
        self.assertEqual(added, [])
        self.assertEqual([e['id'] for e in updated], [self.event['id']])
        self.assertEqual(after[self.event['id']]['verifiedAt'], self.now.isoformat())

    def test_timestamp_only_rechecks_are_not_reported_as_changed_events(self):
        old = deepcopy(next(e for e in self.current['events'] if e['id'] == self.event['id']))
        proposal = {'event': old, 'evidence': [], 'previous': old}
        result, added, updated = weekly.apply_approved(self.current, [proposal], {old['id']}, self.now, [])
        self.assertEqual(added, [])
        self.assertEqual(updated, [], 'Fresh source check timestamps alone are not event changes')
        refreshed = next(e for e in result['events'] if e['id'] == old['id'])
        self.assertEqual(refreshed['sourceCheckedAt'], self.now.isoformat())

    def test_partial_review_preserves_full_review_timestamp(self):
        result, _, _ = weekly.apply_approved(self.current, [], set(), self.now, ['Source unavailable'])
        self.assertEqual(result['asOf'], self.current['asOf'])
        self.assertEqual(result['lastSuccessfulRefresh'], self.current['lastSuccessfulRefresh'])
        self.assertEqual(result['lastAttempt'], self.now.isoformat())

    def test_live_quote_must_match_independently_retrieved_text(self):
        self.fetcher.return_value = 'Introduction\n' + self.quote.upper().replace(' ', '\n ') + '\nFooter'
        proposal = self.validate()
        self.assertEqual(proposal['event']['id'], self.event['id'])
        self.assertTrue(proposal['evidence'][0]['officialDomain'])
        self.fetcher.assert_called_once_with(self.url)

    def test_unsupported_quote_cannot_change_calendar(self):
        self.fetcher.return_value = 'NVIDIA historical investor relations archive. No announcement for this event.'
        with self.assertRaisesRegex(weekly.RefreshError, 'not found'):
            self.validate()

    def test_evidence_must_come_from_actual_search_results(self):
        with self.assertRaisesRegex(weekly.RefreshError, 'not returned by live'):
            self.validate(searched=set())
        self.fetcher.assert_not_called()

    def test_every_cited_source_needs_a_fresh_matching_quote(self):
        change = deepcopy(self.change)
        change['event']['sources'].append({'url': 'https://stockanalysis.com/stocks/nvda/', 'label': 'Provider', 'kind': 'estimate'})
        with self.assertRaisesRegex(weekly.RefreshError, 'own freshly verified quotation'):
            self.validate(change)

    def test_confirmation_requires_first_party_evidence(self):
        for url, kind in [('https://stockanalysis.com/stocks/nvda/', 'official'), (self.url, 'estimate')]:
            with self.subTest(url=url, kind=kind):
                change = deepcopy(self.change)
                change['event'].update(sourceUrl=url, sources=[{'url': url, 'label': 'Source', 'kind': kind}])
                change['evidence'][0]['url'] = url
                with self.assertRaisesRegex(weekly.RefreshError, 'first-party'):
                    self.validate(change, searched={url})

    def test_unrelated_organizer_cannot_confirm_company_earnings(self):
        change = deepcopy(self.change)
        url = 'https://www.microchip.com/en-us/about/events'
        change['event'].update(sourceUrl=url, sources=[{'url': url, 'label': 'Industry participant', 'kind': 'official'}])
        change['evidence'][0]['url'] = url
        with self.assertRaisesRegex(weekly.RefreshError, 'first-party'):
            self.validate(change, searched={url})

    def test_estimated_earnings_cannot_include_a_precise_time(self):
        for fields in [{'time': '14:00 Pacific'}, {'startAt': '2026-11-18T22:00:00Z'}, {'endAt': '2026-11-18T23:00:00Z'}]:
            with self.subTest(fields=fields):
                change = deepcopy(self.change)
                change['event'].update(status='estimated', **fields)
                change['event']['sources'][0]['kind'] = 'estimate'
                with self.assertRaises(weekly.RefreshError):
                    self.validate(change)

    def test_utc_source_day_uses_dst_rules_not_hong_kong_display_day(self):
        change = deepcopy(self.change)
        url = 'https://www.apple.com/investor/earnings-call/'
        quote = 'Apple will announce its fourth-quarter results on November 2, 2026, with its confirmed earnings call at 2:00 p.m. Pacific time.'
        change['event'].update(id='AAPL-2026-11-earnings', companies=['AAPL'], date='2026-11-02',
                               sourceUrl=url, sourceLabel='Apple', sources=[{'url': url, 'label': 'Apple', 'kind': 'official'}],
                               startAt='2026-11-02T22:00:00Z', sourceTimeZone='America/Los_Angeles',
                               time='14:00 Pacific', timeCertainty='verified')
        change['evidence'] = [{'url': url, 'quote': quote, 'supports': ['identity', 'date', 'status', 'time']}]
        self.fetcher.return_value = quote
        proposal = self.validate(change, searched={url})
        self.assertEqual(proposal['event']['date'], '2026-11-02')
        instant = datetime.fromisoformat(proposal['event']['startAt'].replace('Z', '+00:00'))
        self.assertEqual(instant.astimezone(weekly.ZoneInfo('America/Los_Angeles')).hour, 14)
        self.assertEqual(instant.astimezone(weekly.ZoneInfo('Asia/Hong_Kong')).date().isoformat(), '2026-11-03')
        change['event']['date'] = '2026-11-03'
        with self.assertRaisesRegex(weekly.RefreshError, 'published source date'):
            self.validate(change, searched={url})

    def test_normalized_start_must_be_utc_and_end_must_follow_it(self):
        for start, end in [('2026-11-18T14:00:00-08:00', None), ('2026-11-18T22:00:00Z', '2026-11-18T21:00:00Z')]:
            with self.subTest(start=start, end=end):
                change = deepcopy(self.change)
                change['event'].update(startAt=start, endAt=end, time='14:00 Pacific', sourceTimeZone='America/Los_Angeles', timeCertainty='verified')
                with self.assertRaises(weekly.RefreshError):
                    self.validate(change)

    def test_historical_records_require_manual_review(self):
        old = deepcopy(self.event)
        old['date'] = '2026-09-01'
        current = deepcopy(self.current)
        current['events'] = [old]
        with self.assertRaisesRegex(weekly.RefreshError, 'Historical records'):
            self.validate(current=current)

    def test_duplicate_earnings_with_new_id_are_rejected(self):
        change = deepcopy(self.change)
        change['event']['id'] = 'NVDA-new-period-same-date'
        with self.assertRaisesRegex(weekly.RefreshError, 'existing stable ID'):
            self.validate(change)

    def test_final_merge_rejects_two_new_same_period_earnings_ids(self):
        proposals = []
        for event_id in ['NVDA-2027-02-earnings', 'NVDA-2027-02-duplicate']:
            event = deepcopy(self.event)
            event.update(id=event_id, date='2027-02-18')
            proposals.append({'event': event})
        original = deepcopy(self.current)
        with self.assertRaisesRegex(weekly.RefreshError, 'duplicate earnings periods in final dataset'):
            weekly.apply_approved(self.current, proposals, {p['event']['id'] for p in proposals}, self.now, [])
        self.assertEqual(self.current, original)

    def test_final_merge_rejects_existing_id_moved_into_another_period(self):
        current = deepcopy(self.current)
        next_period = deepcopy(self.event)
        next_period.update(id='NVDA-2027-02-earnings', date='2027-02-18')
        current['events'].append(next_period)
        moved = deepcopy(self.event)
        moved['date'] = '2027-02-19'
        with self.assertRaisesRegex(weekly.RefreshError, 'duplicate earnings periods in final dataset'):
            weekly.apply_approved(current, [{'event': moved}], {moved['id']}, self.now, [])

    def test_cross_host_redirect_cannot_inherit_official_source_authority(self):
        for destination in ['https://provider.example/earnings', 'https://investor.nvidia.com/new-location']:
            with self.subTest(destination=destination):
                response = MagicMock()
                response.__enter__.return_value = response
                response.geturl.return_value = destination
                response.read.return_value = self.quote.encode()
                headers = Message()
                headers['Content-Type'] = 'text/plain; charset=utf-8'
                response.headers = headers
                opener = Mock()
                opener.open.return_value = response
                public_dns = [(weekly.socket.AF_INET, weekly.socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))]
                with patch.object(weekly, 'build_opener', return_value=opener), patch.object(weekly.socket, 'getaddrinfo', return_value=public_dns):
                    if destination.startswith('https://provider.example/'):
                        with self.assertRaisesRegex(weekly.RefreshError, 'authority is not inherited'):
                            weekly.fetch_evidence(self.url)
                        response.read.assert_not_called()
                    else:
                        self.assertEqual(weekly.fetch_evidence(self.url), self.quote)

    def test_noncanonical_or_invalid_iso_dates_are_rejected(self):
        for value in ['20261118', '2026-W47-3', '2026-11-31', '2026-1-18']:
            with self.subTest(value=value):
                change = deepcopy(self.change)
                change['event']['date'] = value
                with self.assertRaises((weekly.RefreshError, ValueError)):
                    self.validate(change)

    def test_end_date_without_a_start_date_is_rejected(self):
        change = deepcopy(self.change)
        change['event'].update(id='NVDA-future-monitor', status='unannounced', date=None, endDate='2026-11-19')
        with self.assertRaisesRegex(weekly.RefreshError, 'endDate|end date|start date'):
            self.validate(change)

    def test_timing_window_cannot_claim_an_exact_or_confirmed_day(self):
        change = deepcopy(self.change)
        change['event']['timingWindow'] = {'start': '2026-11-01', 'end': '2026-11-30', 'label': 'November 2026', 'precision': 'month'}
        with self.assertRaisesRegex(weekly.RefreshError, 'approximate window'):
            self.validate(change)

    def test_earnings_need_a_published_day_not_a_guessed_month(self):
        change = deepcopy(self.change)
        change['event'].update(status='estimated', date=None,
                               timingWindow={'start':'2026-11-01','end':'2026-11-30','label':'November','precision':'month'})
        with self.assertRaisesRegex(weekly.RefreshError, 'published day-level date'):
            self.validate(change)

    def test_preflight_reports_missing_configuration_without_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / 'report.json'
            output = io.StringIO()
            with patch.dict(weekly.os.environ, {'OPENAI_API_KEY': 'sensitive-key-never-log'}, clear=True), contextlib.redirect_stdout(output):
                self.assertEqual(weekly.preflight(report_path), 1)
            report = json.loads(report_path.read_text())
            text = output.getvalue() + report_path.read_text()
            self.assertEqual(report['result'], 'blocked')
            self.assertIn('RESEND_API_KEY', text)
            self.assertIn('GLOBAL_TECH_EMAIL_FROM', text)
            self.assertNotIn('sensitive-key-never-log', text)

    def test_preflight_rejects_weaker_model_or_reasoning_policy(self):
        for model, effort in [('other-model', 'max'), ('gpt-6-astra', 'low')]:
            with self.subTest(model=model, effort=effort), tempfile.TemporaryDirectory() as directory:
                with patch.object(weekly, 'MODEL', model), patch.object(weekly, 'EFFORT', effort), patch.dict(weekly.os.environ, {'OPENAI_API_KEY': 'test', 'RESEND_API_KEY': 'test', 'GLOBAL_TECH_EMAIL_FROM': 'calendar@example.com'}, clear=True), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(weekly.preflight(Path(directory) / 'report.json'), 1)

    def test_preflight_rejects_invalid_sender_before_any_api_call(self):
        for sender in ['not-an-email', 'sender@example.com\nBcc: attacker@example.com', 'one@example.com, two@example.com']:
            with self.subTest(sender=sender), tempfile.TemporaryDirectory() as directory:
                output = io.StringIO()
                report_path = Path(directory) / 'report.json'
                environment = {'OPENAI_API_KEY': 'secret-model-token', 'RESEND_API_KEY': 'secret-mail-token', 'GLOBAL_TECH_EMAIL_FROM': sender}
                with patch.dict(weekly.os.environ, environment, clear=True), patch.object(weekly, 'api_request') as api, contextlib.redirect_stdout(output):
                    self.assertEqual(weekly.preflight(report_path), 1)
                api.assert_not_called()
                report = json.loads(report_path.read_text())
                self.assertEqual(report['result'], 'blocked')
                combined = report_path.read_text() + output.getvalue()
                self.assertIn('valid single GLOBAL_TECH_EMAIL_FROM sender', combined)
                self.assertNotIn('secret-model-token', combined)
                self.assertNotIn('secret-mail-token', combined)
                self.assertNotIn(sender, combined)

    def test_independent_review_must_account_for_every_proposal_and_company(self):
        for issue in ['missing-proposal', 'duplicate-approval', 'missing-company']:
            with self.subTest(issue=issue), tempfile.TemporaryDirectory() as directory:
                temporary_root = Path(directory)
                (temporary_root / 'data').mkdir()
                dataset = temporary_root / 'data/events.json'
                dataset.write_text(json.dumps(self.current))
                original = dataset.read_bytes()
                report_path = temporary_root / 'run/report.json'

                def research(label, instructions, payload, schema, workdir):
                    if label == 'independent_review':
                        review = {'approvedIds': [self.event['id']], 'rejected': [],
                                  'companiesReviewed': [c['id'] for c in self.current['companies']],
                                  'warnings': [], 'summary': 'Fixture review'}
                        if issue == 'missing-proposal':
                            review['approvedIds'] = []
                        elif issue == 'duplicate-approval':
                            review['approvedIds'] *= 2
                        else:
                            review['companiesReviewed'].pop()
                        return review, set()
                    checks = [{'company': c['id'], 'outcome': 'checked', 'note': 'Offline fixture'} for c in payload['assignedCompanies']]
                    return {'checks': checks, 'updates': [self.change] if label == 'group_1' else [], 'warnings': []}, {self.url}

                proposal = {'event': self.event, 'evidence': [], 'previous': None}
                with patch.object(weekly, 'ROOT', temporary_root), patch.object(weekly, 'research_call', side_effect=research), patch.object(weekly, 'validate_change', return_value=proposal), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(weekly.run(report_path), 1)
                self.assertEqual(dataset.read_bytes(), original, 'Review-accounting failures must preserve the published dataset')
                report = json.loads(report_path.read_text())
                self.assertEqual(report['result'], 'failed')
                self.assertTrue(report['warnings'])


if __name__ == '__main__':
    unittest.main()
