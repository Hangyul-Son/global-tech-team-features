"""End-to-end browser timezone switching and actual .ics downloads."""
from pathlib import Path
from datetime import datetime, timezone
import json
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[1]
dataset=json.loads((ROOT/'data/events.json').read_text())
exportable_count=sum(bool(e.get('date') or e.get('startAt') or e.get('timingWindow',{}).get('start')) for e in dataset['events'])

def unfold(path):return Path(path).read_bytes().decode().replace('\r\n ','').replace('\r\n\t','')
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--no-proxy-server','--single-process','--no-zygote'])
    context=browser.new_context(timezone_id='America/New_York',accept_downloads=True,viewport={'width':1440,'height':1000})
    page=context.new_page()
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.clock.install(time=datetime(2026,10,15,12,0,tzinfo=timezone.utc))
    page.goto('http://127.0.0.1:8000')
    expect(page).to_have_title('Global Tech')
    expect(page.locator('.brand')).to_contain_text('Global Tech')
    expect(page.locator('#timezone')).to_have_value('Asia/Hong_Kong')
    expect(page.locator('#coverage-count')).to_have_text('12')
    expect(page.locator('#ecosystem-count')).to_have_text('20')
    expect(page.locator('#download-ics')).to_be_disabled()
    page.locator('#list-view').click()
    apple=page.locator('.list-table tr[data-event-id="AAPL-2026-11-earnings"]')
    expect(apple.locator('td').first).to_contain_text('3 Nov 2026')
    expect(apple.locator('td').first).to_contain_text('06:00')
    page.locator('#timezone').select_option('browser')
    expect(apple.locator('td').first).to_contain_text('2 Nov 2026')
    expect(apple.locator('td').first).to_contain_text('17:00')
    page.locator('#timezone').select_option('America/Los_Angeles')
    expect(apple.locator('td').first).to_contain_text('14:00')
    page.reload()
    expect(page.locator('#timezone')).to_have_value('America/Los_Angeles')
    page.locator('#timezone').select_option('Asia/Hong_Kong')
    page.locator('#list-view').click()
    page.locator('#select-events').click()
    for id in ['AAPL-2026-11-earnings','NVDA-2026-11-earnings','anthropic-ipo']:
        page.locator(f'#list-panel tr[data-event-id="{id}"] [data-select-event]').check()
    expect(page.locator('#selection-count')).to_contain_text('3 selected')
    with page.expect_download() as dl:
        page.locator('#download-ics').click()
    download=dl.value
    assert download.suggested_filename=='global-tech-events-2026-10-15.ics'
    download.save_as('/tmp/global-tech-outlook-selected.ics')
    text=unfold('/tmp/global-tech-outlook-selected.ics')
    assert text.count('BEGIN:VEVENT')==3
    assert 'DTSTART:20261102T220000Z' in text
    assert 'DTSTART;VALUE=DATE:20261118' in text
    assert 'DTSTART;VALUE=DATE:20261101' in text and 'DTEND;VALUE=DATE:20261201' in text
    assert text.count('STATUS:TENTATIVE')==2
    assert text.count('TRANSP:TRANSPARENT')==3
    page.locator('#timezone').select_option('America/Los_Angeles')
    expect(page.locator('#selection-count')).to_contain_text('3 selected')
    with page.expect_download() as dl:
        page.locator('#download-ics').click()
    dl.value.save_as('/tmp/global-tech-outlook-la.ics')
    assert 'DTSTART:20261102T220000Z' in unfold('/tmp/global-tech-outlook-la.ics'), 'ICS must preserve the instant, not the display clock'
    page.locator('#clear-selection').click()
    expect(page.locator('#download-ics')).to_be_disabled()
    page.locator('#search').fill('NVIDIA earnings')
    page.locator('#select-shown').click()
    expect(page.locator('#selection-count')).to_contain_text('1 selected')
    page.locator('#clear-filters').click()
    expect(page.locator('#selection-count')).to_contain_text('1 selected')
    page.locator('#clear-selection').click()
    page.locator('#select-shown').click()
    expect(page.locator('#selection-count')).to_contain_text(f'{exportable_count} selected')
    with page.expect_download() as dl:
        page.locator('#download-ics').click()
    dl.value.save_as('/tmp/global-tech-outlook-all.ics')
    assert unfold('/tmp/global-tech-outlook-all.ics').count('BEGIN:VEVENT')==exportable_count
    page.locator('#clear-selection').click()
    page.locator('#timezone').select_option('Asia/Hong_Kong')
    page.locator('#calendar-view').click()
    ocp=page.locator('.calendar-entry[data-event-id="ocp"] [data-select-event]')
    expect(ocp).to_have_count(1)
    ocp.first.check()
    expect(page.locator('#selection-count')).to_contain_text('1 selected')
    assert ocp.evaluate_all('(inputs)=>inputs.every(i=>i.checked)')
    with page.expect_download() as dl:
        page.locator('#download-ics').click()
    dl.value.save_as('/tmp/global-tech-outlook-multiday.ics')
    text=unfold('/tmp/global-tech-outlook-multiday.ics')
    assert text.count('BEGIN:VEVENT')==1
    assert 'DTSTART;VALUE=DATE:20261012' in text and 'DTEND;VALUE=DATE:20261016' in text
    page.locator('#clear-selection').click()
    # Oracle wraps across two weeks, but both segments select one conference.
    oracle=page.locator('.calendar-entry[data-event-id="oracle-ai-world-2026"] [data-select-event]')
    expect(oracle).to_have_count(2)
    oracle.first.check()
    expect(page.locator('#selection-count')).to_contain_text('1 selected')
    assert oracle.evaluate_all('(inputs)=>inputs.every(i=>i.checked)')
    with page.expect_download() as dl:
        page.locator('#download-ics').click()
    dl.value.save_as('/tmp/global-tech-outlook-oracle.ics')
    text=unfold('/tmp/global-tech-outlook-oracle.ics')
    assert text.count('BEGIN:VEVENT')==1
    assert 'DTSTART;VALUE=DATE:20261025' in text and 'DTEND;VALUE=DATE:20261029' in text
    assert 'https://www.oracle.com/ai-world/keynotes/' in text
    oracle.last.uncheck()
    expect(page.locator('#download-ics')).to_be_disabled()
    assert oracle.evaluate_all('(inputs)=>inputs.every(i=>!i.checked)')
    page.locator('#select-events').click()
    page.locator('#timezone').select_option('browser')
    samsung=page.locator('.calendar-entry[data-event-id="005930.KS-2026-10-earnings"]')
    expect(samsung).to_have_attribute('data-start-date','2026-10-28')
    expect(samsung.locator('.calendar-time')).to_have_text('21:00')
    page.locator('#timezone').select_option('Asia/Hong_Kong')
    expect(samsung.locator('.calendar-time')).to_have_text('09:00')
    expect(samsung).to_have_attribute('data-start-date','2026-10-29')
    page.screenshot(path='/tmp/global-tech-timezone-desktop.png',full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    page.locator('#sidebar').evaluate('(e)=>Promise.all(e.getAnimations().map(a=>a.finished.catch(()=>{})))')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    expect(page.locator('#timezone')).to_be_visible()
    page.locator('#list-view').click()
    page.locator('#select-events').click()
    page.locator('#list-panel tr[data-event-id="TSM-2026-10-earnings"] [data-select-event]').check()
    with page.expect_download() as dl:
        page.locator('#download-ics').click()
    dl.value.save_as('/tmp/global-tech-outlook-mobile.ics')
    assert 'DTSTART:20261015T060000Z' in unfold('/tmp/global-tech-outlook-mobile.ics')
    page.screenshot(path='/tmp/global-tech-timezone-mobile.png',full_page=True)
    assert not errors,errors
    browser.close()
    print('PASS Global Tech title; Hong Kong default with New York browser; timezone persistence and date rollover; multi-selection across views/filters; real Outlook .ics downloads; mobile export; connected-event and week-continuation selection.')
