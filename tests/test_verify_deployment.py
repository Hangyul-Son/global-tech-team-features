"""A deployed wrong or unavailable dataset must never produce a success result."""
import contextlib
import hashlib
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('verify_deployment', ROOT / 'scripts/verify_deployment.py')
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


class PublicationVerificationTests(unittest.TestCase):
    def test_only_the_actual_approved_bytes_pass(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = (ROOT / 'data/events.json').read_bytes()
        with patch.object(verify, 'urlopen', return_value=response) as fetch, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(verify.verify(attempts=1), 0)
        request = fetch.call_args.args[0]
        self.assertTrue(request.full_url.startswith(verify.SITE + 'data/events.json?weekly='))

    def test_a_stale_or_wrong_deployment_fails(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"events": []}'
        with patch.object(verify, 'urlopen', return_value=response), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(verify.verify(attempts=1), 1)

    def test_an_unreachable_site_is_not_a_success(self):
        with patch.object(verify, 'urlopen', side_effect=URLError('unavailable')), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(verify.verify(attempts=1), 1)

    def test_actual_deployment_url_is_used_and_trailing_slash_normalized(self):
        approved = (ROOT / 'data/events.json').read_bytes()
        response = MagicMock()
        response.__enter__.return_value.read.return_value = approved
        deployment_url = 'https://hangyul-son.github.io/another-repository'
        with patch.object(verify, 'urlopen', return_value=response) as fetch, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(verify.verify(attempts=1, site_url=deployment_url), 0)
        expected = deployment_url + '/data/events.json?weekly=' + hashlib.sha256(approved).hexdigest()
        self.assertEqual(fetch.call_args.args[0].full_url, expected)

    def test_invalid_site_url_is_rejected_before_network_access(self):
        urls = ['', 'http://example.com/site/', 'https://user:password@example.com/site/',
                'https://example.com/site/?query=yes', 'https://example.com/site/?',
                'https://example.com/site/#fragment', 'https://example.com/site/#',
                'https://example.com/site/\nInjected', 'https://example.com:8443/site/',
                'https://example.com:invalid/site/', 'https://example.com\\attacker/path/',
                'https://[broken/', 'not-a-url']
        for value in urls:
            with self.subTest(url=value), patch.object(verify, 'urlopen') as fetch, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(verify.verify(attempts=1, site_url=value), 1)
                fetch.assert_not_called()

    def test_cli_passes_actual_pages_url_to_verification(self):
        deployment_url = 'https://hangyul-son.github.io/global-tech-team-features/'
        with patch.object(verify, 'verify', return_value=0) as check:
            self.assertEqual(verify.main(['--site-url', deployment_url]), 0)
        check.assert_called_once_with(site_url=deployment_url)


if __name__ == '__main__':
    unittest.main()
