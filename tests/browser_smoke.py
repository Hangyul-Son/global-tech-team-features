"""Optional real-browser checks. Run a server on port 8000 first.
Uses the environment's Python Playwright and Chromium installations.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
        args=['--no-sandbox','--disable-dev-shm-usage','--no-proxy-server','--single-process','--no-zygote'])
    page = browser.new_page(viewport={'width':1440,'height':1000})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8000')
    expect(page.locator('#universe-count')).to_have_text('22')
    expect(page.locator('.coverage-company')).to_have_count(12)
    # Navigate deterministically to the seed month, even on future machines.
    page.clock.install(time=__import__('datetime').datetime(2026,10,15,12,0,tzinfo=__import__('datetime').timezone.utc))
    page.reload()
    expect(page.locator('#month-label')).to_have_text('October 2026')
    expect(page.locator('.calendar-event')).to_have_count(3)
    expect(page.locator('.estimate-chip')).to_have_count(10)
    page.locator('#list-view').click()
    expect(page.locator('#list-panel')).to_be_visible()
    expect(page.locator('#calendar-panel')).to_be_hidden()
    expect(page.locator('.list-table tbody tr')).to_have_count(13)
    page.locator('#universe').select_option('coverage')
    expect(page.locator('.list-table tbody tr')).to_have_count(5)
    page.locator('#status').select_option('confirmed')
    expect(page.locator('.list-table tbody tr')).to_have_count(3)
    page.locator('#search').fill('Microsoft')
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
    page.locator('#search').fill('no such company')
    expect(page.locator('#list-panel')).to_contain_text('No events match')
    expect(page.locator('#radar')).to_contain_text('No undated watch items')
    page.locator('#clear-filters').click()
    page.locator('#today-button').click()
    page.locator('#calendar-view').click()
    page.locator('#status').select_option('estimated')
    expect(page.locator('.calendar-event')).to_have_count(0)
    expect(page.locator('.estimate-chip')).to_have_count(10)
    page.locator('#clear-filters').click()
    # Untrusted data is rendered as text, never executed or used as a script URL.
    hostile=json.loads((ROOT/'data/events.json').read_text())
    hostile['events'][0].update(title='<img src=x onerror=alert(1)>',sourceUrl='javascript:alert(1)')
    page.route('**/data/events.json',lambda route:route.fulfill(json=hostile))
    page.reload()
    page.locator('#list-view').click()
    page.get_by_role('button',name='<img src=x onerror=alert(1)>',exact=True).click()
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
    page.screenshot(path='/tmp/catalyst-desktop.png',full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile document overflows'
    assert page.locator('#universe').bounding_box()['width'] >= 85, 'Mobile filters are too narrow'
    page.locator('#list-view').click()
    expect(page.locator('.list-table')).to_be_visible()
    page.locator('.event-name').first.click()
    expect(page.locator('#event-dialog')).to_be_visible()
    page.keyboard.press('Escape')
    page.locator('#calendar-view').click()
    page.screenshot(path='/tmp/catalyst-mobile.png',full_page=True)
    assert not errors,errors
    browser.close()
    print('PASS desktop/mobile views, filters, navigation, source briefs, keyboard dismissal, estimated precision, empty states, safe rendering and multi-day events; no browser errors.')
