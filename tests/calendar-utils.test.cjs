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
test('unknown and conflicting times remain date-only in all zones',()=>{
 const amd=event('AMD-2026-11-earnings');
 assert.equal(amd.startAt,undefined);
 assert.equal(Cal.eventDate(amd,'Asia/Hong_Kong'),'2026-11-03');
 assert.equal(Cal.eventDate(amd,'America/Los_Angeles'),'2026-11-03');
 assert.equal(Cal.eventTime(amd),'Time needs verification');
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
 const out=unfold(Cal.toICS([event('ocp'),event('NVDA-2026-11-earnings')]));
 assert.match(out,/DTSTART;VALUE=DATE:20261012/);
 assert.match(out,/DTEND;VALUE=DATE:20261016/);
 assert.match(out,/DTSTART;VALUE=DATE:20261118/);
 assert.match(out,/DTEND;VALUE=DATE:20261119/);
 assert.match(out,/STATUS:TENTATIVE/);
 assert.match(out,/SUMMARY:\[Tentative\] NVIDIA earnings/);
});
test('IPO windows are explicitly tentative transparent ranges, never point appointments',()=>{
 const out=unfold(Cal.toICS([event('anthropic-ipo'),event('openai-ipo')]));
 assert.match(out,/TIMING WINDOW/);
 assert.match(out,/DTSTART;VALUE=DATE:20261101/);
 assert.match(out,/DTEND;VALUE=DATE:20261201/);
 assert.match(out,/DTSTART;VALUE=DATE:20270101/);
 assert.match(out,/DTEND;VALUE=DATE:20280101/);
 assert.equal((out.match(/TRANSP:TRANSPARENT/g)||[]).length,2);
 assert.equal((out.match(/STATUS:TENTATIVE/g)||[]).length,2);
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
test('every current event can serialize without fabricating missing times',()=>{
 const out=Cal.toICS(data.events,new Date('2026-10-15T12:00:00Z'));
 assert.equal((out.match(/BEGIN:VEVENT/g)||[]).length,data.events.length);
 for(const e of data.events){
  const block=unfold(Cal.toICS([e]));
  assert.ok(block.includes(e.startAt?'DTSTART:':'DTSTART;VALUE=DATE:'));
 }
});
