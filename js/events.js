'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const date = iso => new Date(`${iso}T12:00:00Z`);
  const Cal=GlobalTechCalendar;
  const browserZone=Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  let zonePreference=Cal.DEFAULT_ZONE;
  try{zonePreference=localStorage.getItem('globalTech.timezone') || Cal.DEFAULT_ZONE;}catch{}
  if(zonePreference!=='browser' && !Cal.validZone(zonePreference))zonePreference=Cal.DEFAULT_ZONE;
  let zone=zonePreference==='browser'?browserZone:zonePreference;
  let today=Cal.dateKeyAt(new Date(),zone);
  const selected=new Set();
  let selecting=false, visibleEvents=[];
  const monthKey = d => `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2,'0')}`;
  const dayKey = d => `${monthKey(d)}-${String(d.getUTCDate()).padStart(2,'0')}`;
  const prettyDay = iso => date(iso).toLocaleDateString('en-GB', {day:'numeric',month:'short',year:'numeric',timeZone:'UTC'});
  const prettyMonth = key => date(`${key}-01`).toLocaleDateString('en-GB',{month:'long',year:'numeric',timeZone:'UTC'});
  const labels = {confirmed:'Confirmed', estimated:'Estimated date', reported:'Reported date', unannounced:'Date unannounced'};
  let data, companies, view = 'calendar', month = date(`${today.slice(0,7)}-01`);
  const priority = e => e.companies.some(id => companies.get(id)?.coverage);
  const dateStatus = e => e.timingWindow ? (e.status==='reported'?'Reported window':'Estimated window') : labels[e.status];
  const rangeStart = e => Cal.eventDate(e,zone);
  const rangeEnd = e => Cal.eventEndDate(e,zone);
  const timingLabel = e => e.timingWindow ? e.timingWindow.label : rangeStart(e) ? prettyDay(rangeStart(e))+(rangeEnd(e)!==rangeStart(e)?' – '+prettyDay(rangeEnd(e)):'') : 'Timing not yet sourced';
  const certaintyClass = e => e.status==='confirmed'?'confirmed-event':'unconfirmed';
  const stale = e => ['confirmed','estimated','reported'].includes(e.status) && (!e.sourceCheckedAt || Date.now()-Date.parse(e.sourceCheckedAt)>14*86400000);
  const lifecycle = e => !rangeStart(e) ? 'Timing unknown' : rangeEnd(e) < today ? (e.timingWindow?'Past window':'Past date') : rangeStart(e) > today ? (e.timingWindow?'Future window':'Upcoming') : e.timingWindow ? 'Current window' : rangeStart(e)===today && rangeEnd(e)===today ? 'Today' : 'Current date range';
  const badge = e => `<span class="badge ${escape(e.status)}">${dateStatus(e)}${stale(e)?' · recheck':''}</span>`;
  const coverage = e => priority(e) ? '<span class="coverage-tag" role="img" aria-label="Coverage company" title="Coverage company">★</span>' : '';
  const sourceURL = url => {try {const u = new URL(url); return u.protocol === 'https:' ? u.href : null;} catch {return null;}};
  const eventKind = e => 'kind-' + e.type.toLowerCase().replaceAll(' ', '-');
  const temporalClass = e => !rangeStart(e) ? '' : rangeStart(e) > today ? 'upcoming' : rangeEnd(e) < today ? 'past' : 'current';
  function evidence(e) {
    const entries = [{url:e.sourceUrl,label:e.sourceLabel},...(e.sources || [])], seen = new Set();
    return entries.filter(item => {const url=sourceURL(item.url);if(!url || seen.has(url))return false;seen.add(url);return true;});
  }
  const sourceLinks = e => `<div class="event-sources">${evidence(e).map(item=>`<a href="${escape(sourceURL(item.url))}" target="_blank" rel="noopener noreferrer">${escape(item.label)} ↗</a>`).join('')}</div>`;
  function selectionControl(e,detail=false) {
    if(!selecting && !detail)return '';
    return `<label class="${detail?'detail-export':'event-select'}"><input type="checkbox" data-select-event="${escape(e.id)}" aria-label="Select ${escape(e.title)}" ${selected.has(e.id)?'checked':''} ${Cal.canExport(e)?'':'disabled title="No sourced date or timing window"'}>${detail?' Select for Outlook export':''}</label>`;
  }
  function updateSelection() {
    $('selection-bar').hidden=!selecting && selected.size===0;
    $('selection-count').textContent=`${selected.size} selected across all dates`;
    $('download-ics').disabled=selected.size===0;
    $('download-ics').textContent=selected.size?`Download .ics (${selected.size})`:'Download .ics';
    $('select-events').setAttribute('aria-pressed',String(selecting));
    $('select-events').textContent=selecting?'Done selecting':'Select events';
    document.querySelectorAll('[data-select-event]').forEach(input=>{input.checked=selected.has(input.dataset.selectEvent);});
    document.querySelectorAll('[data-event-id]').forEach(el=>el.classList.toggle('selected',selected.has(el.dataset.eventId)));
  }
  function updateDateLabel() {
    $('today-label').textContent=prettyDay(today)+' · '+zone;
  }
  function matches(e) {
    const query = $('search').value.trim().toLowerCase();
    const haystack = [e.title,e.type,e.importance,e.organizer,e.timingWindow?.label,...e.companies.flatMap(id => [id,companies.get(id)?.name])].join(' ').toLowerCase();
    return (!query || haystack.includes(query)) &&
      ($('type').value === 'all' || e.type === $('type').value) &&
      ($('status').value === 'all' || e.status === $('status').value) &&
      ($('universe').value === 'all' || ($('universe').value === 'coverage' ? priority(e) : !priority(e)));
  }
  function inMonth(e) {
    if (!rangeStart(e)) return false;
    const end = new Date(Date.UTC(month.getUTCFullYear(),month.getUTCMonth()+1,0));
    return rangeStart(e) <= dayKey(end) && rangeEnd(e) >= dayKey(month);
  }
  function jumpToToday() {
    const panel=$('list-panel'), marker=$('timeline-today');
    if(!marker || view!=='list') return;
    const heading=panel.querySelector('thead')?.getBoundingClientRect().height || 0;
    panel.scrollTop=Math.max(0,panel.scrollTop+marker.getBoundingClientRect().top-panel.getBoundingClientRect().top-heading);
  }
  function render({centerTimeline=false}={}) {
    const previousScroll=$('list-panel').scrollTop;
    const filtered = data.events.filter(matches).sort((a,b)=>Cal.orderKey(a,zone).localeCompare(Cal.orderKey(b,zone)) || Number(priority(b))-Number(priority(a)) || a.title.localeCompare(b.title));
    const scheduled = filtered.filter(inMonth);
    visibleEvents=view==='list'?filtered:scheduled;
    const undated = filtered.filter(e => !rangeStart(e));
    $('month-label').textContent = view==='list'?'All events':prettyMonth(monthKey(month));
    const past=filtered.filter(e=>rangeEnd(e) && rangeEnd(e)<today).length;
    $('results-count').textContent = view==='list' ? `${filtered.length} events · ${past} past · scroll for all dates` : `${scheduled.length} events this month · ${undated.length} without timing`;
    $('calendar-panel').hidden = view !== 'calendar';
    $('list-panel').hidden = view !== 'list';
    $('timeline-hint').hidden=view!=='list';
    $('prev-month').hidden=view==='list';
    $('next-month').hidden=view==='list';
    $('today-button').textContent=view==='list'?'Jump to today':'This month';
    $('calendar-view').setAttribute('aria-pressed', String(view === 'calendar'));
    $('list-view').setAttribute('aria-pressed', String(view === 'list'));
    renderCalendar(scheduled);
    renderList(filtered);
    $('radar-count').textContent = `${undated.length} watch items`;
    document.querySelector('.watch-section').hidden=view==='list' || undated.length===0;
    $('radar').innerHTML = undated.length ? undated.map(e => `<article class="radar-card ${eventKind(e)} ${certaintyClass(e)} ${selecting?'selecting':''}" data-event-id="${escape(e.id)}"><div class="radar-top"><span class="type-tag">${escape(e.type)}</span>${coverage(e)}</div><button class="event-name" data-event="${escape(e.id)}">${escape(e.title)}</button><p>${escape(e.importance)}</p><div class="radar-bottom"><span>Timing not yet sourced</span></div>${sourceLinks(e)}</article>`).join('') : '';
    updateSelection();
    if(centerTimeline && view==='list') requestAnimationFrame(jumpToToday);
    else if(view==='list') $('list-panel').scrollTop=previousScroll;
  }
  function renderCalendar(events) {
    let html = ['MON','TUE','WED','THU','FRI','SAT','SUN'].map(d => `<div class="weekday">${d}</div>`).join('');
    const offset = (month.getUTCDay()+6)%7;
    const days = new Date(Date.UTC(month.getUTCFullYear(),month.getUTCMonth()+1,0)).getUTCDate();
    const cells = Math.ceil((offset+days)/7)*7;
    for (let i=0; i<cells; i++) {
      const d = new Date(Date.UTC(month.getUTCFullYear(),month.getUTCMonth(),1-offset+i));
      const key = dayKey(d), outside = monthKey(d) !== monthKey(month);
      const items = outside ? [] : events.filter(e => !e.timingWindow && rangeStart(e) && rangeStart(e) <= key && rangeEnd(e) >= key);
      html += `<div class="day ${outside?'outside':''} ${key===today?'today':''} ${i%7>=5?'weekend':''}"><time class="day-number" datetime="${key}" ${key===today?'aria-current="date"':''}>${d.getUTCDate()}</time>${items.map(e=>{
        const title=e.type==='Earnings'?`${e.companies.join(' / ')} earnings`:e.title;
        const description=`${priority(e)?'Coverage: ':''}${e.title}. ${dateStatus(e)}${e.startAt?'. '+Cal.eventTime(e,zone)+' · '+timingLabel(e):'. Time not verified'}. Open event details.`;
        return `<div class="calendar-entry ${eventKind(e)} ${temporalClass(e)} ${certaintyClass(e)} ${selecting?'selecting':''}" data-event-id="${escape(e.id)}">${selectionControl(e)}<button class="calendar-event ${escape(e.status)}" data-event="${escape(e.id)}" title="${escape(e.title)}" aria-label="${escape(description)}">${priority(e)?'<b class="event-star" aria-hidden="true">★</b> ':''}${e.startAt?`<time class="calendar-time" datetime="${escape(e.startAt)}">${escape(Cal.shortTime(e,zone))}</time> `:''}${escape(title)}</button></div>`;
      }).join('')}</div>`;
    }
    $('calendar').innerHTML = html;
    const windows=events.filter(e=>e.timingWindow);
    $('timing-windows').hidden=windows.length===0;
    $('timing-windows').innerHTML=windows.length ? `<h3>Approximate timing windows</h3><div class="window-grid">${windows.map(e=>`<article class="timing-window ${eventKind(e)} ${certaintyClass(e)} ${selecting?'selecting':''}" data-event-id="${escape(e.id)}">${selectionControl(e)}<button class="event-name" data-event="${escape(e.id)}">${priority(e)?'<span class="event-star" aria-label="Coverage">★</span> ':''}${escape(e.title)}</button><span class="window-label">${escape(e.timingWindow.label)}</span></article>`).join('')}</div>` : '';

  }
  function renderList(events) {
    if(!events.length) {
      $('list-panel').innerHTML='<p class="empty">No events match these filters. Try another search or reset filters.</p>';
      return;
    }
    let marked=false;
    const marker=()=>`<tr class="timeline-today" id="timeline-today"><td colspan="5">Today · ${escape(prettyDay(today))} <span>↑ Scroll up for past events · Scroll down for what’s next ↓</span></td></tr>`;
    let rows='';
    for(const e of events) {
      if(!marked && (!rangeStart(e) || rangeStart(e)>=today)) {rows+=marker();marked=true;}
      rows+=`<tr class="${temporalClass(e)} ${eventKind(e)} ${certaintyClass(e)} ${selecting?'selecting':''}" data-event-id="${escape(e.id)}"><td>${escape(timingLabel(e))}<small>${escape(lifecycle(e))}${e.timingWindow?' · window only':e.status==='estimated'?' · estimate, not confirmed':''}</small><small>${escape(e.timingWindow?'No exact day or time announced':Cal.eventTime(e,zone))}</small>${!e.startAt && e.date?'<small>Source date · time unverified</small>':''}</td><td>${selectionControl(e)}<button class="event-name" data-event="${escape(e.id)}">${priority(e)?'<b class="event-star" aria-label="Coverage">★</b> ':''}${escape(e.title)}</button><small>${escape(e.companies.length?e.companies.join(' · '):e.organizer || 'Industry event')}</small></td><td><span class="type-tag">${escape(e.type)}</span></td><td>${badge(e)}${e.dateConflict?'<small>Source discrepancy · see brief</small>':''}</td><td>${sourceLinks(e)}</td></tr>`;
    }
    if(!marked)rows+=marker();
    $('list-panel').innerHTML=`<table class="list-table"><caption class="sr-only">All events, chronological from past to future; starts near today</caption><thead><tr><th scope="col">Date / timing window</th><th scope="col">Event</th><th scope="col">Type</th><th scope="col">Date status</th><th scope="col">Sources / event links</th></tr></thead><tbody>${rows}</tbody></table>`;
  }
  function showEvent(id) {
    const e = data.events.find(e => e.id === id);
    if (!e) return;
    const url = sourceURL(e.sourceUrl);
    $('event-detail').innerHTML = `${badge(e)} <span>${coverage(e)}</span><p class="event-lifecycle">${escape(lifecycle(e))}</p><h2>${escape(e.title)}</h2><p>${escape(e.importance)}</p>${stale(e)?'<p class="detail-note">Source check is more than 14 days old or unavailable. Recheck for schedule changes.</p>':''}<dl><dt>Companies</dt><dd>${escape(e.companies.length?e.companies.map(id=>`${companies.get(id).name} (${id})`).join(', '):e.organizer || 'Industry event')}</dd><dt>Date / window</dt><dd>${escape(timingLabel(e))}</dd><dt>Time (${escape(zone)})</dt><dd>${escape(Cal.eventTime(e,zone))}${e.endAt?' – '+escape(Cal.eventTime({...e,startAt:e.endAt},zone)):''}</dd><dt>Published source</dt><dd>${escape(e.date || e.timingWindow?.label || '')}${e.time?' · '+escape(e.time):''}${e.sourceTimeZone?' · '+escape(e.sourceTimeZone):''}</dd><dt>Source checked</dt><dd>${e.sourceCheckedAt?escape(new Date(e.sourceCheckedAt).toLocaleString('en-GB',{timeZone:'UTC'}))+' UTC':'Not checked'}</dd><dt>Official status</dt><dd>${e.status==='confirmed'?'Official announcement or participant schedule verified':e.status==='estimated'?(e.timingWindow?'Unconfirmed timing window · not a scheduled listing':'Unconfirmed estimate · source checked, date not announced'):e.status==='reported'?'Media-reported date · primary confirmation not verified':'No date announced'}</dd><dt>Source</dt><dd>${escape(e.sourceLabel)}</dd></dl>${e.dateConflict?`<p class="conflict-note"><strong>Source discrepancy:</strong> ${escape(e.dateConflict)}</p>`:''}<p class="detail-note">${escape(e.basis)}</p><ul class="source-list">${(e.sources || []).map(src=>{const href=sourceURL(src.url);return href?`<li><a href="${escape(href)}" target="_blank" rel="noopener noreferrer">${escape(src.label)} ↗</a> <small>${escape(src.kind)}</small></li>`:'';}).join('')}</ul>${url?`<a class="source-link" href="${escape(url)}" target="_blank" rel="noopener noreferrer">Open source evidence ↗</a>`:''}${selectionControl(e,true)}<p>Events are maintained by the research team through Codex. Public visitors cannot add, edit or delete entries.</p>`;
    $('event-dialog').showModal();
  }
  document.addEventListener('click', event => {
    const trigger = event.target.closest('[data-event]');
    if (trigger) showEvent(trigger.dataset.event);
    if (event.target.closest('.close-dialog')) event.target.closest('dialog').close();
  });
  for (const id of ['methodology-button','footer-methodology']) $(id).addEventListener('click', ()=>$('methodology-dialog').showModal());
  for (const id of ['search','universe','type','status']) $(id).addEventListener(id==='search'?'input':'change',()=>{if(data) render({centerTimeline:view==='list'});});
  for (const mode of ['calendar','list']) $(`${mode}-view`).addEventListener('click',()=>{view=mode;if(data)render({centerTimeline:mode==='list'});});
  for (const [id,delta] of [['prev-month',-1],['next-month',1]]) $(id).addEventListener('click',()=>{month=new Date(Date.UTC(month.getUTCFullYear(),month.getUTCMonth()+delta,1));if(data)render();});
  $('today-button').addEventListener('click',()=>{if(view==='list'){jumpToToday();return;}month=date(`${today.slice(0,7)}-01`);if(data)render();});
  $('clear-filters').addEventListener('click',()=>{$('search').value='';for(const id of ['universe','type','status'])$(id).value='all';if(data)render({centerTimeline:view==='list'});});
  $('select-events').addEventListener('click',()=>{selecting=!selecting;if(data)render();});
  $('select-shown').addEventListener('click',()=>{visibleEvents.filter(Cal.canExport).forEach(e=>selected.add(e.id));updateSelection();});
  $('clear-selection').addEventListener('click',()=>{selected.clear();updateSelection();});
  document.addEventListener('change',event=>{
    const input=event.target.closest('[data-select-event]');
    if(!input)return;
    if(input.checked)selected.add(input.dataset.selectEvent);else selected.delete(input.dataset.selectEvent);
    updateSelection();
  });
  $('download-ics').addEventListener('click',()=>{
    if(!data || !selected.size)return;
    const content=Cal.toICS(data.events.filter(e=>selected.has(e.id)));
    const url=URL.createObjectURL(new Blob([content],{type:'text/calendar;charset=utf-8'}));
    const link=document.createElement('a');link.href=url;link.download=`global-tech-events-${today}.ics`;document.body.append(link);link.click();link.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  $('timezone').addEventListener('change',()=>{
    const wasCurrent=monthKey(month)===today.slice(0,7);
    zonePreference=$('timezone').value;
    zone=zonePreference==='browser'?browserZone:zonePreference;
    if(!Cal.validZone(zone)){zone=Cal.DEFAULT_ZONE;zonePreference=zone;$('timezone').value=zone;}
    try{localStorage.setItem('globalTech.timezone',zonePreference);}catch{}
    today=Cal.dateKeyAt(new Date(),zone);
    if(wasCurrent)month=date(`${today.slice(0,7)}-01`);
    updateDateLabel();if(data)render({centerTimeline:view==='list'});
  });
  $('timezone').querySelector('[value="browser"]').textContent=`Browser (${browserZone})`;
  if(![...$('timezone').options].some(o=>o.value===zonePreference))$('timezone').add(new Option(zonePreference,zonePreference));
  $('timezone').value=zonePreference;
  const mobile=window.matchMedia('(max-width: 800px)');
  function setDrawer(open, returnFocus=false) {
    $('sidebar').classList.toggle('open',open);
    $('sidebar').inert=mobile.matches && !open;
    $('open-universe').setAttribute('aria-expanded',String(open));
    if(open) $('close-universe').focus();
    else if(returnFocus) $('open-universe').focus();
  }
  $('open-universe').addEventListener('click',()=>setDrawer(true));
  $('close-universe').addEventListener('click',()=>setDrawer(false,true));
  document.addEventListener('keydown',event=>{if(event.key==='Escape' && $('sidebar').classList.contains('open'))setDrawer(false,true);});
  document.addEventListener('click',event=>{if(mobile.matches && !event.target.closest('#sidebar, #open-universe') && $('sidebar').classList.contains('open'))setDrawer(false);});
  mobile.addEventListener('change',()=>setDrawer(false));
  setDrawer(false);
  async function init() {
    try {
      const response = await fetch('data/events.json',{cache:'no-cache'});
      if(!response.ok) throw new Error('Dataset could not be loaded.');
      data=await response.json();
      companies=new Map(data.companies.map(c=>[c.id,c]));
      updateDateLabel();
      $('universe-count').textContent=data.companies.length;
      const covered=data.companies.filter(c=>c.coverage), wider=data.companies.filter(c=>!c.coverage);
      $('coverage-count').textContent=covered.length;
      $('ecosystem-count').textContent=wider.length;
      const companyRow=(c,covered)=>`<div class="${covered?'coverage-company':'universe-company'}"><span class="ticker">${escape(c.id)}</span><span class="company-name">${escape(c.name)}</span>${covered?'<span class="coverage-star" aria-label="Coverage">★</span>':''}</div>`;
      $('coverage-list').innerHTML=covered.map(c=>companyRow(c,true)).join('');
      $('ecosystem-list').innerHTML=wider.map(c=>companyRow(c,false)).join('');
      $('freshness').textContent=`Dataset reviewed: ${prettyDay(data.asOf)}. ${data.lastSuccessfulRefresh?'Last source review: '+prettyDay(data.lastSuccessfulRefresh.slice(0,10))+'.':'No successful source check yet.'} Published estimates are not company-confirmed.`;
      render();
    } catch(error) {
      $('calendar').innerHTML='<p class="loading-error">Unable to load events. Please reload or check the public dataset link below.</p>';
      $('freshness').textContent='Event data unavailable. No events have been verified by this session.';
      console.error(error);
    }
  }
  init();
})();
