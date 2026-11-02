/* Home Lens display preferences. Storage/data amounts remain HKD and saleable sq ft. */
(function(global){
  'use strict';
  const SQFT_PER_SQM=1/0.09290304;
  const SQM_PER_PYEONG=400/121;
  const SQFT_PER_PYEONG=SQM_PER_PYEONG*SQFT_PER_SQM;
  const STORE_KEY='homeLensDisplayPreferences';
  const currencies=['HKD','KRW','dual'], areas=['sqft','sqm','pyeong','all'];
  let prefs={currency:'dual',area:'all'}, fx=null, onChange=()=>{};
  try{const saved=JSON.parse(localStorage.getItem(STORE_KEY)||'null');if(saved&&currencies.includes(saved.currency))prefs.currency=saved.currency;if(saved&&areas.includes(saved.area))prefs.area=saved.area}catch{}
  const fmt=(n,d=0)=>new Intl.NumberFormat('en-HK',{maximumFractionDigits:d,minimumFractionDigits:d}).format(n);
  const finite=n=>n!==null&&n!==undefined&&n!==''&&Number.isFinite(Number(n));
  const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const rate=()=>fx&&Number.isFinite(+fx.hkdToKrw)&&+fx.hkdToKrw>0?+fx.hkdToKrw:null;
  function hkdText(value,compact){const sign=value<0?'-':'';const n=Math.abs(value);return sign+'HK$'+(compact&&n>=1e6?fmt(n/1e6,2)+'m':fmt(n,0))}
  function krwText(value,compact){const sign=value<0?'-':'';const n=Math.abs(value);if(compact&&n>=1e8)return sign+'₩'+fmt(n/1e8,2)+'억';if(compact&&n>=1e4)return sign+'₩'+fmt(n/1e4,n>=1e6?0:1)+'만';return sign+'₩'+fmt(n,0)}
  function formatMoney(hkd,compact=false){if(!finite(hkd))return '—';const n=Number(hkd),h=hkdText(n,compact),r=rate();if(prefs.currency==='HKD')return h;if(!r)return prefs.currency==='KRW'?'KRW unavailable':h+' · KRW unavailable';const k=krwText(n*r,compact);return prefs.currency==='KRW'?k:h+' · '+k}
  function formatMapMoney(hkd){if(!finite(hkd))return '—';const r=rate();return prefs.currency==='HKD'||!r?hkdText(Number(hkd),true):krwText(Number(hkd)*r,true)}
  function selectedArea(){return prefs.area==='all'?'sqft':prefs.area}
  function areaFromSqft(sqft,unit=selectedArea()){if(!finite(sqft))return NaN;return Number(sqft)/(unit==='sqm'?SQFT_PER_SQM:unit==='pyeong'?SQFT_PER_PYEONG:1)}
  function areaToSqft(amount,unit=selectedArea()){if(!finite(amount))return NaN;return Number(amount)*(unit==='sqm'?SQFT_PER_SQM:unit==='pyeong'?SQFT_PER_PYEONG:1)}
  function areaLabel(unit=selectedArea()){return unit==='sqm'?'m²':unit==='pyeong'?'평':'sq ft'}
  function oneArea(sqft,unit){const n=areaFromSqft(sqft,unit);return fmt(n,unit==='sqft'?(Number.isInteger(n)?0:1):1)+(unit==='pyeong'?'평':' '+areaLabel(unit))}
  function formatArea(sqft,withAll=false){if(!finite(sqft))return '—';if(withAll||prefs.area==='all')return ['sqft','sqm','pyeong'].map(unit=>oneArea(sqft,unit)).join(' · ');return oneArea(sqft,prefs.area)}
  function formatAreaCompact(sqft){return finite(sqft)?oneArea(Number(sqft),selectedArea()):'—'}
  function formatPerArea(hkdPerSqft,monthly=false){if(!finite(hkdPerSqft))return '—';const unit=selectedArea(),mult=unit==='sqm'?SQFT_PER_SQM:unit==='pyeong'?SQFT_PER_PYEONG:1;return formatMoney(Number(hkdPerSqft)*mult,false)+' / '+areaLabel(unit)+(monthly?' / month':'')}
  function getDisplayPreferences(){return {...prefs,fx:fx?{...fx}:null}}
  function save(){try{localStorage.setItem(STORE_KEY,JSON.stringify(prefs))}catch{}}
  function refreshPreferenceNote(){const note=document.getElementById('displayFxNote');if(!note)return;const r=rate();if(!r){note.textContent='KRW conversion unavailable until a dated exchange rate is verified. Original prices are in HKD.';return}note.innerHTML=`<a href="${escape(fx.source||'https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html')}" target="_blank" rel="noopener noreferrer">1 HKD ≈ ₩${fmt(r,2)} · ${escape(fx.date)} · ${escape(fx.sourceName||'ECB reference rate')}</a><span>Indicative conversion; bank spreads and fees excluded. 1평 = 3.305785 m².</span>`}
  function setDisplayPreferences(next={}){if(currencies.includes(next.currency))prefs.currency=next.currency;if(areas.includes(next.area))prefs.area=next.area;save();const currencySelect=document.getElementById('displayCurrency'),areaSelect=document.getElementById('displayArea');if(currencySelect)currencySelect.value=prefs.currency;if(areaSelect)areaSelect.value=prefs.area;refreshPreferenceNote();onChange(getDisplayPreferences());global.dispatchEvent(new CustomEvent('homelens:displaychange',{detail:getDisplayPreferences()}));return getDisplayPreferences()}
  function initDisplayPreferences(options={}){fx=options.fx||null;onChange=typeof options.onChange==='function'?options.onChange:()=>{};const container=document.getElementById('displayPreferences');if(container){container.classList.add('display-preferences');container.innerHTML=`<div class="display-pref-controls"><label for="displayCurrency">Currency<select id="displayCurrency"><option value="dual">HKD + 원 KRW</option><option value="HKD">HKD · Hong Kong dollar</option><option value="KRW">원 KRW · Korean won</option></select></label><label for="displayArea">Area<select id="displayArea"><option value="all">sq ft + m² + 평</option><option value="sqft">Square feet · sq ft</option><option value="sqm">Square metres · m²</option><option value="pyeong">평 · pyeong</option></select></label></div><p class="display-fx-note" id="displayFxNote"></p>`;document.getElementById('displayCurrency').value=prefs.currency;document.getElementById('displayArea').value=prefs.area;document.getElementById('displayCurrency').addEventListener('change',e=>setDisplayPreferences({currency:e.target.value}));document.getElementById('displayArea').addEventListener('change',e=>setDisplayPreferences({area:e.target.value}));refreshPreferenceNote()}return getDisplayPreferences()}
  Object.assign(global,{formatMoney,formatMapMoney,formatArea,formatAreaCompact,formatPerArea,areaFromSqft,areaToSqft,areaLabel,getDisplayPreferences,setDisplayPreferences,initDisplayPreferences,HOME_LENS_AREA_UNITS:Object.freeze({SQFT_PER_SQM,SQM_PER_PYEONG,SQFT_PER_PYEONG})});
})(window);
