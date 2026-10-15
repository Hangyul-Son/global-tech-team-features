'use strict';
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.GlobalTechCalendar=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
  const DEFAULT_ZONE='Asia/Hong_Kong';
  function validZone(zone){try{new Intl.DateTimeFormat('en',{timeZone:zone});return true;}catch{return false;}}
  function dateKeyAt(instant,zone=DEFAULT_ZONE){
    const parts=new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(instant));
    const p=Object.fromEntries(parts.map(x=>[x.type,x.value]));return `${p.year}-${p.month}-${p.day}`;
  }
  function eventDate(event,zone=DEFAULT_ZONE){return event.startAt?dateKeyAt(event.startAt,zone):event.date||event.timingWindow?.start||'';}
  function eventEndDate(event,zone=DEFAULT_ZONE){
    if(event.startAt)return event.endAt?dateKeyAt(new Date(Date.parse(event.endAt)-1),zone):eventDate(event,zone);
    return event.endDate||event.timingWindow?.end||event.date||'';
  }
  function eventTime(event,zone=DEFAULT_ZONE){return event.startAt?new Intl.DateTimeFormat('en-GB',{timeZone:zone,hour:'2-digit',minute:'2-digit',hourCycle:'h23',timeZoneName:'short'}).format(new Date(event.startAt)):event.time?'Time needs verification':'Time not announced';}
  function shortTime(event,zone=DEFAULT_ZONE){return event.startAt?new Intl.DateTimeFormat('en-GB',{timeZone:zone,hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(event.startAt)):'';}
  function orderKey(event,zone=DEFAULT_ZONE){return `${eventDate(event,zone)||'9999-12-31'}T${event.startAt?shortTime(event,zone):'99:99'}`;}
  function canExport(event){return Boolean(event.date||event.startAt||event.timingWindow?.start);}
  const escapeText=value=>String(value??'').replace(/\\/g,'\\\\').replace(/\r\n|\r|\n/g,'\\n').replace(/;/g,'\\;').replace(/,/g,'\\,');
  function utcStamp(value){const d=new Date(value);if(!Number.isFinite(d.getTime()))throw new Error('Invalid event timestamp');return d.toISOString().replace(/[-:]/g,'').replace(/\.\d{3}Z$/,'Z');}
  function addDay(day){const d=new Date(day+'T12:00:00Z');if(!Number.isFinite(d.getTime()))throw new Error('Invalid event date');d.setUTCDate(d.getUTCDate()+1);return d.toISOString().slice(0,10);}
  function foldLine(line){
    const encoder=new TextEncoder();let current='',bytes=0;const lines=[];
    for(const char of line){const width=encoder.encode(char).length;if(bytes+width>75){lines.push(current);current=' ';bytes=1;}current+=char;bytes+=width;}
    lines.push(current);return lines.join('\r\n');
  }
  function toICS(events,now=new Date()){
    const unique=[...new Map(events.map(e=>[e.id,e])).values()];
    if(!unique.length)throw new Error('Select at least one event');
    const lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Global Tech//Technology Events//EN','CALSCALE:GREGORIAN','METHOD:PUBLISH','X-WR-CALNAME:Global Tech'];
    for(const event of unique){
      if(!canExport(event))throw new Error('An event has no sourced date or timing window');
      const window=event.timingWindow;
      const title=`${event.status==='confirmed'?'':'[Tentative] '}${event.title}${window?' — TIMING WINDOW: '+window.label:''}`;
      lines.push('BEGIN:VEVENT',`UID:${encodeURIComponent(event.id)}@global-tech.calendar`,`DTSTAMP:${utcStamp(now)}`,`SUMMARY:${escapeText(title)}`);
      if(event.startAt){
        lines.push(`DTSTART:${utcStamp(event.startAt)}`);
        if(event.endAt)lines.push(`DTEND:${utcStamp(event.endAt)}`);
      }else{
        const start=event.date||window.start,end=event.endDate||window?.end||start;
        lines.push(`DTSTART;VALUE=DATE:${start.replaceAll('-','')}`,`DTEND;VALUE=DATE:${addDay(end).replaceAll('-','')}`);
      }
      const detail=[`Date status: ${event.status}.`,window?`APPROXIMATE ${window.precision.toUpperCase()} WINDOW — not an exact event date or confirmed listing. Boundaries only describe the reported uncertainty period.`:event.startAt?`Published source time: ${event.time||''} (${event.sourceTimeZone||'UTC'}).${event.endAt?'':' End time has not been announced; no duration is assumed.'}`:'Date only: no verified start time is available. This is an all-day calendar marker, not a midnight appointment.',event.basis,event.dateConflict||'',`Source: ${event.sourceLabel||''}`,event.sourceUrl,...(event.sources||[]).map(s=>`${s.label}: ${s.url}`)].filter(Boolean).join('\n');
      lines.push(`DESCRIPTION:${escapeText(detail)}`,`STATUS:${event.status==='confirmed'?'CONFIRMED':'TENTATIVE'}`,'TRANSP:TRANSPARENT',`CATEGORIES:${escapeText(event.type)}`);
      try{const url=new URL(event.sourceUrl);if(url.protocol==='https:')lines.push(`URL:${url.href}`);}catch{}
      lines.push('END:VEVENT');
    }
    lines.push('END:VCALENDAR');return lines.map(foldLine).join('\r\n')+'\r\n';
  }
  return {DEFAULT_ZONE,validZone,dateKeyAt,eventDate,eventEndDate,eventTime,shortTime,orderKey,canExport,toICS,escapeText,foldLine};
});
