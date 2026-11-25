#!/usr/bin/env python3
"""Compose and send the Global Tech daily brief to the fixed team recipient.

The brief is built only from the reviewed dataset (data/events.json) plus an
optional run report written by the daily routine. It lists, in Hong Kong time:

* Today
* Next 7 days (the following seven calendar days)
* Next 30 days (days 8-30, so nothing is repeated from the 7-day section)

Events involving one of the 12 coverage companies carry a star and are
highlighted, exactly as on the website. Delivery uses the Resend HTTPS API.
RESEND_API_KEY may be absent inside a Claude cloud session: the session's
network proxy injects the saved credential for api.resend.com, so a
placeholder bearer token is sent and replaced in transit.
"""

import argparse
from datetime import date, datetime, timedelta, timezone
from email.utils import formataddr, getaddresses, parseaddr
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / 'data/events.json'
RECIPIENT = 'hangyul.son@clsa.com'
ENDPOINT = 'https://api.resend.com/emails'
DEFAULT_SITE = 'https://hangyul-son.github.io/global-tech-team-features/'
DEFAULT_SENDER = 'Global Tech <onboarding@resend.dev>'
PROXY_PLACEHOLDER_KEY = 're_injected_by_session_proxy'
HKT = ZoneInfo('Asia/Hong_Kong')
RESULTS = {
    'published': 'Calendar updated and published',
    'unchanged': 'Research completed · no calendar changes',
    'unpublished': 'Calendar changes committed · live site not yet verified',
    'failed': 'Research run FAILED · calendar not updated',
    'blocked': 'Research run BLOCKED · calendar not updated',
}
STATUS_LABELS = {
    'confirmed': 'Confirmed',
    'estimated': 'Estimate',
    'reported': 'Media-reported',
    'unannounced': 'Not announced',
}
# Event type owns colour on the website; the brief mirrors that palette.
TYPE_COLORS = {
    'Earnings': '#1e53b5',
    'Conference': '#116b60',
    'Keynote': '#7043ad',
    'Investor day': '#925b10',
    'Operating update': '#286679',
    'IPO watch': '#4e6077',
}
DEFAULT_TYPE_COLOR = '#4e6077'
HIGHLIGHT_BG = '#fff4d6'
HIGHLIGHT_BORDER = '#d9a21b'
STAR_COLOR = '#967016'
MAX_REPORT_BYTES = 1_000_000
MAX_LIST = 40


class BriefError(Exception):
    """An actionable failure without remote response contents."""


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def clean_text(value, limit=1000):
    if not isinstance(value, str):
        return ''
    text = ''.join(c if ord(c) >= 32 and ord(c) != 127 else ' ' for c in value)
    return re.sub(r'\s+', ' ', text).strip()[:limit]


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


def esc(value):
    return html.escape(str(value), quote=True)


def parse_instant(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def day_label(day):
    return f"{day.strftime('%a')} {day.day} {day.strftime('%b')}"


def long_day(day):
    return f"{day.strftime('%A')}, {day.day} {day.strftime('%B %Y')}"


def range_label(start, end):
    if start == end:
        return day_label(start)
    return f'{day_label(start)} – {day_label(end)}'


def validate_sender(value):
    if not isinstance(value, str) or not value or len(value) > 320 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise BriefError('GLOBAL_TECH_EMAIL_FROM must contain one valid email sender without control characters.')
    name, address = parseaddr(value)
    addresses = getaddresses([value])
    if len(addresses) != 1 or addresses[0] != (name, address) or not re.fullmatch(
            r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}", address):
        raise BriefError('GLOBAL_TECH_EMAIL_FROM must contain one valid email sender.')
    return formataddr((name, address))


# --------------------------------------------------------------------------
# Dataset -> brief rows
# --------------------------------------------------------------------------

def event_span(event):
    """Return (start, end) Hong Kong calendar dates, or None when undated.

    Mirrors js/calendar-utils.js: verified instants are converted to Hong Kong
    time; date-only events keep their published source date; timing windows
    use their uncertainty boundaries.
    """
    if event.get('startAt'):
        start = parse_instant(event['startAt']).astimezone(HKT).date()
        end = start
        if event.get('endAt'):
            end = (parse_instant(event['endAt']) - timedelta(seconds=1)).astimezone(HKT).date()
            end = max(end, start)
        return start, end
    if event.get('date'):
        start = date.fromisoformat(event['date'])
        end = date.fromisoformat(event['endDate']) if event.get('endDate') else start
        return start, max(start, end)
    window = event.get('timingWindow')
    if window and window.get('start'):
        start = date.fromisoformat(window['start'])
        end = date.fromisoformat(window.get('end') or window['start'])
        return start, max(start, end)
    return None


def time_label(event):
    """Hong Kong time for verified instants; never invents a clock time."""
    if event.get('startAt'):
        start = parse_instant(event['startAt'])
        local = start.astimezone(HKT)
        text = f"{local:%H:%M} HKT"
        source_zone = event.get('sourceTimeZone')
        if source_zone and source_zone != 'Asia/Hong_Kong':
            try:
                source = start.astimezone(ZoneInfo(source_zone))
                text += f" · {day_label(source.date())} {source:%H:%M} {source.tzname()}"
            except (KeyError, ValueError):
                pass
        if event.get('timeCertainty') == 'reported':
            text += ' (reported)'
        return text
    if event.get('timingWindow'):
        return 'Timing window · no exact day'
    if event.get('time'):
        # Published wording exists but was not normalized to a verified instant.
        return 'Source time: ' + clean_text(event['time'], 120)
    return 'Time not announced'


def build_rows(data, today):
    companies = {c['id']: c for c in data.get('companies', [])}
    coverage = {cid for cid, c in companies.items() if c.get('coverage')}
    sections = [
        ('today', 'Today', today, today),
        ('week', 'Next 7 days', today + timedelta(days=1), today + timedelta(days=7)),
        ('month', 'Next 30 days (days 8–30)', today + timedelta(days=8), today + timedelta(days=30)),
    ]
    out = {key: [] for key, *_ in sections}
    for event in data.get('events', []):
        span = event_span(event)
        if not span:
            continue
        start, end = span
        for key, _label, first, last in sections:
            if start <= last and end >= first:
                starred = bool(set(event.get('companies') or []) & coverage)
                tickers = list(dict.fromkeys(event.get('companies') or []))
                names = [companies[t]['name'] for t in tickers if t in companies]
                out[key].append({
                    'id': event['id'],
                    'title': clean_text(event.get('title'), 300),
                    'type': clean_text(event.get('type'), 60),
                    'status': event.get('status', ''),
                    'statusLabel': STATUS_LABELS.get(event.get('status'), clean_text(event.get('status'), 40)),
                    'start': start,
                    'end': end,
                    'ongoing': start < first,
                    'window': (event.get('timingWindow') or {}).get('label'),
                    'time': time_label(event),
                    'sortTime': event.get('startAt') or '',
                    'starred': starred,
                    'tickers': tickers,
                    'names': names or ([event['organizer']] if event.get('organizer') else []),
                    'coverageNames': [companies[t]['name'] for t in tickers if t in coverage],
                    'importance': clean_text(event.get('importance'), 300),
                    'source': safe_url(event.get('sourceUrl')),
                    'sourceLabel': clean_text(event.get('sourceLabel'), 120) or 'Source',
                    'conflict': bool(event.get('dateConflict')),
                })
                break  # each event appears once, in the earliest section it touches
    for rows in out.values():
        rows.sort(key=lambda r: (r['start'], r['sortTime'] or '~', not r['starred'], r['title']))
    return [(key, label, first, last, out[key]) for key, label, first, last in sections]


# --------------------------------------------------------------------------
# Run report
# --------------------------------------------------------------------------

def load_report(path):
    if path is None:
        return {}
    try:
        if path.stat().st_size > MAX_REPORT_BYTES:
            raise BriefError('Run report exceeds the size limit.')
        report = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError):
        raise BriefError('Run report could not be read as JSON.') from None
    if not isinstance(report, dict):
        raise BriefError('Run report must be a JSON object.')
    return report


def report_items(report, field):
    items = report.get(field, [])
    if not isinstance(items, list):
        return []
    rows = []
    for item in items[:MAX_LIST]:
        if isinstance(item, str):
            item = {'title': item}
        if not isinstance(item, dict):
            continue
        title = clean_text(item.get('title') or item.get('headline'), 300)
        if not title:
            continue
        companies = item.get('companies') if isinstance(item.get('companies'), list) else []
        rows.append({
            'title': title,
            'detail': clean_text(item.get('detail') or item.get('change'), 600),
            'date': clean_text(item.get('date'), 60),
            'source': safe_url(item.get('sourceUrl') or item.get('url')),
            'companies': [clean_text(c, 20) for c in companies if isinstance(c, str)],
        })
    return rows


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def coverage_line(rows):
    """One-line digest of starred events, grouped by Hong Kong date."""
    starred = [r for r in rows if r['starred']]
    if not starred:
        return 'No coverage-company events in this window.'
    by_day = {}
    for r in starred:
        who = '/'.join(r['coverageNames']) or '/'.join(r['tickers'])
        by_day.setdefault(r['start'], []).append(f"{who} {r['type'].lower()}")
    parts = [f"{day_label(day)}: {', '.join(dict.fromkeys(items))}" for day, items in by_day.items()]
    return 'Coverage: ' + ' · '.join(parts)


def compose(data, today, result, report, site_url, generated_at=None):
    if result not in RESULTS:
        raise BriefError('Unknown run result.')
    if not safe_url(site_url):
        raise BriefError('Site link must be a valid HTTPS URL without credentials.')
    generated_at = generated_at or datetime.now(timezone.utc)
    sections = build_rows(data, today)
    coverage = {c['id'] for c in data.get('companies', []) if c.get('coverage')}
    developments = report_items(report, 'developments')
    added = report_items(report, 'added')
    updated = report_items(report, 'updated')
    warnings = [clean_text(w, 600) for w in report.get('warnings', []) if isinstance(w, str) and clean_text(w)] \
        if isinstance(report.get('warnings'), list) else []
    summary = clean_text(report.get('summary'), 1500)
    counts = {key: (len(rows), sum(r['starred'] for r in rows)) for key, _l, _f, _t, rows in sections}

    status_label = RESULTS[result]
    if result == 'published' and warnings:
        status_label = 'Calendar updated and published · with exceptions'
    subject = (f"Global Tech daily brief · {day_label(today)} {today.year} · "
               f"Today {counts['today'][0]} · 7d ★{counts['week'][1]}/{counts['week'][0]} · "
               f"30d ★{counts['month'][1]}/{counts['month'][0]}")
    if result in ('failed', 'blocked'):
        subject += f' · {result.upper()}'

    # ---------------- plain text ----------------
    t = [f'GLOBAL TECH DAILY BRIEF — {long_day(today)} (Hong Kong time)',
         f'Run: {status_label}', f'Calendar: {site_url}', '']
    if summary:
        t += [summary, '']
    if developments:
        t.append("WHAT'S GOING ON")
        for d in developments:
            star = '★ ' if set(d['companies']) & coverage else '- '
            t.append(f"{star}{d['title']}" + (f" ({d['date']})" if d['date'] else ''))
            if d['detail']:
                t.append(f"    {d['detail']}")
            if d['source']:
                t.append(f"    {d['source']}")
        t.append('')
    for key, label, first, last, rows in sections:
        heading = f'{label.upper()} — {range_label(first, last)}'
        t += [heading, '=' * len(heading)]
        if key != 'today':
            t.append('★ ' + coverage_line(rows))
        if not rows:
            t.append('No tracked events.')
        for r in rows:
            mark = '★ ' if r['starred'] else '  '
            when = r['window'] or range_label(r['start'], r['end'])
            prefix = '(ongoing) ' if r['ongoing'] else ''
            t.append(f"{mark}{prefix}{when} · {r['time']}")
            t.append(f"    {r['title']} [{r['type']} · {r['statusLabel']}]" + (' · source discrepancy' if r['conflict'] else ''))
            if r['tickers']:
                t.append(f"    {' · '.join(r['tickers'])}")
            if r['source']:
                t.append(f"    {r['source']}")
        t.append('')
    if added or updated:
        t.append('CALENDAR CHANGES IN THIS RUN')
        for title, items in (('Added', added), ('Updated', updated)):
            for item in items:
                t.append(f"- {title}: {item['title']}" + (f" ({item['date']})" if item['date'] else ''))
                if item['detail']:
                    t.append(f"    {item['detail']}")
                if item['source']:
                    t.append(f"    {item['source']}")
        t.append('')
    if warnings:
        t.append('EXCEPTIONS / OPEN ITEMS')
        t += [f'- {w}' for w in warnings[:30]]
        t.append('')
    t += ['★ = coverage company (TSM, NVDA, AMD, AVGO, MRVL, AAPL, MSFT, ORCL, CRM, NOW, ADBE, WDAY).',
          'Times are Hong Kong time; date-only events keep their published source date. '
          'Estimates and media reports are not company confirmations; dates remain subject to change.',
          f"Generated {generated_at.astimezone(HKT):%Y-%m-%d %H:%M} HKT from the reviewed calendar dataset."]
    text = '\n'.join(t) + '\n'

    # ---------------- HTML ----------------
    font = "font-family:-apple-system,'Segoe UI',Arial,Helvetica,sans-serif;"
    h = [f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
         f'<title>{esc(subject)}</title></head>'
         f'<body style="margin:0;padding:0;background:#f3f5f8;{font}color:#1c2533;">'
         '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="#f3f5f8"><tr><td align="center" style="padding:16px 8px;">'
         '<table role="presentation" width="680" cellpadding="0" cellspacing="0" style="max-width:680px;width:100%;background:#ffffff;border:1px solid #dde3ea;">']
    run_color = '#9e3939' if result in ('failed', 'blocked') else ('#925b10' if warnings or result == 'unpublished' else '#116b60')
    h.append('<tr><td bgcolor="#1d2633" style="background:#1d2633;padding:18px 22px;color:#ffffff;">'
             f'<div style="font-size:22px;font-weight:700;letter-spacing:-0.4px;{font}">Global Tech · daily brief</div>'
             f'<div style="font-size:13px;color:#bfcfe3;margin-top:4px;{font}">{esc(long_day(today))} · Hong Kong time</div>'
             '</td></tr>')
    h.append(f'<tr><td style="padding:14px 22px 4px 22px;font-size:13px;{font}">'
             f'<span style="color:{run_color};font-weight:700;">{esc(status_label)}</span>'
             f' &nbsp;·&nbsp; <a href="{esc(site_url)}" style="color:#1e53b5;">Open the calendar ↗</a></td></tr>')
    stats = []
    for key, label, *_rest in sections:
        total, stars = counts[key]
        stats.append(f'<td align="center" style="padding:8px 4px;border:1px solid #e3e8ee;{font}">'
                     f'<div style="font-size:11px;color:#63748b;text-transform:uppercase;letter-spacing:0.8px;">{esc(label)}</div>'
                     f'<div style="font-size:18px;font-weight:700;color:#1c2533;">{total}</div>'
                     f'<div style="font-size:12px;color:{STAR_COLOR};font-weight:700;">★ {stars} coverage</div></td>')
    h.append('<tr><td style="padding:8px 22px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
             + ''.join(stats) + '</tr></table></td></tr>')
    if summary:
        h.append(f'<tr><td style="padding:6px 22px;font-size:14px;line-height:1.5;{font}">{esc(summary)}</td></tr>')
    if developments:
        h.append(section_heading("What's going on", 'Developments found in this morning’s research', font))
        h.append('<tr><td style="padding:0 22px 6px 22px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">')
        for d in developments:
            starred = bool(set(d['companies']) & coverage)
            h.append(row_open(starred) + f'<td style="padding:8px 10px;font-size:13px;line-height:1.45;{font}">'
                     + (f'<b style="color:{STAR_COLOR};">★</b> ' if starred else '')
                     + f'<b>{esc(d["title"])}</b>' + (f' <span style="color:#63748b;">· {esc(d["date"])}</span>' if d['date'] else '')
                     + (f'<div style="color:#3d4a5c;margin-top:2px;">{esc(d["detail"])}</div>' if d['detail'] else '')
                     + (f'<div style="margin-top:2px;"><a href="{esc(d["source"])}" style="color:#1e53b5;font-size:12px;">Source ↗</a></div>' if d['source'] else '')
                     + '</td></tr>')
        h.append('</table></td></tr>')
    for key, label, first, last, rows in sections:
        h.append(section_heading(label, range_label(first, last), font))
        if key != 'today':
            h.append(f'<tr><td style="padding:0 22px 6px 22px;font-size:12px;color:{STAR_COLOR};font-weight:600;{font}">'
                     f'★ {esc(coverage_line(rows))}</td></tr>')
        h.append('<tr><td style="padding:0 22px 8px 22px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">')
        if not rows:
            h.append(f'<tr><td style="padding:10px;font-size:13px;color:#6f7e92;{font}">No tracked events.</td></tr>')
        for r in rows:
            h.append(render_event(r, font))
        h.append('</table></td></tr>')
    if added or updated:
        h.append(section_heading('Calendar changes in this run', 'Reviewed additions and corrections', font))
        h.append(f'<tr><td style="padding:0 22px 8px 22px;font-size:13px;line-height:1.5;{font}"><ul style="margin:0;padding-left:18px;">')
        for title, items in (('Added', added), ('Updated', updated)):
            for item in items:
                h.append(f'<li><b>{title}:</b> {esc(item["title"])}'
                         + (f' <span style="color:#63748b;">({esc(item["date"])})</span>' if item['date'] else '')
                         + (f'<br><span style="color:#3d4a5c;">{esc(item["detail"])}</span>' if item['detail'] else '')
                         + (f' <a href="{esc(item["source"])}" style="color:#1e53b5;">source ↗</a>' if item['source'] else '')
                         + '</li>')
        h.append('</ul></td></tr>')
    if warnings:
        h.append(section_heading('Exceptions / open items', 'Not verified or not completed in this run', font))
        h.append(f'<tr><td style="padding:0 22px 8px 22px;font-size:13px;line-height:1.5;color:#5b4a1d;{font}"><ul style="margin:0;padding-left:18px;">'
                 + ''.join(f'<li>{esc(w)}</li>' for w in warnings[:30]) + '</ul></td></tr>')
    h.append(f'<tr><td style="padding:14px 22px 18px 22px;border-top:1px solid #e3e8ee;font-size:11px;line-height:1.6;color:#63748b;{font}">'
             f'<b style="color:{STAR_COLOR};">★</b> highlighted rows = coverage companies (TSM, NVDA, AMD, AVGO, MRVL, AAPL, MSFT, ORCL, CRM, NOW, ADBE, WDAY). '
             'Solid border = officially confirmed; dotted border = estimate, media report or timing window. '
             'Times are Hong Kong time with the source-zone time alongside; date-only events keep their published source date and no clock time is invented. '
             'Estimates and media reports are not company confirmations; dates remain subject to change.<br>'
             f'Generated {generated_at.astimezone(HKT):%Y-%m-%d %H:%M} HKT from the reviewed calendar dataset · '
             f'<a href="{esc(site_url)}" style="color:#1e53b5;">{esc(site_url)}</a></td></tr>')
    h.append('</table></td></tr></table></body></html>')
    return subject, text, ''.join(h)


def section_heading(label, sub, font):
    return (f'<tr><td style="padding:16px 22px 6px 22px;{font}">'
            f'<div style="font-size:16px;font-weight:700;color:#1c2533;border-bottom:2px solid #1d2633;padding-bottom:4px;">'
            f'{esc(label)} <span style="font-size:12px;font-weight:400;color:#63748b;">· {esc(sub)}</span></div></td></tr>')


def row_open(starred):
    if starred:
        return f'<tr bgcolor="{HIGHLIGHT_BG}" style="background:{HIGHLIGHT_BG};border-left:4px solid {HIGHLIGHT_BORDER};">'
    return '<tr>'


def render_event(r, font):
    color = TYPE_COLORS.get(r['type'], DEFAULT_TYPE_COLOR)
    border = 'solid' if r['status'] == 'confirmed' else 'dotted'
    when = r['window'] or range_label(r['start'], r['end'])
    if r['ongoing']:
        when = 'Ongoing · ' + when
    star = f'<b style="color:{STAR_COLOR};font-size:15px;">★</b> ' if r['starred'] else ''
    weight = '700' if r['starred'] else '600'
    left_bar = HIGHLIGHT_BORDER if r['starred'] else '#ffffff'
    bg = HIGHLIGHT_BG if r['starred'] else '#ffffff'
    who = ' · '.join(r['tickers']) if r['tickers'] else ' · '.join(r['names'])
    source = (f'<a href="{esc(r["source"])}" style="color:#1e53b5;">{esc(r["sourceLabel"])} ↗</a>' if r['source'] else '')
    return (f'<tr><td style="padding:3px 0;">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="{bg}" '
            f'style="background:{bg};border-left:4px solid {left_bar};"><tr>'
            f'<td width="128" valign="top" style="padding:8px 8px 8px 10px;font-size:12px;line-height:1.4;color:#3d4a5c;{font}">'
            f'<b>{esc(when)}</b><br><span style="color:#63748b;">{esc(r["time"])}</span></td>'
            f'<td valign="top" style="padding:8px 10px 8px 4px;font-size:13px;line-height:1.45;{font}">'
            f'<div style="font-weight:{weight};color:#1c2533;">{star}{esc(r["title"])}</div>'
            f'<div style="margin-top:3px;font-size:11px;">'
            f'<span style="color:{color};border:1px {border} {color};padding:0 5px;border-radius:3px;">{esc(r["type"])}</span> '
            f'<span style="color:#53657b;{"font-style:italic;" if r["status"] != "confirmed" else ""}">{esc(r["statusLabel"])}</span>'
            + (' <span style="color:#9e3939;">· source discrepancy</span>' if r['conflict'] else '')
            + (f' <span style="color:#63748b;">· {esc(who)}</span>' if who else '')
            + (f' · {source}' if source else '')
            + '</div></td></tr></table></td></tr>')


# --------------------------------------------------------------------------
# Delivery
# --------------------------------------------------------------------------

def idempotency_key(today, result, nonce=''):
    digest = hashlib.sha256(f'{today.isoformat()}:{result}:{RECIPIENT}:{nonce}'.encode('utf-8')).hexdigest()[:48]
    return 'global-tech-daily-' + digest


def send(payload, api_key, key, attempts=3):
    encoded = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    for attempt in range(attempts):
        request = Request(ENDPOINT, data=encoded, method='POST', headers={
            'Authorization': 'Bearer ' + api_key,
            'Content-Type': 'application/json',
            'Idempotency-Key': key,
            'User-Agent': 'GlobalTechDailyBrief/1.0',
        })
        try:
            with urlopen(request, timeout=30) as response:
                if not 200 <= response.status < 300:
                    raise BriefError('Email provider did not accept the brief.')
                raw = response.read(65537)
            try:
                result = json.loads(raw)
            except (ValueError, UnicodeError):
                raise BriefError('Email provider returned an invalid response.') from None
            if not isinstance(result, dict) or not isinstance(result.get('id'), str) or not result['id']:
                raise BriefError('Email provider did not return a message identifier.')
            return result['id']
        except HTTPError as error:
            if error.code in (401, 403):
                raise BriefError(f'Email provider rejected the credential (HTTP {error.code}). '
                                 'Save a Resend API key for api.resend.com in the session environment.') from None
            retry = error.code == 429 or 500 <= error.code <= 599
            if not retry or attempt == attempts - 1:
                raise BriefError(f'Email provider rejected the brief (HTTP {error.code}).') from None
        except (URLError, TimeoutError, OSError):
            if attempt == attempts - 1:
                raise BriefError('Email provider could not be reached (is api.resend.com allowed for this session?).') from None
        if attempt < attempts - 1:
            time.sleep(attempt + 1)
    raise BriefError('Email brief was not accepted.')


def main(argv=None, environ=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--result', required=True, choices=RESULTS)
    parser.add_argument('--report', type=Path, help='Optional run report JSON (summary, developments, added, updated, warnings).')
    parser.add_argument('--dataset', type=Path, default=DATASET)
    parser.add_argument('--date', help='Hong Kong brief date YYYY-MM-DD (default: today in Hong Kong).')
    parser.add_argument('--site-url', default=DEFAULT_SITE)
    parser.add_argument('--html-out', type=Path, help='Also write the rendered HTML to this path.')
    parser.add_argument('--dry-run', action='store_true', help='Print the text version without contacting the email service.')
    parser.add_argument('--resend-nonce', default='', help='Change to deliberately send a second brief for the same day.')
    args = parser.parse_args(argv)
    environ = os.environ if environ is None else environ
    try:
        today = date.fromisoformat(args.date) if args.date else datetime.now(HKT).date()
        try:
            data = json.loads(args.dataset.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, ValueError):
            raise BriefError('Calendar dataset could not be read.') from None
        report = load_report(args.report)
        subject, text, body_html = compose(data, today, args.result, report, args.site_url)
        if args.html_out:
            args.html_out.parent.mkdir(parents=True, exist_ok=True)
            args.html_out.write_text(body_html, encoding='utf-8')
        if args.dry_run:
            print(f'To: {RECIPIENT}\nSubject: {subject}\n\n{text}', end='')
            return 0
        api_key = environ.get('RESEND_API_KEY', '').strip() or PROXY_PLACEHOLDER_KEY
        if any(ord(c) < 33 or ord(c) == 127 for c in api_key):
            raise BriefError('RESEND_API_KEY contains invalid characters.')
        sender = validate_sender(environ.get('GLOBAL_TECH_EMAIL_FROM', '').strip() or DEFAULT_SENDER)
        payload = {'from': sender, 'to': [RECIPIENT], 'subject': subject, 'text': text, 'html': body_html}
        message_id = send(payload, api_key, idempotency_key(today, args.result, args.resend_nonce))
        print(f'Daily brief accepted by the email provider for {RECIPIENT} (message id {message_id}).')
        return 0
    except BriefError as error:
        print(f'Daily brief failed: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
