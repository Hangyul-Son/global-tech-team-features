#!/usr/bin/env python3
"""Only report success when the public dataset matches the approved artifact."""
import hashlib
from pathlib import Path
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SITE = 'https://hangyul-son.github.io/train-me-to-be-a-better-financial-analyst/'


def verify(attempts=12):
    expected = hashlib.sha256((ROOT / 'data/events.json').read_bytes()).hexdigest()
    for attempt in range(attempts):
        try:
            request = Request(SITE + 'data/events.json?weekly=' + expected,
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


if __name__ == '__main__':
    raise SystemExit(verify())
