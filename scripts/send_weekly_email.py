#!/usr/bin/env python3
"""Send a plain-text weekly-run result to the fixed Global Tech recipient.

Requires a verified Resend sender in GLOBAL_TECH_EMAIL_FROM and RESEND_API_KEY.
Report contents cannot select the recipient, sender, result or message format.
"""

import argparse
from datetime import datetime, timezone
from email.utils import formataddr, getaddresses, parseaddr
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import textwrap
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


RECIPIENT = 'hangyul.son@clsa.com'
ENDPOINT = 'https://api.resend.com/emails'
DEFAULT_SITE = 'https://hangyul-son.github.io/global-tech-team-features/'
RESULTS = {
    'published': ('Published', 'The calendar update was published.'),
    'unchanged': ('No calendar changes', 'The research run completed without calendar changes.'),
    'failed': ('FAILED', 'The weekly update failed. A successful update is not being claimed.'),
    'blocked': ('BLOCKED', 'The weekly update was blocked. A successful update is not being claimed.'),
}
MAX_REPORT_BYTES = 1_000_000
MAX_BODY_LINES = 240
LINE_WIDTH = 1024
TEXT_WIDTH = 140


class NotificationError(Exception):
    """An actionable notification failure without remote response contents."""


def clean_text(value, limit=1000):
    if not isinstance(value, str):
        return ''
    return re.sub(r'\s+', ' ', ''.join(c if ord(c) >= 32 and ord(c) != 127 else ' ' for c in value)).strip()[:limit]


def safe_url(value):
    if not isinstance(value, str) or len(value) > 1000 or any(ord(c) <= 32 or ord(c) == 127 for c in value):
        return None
    try:
        url = urlsplit(value)
        if url.scheme != 'https' or not url.hostname or url.username or url.password:
            return None
        _ = url.port
    except ValueError:
        return None
    return value


def validate_sender(value):
    if not isinstance(value, str) or not value or len(value) > 320 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise NotificationError('GLOBAL_TECH_EMAIL_FROM must contain one valid email sender without control characters.')
    name, address = parseaddr(value)
    addresses = getaddresses([value])
    if len(addresses) != 1 or addresses[0] != (name, address) or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}", address):
        raise NotificationError('GLOBAL_TECH_EMAIL_FROM must contain one valid email sender.')
    return formataddr((name, address))


def load_report(path):
    if path is None:
        return {}
    try:
        if path.stat().st_size > MAX_REPORT_BYTES:
            raise NotificationError('Weekly report exceeds the notification size limit.')
        report = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError):
        raise NotificationError('Weekly report could not be read as JSON.') from None
    if not isinstance(report, dict):
        raise NotificationError('Weekly report must be a JSON object.')
    return report


def idempotency_key(report, environ, result):
    run_id = environ.get('GITHUB_RUN_ID')
    if run_id:
        identity = f"github:{run_id}:{environ.get('GITHUB_RUN_ATTEMPT', '1')}"
    else:
        timestamp = clean_text(report.get('completedAt')) or clean_text(report.get('startedAt'))
        identity = 'report:' + (timestamp or datetime.now(timezone.utc).isoformat(timespec='microseconds'))
    digest = hashlib.sha256(f'{identity}:{result}'.encode('utf-8')).hexdigest()[:48]
    return 'global-tech-weekly-' + digest


def compose_message(result, report, site_url, run_url=None):
    if result not in RESULTS:
        raise NotificationError('Unknown weekly-run result.')
    if not safe_url(site_url) or (run_url and not safe_url(run_url)):
        raise NotificationError('Site and workflow links must be valid HTTPS URLs without credentials.')
    warnings = report.get('warnings', [])
    if not isinstance(warnings, list):
        warnings = []
    label, explanation = RESULTS[result]
    if result == 'published' and warnings:
        label = 'Published with exceptions'
        explanation = 'The calendar update was published with exceptions. Review the warnings below.'
    lines = ['Global Tech weekly update', f'Result: {label}', explanation, '',
             f'Website: {site_url}', f'Workflow run: {run_url or "Not supplied"}', '']
    for key, title in [('startedAt', 'Started'), ('completedAt', 'Completed'), ('model', 'Model'), ('reasoning', 'Reasoning')]:
        value = clean_text(report.get(key), 500)
        if value:
            lines.append(f'{title}: {value}')
    lines += ['', 'Warnings / exceptions:']
    if warnings:
        lines += ['- ' + (clean_text(item, 600) or 'Unspecified warning') for item in warnings[:30]]
        if len(warnings) > 30:
            lines.append('Additional warnings omitted; see the workflow report.')
    else:
        lines.append('No warnings were supplied in the run report.')
    sections = [('added', 'Added events'), ('updated', 'Updated events')]
    if result in ('failed', 'blocked'):
        sections = [('added', 'Proposed additions (publication not verified)'),
                    ('updated', 'Proposed changes (publication not verified)')]
    for field, title in sections:
        records = report.get(field, [])
        if not isinstance(records, list):
            records = []
        lines += ['', f'{title}: {len(records)}']
        for event in records[:40]:
            if not isinstance(event, dict):
                continue
            title_text = clean_text(event.get('title'), 250) or 'Untitled event'
            date_text = clean_text(event.get('date'), 100) or 'No exact date supplied'
            lines.append(f'- {date_text}: {title_text}')
            source = safe_url(event.get('sourceUrl'))
            lines.append(f'  Source: {source}' if source else '  Source link unavailable in run report.')
        if len(records) > 40:
            lines.append('Additional changes omitted from this email; see the workflow report.')
    lines += ['', 'Dates remain subject to change. Estimates are not company confirmations.',
              'This email reports the workflow result; it is not a guarantee of complete or error-free coverage.']
    wrapped = []
    for line in lines:
        # Keep bounded HTTPS links intact so plain-text email clients can open
        # long official IR URLs instead of linking only the first wrapped part.
        if len(line) <= LINE_WIDTH and any(safe_url(token) for token in line.split()):
            wrapped.append(line)
        else:
            wrapped.extend(textwrap.wrap(line, width=TEXT_WIDTH, break_long_words=True, break_on_hyphens=False) or [''])
    if len(wrapped) > MAX_BODY_LINES:
        wrapped = wrapped[:MAX_BODY_LINES - 1] + ['Email truncated; see the workflow report for full details.']
    return f'Global Tech weekly update - {label}', '\n'.join(wrapped) + '\n'


def send_notification(payload, api_key, key, attempts=3):
    encoded = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    for attempt in range(attempts):
        request = Request(ENDPOINT, data=encoded, method='POST', headers={
            'Authorization': 'Bearer ' + api_key,
            'Content-Type': 'application/json',
            'Idempotency-Key': key,
            'User-Agent': 'GlobalTechWeeklyNotifier/1.0',
        })
        try:
            with urlopen(request, timeout=20) as response:
                if not 200 <= response.status < 300:
                    raise NotificationError('Email provider did not accept the notification.')
                raw = response.read(65537)
            if len(raw) > 65536:
                raise NotificationError('Email provider returned an invalid response.')
            try:
                result = json.loads(raw)
            except (ValueError, UnicodeError):
                raise NotificationError('Email provider returned an invalid response.') from None
            if not isinstance(result, dict) or not isinstance(result.get('id'), str) or not result['id']:
                raise NotificationError('Email provider did not return a notification identifier.')
            return result['id']
        except HTTPError as error:
            retry = error.code == 429 or 500 <= error.code <= 599
            if not retry or attempt == attempts - 1:
                raise NotificationError(f'Email provider rejected the notification (HTTP {error.code}).') from None
        except (URLError, TimeoutError, OSError):
            if attempt == attempts - 1:
                raise NotificationError('Email provider could not be reached after retrying.') from None
        if attempt < attempts - 1:
            time.sleep(attempt + 1)
    raise NotificationError('Email notification was not accepted.')


def main(argv=None, environ=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--result', required=True, choices=RESULTS)
    parser.add_argument('--run-url')
    parser.add_argument('--site-url', default=DEFAULT_SITE)
    parser.add_argument('--dry-run', action='store_true', help='Print the plain-text message without contacting the email service.')
    args = parser.parse_args(argv)
    environ = os.environ if environ is None else environ
    try:
        report = load_report(args.report)
        subject, body = compose_message(args.result, report, args.site_url, args.run_url)
        if args.dry_run:
            print(f'To: {RECIPIENT}\nSubject: {subject}\n\n{body}', end='')
            return 0
        api_key = environ.get('RESEND_API_KEY', '').strip()
        if not api_key or any(ord(c) < 33 or ord(c) == 127 for c in api_key):
            raise NotificationError('RESEND_API_KEY is required for email notifications.')
        sender = validate_sender(environ.get('GLOBAL_TECH_EMAIL_FROM', ''))
        payload = {'from': sender, 'to': [RECIPIENT], 'subject': subject, 'text': body}
        send_notification(payload, api_key, idempotency_key(report, environ, args.result))
        print('Weekly notification accepted by the email provider.')
        return 0
    except NotificationError as error:
        print(f'Weekly notification failed: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
