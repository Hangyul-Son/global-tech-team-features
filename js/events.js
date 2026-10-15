'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const date = iso => new Date(`${iso}T12:00:00Z`);
  const today = new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Hong_Kong', year:'numeric', month:'2-digit', day:'2-digit'}).format(new Date());
  const monthKey = d => `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2,'0')}`;
  const dayKey = d => `${monthKey(d)}-${String(d.getUTCDate()).padStart(2,'0')}`;
  const prettyDay = iso => date(iso).toLocaleDateString('en-GB', {day:'numeric',month:'short',year:'numeric',timeZone:'UTC'});
  const prettyMonth = key => date(`${key}-01`).toLocaleDateString('en-GB',{month:'long',year:'numeric',timeZone:'UTC'});
  const labels = {confirmed:'Confirmed', estimated:'Estimated date', reported:'Reported date', unannounced:'Date unannounced'};
  let data, companies, view = 'calendar', month = date(`${today.slice(0,7)}-01`);
  const priority = e => e.companies.some(id => companies.get(id)?.coverage);
  const dateStatus = e => e.timingWindow ? (e.status==='reported'?'Reported window':'Estimated window') : labels[e.status];
  const rangeStart = e => e.date || e.timingWindow?.start || '';
  const rangeEnd = e => e.endDate || e.timingWindow?.end || e.date || '';
  const timingLabel = e => e.timingWindow ? e.timingWindow.label : e.date ? prettyDay(e.date)+(e.endDate && e.endDate!==e.date?' – '+prettyDay(e.endDate):'') : 'Timing not yet sourced';
  const certaintyClass = e => e.status==='confirmed'?'confirmed-event':'unconfirmed';
  const stale = e => ['confirmed','estimated','reported'].includes(e.status) && (!e.sourceCheckedAt || Date.now()-Date.parse(e.sourceCheckedAt)>14*86400000);
  const lifecycle = e => !rangeStart(e) ? 'Timing unknown' : rangeEnd(e) < today ? (e.timingWindow?'Past window':'Past date') : rangeStart(e) > today ? (e.timingWindow?'Future window':'Upcoming') : e.timingWindow ? 'Current window' : e.date===today && !e.endDate ? 'Today' : 'Current date range';
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
    const filtered = data.events.filter(matches).sort((a,b)=>(rangeStart(a)||'9999-12-31').localeCompare(rangeStart(b)||'9999-12-31') || Number(priority(b))-Number(priority(a)) || a.title.localeCompare(b.title));
    const scheduled = filtered.filter(inMonth);
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
    $('radar').innerHTML = undated.length ? undated.map(e => `<article class="radar-card ${eventKind(e)} ${certaintyClass(e)}" data-event-id="${escape(e.id)}"><div class="radar-top"><span class="type-tag">${escape(e.type)}</span>${coverage(e)}</div><button class="event-name" data-event="${escape(e.id)}">${escape(e.title)}</button><p>${escape(e.importance)}</p><div class="radar-bottom"><span>Timing not yet sourced</span></div>${sourceLinks(e)}</article>`).join('') : '';
    if(centerTimeline && view==='list') requestAnimationFrame(jumpToToday);
  }
  function renderCalendar(events) {
    let html = ['MON','TUE','WED','THU','FRI','SAT','SUN'].map(d => `<div class="weekday">${d}</div>`).join('');
    const offset = (month.getUTCDay()+6)%7;
    const days = new Date(Date.UTC(month.getUTCFullYear(),month.getUTCMonth()+1,0)).getUTCDate();
    const cells = Math.ceil((offset+days)/7)*7;
    for (let i=0; i<cells; i++) {
      const d = new Date(Date.UTC(month.getUTCFullYear(),month.getUTCMonth(),1-offset+i));
      const key = dayKey(d), outside = monthKey(d) !== monthKey(month);
      const items = outside ? [] : events.filter(e => e.date && e.date <= key && (e.endDate || e.date) >= key);
      html += `<div class="day ${outside?'outside':''} ${key===today?'today':''} ${i%7>=5?'weekend':''}"><time class="day-number" datetime="${key}" ${key===today?'aria-current="date"':''}>${d.getUTCDate()}</time>${items.map(e=>{
        const url=sourceURL(e.sourceUrl);
        return `<div class="calendar-entry ${eventKind(e)} ${temporalClass(e)} ${certaintyClass(e)}" data-event-id="${escape(e.id)}"><button class="calendar-event ${escape(e.status)}" data-event="${escape(e.id)}">${priority(e)?'<b class="event-star" aria-label="Coverage">★</b> ':''}${escape(e.title)}<span>${escape(labels[e.status])} · ${escape(lifecycle(e))}${e.time?' · '+escape(e.time):''}</span></button>${url?`<a class="calendar-source" href="${escape(url)}" target="_blank" rel="noopener noreferrer" aria-label="Source for ${escape(e.title)}">${e.status==='estimated'?'Estimate source':'Source'} ↗</a>`:''}</div>`;
      }).join('')}</div>`;
    }
    $('calendar').innerHTML = html;
    const windows=events.filter(e=>e.timingWindow);
    $('timing-windows').hidden=windows.length===0;
    $('timing-windows').innerHTML=windows.length ? `<h3>Timing windows · exact date unconfirmed</h3><div class="radar-grid">${windows.map(e=>`<article class="radar-card ${eventKind(e)} ${certaintyClass(e)}" data-event-id="${escape(e.id)}"><div class="radar-top"><span class="type-tag">${escape(e.type)}</span>${coverage(e)}</div><button class="event-name" data-event="${escape(e.id)}">${escape(e.title)}</button><strong class="window-label">${escape(e.timingWindow.label)}</strong>${badge(e)}<p>Shown as a ${escape(e.timingWindow.precision)} window, not an exact event day.</p>${sourceLinks(e)}</article>`).join('')}</div>` : '';

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
      rows+=`<tr class="${temporalClass(e)} ${eventKind(e)} ${certaintyClass(e)}" data-event-id="${escape(e.id)}"><td>${escape(timingLabel(e))}<small>${escape(lifecycle(e))}${e.timingWindow?' · window only':e.status==='estimated'?' · estimate, not confirmed':''}</small><small>${escape(e.time || (e.timingWindow?'No exact day or time announced':'Time not confirmed'))}</small></td><td><button class="event-name" data-event="${escape(e.id)}">${priority(e)?'<b class="event-star" aria-label="Coverage">★</b> ':''}${escape(e.title)}</button><small>${escape(e.companies.length?e.companies.join(' · '):e.organizer || 'Industry event')}</small></td><td><span class="type-tag">${escape(e.type)}</span></td><td>${badge(e)}${e.dateConflict?'<small>Source discrepancy · see brief</small>':''}</td><td>${sourceLinks(e)}</td></tr>`;
    }
    if(!marked)rows+=marker();
    $('list-panel').innerHTML=`<table class="list-table"><caption class="sr-only">All events, chronological from past to future; starts near today</caption><thead><tr><th scope="col">Date / timing window</th><th scope="col">Event</th><th scope="col">Type</th><th scope="col">Date status</th><th scope="col">Sources / event links</th></tr></thead><tbody>${rows}</tbody></table>`;
  }
  function showEvent(id) {
    const e = data.events.find(e => e.id === id);
    if (!e) return;
    const url = sourceURL(e.sourceUrl);
    $('event-detail').innerHTML = `${badge(e)} <span>${coverage(e)}</span><p class="event-lifecycle">${escape(lifecycle(e))}</p><h2>${escape(e.title)}</h2><p>${escape(e.importance)}</p>${stale(e)?'<p class="detail-note">Source check is more than 14 days old or unavailable. Recheck for schedule changes.</p>':''}<dl><dt>Companies</dt><dd>${escape(e.companies.length?e.companies.map(id=>`${companies.get(id).name} (${id})`).join(', '):e.organizer || 'Industry event')}</dd><dt>Date / window</dt><dd>${escape(timingLabel(e))}</dd><dt>Time</dt><dd>${escape(e.time || 'Not published / not verified')}</dd><dt>Source checked</dt><dd>${e.sourceCheckedAt?escape(new Date(e.sourceCheckedAt).toLocaleString('en-GB',{timeZone:'UTC'}))+' UTC':'Not checked'}</dd><dt>Official status</dt><dd>${e.status==='confirmed'?'Official announcement or participant schedule verified':e.status==='estimated'?(e.timingWindow?'Unconfirmed timing window · not a scheduled listing':'Unconfirmed estimate · source checked, date not announced'):e.status==='reported'?'Media-reported date · primary confirmation not verified':'No date announced'}</dd><dt>Source</dt><dd>${escape(e.sourceLabel)}</dd></dl>${e.dateConflict?`<p class="conflict-note"><strong>Source discrepancy:</strong> ${escape(e.dateConflict)}</p>`:''}<p class="detail-note">${escape(e.basis)}</p><ul class="source-list">${(e.sources || []).map(src=>{const href=sourceURL(src.url);return href?`<li><a href="${escape(href)}" target="_blank" rel="noopener noreferrer">${escape(src.label)} ↗</a> <small>${escape(src.kind)}</small></li>`:'';}).join('')}</ul>${url?`<a class="source-link" href="${escape(url)}" target="_blank" rel="noopener noreferrer">Open source evidence ↗</a>`:''}<p>Events are maintained by the research team through Codex. Public visitors cannot add, edit or delete entries.</p>`;
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
      $('today-label').textContent = date(today).toLocaleDateString('en-GB',{weekday:'short',day:'numeric',month:'long',year:'numeric',timeZone:'UTC'})+' · HKT';
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
