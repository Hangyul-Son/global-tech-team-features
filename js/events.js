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
  const stale = e => ['confirmed','estimated','reported'].includes(e.status) && (!e.sourceCheckedAt || Date.now()-Date.parse(e.sourceCheckedAt)>14*86400000);
  const lifecycle = e => !e.date ? '' : (e.endDate || e.date) < today ? 'Past date' : e.date > today ? 'Upcoming' : e.date === today && !e.endDate ? 'Today' : 'Current date range';
  const badge = e => `<span class="badge ${escape(e.status)}">${labels[e.status]}${stale(e)?' · recheck':''}</span>`;
  const coverage = e => priority(e) ? '<span class="coverage-tag">★ OUR COVERAGE</span>' : '';
  const sourceURL = url => {try {const u = new URL(url); return u.protocol === 'https:' ? u.href : null;} catch {return null;}};
  function matches(e) {
    const query = $('search').value.trim().toLowerCase();
    const haystack = [e.title,e.type,e.importance,...e.companies.flatMap(id => [id,companies.get(id)?.name])].join(' ').toLowerCase();
    return (!query || haystack.includes(query)) &&
      ($('type').value === 'all' || e.type === $('type').value) &&
      ($('status').value === 'all' || e.status === $('status').value) &&
      ($('universe').value === 'all' || ($('universe').value === 'coverage' ? priority(e) : !priority(e)));
  }
  function inMonth(e) {
    if (e.window) return e.window === monthKey(month);
    if (!e.date) return false;
    const end = new Date(Date.UTC(month.getUTCFullYear(),month.getUTCMonth()+1,0));
    return e.date <= dayKey(end) && (e.endDate || e.date) >= dayKey(month);
  }
  function render() {
    const filtered = data.events.filter(matches);
    const scheduled = filtered.filter(inMonth).sort((a,b) => (a.date || `${a.window}-32`).localeCompare(b.date || `${b.window}-32`) || Number(priority(b))-Number(priority(a)) || a.title.localeCompare(b.title));
    const undated = filtered.filter(e => !e.date && !e.window);
    $('month-label').textContent = prettyMonth(monthKey(month));
    $('results-count').textContent = `${scheduled.length} ${scheduled.length === 1 ? 'event' : 'events'} this month · ${undated.length} undated`;
    $('calendar-panel').hidden = view !== 'calendar';
    $('list-panel').hidden = view !== 'list';
    $('calendar-view').setAttribute('aria-pressed', String(view === 'calendar'));
    $('list-view').setAttribute('aria-pressed', String(view === 'list'));
    renderCalendar(scheduled);
    renderList(scheduled);
    $('radar-count').textContent = `${undated.length} watch items`;
    $('radar').innerHTML = undated.length ? undated.map(e => `<button class="radar-card ${priority(e)?'priority':''}" data-event="${escape(e.id)}"><div class="radar-top"><span>${escape(e.type)}</span>${coverage(e)}</div><h3>${escape(e.title)}</h3><p>${escape(e.importance)}</p><div class="radar-bottom"><span>Date unannounced</span><span>View brief ↗</span></div></button>`).join('') : '<p class="empty">No undated watch items match these filters.</p>';
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
      html += `<div class="day ${outside?'outside':''} ${key===today?'today':''} ${i%7>=5?'weekend':''}"><time class="day-number" datetime="${key}" ${key===today?'aria-current="date"':''}>${d.getUTCDate()}</time>${items.map(e=>`<button class="calendar-event ${escape(e.status)} ${priority(e)?'priority':''}" data-event="${escape(e.id)}">${priority(e)?'★ ':''}${escape(e.title)}<span>${escape(labels[e.status])} · ${escape(lifecycle(e))}${e.time?' · '+escape(e.time):''}</span></button>`).join('')}</div>`;
    }
    $('calendar').innerHTML = html;
    const estimates = events.filter(e=>e.window);
    $('month-estimates').hidden = estimates.length === 0;
    $('month-estimates').innerHTML = `<div class="estimate-heading">◷ Expected reporting windows <small>Month estimates only. Exact dates unverified.</small></div>${estimates.length ? `<div class="estimate-chips">${estimates.map(e=>`<button class="estimate-chip ${priority(e)?'priority':''}" data-event="${escape(e.id)}">${priority(e)?'★ ':''}${escape(e.companies.join(', '))}<span>Earnings · est.</span></button>`).join('')}</div>` : '<p class="empty">No estimated reporting windows match this month.</p>'}${!events.some(e=>e.date)?'<p class="calendar-note">No verified, dated events for this selection. Month estimates appear above, without an implied calendar day.</p>':''}`;
  }
  function renderList(events) {
    $('list-panel').innerHTML = events.length ? `<table class="list-table"><caption class="sr-only">Events for ${prettyMonth(monthKey(month))}</caption><thead><tr><th scope="col">Date / window</th><th scope="col">Event</th><th scope="col">Type</th><th scope="col">Date status</th></tr></thead><tbody>${events.map(e=>`<tr class="${priority(e)?'priority-row':''}"><td>${e.date?escape(prettyDay(e.date))+(e.endDate && e.endDate!==e.date?' – '+escape(prettyDay(e.endDate)):''):escape(prettyMonth(e.window))}<small>${escape(lifecycle(e))}${e.status==='estimated'?' · estimate, not confirmed':''}</small><small>${e.date?escape(e.time || 'Time not confirmed'):'Month only · day unknown'}</small></td><td><button class="event-name" data-event="${escape(e.id)}">${escape(e.title)}</button><small>${escape(e.companies.join(' · '))} ${coverage(e)}</small></td><td>${escape(e.type)}</td><td>${badge(e)}</td></tr>`).join('')}</tbody></table>` : '<p class="empty">No events match this month and these filters. Try another month or reset filters. Undated watch items appear below.</p>';
  }
  function showEvent(id) {
    const e = data.events.find(e => e.id === id);
    if (!e) return;
    const url = sourceURL(e.sourceUrl);
    $('event-detail').innerHTML = `${badge(e)} <span>${coverage(e)}</span><p class="event-lifecycle">${escape(lifecycle(e))}</p><h2>${escape(e.title)}</h2><p>${escape(e.importance)}</p>${stale(e)?'<p class="detail-note">Source check is more than 14 days old or unavailable. Recheck for schedule changes.</p>':''}<dl><dt>Companies</dt><dd>${escape(e.companies.map(id=>`${companies.get(id).name} (${id})`).join(', '))}</dd><dt>Date / window</dt><dd>${e.date?escape(prettyDay(e.date))+(e.endDate && e.endDate!==e.date?' – '+escape(prettyDay(e.endDate)):''):e.window?escape(prettyMonth(e.window))+' · month estimate only':'No verified date'}</dd><dt>Time</dt><dd>${escape(e.time || 'Not published / not verified')}</dd><dt>Source checked</dt><dd>${e.sourceCheckedAt?escape(new Date(e.sourceCheckedAt).toLocaleString('en-GB',{timeZone:'UTC'}))+' UTC':'Not checked'}</dd><dt>Official status</dt><dd>${e.status==='confirmed'?'Official announcement or participant schedule verified':e.status==='estimated'?'Unconfirmed estimate · source checked, date not announced':e.status==='reported'?'Media-reported date · primary confirmation not verified':'No date announced'}</dd><dt>Source</dt><dd>${escape(e.sourceLabel)}</dd></dl>${e.dateConflict?`<p class="conflict-note"><strong>Source discrepancy:</strong> ${escape(e.dateConflict)}</p>`:''}<p class="detail-note">${escape(e.basis)}</p><ul class="source-list">${(e.sources || []).map(src=>{const href=sourceURL(src.url);return href?`<li><a href="${escape(href)}" target="_blank" rel="noopener noreferrer">${escape(src.label)} ↗</a> <small>${escape(src.kind)}</small></li>`:'';}).join('')}</ul>${url?`<a class="source-link" href="${escape(url)}" target="_blank" rel="noopener noreferrer">Open source evidence ↗</a>`:''}<p>Events are maintained by the research team through Codex. Public visitors cannot add, edit or delete entries.</p>`;
    $('event-dialog').showModal();
  }
  document.addEventListener('click', event => {
    const trigger = event.target.closest('[data-event]');
    if (trigger) showEvent(trigger.dataset.event);
    if (event.target.closest('.close-dialog')) event.target.closest('dialog').close();
  });
  for (const id of ['methodology-button','footer-methodology']) $(id).addEventListener('click', ()=>$('methodology-dialog').showModal());
  for (const id of ['search','universe','type','status']) $(id).addEventListener(id==='search'?'input':'change',()=>{if(data) render();});
  for (const mode of ['calendar','list']) $(`${mode}-view`).addEventListener('click',()=>{view=mode;if(data)render();});
  for (const [id,delta] of [['prev-month',-1],['next-month',1]]) $(id).addEventListener('click',()=>{month=new Date(Date.UTC(month.getUTCFullYear(),month.getUTCMonth()+delta,1));if(data)render();});
  $('today-button').addEventListener('click',()=>{month=date(`${today.slice(0,7)}-01`);if(data)render();});
  $('clear-filters').addEventListener('click',()=>{$('search').value='';for(const id of ['universe','type','status'])$(id).value='all';if(data)render();});
  async function init() {
    try {
      const response = await fetch('data/events.json',{cache:'no-cache'});
      if(!response.ok) throw new Error('Dataset could not be loaded.');
      data=await response.json();
      companies=new Map(data.companies.map(c=>[c.id,c]));
      $('today-label').textContent = date(today).toLocaleDateString('en-GB',{weekday:'short',day:'numeric',month:'long',year:'numeric',timeZone:'UTC'})+' · HKT';
      $('universe-count').textContent=data.companies.length;
      $('confirmed-count').textContent=data.events.filter(e=>e.status==='confirmed').length;
      $('watch-count').textContent=data.events.filter(e=>['estimated','reported'].includes(e.status)).length;
      let sidebar='';
      for(const [label,filter] of [['SEMICONDUCTORS & HARDWARE',c=>c.sector!=='Software & cloud'],['SOFTWARE & CLOUD',c=>c.sector==='Software & cloud']]) {
        sidebar+=`<div class="coverage-sector">${label}</div>`;
        sidebar+=data.companies.filter(c=>c.coverage&&filter(c)).map(c=>`<div class="coverage-company"><span class="ticker">${escape(c.id)}</span><span>${escape(c.name)}</span><span class="coverage-star" aria-label="Priority coverage">★</span></div>`).join('');
      }
      $('coverage-list').innerHTML=sidebar;
      $('freshness').textContent=`Dataset reviewed: ${prettyDay(data.asOf)}. ${data.lastSuccessfulRefresh?'Last source review: '+prettyDay(data.lastSuccessfulRefresh.slice(0,10))+'.':'No successful source check yet.'} Published estimates are not company-confirmed.`;
      if(data.events.some(e=>e.status==='confirmed')) {
        $('data-notice').querySelector('strong').textContent='Official dates, published estimates & reported events';
        $('data-notice').querySelector('p').textContent='Estimated earnings dates are sourced from public calendars, not assumed reporting months. Reported events are labeled separately. Open a brief for sources, conflicts and last-check times.';
      }
      render();
    } catch(error) {
      $('calendar').innerHTML='<p class="loading-error">Unable to load events. Please reload or check the public dataset link below.</p>';
      $('freshness').textContent='Event data unavailable. No events have been verified by this session.';
      console.error(error);
    }
  }
  init();
})();
