#!/usr/bin/env python3
"""Only report success when the public dataset matches the approved artifact."""
import argparse
import hashlib
from pathlib import Path
import re
import time
from urllib.error import URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SITE = 'https://hangyul-son.github.io/global-tech-team-features/'


def normalize_site_url(value):
    if not isinstance(value, str) or not value or len(value) > 1000 or any(ord(c) <= 32 or ord(c) == 127 for c in value) or '?' in value or '#' in value or '\\' in value:
        raise ValueError('Invalid public site URL.')
    try:
        parts = urlsplit(value)
        host = parts.hostname or ''
        if parts.scheme != 'https' or not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', host) or '.' not in host or parts.username or parts.password or parts.port not in (None, 443):
            raise ValueError('Invalid public site URL.')
    except ValueError:
        raise ValueError('Invalid public site URL.') from None
    return urlunsplit(('https', parts.netloc.lower(), parts.path.rstrip('/') + '/', '', ''))


def verify(attempts=12, site_url=None):
    try:
        site = normalize_site_url(SITE if site_url is None else site_url)
    except ValueError:
        print('Public deployment URL is invalid. Verification was not attempted.')
        return 1
    expected = hashlib.sha256((ROOT / 'data/events.json').read_bytes()).hexdigest()
    for attempt in range(attempts):
        try:
            request = Request(site + 'data/events.json?weekly=' + expected,
                              headers={'Cache-Control': 'no-cache'})
            with urlopen(request, timeout=20) as response:
                actual = hashlib.sha256(response.read(5_000_001)).hexdigest()
            if actual == expected:
                print('Public calendar matches the approved event dataset.')
                return 0
        except (URLError, TimeoutError, OSError):
            pass
        if attempt < attempts - 1:
            time.sleep(6)
    print('Public deployment could not be verified. A success email must not be sent.')
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-url', default=SITE, help='Actual HTTPS URL returned by the Pages deployment.')
    args = parser.parse_args(argv)
    return verify(site_url=args.site_url)


if __name__ == '__main__':
    raise SystemExit(main())
