"""Real-browser checks. Serve this checkout on port 8000 first."""
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]
dataset=json.loads((ROOT/'data/events.json').read_text())
by_id={e['id']:e for e in dataset['events']}
company_map={c['id']:c for c in dataset['companies']}
priority=lambda e:any(company_map[c]['coverage'] for c in e['companies'])
def displayed_range(event):
    if event.get('startAt'):
        start=datetime.fromisoformat(event['startAt'].replace('Z','+00:00')).astimezone(ZoneInfo('Asia/Hong_Kong')).date()
        end=(datetime.fromisoformat(event['endAt'].replace('Z','+00:00'))-timedelta(milliseconds=1)).astimezone(ZoneInfo('Asia/Hong_Kong')).date() if event.get('endAt') else start
        return start,end
    start=event.get('date') or event.get('timingWindow',{}).get('start')
    end=event.get('endDate') or event.get('timingWindow',{}).get('end') or start
    return (date.fromisoformat(start),date.fromisoformat(end)) if start else (None,None)

def calendar_segments(event, month_start=date(2026,10,1), month_end=date(2026,10,31)):
    if event.get('timingWindow'):
        return 0
    start,end=displayed_range(event)
    if not start or start>month_end or end<month_start:
        return 0
    start,end=max(start,month_start),min(end,month_end)
    first_monday=start-timedelta(days=start.weekday())
    last_monday=end-timedelta(days=end.weekday())
    return (last_monday-first_monday).days//7+1

occurrences=sum(calendar_segments(e) for e in dataset['events'])
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--no-proxy-server','--single-process','--no-zygote'])
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.clock.install(time=datetime(2026,10,15,12,0,tzinfo=timezone.utc))
    page.goto('http://127.0.0.1:8000')
    expect(page.locator('#universe-count')).to_have_text(str(len(dataset['companies'])))
    expect(page.locator('.coverage-company')).to_have_count(sum(c['coverage'] for c in dataset['companies']))
    expect(page.locator('.universe-company')).to_have_count(sum(not c['coverage'] for c in dataset['companies']))
    expect(page.locator('#coverage-list')).to_contain_text('Apple')
    assert page.locator('body').evaluate('(e)=>getComputedStyle(e).fontSize')=='15px'
    expect(page.locator('.brand')).to_have_text('Global Tech')
    expect(page.locator('.brand-mark, .brand svg, .brand img')).to_have_count(0)
    for name in ['Meta','Intel','Arm','Qualcomm','Snowflake','CrowdStrike','Palo Alto Networks']:
        expect(page.locator('#ecosystem-list')).to_contain_text(name)
        expect(page.locator('#coverage-list')).not_to_contain_text(name)
    assert page.locator('#calendar-view').bounding_box()['y']<100
    expect(page.locator('.calendar-event')).to_have_count(occurrences)
    assert page.locator('.calendar-event').evaluate_all('(els)=>els.every(e=>parseFloat(getComputedStyle(e).fontSize)>=12)')
    # Certainty controls the border, not whether a date is in the future.
    for entry in page.locator('.calendar-entry').all():
        event=by_id[entry.get_attribute('data-event-id')]
        style=entry.evaluate('(e)=>getComputedStyle(e).borderTopStyle')
        assert style==('solid' if event['status']=='confirmed' else 'dotted'),(event['id'],style)
        assert entry.locator('a, .badge').count()==0
        assert entry.locator('.calendar-event').get_attribute('title')==event['title']
        assert 'Confirmed' not in entry.inner_text() and 'Upcoming' not in entry.inner_text()
    for event_id in ['005930.KS-2026-10-earnings','AMZN-2026-10-earnings','2454.TW-2026-10-earnings']:
        style='solid' if by_id[event_id]['status']=='confirmed' else 'dotted'
        assert page.locator(f'.calendar-entry[data-event-id="{event_id}"]').evaluate('(e)=>getComputedStyle(e).borderTopStyle')==style
    expect(page.locator('.calendar-entry[data-event-id="ASML-2026-10-earnings"]')).to_have_count(1)
    expect(page.locator('.calendar-entry[data-event-id="mit-ai-2026"]')).to_have_count(1)
    cloudflare=page.locator('.calendar-entry[data-event-id="cloudflare-connect-2026"]')
    expect(cloudflare).to_have_count(1)
    expect(cloudflare).to_have_attribute('data-start-date','2026-10-19')
    expect(cloudflare).to_have_attribute('data-end-date','2026-10-21')
    first_day=page.locator('.day[data-date="2026-10-19"]').bounding_box()
    last_day=page.locator('.day[data-date="2026-10-21"]').bounding_box()
    band=cloudflare.bounding_box()
    assert first_day['x']<=band['x']<=first_day['x']+8
    assert last_day['x']+last_day['width']-8<=band['x']+band['width']<=last_day['x']+last_day['width']
    assert band['width']>first_day['width']*2.85, 'One connected bar must cover all three conference dates'
    oracle=page.locator('.calendar-entry[data-event-id="oracle-ai-world-2026"]')
    expect(oracle).to_have_count(2)
    expect(oracle.nth(0)).to_have_attribute('data-start-date','2026-10-25')
    expect(oracle.nth(0)).to_have_attribute('data-end-date','2026-10-25')
    expect(oracle.nth(1)).to_have_attribute('data-start-date','2026-10-26')
    expect(oracle.nth(1)).to_have_attribute('data-end-date','2026-10-28')
    assert 'continues-after' in oracle.nth(0).get_attribute('class')
    assert 'continues-before' not in oracle.nth(0).get_attribute('class')
    assert 'continues-before' in oracle.nth(1).get_attribute('class')
    assert 'continues-after' not in oracle.nth(1).get_attribute('class')
    expect(oracle.nth(0).locator('.continuation-arrow')).to_have_text('→')
    expect(oracle.nth(1).locator('.continuation-arrow')).to_have_text('←')
    expect(page.locator('.calendar-entry[data-event-id^="oracle-ai-world-2026-"]')).to_have_count(0)
    oracle.nth(0).locator('.calendar-event').click()
    expect(page.locator('#event-detail h2')).to_have_text('Oracle AI World 2026')
    expect(page.locator('#event-detail')).to_contain_text('Clay Magouyrk')
    expect(page.locator('#event-detail')).to_contain_text('9:00 a.m.')
    expect(page.locator('#event-detail')).to_contain_text('3:30 p.m.')
    expect(page.locator('#event-detail .source-list a[href="https://www.oracle.com/ai-world/keynotes/"]')).to_have_count(1)
    page.keyboard.press('Escape')
    # Events sharing the same date columns need separate visible rows.
    ocp_band=page.locator('.calendar-entry[data-event-id="ocp"]').bounding_box()
    workday_band=page.locator('.calendar-entry[data-event-id="workday-rising-us-2026"]').bounding_box()
    assert abs(ocp_band['x']-workday_band['x'])<1
    assert abs(ocp_band['width']-workday_band['width'])<1
    assert ocp_band['y']+ocp_band['height']<=workday_band['y'] or workday_band['y']+workday_band['height']<=ocp_band['y'], 'Overlapping conference dates must occupy separate rows'
    earnings_colors=page.locator('.calendar-entry.kind-earnings').evaluate_all('(els)=>els.map(e=>getComputedStyle(e).backgroundColor)')
    assert len(set(earnings_colors))==1
    # Larger default type and the expanded event set need room for readable
    # overlapping rows while still keeping October within the desktop viewport.
    assert page.locator('#calendar').bounding_box()['height']<700, 'Calendar should stay compact at desktop width'
    page.locator('.calendar-entry[data-event-id="005930.KS-2026-10-earnings"] .calendar-event').click()
    expect(page.locator('#event-detail .source-link')).to_have_attribute('href',by_id['005930.KS-2026-10-earnings']['sourceUrl'])
    expect(page.locator('#event-detail')).to_contain_text('10:00 KST')
    page.keyboard.press('Escape')
    page.locator('#list-view').click()
    rows=page.locator('.list-table tbody tr[data-event-id]')
    expect(rows).to_have_count(len(dataset['events']))
    expect(rows.filter(has=page.locator('[data-event="oracle-ai-world-2026"]'))).to_have_count(1)
    expect(page.locator('.list-table tr[data-event-id^="oracle-ai-world-2026-"]')).to_have_count(0)
    assert not any('Clay Magouyrk' in title for title in rows.locator('.event-name').all_text_contents())
    expect(page.locator('#month-label')).to_have_text('All events')
    expect(page.locator('#prev-month')).to_be_hidden()
    expect(page.locator('#next-month')).to_be_hidden()
    page.wait_for_function('document.getElementById("list-panel").scrollTop>0')
    assert page.locator('#timeline-today').bounding_box()['y']>=page.locator('#list-panel').bounding_box()['y']
    assert page.locator('#timeline-today').bounding_box()['y']<page.locator('#list-panel').bounding_box()['y']+70
    # All history and future events exist simultaneously, without month paging.
    ids=rows.evaluate_all('(els)=>els.map(e=>e.dataset.eventId)')
    assert set(ids)==set(by_id), 'Every event must exist in the single list'
    starts=[displayed_range(by_id[id])[0] or date.max for id in ids]
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
    expect(page.locator(f'.list-table tr[data-event-id="{ids[-1]}"] .event-name')).to_be_visible()
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
    page.locator('#search').fill('NVIDIA')
    page.locator('#type').select_option('Earnings')
    expect(rows).to_have_count(1)
    rows.locator('.event-name').click()
    nvidia=by_id['NVDA-2026-11-earnings']
    nvidia_day=displayed_range(nvidia)[0]
    expect(page.locator('#event-detail')).to_contain_text(f'{nvidia_day.day} {nvidia_day.strftime("%b %Y")}')
    expect(page.locator('#event-detail .badge')).to_contain_text({'confirmed':'Confirmed','estimated':'Estimated date','reported':'Reported date','unannounced':'Date unannounced'}[nvidia['status']])
    expect(page.locator('#event-detail .source-link')).to_have_attribute('href',nvidia['sourceUrl'])
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
    fixture['events'].append(dict(fixture['events'][0],id='test-multiday',title='Cross-month fixture',date='2026-09-30',endDate='2026-10-02',startAt=None,endAt=None))
    page.route('**/data/events.json',lambda r:r.fulfill(json=fixture))
    page.reload()
    expect(page.locator('.calendar-entry[data-event-id="test-multiday"]')).to_have_count(1)
    expect(page.locator('.calendar-entry[data-event-id="test-multiday"]')).to_have_attribute('data-start-date','2026-10-01')
    expect(page.locator('.calendar-entry[data-event-id="test-multiday"]')).to_have_attribute('data-end-date','2026-10-02')
    assert 'continues-before' in page.locator('.calendar-entry[data-event-id="test-multiday"]').get_attribute('class')
    page.unroute('**/data/events.json')
    page.reload()
    # Unequal topic counts must not give one research company more watchlist cards
    # or a larger initial footprint. Shared coverage links do not star its card.
    watch_fixture=json.loads((ROOT/'data/events.json').read_text())
    watch_fixture['events']=[]
    for company,count in [('AMZN',1),('ASML',2),('SPACEX',5)]:
        for number in range(count):
            watch_fixture['events'].append(dict(dataset['events'][0],id=f'watch-fixture-{company}-{number}',companies=[company],title=f'Fixture {company} topic {number}',date=None,endDate=None,window=None,timingWindow=None,status='unannounced',time=None,startAt=None,endAt=None,verifiedAt=None))
    watch_fixture['events'].append(dict(watch_fixture['events'][0],id='watch-fixture-shared',companies=['SPACEX','NVDA'],title='Fixture shared coverage topic'))
    page.route('**/data/events.json',lambda r:r.fulfill(json=watch_fixture))
    page.reload()
    cards=page.locator('#radar [data-watch-company]')
    expect(cards).to_have_count(4)
    expect(page.locator('#radar-count')).to_have_text('4 companies')
    assert cards.evaluate_all('(els)=>els.map(e=>e.dataset.watchCompany)')==['AMZN','ASML','NVDA','SPACEX']
    spacex=page.locator('#radar [data-watch-company="SPACEX"]')
    expect(spacex.locator('summary')).to_contain_text('6 topics')
    assert not spacex.locator('details').evaluate('(e)=>e.open')
    expect(spacex.locator('.coverage-tag')).to_have_count(0)
    expect(page.locator('#radar [data-watch-company="NVDA"] .coverage-tag')).to_have_count(1)
    heights=[page.locator(f'#radar [data-watch-company="{company}"]').bounding_box()['height'] for company in ['AMZN','ASML','SPACEX']]
    assert max(heights)-min(heights)<2, 'Research companies get the same collapsed card size regardless of topic count'
    spacex.locator('summary').click()
    expect(spacex.locator('.watch-topic')).to_have_count(6)
    expect(spacex.locator('.watch-topic .event-sources a').first).to_be_visible()
    spacex.locator('.watch-topic .event-name').first.click()
    expect(page.locator('#event-dialog')).to_be_visible()
    expect(page.locator('#event-detail .source-list a').first).to_be_visible()
    page.keyboard.press('Escape')
    page.locator('#search').fill('Fixture ASML')
    expect(page.locator('#radar [data-watch-company]')).to_have_count(1)
    expect(page.locator('#radar [data-watch-company="ASML"] summary')).to_contain_text('2 topics')
    page.unroute('**/data/events.json')
    page.reload()
    page.screenshot(path='/tmp/catalyst-desktop.png',full_page=True)
    page.locator('#list-view').click()
    page.screenshot(path='/tmp/catalyst-list.png',full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    page.locator('#sidebar').evaluate('(e)=>Promise.all(e.getAnimations().map(a=>a.finished.catch(()=>{})))')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    expect(page.locator('#next-month')).to_be_hidden()
    page.locator('#open-universe').click()
    expect(page.locator('#ecosystem-list')).to_contain_text('Palo Alto Networks')
    expect(page.locator('#ecosystem-list')).to_contain_text('OpenAI')
    page.locator('#close-universe').click()
    page.locator('#today-button').click()
    assert page.locator('#timeline-today').bounding_box()['y']<page.locator('#list-panel').bounding_box()['y']+80
    row=page.locator('.list-table tr[data-event-id="TSM-2026-10-earnings"]')
    expect(row.locator('.event-sources a').first).to_be_attached()
    row.locator('.event-name').click()
    expect(page.locator('#event-dialog')).to_be_visible()
    expect(page.locator('#event-detail .source-list a').first).to_be_visible()
    page.keyboard.press('Escape')
    page.locator('#sidebar').evaluate('(e)=>Promise.all(e.getAnimations().map(a=>a.finished.catch(()=>{})))')
    page.screenshot(path='/tmp/catalyst-mobile-list.png',full_page=True)
    page.locator('#calendar-view').click()
    assert page.locator('#calendar-view').bounding_box()['y']<100
    page.screenshot(path='/tmp/catalyst-mobile.png',full_page=True)
    assert not errors,errors
    browser.close()
    print('PASS connected multi-day bands and week continuations; separate overlapping rows; merged Oracle keynote details; larger font and text-only brand; certainty borders; full timeline and sources; IPO windows; filters; safe rendering; desktop/mobile.')
