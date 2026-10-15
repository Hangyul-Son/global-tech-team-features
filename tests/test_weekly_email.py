import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('weekly_email', ROOT / 'scripts/send_weekly_email.py')
email = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(email)


class Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return b'{"id":"accepted-message-id"}'


class WeeklyEmailTests(unittest.TestCase):
    def setUp(self):
        self.environ = {'RESEND_API_KEY': 'test-secret-not-for-output',
                        'GLOBAL_TECH_EMAIL_FROM': 'Global Tech <calendar@example.com>',
                        'GITHUB_RUN_ID': '12345', 'GITHUB_RUN_ATTEMPT': '1'}
        self.report = {'model': 'chosen-model', 'reasoning': 'maximum',
                       'startedAt': '2026-10-17T18:00:00Z', 'completedAt': '2026-10-17T18:30:00Z',
                       'added': [{'title': 'Company earnings', 'date': '2026-10-25',
                                  'sourceUrl': 'https://example.com/earnings'}],
                       'updated': [], 'warnings': ['A source could not be reached.'],
                       'to': ['attacker@example.com'], 'result': 'published', 'html': '<script>unsafe</script>'}

    def test_payload_has_fixed_recipient_and_plain_text_only(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / 'report.json'
            report.write_text(json.dumps(self.report))
            with patch.object(email, 'urlopen', return_value=Response()) as request, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(email.main(['--result', 'published', '--report', str(report), '--run-url', 'https://github.com/example/actions/runs/1'], self.environ), 0)
        sent = request.call_args.args[0]
        payload = json.loads(sent.data)
        self.assertEqual(sent.full_url, 'https://api.resend.com/emails')
        self.assertEqual(sent.method, 'POST')
        self.assertEqual(payload['to'], ['hangyul.son@clsa.com'])
        self.assertNotIn('html', payload)
        self.assertIn('Company earnings', payload['text'])
        self.assertIn('https://example.com/earnings', payload['text'])
        self.assertIn('https://github.com/example/actions/runs/1', payload['text'])
        self.assertIn('A source could not be reached.', payload['text'])
        self.assertNotIn(self.environ['RESEND_API_KEY'], payload['text'])

    def test_failed_and_blocked_never_claim_publication(self):
        for result in ['failed', 'blocked']:
            with self.subTest(result=result):
                subject, text = email.compose_message(result, self.report, email.DEFAULT_SITE, 'https://github.com/example/run/1')
                self.assertIn(result.upper(), subject)
                self.assertIn('A successful update is not being claimed.', text)
                self.assertNotIn('The calendar update was published.', text)
                self.assertIn('Proposed additions (publication not verified): 1', text)
                self.assertIn('Proposed changes (publication not verified): 0', text)
                self.assertNotIn('Added events:', text)
                self.assertNotIn('Updated events:', text)
        subject, text = email.compose_message('unchanged', {}, email.DEFAULT_SITE)
        self.assertIn('No calendar changes', subject)
        self.assertIn('without calendar changes', text)

    def test_published_with_warnings_is_prominent_in_subject_and_body(self):
        subject, text = email.compose_message('published', self.report, email.DEFAULT_SITE)
        self.assertIn('Published with exceptions', subject)
        self.assertIn('Result: Published with exceptions', text)
        self.assertIn('published with exceptions', text)
        self.assertIn('A source could not be reached.', text)
        self.assertIn('Added events: 1', text)

    def test_fully_published_result_does_not_invent_exceptions(self):
        report = {**self.report, 'warnings': []}
        subject, text = email.compose_message('published', report, email.DEFAULT_SITE)
        self.assertEqual(subject, 'Global Tech weekly update - Published')
        self.assertIn('The calendar update was published.', text)
        self.assertNotIn('Published with exceptions', text)

    def test_idempotency_uses_run_and_attempt_or_report_timestamp(self):
        key = email.idempotency_key(self.report, self.environ, 'published')
        self.assertEqual(key, email.idempotency_key(self.report, self.environ, 'published'))
        self.assertNotEqual(key, email.idempotency_key(self.report, {**self.environ, 'GITHUB_RUN_ATTEMPT': '2'}, 'published'))
        self.assertNotEqual(key, email.idempotency_key(self.report, self.environ, 'failed'))
        report_key = email.idempotency_key(self.report, {}, 'published')
        self.assertEqual(report_key, email.idempotency_key(self.report, {}, 'published'))
        self.assertNotEqual(report_key, email.idempotency_key({**self.report, 'completedAt': '2026-10-24T18:30:00Z'}, {}, 'published'))
        self.assertNotEqual(email.idempotency_key({}, {}, 'failed'), email.idempotency_key({}, {}, 'failed'))

    def test_retries_transient_errors_with_same_idempotency_key(self):
        failures = [HTTPError(email.ENDPOINT, 429, 'rate limit', {}, None),
                    HTTPError(email.ENDPOINT, 503, 'temporary', {}, None), Response()]
        with patch.object(email, 'urlopen', side_effect=failures) as request, patch.object(email.time, 'sleep') as sleep:
            message_id = email.send_notification({'to': [email.RECIPIENT]}, 'secret', 'same-key')
        self.assertEqual(message_id, 'accepted-message-id')
        self.assertEqual(request.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertTrue(all(call.args[0].get_header('Idempotency-key') == 'same-key' for call in request.call_args_list))

    def test_provider_failure_is_nonzero_without_response_or_key_logging(self):
        remote_body = io.BytesIO(b'very-sensitive-remote-body')
        failure = HTTPError(email.ENDPOINT, 401, 'remote secret message', {}, remote_body)
        errors = io.StringIO()
        with patch.object(email, 'urlopen', side_effect=failure) as request, contextlib.redirect_stderr(errors):
            self.assertEqual(email.main(['--result', 'failed'], self.environ), 1)
        self.assertEqual(request.call_count, 1)
        self.assertIn('HTTP 401', errors.getvalue())
        self.assertNotIn('very-sensitive', errors.getvalue())
        self.assertNotIn('remote secret', errors.getvalue())
        self.assertNotIn(self.environ['RESEND_API_KEY'], errors.getvalue())

    def test_network_retries_are_bounded(self):
        with patch.object(email, 'urlopen', side_effect=URLError('sensitive-network-details')) as request, patch.object(email.time, 'sleep'):
            with self.assertRaisesRegex(email.NotificationError, 'could not be reached'):
                email.send_notification({}, 'secret', 'same-key')
        self.assertEqual(request.call_count, 3)

    def test_missing_configuration_fails_without_network(self):
        for environ in [{}, {'RESEND_API_KEY': 'test'}]:
            with self.subTest(keys=list(environ)), patch.object(email, 'urlopen') as request, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(email.main(['--result', 'blocked'], environ), 1)
                request.assert_not_called()

    def test_sender_newlines_and_multiple_addresses_are_rejected(self):
        for value in ['calendar@example.com\nBcc: attacker@example.com',
                      'one@example.com, two@example.com', 'not-an-email', '']:
            with self.subTest(value=value), self.assertRaises(email.NotificationError):
                email.validate_sender(value)
        self.assertEqual(email.validate_sender('Global Tech <calendar@example.com>'), 'Global Tech <calendar@example.com>')

    def test_dry_run_needs_no_credentials_and_does_not_send(self):
        output = io.StringIO()
        with patch.object(email, 'urlopen') as request, contextlib.redirect_stdout(output):
            self.assertEqual(email.main(['--result', 'blocked', '--dry-run'], {}), 0)
        request.assert_not_called()
        self.assertIn('To: hangyul.son@clsa.com', output.getvalue())
        self.assertIn('Result: BLOCKED', output.getvalue())

    def test_report_text_is_capped_and_links_reject_injection(self):
        report = {**self.report, 'warnings': ['bad\nheader\r' + ('word ' * 1000)] * 1000,
                  'added': [{'title': 'x' * 10000, 'date': '2026-10-25', 'sourceUrl': 'javascript:alert(1)'}] * 1000}
        subject, body = email.compose_message('published', report, email.DEFAULT_SITE)
        self.assertLessEqual(len(body.splitlines()), email.MAX_BODY_LINES)
        self.assertTrue(all(len(line) <= email.LINE_WIDTH for line in body.splitlines()))
        self.assertNotIn('javascript:', body)
        self.assertNotIn('\r', body)
        for link in ['https://user:password@example.com/', 'http://example.com/', 'https://example.com/\nBcc:']:
            with self.subTest(link=link), self.assertRaises(email.NotificationError):
                email.compose_message('published', {}, link)

    def test_long_official_source_urls_remain_openable(self):
        source = 'https://example.com/investor/news/' + ('long-name-' * 30)
        report = {'added': [{'title': 'Earnings', 'date': '2026-10-25', 'sourceUrl': source}]}
        _, body = email.compose_message('published', report, email.DEFAULT_SITE)
        self.assertIn(source, body)
        self.assertTrue(all(len(line) <= email.LINE_WIDTH for line in body.splitlines()))

    def test_invalid_report_is_rejected_before_sending(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / 'report.json'
            report.write_text('[]')
            with patch.object(email, 'urlopen') as request, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(email.main(['--result', 'failed', '--report', str(report)], self.environ), 1)
        request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
