const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const Cal=require('../js/calendar-utils.js');
const data=JSON.parse(fs.readFileSync(require('node:path').join(__dirname,'../data/events.json')));
const event=id=>data.events.find(e=>e.id===id);
const unfold=text=>text.replace(/\r\n[ \t]/g,'');

test('Hong Kong default and date rollover for published US calls',()=>{
 assert.equal(Cal.DEFAULT_ZONE,'Asia/Hong_Kong');
 const apple=event('AAPL-2026-11-earnings');
 assert.equal(apple.startAt,'2026-11-02T22:00:00Z');
 assert.equal(Cal.eventDate(apple),'2026-11-03');
 assert.equal(Cal.shortTime(apple),'06:00');
 assert.equal(Cal.eventDate(apple,'America/Los_Angeles'),'2026-11-02');
 assert.equal(Cal.shortTime(apple,'America/Los_Angeles'),'14:00');
 assert.equal(Cal.shortTime(event('005930.KS-2026-10-earnings')),'09:00');
});
test('DST and calendar month/year rollover use IANA rules',()=>{
 assert.equal(Cal.shortTime({startAt:'2026-10-28T21:00:00Z'},'America/Los_Angeles'),'14:00');
 assert.equal(Cal.shortTime({startAt:'2026-11-04T22:00:00Z'},'America/Los_Angeles'),'14:00');
 assert.equal(Cal.eventDate({startAt:'2026-12-31T23:30:00Z',date:'2026-12-31'}),'2027-01-01');
 assert.equal(Cal.eventDate({startAt:'2026-10-31T23:30:00Z',date:'2026-10-31'}),'2026-11-01');
 assert.equal(Cal.validZone('Not/AZone'),false);
});
test('unannounced times remain date-only; verified NVIDIA and AMD calls convert across zones',()=>{
 const workday=event('WDAY-2026-11-earnings');
 assert.equal(workday.startAt,undefined);
 assert.equal(Cal.eventDate(workday,'Asia/Hong_Kong'),workday.date);
 assert.equal(Cal.eventTime(workday),'Time not announced');
 const nvda=event('NVDA-2026-11-earnings');
 assert.equal(nvda.startAt,'2026-11-17T22:00:00Z');
 assert.equal(Cal.eventDate(nvda,'Asia/Hong_Kong'),'2026-11-18');
 assert.equal(Cal.shortTime(nvda,'Asia/Hong_Kong'),'06:00');
 assert.equal(Cal.eventDate(nvda,'America/Los_Angeles'),'2026-11-17');
 assert.equal(Cal.shortTime(nvda,'America/Los_Angeles'),'14:00');
 const amd=event('AMD-2026-11-earnings');
 assert.equal(amd.startAt,'2026-11-03T22:00:00Z');
 assert.equal(Cal.eventDate(amd,'Asia/Hong_Kong'),'2026-11-04');
 assert.equal(Cal.shortTime(amd,'Asia/Hong_Kong'),'06:00');
 assert.equal(Cal.shortTime(amd,'America/Los_Angeles'),'14:00');
});
test('UTC ICS events keep real times, stable UIDs, and deduplicate multiday selections',()=>{
 const apple=event('AAPL-2026-11-earnings');
 const out=unfold(Cal.toICS([apple,apple],new Date('2026-10-15T12:00:00Z')));
 assert.equal((out.match(/BEGIN:VEVENT/g)||[]).length,1);
 assert.match(out,/DTSTART:20261102T220000Z\r\n/);
 assert.match(out,/DTSTAMP:20261015T120000Z/);
 assert.match(out,/UID:AAPL-2026-11-earnings@global-tech.calendar/);
 assert.match(out,/STATUS:CONFIRMED/);
 assert.ok(!out.includes('DTEND:'),'Do not invent a call end time');
 const tsm=unfold(Cal.toICS([event('TSM-2026-10-earnings')]));
 assert.match(tsm,/DTSTART:20261015T060000Z/);
 assert.match(tsm,/DTEND:20261015T073000Z/);
});
test('all-day end dates are exclusive; estimates are tentative',()=>{
 const forecast={...event('NVDA-2026-11-earnings'),id:'forecast-fixture',title:'Forecast fixture',date:'2026-11-18',status:'estimated',verifiedAt:null,startAt:undefined,endAt:undefined,time:null,sourceTimeZone:undefined,timeCertainty:undefined,timeCheckedAt:undefined};
 const out=unfold(Cal.toICS([event('ocp'),forecast]));
 assert.match(out,/DTSTART;VALUE=DATE:20261012/);
 assert.match(out,/DTEND;VALUE=DATE:20261016/);
 assert.match(out,/DTSTART;VALUE=DATE:20261118/);
 assert.match(out,/DTEND;VALUE=DATE:20261119/);
 assert.match(out,/STATUS:TENTATIVE/);
 assert.match(out,/SUMMARY:\[Tentative\] Forecast fixture/);
});
test('Reported IPO windows are tentative; undated IPO watch items cannot be exported',()=>{
 const out=unfold(Cal.toICS([event('anthropic-ipo')]));
 assert.match(out,/TIMING WINDOW/);
 assert.match(out,/DTSTART;VALUE=DATE:20261101/);
 assert.match(out,/DTEND;VALUE=DATE:20261201/);
 assert.equal((out.match(/TRANSP:TRANSPARENT/g)||[]).length,1);
 assert.equal((out.match(/STATUS:TENTATIVE/g)||[]).length,1);
 assert.equal(Cal.canExport(event('openai-ipo')),false);
 assert.throws(()=>Cal.toICS([event('openai-ipo')]),/no sourced date/);
});
test('RFC 5545 UTF-8 folding, escaping, CRLF and injection protection',()=>{
 const e={...event('TSM-2026-10-earnings'),title:'測試,;\\\nBEGIN:VALARM '+ '한글'.repeat(80)};
 const out=Cal.toICS([e]);
 assert.ok(out.endsWith('\r\n'));
 assert.ok(out.split('\r\n').every(line=>Buffer.byteLength(line,'utf8')<=75));
 assert.ok(!out.includes('\r\nBEGIN:VALARM'));
 assert.match(unfold(out),/測試\\,\\;\\\\\\nBEGIN:VALARM/);
 assert.equal(Cal.canExport({date:null}),false);
 assert.throws(()=>Cal.toICS([]),/Select at least/);
 assert.throws(()=>Cal.toICS([{id:'unknown',date:null}]),/no sourced date/);
});
test('all scheduled events serialize; undated watch items never become fictitious appointments',()=>{
 const scheduled=data.events.filter(Cal.canExport);
 const undated=data.events.filter(e=>!Cal.canExport(e));
 const out=Cal.toICS(scheduled,new Date('2026-10-15T12:00:00Z'));
 assert.equal((out.match(/BEGIN:VEVENT/g)||[]).length,scheduled.length);
 for(const e of scheduled){
  const block=unfold(Cal.toICS([e]));
  assert.ok(block.includes(e.startAt?'DTSTART:':'DTSTART;VALUE=DATE:'));
 }
 for(const e of undated)assert.throws(()=>Cal.toICS([e]),/no sourced date/);
});
