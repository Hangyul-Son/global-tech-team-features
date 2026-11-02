#!/usr/bin/env python3
"""Verify the deployed property JSON files against this exact checkout.

Only public data is read. No credentials or private service are required.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

FILES = ('data.json', 'trends.json', 'listings.json', 'refresh-status.json')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify(site_url: str, site_dir: Path, *, attempts: int = 6,
           delay: float = 10.0, timeout: float = 15.0) -> bool:
    """Retry CDN propagation, with each request/wait and total budget bounded."""
    if attempts < 1 or not 0 <= delay <= 30 or not 0 < timeout <= 30:
        raise ValueError('Invalid retry bounds')
    public_base = site_url.rstrip('/') + '/' + site_dir.name + '/'
    expected = {}
    for name in FILES:
        payload = (site_dir / name).read_bytes()
        json.loads(payload)
        expected[name] = digest(payload)
    # Cap the complete verification step to two minutes, including network I/O.
    deadline = time.monotonic() + 120
    remaining = set(FILES)
    for attempt in range(1, attempts + 1):
        for name in sorted(remaining):
            budget = deadline - time.monotonic()
            if budget <= 0:
                break
            # A content-hash query avoids stale CDN cache entries. The hash is
            # public and identifies the dataset; it is not a credential.
            url = public_base + urllib.parse.quote(name) + '?v=' + expected[name]
            request = urllib.request.Request(url, headers={
                'User-Agent': 'HomeLens-PagesVerifier/1.0',
                'Accept': 'application/json',
            })
            try:
                with urllib.request.urlopen(request, timeout=min(timeout, budget)) as response:
                    payload = response.read(16 * 1024 * 1024 + 1)
                    if len(payload) > 16 * 1024 * 1024:
                        raise ValueError('Published JSON exceeded verification size bound')
                    json.loads(payload)
                    observed = digest(payload)
                    if observed != expected[name]:
                        print(f'{name}: CDN serves a different dataset; retrying.', flush=True)
                        continue
                remaining.remove(name)
                print(f'{name}: published SHA-256 matches {expected[name]}', flush=True)
            except (OSError, ValueError, urllib.error.URLError) as error:
                print(f'{name}: verification attempt {attempt} failed: {error}', flush=True)
        if not remaining:
            print('Public property datasets match the checked-out source.', flush=True)
            return True
        if attempt < attempts:
            wait = min(delay, max(0.0, deadline - time.monotonic()))
            if wait:
                time.sleep(wait)
        if time.monotonic() >= deadline:
            break
    print('Publication verification incomplete for: ' + ', '.join(sorted(remaining)), file=sys.stderr)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-url', required=True)
    parser.add_argument('--site-dir', type=Path, default=Path('hong-kong-property'))
    args = parser.parse_args()
    parsed = urllib.parse.urlparse(args.site_url)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        parser.error('--site-url must be an HTTP(S) origin/base URL')
    return 0 if verify(args.site_url, args.site_dir) else 1


if __name__ == '__main__':
    raise SystemExit(main())
