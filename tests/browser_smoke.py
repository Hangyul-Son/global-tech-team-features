"""Optional real-browser checks. Run a server on port 8000 first.
Uses the environment's Python Playwright and Chromium installations.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
dataset=json.loads((ROOT/'data/events.json').read_text())
october=[e for e in dataset['events'] if e.get('date') and e['date']<='2026-10-31' and (e.get('endDate') or e['date'])>='2026-10-01']
company_map={c['id']:c for c in dataset['companies']}
priority=lambda e:any(company_map[c]['coverage'] for c in e['companies'])
from datetime import date
occurrences=sum((min(date.fromisoformat(e.get('endDate') or e['date']),date(2026,10,31))-max(date.fromisoformat(e['date']),date(2026,10,1))).days+1 for e in october)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
        args=['--no-sandbox','--disable-dev-shm-usage','--no-proxy-server','--single-process','--no-zygote'])
    page = browser.new_page(viewport={'width':1440,'height':1000})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8000')
    expect(page.locator('#universe-count')).to_have_text('24')
    expect(page.locator('.coverage-company')).to_have_count(13)
    expect(page.locator('.universe-company')).to_have_count(11)
    expect(page.locator('#coverage-list')).to_contain_text('Meta')
    expect(page.locator('#ecosystem-list')).to_contain_text('CoreWeave')
    expect(page.locator('#ecosystem-list')).to_contain_text('Nebius')
    assert page.locator('#calendar-view').bounding_box()['y'] < 100, 'View controls must be near the top'
    assert page.locator('.page-heading, .metrics, a[href="research.html"]').count() == 0
    # Navigate deterministically to the seed month, even on future machines.
    page.clock.install(time=__import__('datetime').datetime(2026,10,15,12,0,tzinfo=__import__('datetime').timezone.utc))
    page.reload()
    expect(page.locator('#month-label')).to_have_text('October 2026')
    expect(page.locator('.calendar-event')).to_have_count(occurrences)
    expect(page.locator('.calendar-event').filter(has_text='ASML Q3 financial results')).to_have_count(1)
    expect(page.locator('.calendar-event').filter(has_text='Anthropic pre-IPO investor day')).to_contain_text('Past date')
    expect(page.locator('.radar-card').filter(has_text='OCP')).to_have_count(0)
    expect(page.locator('.radar-card').filter(has_text='investor day')).to_have_count(0)
    expect(page.locator('.estimate-chip')).to_have_count(0)
    page.locator('#list-view').click()
    expect(page.locator('#list-panel')).to_be_visible()
    expect(page.locator('#calendar-panel')).to_be_hidden()
    expect(page.locator('.list-table tbody tr')).to_have_count(len(october))
    page.locator('#universe').select_option('coverage')
    expect(page.locator('.list-table tbody tr')).to_have_count(sum(priority(e) for e in october))
    page.locator('#status').select_option('confirmed')
    expect(page.locator('.list-table tbody tr')).to_have_count(sum(priority(e) and e['status']=='confirmed' for e in october))
    page.locator('#search').fill('Microsoft FY27')
    expect(page.locator('.list-table tbody tr')).to_have_count(1)
    page.locator('.event-name').click()
    expect(page.locator('#event-dialog')).to_be_visible()
    expect(page.locator('#event-detail')).to_contain_text('28 Oct 2026')
    expect(page.locator('#event-detail .source-link')).to_have_attribute('href','https://www.microsoft.com/en-us/Investor')
    page.keyboard.press('Escape')
    expect(page.locator('#event-dialog')).not_to_be_visible()
    page.locator('#clear-filters').click()
    page.locator('#next-month').click()
    expect(page.locator('#month-label')).to_have_text('November 2026')
    expect(page.locator('.list-table')).to_contain_text('AMD Q3 financial results')
    page.locator('#search').fill('NVIDIA')
    page.locator('.list-table tr[data-event-id="NVDA-2026-11-earnings"] .event-name').click()
    expect(page.locator('#event-detail')).to_contain_text('18 Nov 2026')
    expect(page.locator('#event-detail')).to_contain_text('Unconfirmed estimate')
    expect(page.locator('#event-detail')).to_contain_text('MarketBeat')
    page.keyboard.press('Escape')
    page.locator('#search').fill('no such company')
    expect(page.locator('#list-panel')).to_contain_text('No events match')
    expect(page.locator('#radar')).to_contain_text('No undated watch items')
    page.locator('#clear-filters').click()
    page.locator('#today-button').click()
    page.locator('#calendar-view').click()
    page.locator('#status').select_option('estimated')
    expect(page.locator('.calendar-event')).to_have_count(sum(e['status']=='estimated' for e in october))
    expect(page.locator('.calendar-event.estimated')).to_have_count(sum(e['status']=='estimated' for e in october))
    expect(page.locator('.estimate-chip')).to_have_count(0)
    page.locator('#clear-filters').click()
    page.locator('#status').select_option('reported')
    page.locator('.calendar-event').filter(has_text='Anthropic pre-IPO investor day').click()
    expect(page.locator('#event-detail')).to_contain_text('Past date')
    expect(page.locator('#event-detail')).to_contain_text('Bloomberg')
    expect(page.locator('#event-detail')).to_contain_text('primary confirmation not verified')
    page.keyboard.press('Escape')
    page.locator('#clear-filters').click()
    # Untrusted data is rendered as text, never executed or used as a script URL.
    hostile=json.loads((ROOT/'data/events.json').read_text())
    hostile['events'][0].update(title='<img src=x onerror=alert(1)>',sourceUrl='javascript:alert(1)')
    page.route('**/data/events.json',lambda route:route.fulfill(json=hostile))
    page.reload()
    page.locator('#list-view').click()
    page.locator(f'.list-table tr[data-event-id="{hostile["events"][0]["id"]}"] .event-name').click()
    expect(page.locator('#event-detail img')).to_have_count(0)
    expect(page.locator('#event-detail .source-link')).to_have_count(0)
    page.keyboard.press('Escape')
    page.unroute('**/data/events.json')
    page.reload()
    # A multi-day event spanning months must render on every applicable day.
    fixture=json.loads((ROOT/'data/events.json').read_text())
    fixture['events'].append(dict(fixture['events'][0],id='test-multiday',title='Cross-month fixture',status='confirmed',window=None,date='2026-09-30',endDate='2026-10-02'))
    page.route('**/data/events.json',lambda route:route.fulfill(json=fixture))
    page.reload()
    expect(page.locator('.calendar-event').filter(has_text='Cross-month fixture')).to_have_count(2)
    page.unroute('**/data/events.json')
    page.reload()
    # Every dated event and every cited link is accessible directly in list view.
    page.locator('#list-view').click()
    seen=set()
    for iteration in range(6):
        for row in page.locator('.list-table tbody tr').all():
            event_id=row.get_attribute('data-event-id')
            event=next(e for e in dataset['events'] if e['id']==event_id)
            seen.add(event_id)
            actual=row.locator('.event-sources a').evaluate_all('(links)=>links.map(a=>a.href)')
            expected=page.evaluate('(entries)=>[...new Set(entries.map(e=>new URL(e.url).href))]',[{'url':event['sourceUrl']},*event['sources']])
            assert set(actual)==set(expected),(event_id,actual,expected)
            assert row.locator('.event-sources a[target="_blank"]').count()==len(actual)
            assert row.locator('button .event-star').count()==int(priority(event))
        page.locator('#next-month').click()
    assert seen=={e['id'] for e in dataset['events'] if e['date']}, 'A dated event was omitted from list navigation'
    for card in page.locator('.radar-card').all():
        assert card.locator('.event-sources a').count()>0, 'An undated watch item has no visible evidence'
    page.locator('#today-button').click()
    page.locator('#calendar-view').click()
    assert page.locator('.calendar-source').count()==occurrences
    for entry in page.locator('.calendar-entry').all():
        event=next(e for e in dataset['events'] if e['id']==entry.get_attribute('data-event-id'))
        assert entry.locator('.calendar-source').get_attribute('href')==event['sourceUrl']
        style=entry.evaluate('(el)=>getComputedStyle(el).borderTopStyle')
        assert style==('dotted' if event['date']>'2026-10-15' else 'solid'),(event['id'],style)
    # Type color does not change when the event belongs to coverage.
    calendar_colors=page.locator('.calendar-entry.kind-earnings').evaluate_all('(els)=>els.map(el=>getComputedStyle(el).backgroundColor)')
    assert len(set(calendar_colors))==1
    page.screenshot(path='/tmp/catalyst-desktop.png',full_page=True)
    page.locator('#list-view').click()
    page.screenshot(path='/tmp/catalyst-list.png',full_page=True)
    page.locator('#calendar-view').click()
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile document overflows'
    assert page.locator('#universe').bounding_box()['width'] >= 85, 'Mobile filters are too narrow'
    assert page.locator('#calendar-view').bounding_box()['y'] < 100
    page.locator('#open-universe').click()
    expect(page.locator('#sidebar')).to_be_visible()
    expect(page.locator('#ecosystem-list')).to_contain_text('Nebius')
    page.locator('#close-universe').click()
    expect(page.locator('#open-universe')).to_have_attribute('aria-expanded','false')
    page.locator('#list-view').click()
    expect(page.locator('.list-table')).to_be_visible()
    for row in page.locator('.list-table tbody tr').all():
        expect(row.locator('.event-sources a').first).to_be_visible()
    page.locator('.event-name').first.click()
    expect(page.locator('#event-dialog')).to_be_visible()
    page.keyboard.press('Escape')
    page.screenshot(path='/tmp/catalyst-mobile-list.png',full_page=True)
    page.locator('#calendar-view').click()
    page.screenshot(path='/tmp/catalyst-mobile.png',full_page=True)
    assert not errors,errors
    browser.close()
    print('PASS desktop/mobile views, filters, navigation, source briefs, keyboard dismissal, estimated precision, empty states, safe rendering and multi-day events; no browser errors.')
