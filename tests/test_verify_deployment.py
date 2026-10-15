"""A deployed wrong or unavailable dataset must never produce a success result."""
import contextlib
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


if __name__ == '__main__':
    unittest.main()
