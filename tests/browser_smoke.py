"""Real-browser checks. Serve this checkout on port 8000 first."""
import json
from datetime import date, datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
dataset=json.loads((ROOT/'data/events.json').read_text())
by_id={e['id']:e for e in dataset['events']}
company_map={c['id']:c for c in dataset['companies']}
priority=lambda e:any(company_map[c]['coverage'] for c in e['companies'])
october=[e for e in dataset['events'] if e.get('date') and e['date']<='2026-10-31' and (e.get('endDate') or e['date'])>='2026-10-01']
occurrences=sum((min(date.fromisoformat(e.get('endDate') or e['date']),date(2026,10,31))-max(date.fromisoformat(e['date']),date(2026,10,1))).days+1 for e in october)
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--no-proxy-server','--single-process','--no-zygote'])
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.clock.install(time=datetime(2026,10,15,12,0,tzinfo=timezone.utc))
    page.goto('http://127.0.0.1:8000')
    expect(page.locator('#universe-count')).to_have_text('32')
    expect(page.locator('.coverage-company')).to_have_count(19)
    expect(page.locator('.universe-company')).to_have_count(13)
    for name in ['Apple','Intel','Arm','Qualcomm','Snowflake','CrowdStrike','Palo Alto Networks']:
        expect(page.locator('#coverage-list')).to_contain_text(name)
    assert page.locator('#calendar-view').bounding_box()['y']<100
    expect(page.locator('.calendar-event')).to_have_count(occurrences)
    # Certainty controls the border, not whether a date is in the future.
    for entry in page.locator('.calendar-entry').all():
        event=by_id[entry.get_attribute('data-event-id')]
        style=entry.evaluate('(e)=>getComputedStyle(e).borderTopStyle')
        assert style==('solid' if event['status']=='confirmed' else 'dotted'),(event['id'],style)
        assert entry.locator('.calendar-source').get_attribute('href')==event['sourceUrl']
    for event_id,style in [('005930.KS-2026-10-earnings','solid'),('AMZN-2026-10-earnings','dotted'),('2454.TW-2026-10-earnings','dotted')]:
        assert page.locator(f'.calendar-entry[data-event-id="{event_id}"]').evaluate('(e)=>getComputedStyle(e).borderTopStyle')==style
    expect(page.locator('.calendar-entry[data-event-id="ASML-2026-10-earnings"]')).to_have_count(1)
    expect(page.locator('.calendar-entry[data-event-id="mit-ai-2026"]')).to_have_count(1)
    expect(page.locator('.calendar-entry[data-event-id="cloudflare-connect-2026"]')).to_have_count(3)
    earnings_colors=page.locator('.calendar-entry.kind-earnings').evaluate_all('(els)=>els.map(e=>getComputedStyle(e).backgroundColor)')
    assert len(set(earnings_colors))==1
    page.locator('#list-view').click()
    rows=page.locator('.list-table tbody tr[data-event-id]')
    expect(rows).to_have_count(len(dataset['events']))
    expect(page.locator('#month-label')).to_have_text('All events')
    expect(page.locator('#prev-month')).to_be_hidden()
    expect(page.locator('#next-month')).to_be_hidden()
    page.wait_for_function('document.getElementById("list-panel").scrollTop>0')
    assert page.locator('#timeline-today').bounding_box()['y']>=page.locator('#list-panel').bounding_box()['y']
    assert page.locator('#timeline-today').bounding_box()['y']<page.locator('#list-panel').bounding_box()['y']+70
    # All history and future events exist simultaneously, without month paging.
    ids=rows.evaluate_all('(els)=>els.map(e=>e.dataset.eventId)')
    assert set(ids)==set(by_id), 'Every event must exist in the single list'
    starts=[by_id[id].get('date') or by_id[id].get('timingWindow',{}).get('start') or '9999-12-31' for id in ids]
    assert starts==sorted(starts), 'Dates and window starts must remain chronological'
    for row in rows.all():
        event=by_id[row.get_attribute('data-event-id')]
        actual=row.locator('.event-sources a').evaluate_all('(els)=>els.map(a=>a.href)')
        expected_links=page.evaluate('(entries)=>[...new Set(entries.map(e=>new URL(e.url).href))]',[{'url':event['sourceUrl']},*event['sources']])
        assert set(actual)==set(expected_links),event['id']
        assert row.locator('.event-star').count()==int(priority(event))
        assert row.locator('td').first.evaluate('(e)=>getComputedStyle(e).borderTopStyle')==('solid' if event['status']=='confirmed' else 'dotted')
    page.locator('#list-panel').evaluate('(p)=>p.scrollTop=0')
    expect(page.locator('.list-table tr[data-event-id="oracle-ai-world-2025"] .event-name')).to_be_visible()
    page.locator('#list-panel').evaluate('(p)=>p.scrollTop=p.scrollHeight')
    expect(page.locator('.list-table tr[data-event-id="ARM-2027-05-earnings"] .event-name')).to_be_visible()
    page.locator('#today-button').click()
    assert page.locator('#list-panel').evaluate('(p)=>p.scrollTop')>0
    # IPOs show their actual sourced precision, not the first day of a period.
    for event_id,label in [('anthropic-ipo','November 2026'),('openai-ipo','2027')]:
        row=page.locator(f'.list-table tr[data-event-id="{event_id}"]')
        expect(row.locator('td').first).to_contain_text(label)
        assert '1 Jan 2027' not in row.locator('td').first.inner_text()
        assert '1 Nov 2026' not in row.locator('td').first.inner_text()
    page.locator('#search').fill('OpenAI potential IPO')
    expect(rows).to_have_count(1)
    rows.locator('.event-name').click()
    expect(page.locator('#event-detail')).to_contain_text('Unconfirmed timing window')
    expect(page.locator('#event-detail')).to_contain_text('quarter unconfirmed')
    page.keyboard.press('Escape')
    page.locator('#search').fill('NVIDIA earnings')
    expect(rows).to_have_count(1)
    rows.locator('.event-name').click()
    expect(page.locator('#event-detail')).to_contain_text('18 Nov 2026')
    expect(page.locator('#event-detail')).to_contain_text('Unconfirmed estimate')
    page.keyboard.press('Escape')
    page.locator('#search').fill('no such event xyz')
    expect(page.locator('#list-panel')).to_contain_text('No events match')
    page.locator('#clear-filters').click()
    page.locator('#universe').select_option('coverage')
    expect(rows).to_have_count(sum(priority(e) for e in dataset['events']))
    page.locator('#status').select_option('confirmed')
    expect(rows).to_have_count(sum(priority(e) and e['status']=='confirmed' for e in dataset['events']))
    page.locator('#clear-filters').click()
    page.locator('#calendar-view').click()
    page.locator('#next-month').click()
    expect(page.locator('#month-label')).to_have_text('November 2026')
    expect(page.locator('#timing-windows [data-event-id="anthropic-ipo"]')).to_contain_text('November 2026')
    expect(page.locator('#timing-windows [data-event-id="anthropic-ipo-marketing"]')).to_contain_text('Week of 9 November')
    expect(page.locator('.calendar-entry[data-event-id="anthropic-ipo"]')).to_have_count(0)
    page.locator('#next-month').click()
    page.locator('#next-month').click()
    expect(page.locator('#month-label')).to_have_text('January 2027')
    expect(page.locator('#timing-windows [data-event-id="openai-ipo"]')).to_contain_text('2027')
    expect(page.locator('.calendar-entry[data-event-id="openai-ipo"]')).to_have_count(0)
    page.locator('#today-button').click()
    # Safe rendering of untrusted data and URLs, including the unpaged list.
    hostile=json.loads((ROOT/'data/events.json').read_text())
    hostile['events'][0].update(title='<img src=x onerror=alert(1)>',sourceUrl='javascript:alert(1)')
    page.route('**/data/events.json',lambda r:r.fulfill(json=hostile))
    page.reload()
    page.locator('#list-view').click()
    page.locator(f'.list-table tr[data-event-id="{hostile["events"][0]["id"]}"] .event-name').click()
    expect(page.locator('#event-detail img')).to_have_count(0)
    expect(page.locator('#event-detail .source-link')).to_have_count(0)
    page.keyboard.press('Escape')
    page.unroute('**/data/events.json')
    fixture=json.loads((ROOT/'data/events.json').read_text())
    fixture['events'].append(dict(fixture['events'][0],id='test-multiday',title='Cross-month fixture',date='2026-09-30',endDate='2026-10-02'))
    page.route('**/data/events.json',lambda r:r.fulfill(json=fixture))
    page.reload()
    expect(page.locator('.calendar-entry[data-event-id="test-multiday"]')).to_have_count(2)
    page.unroute('**/data/events.json')
    page.reload()
    page.screenshot(path='/tmp/catalyst-desktop.png',full_page=True)
    page.locator('#list-view').click()
    page.screenshot(path='/tmp/catalyst-list.png',full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    expect(page.locator('#next-month')).to_be_hidden()
    page.locator('#open-universe').click()
    expect(page.locator('#coverage-list')).to_contain_text('Palo Alto Networks')
    expect(page.locator('#ecosystem-list')).to_contain_text('OpenAI')
    page.locator('#close-universe').click()
    page.locator('#today-button').click()
    assert page.locator('#timeline-today').bounding_box()['y']<page.locator('#list-panel').bounding_box()['y']+80
    row=page.locator('.list-table tr[data-event-id="TSM-2026-10-earnings"]')
    expect(row.locator('.event-sources a').first).to_be_visible()
    row.locator('.event-name').click()
    expect(page.locator('#event-dialog')).to_be_visible()
    page.keyboard.press('Escape')
    page.screenshot(path='/tmp/catalyst-mobile-list.png',full_page=True)
    page.locator('#calendar-view').click()
    assert page.locator('#calendar-view').bounding_box()['y']<100
    page.screenshot(path='/tmp/catalyst-mobile.png',full_page=True)
    assert not errors,errors
    browser.close()
    print('PASS certainty borders; single chronological timeline centered on today; all sources; historic and future scrolling; IPO precision windows; industry events; filters; safe rendering; desktop/mobile.')
