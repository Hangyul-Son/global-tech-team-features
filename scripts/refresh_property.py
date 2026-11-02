#!/usr/bin/env python3
"""Refresh the public Hong Kong tracker without converting failures into fresh data.

Stdlib only. Default checkout layout:
  scripts/refresh_property.py
  scripts/property_trends.py
  scripts/property_listings.py
  hong-kong-property/{data,trends,listings,refresh-status}.json

Run --offline-check for deterministic parser/failure-guard checks, or
--site-dir PATH --skip-listings to validate smaller live sources without recrawling
sale advertisements. Normal unattended runs refresh every supported component.
Estate 90-day snapshots remain dated source observations until separately verified.
"""
import argparse,copy,csv,datetime,importlib.util,io,json,math,os,pathlib,re,subprocess,sys,tempfile,urllib.request,xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo
UTC=datetime.timezone.utc
FX_URL='https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml'
RVD_URLS={'price':'https://www.rvd.gov.hk/datagovhk/1.4M.csv','rent':'https://www.rvd.gov.hk/datagovhk/1.3M.csv'}
RVD_KEYS={'price':['price','priceA','priceB'],'rent':['rent','rentA','rentB']}

def now_iso():return datetime.datetime.now(UTC).isoformat(timespec='seconds')
def today_hk():return datetime.datetime.now(ZoneInfo('Asia/Hong_Kong')).date()
def load_json(path,default=None):
    try:return json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
    except (FileNotFoundError,json.JSONDecodeError):return copy.deepcopy(default)
def atomic_json(path,value):
    path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,prefix='.'+path.name+'.',suffix='.tmp',delete=False) as f:
        temp=f.name;json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temp,path)
def download(url):
    request=urllib.request.Request(url,headers={'User-Agent':'HomeLensHK/1.0 (+public property-data research; weekly refresh)','Accept':'application/xml,text/csv,text/html;q=0.8,*/*;q=0.5'})
    with urllib.request.urlopen(request,timeout=35) as response:
        if response.status!=200:raise ValueError('HTTP '+str(response.status))
        return response.read()
def finite_positive(value):return isinstance(value,(int,float)) and math.isfinite(value) and value>0

def parse_ecb(raw,old=None,checked=None):
    root=ET.fromstring(raw);points=[]
    for element in root.iter():
        if element.attrib.get('time'):
            rates={child.attrib.get('currency'):float(child.attrib['rate']) for child in element if child.attrib.get('currency') in {'HKD','KRW'} and child.attrib.get('rate')}
            if set(rates)=={'HKD','KRW'}:points.append((element.attrib['time'],rates))
    if not points:raise ValueError('ECB same-day HKD/KRW rate pair absent')
    date,rates=max(points,key=lambda p:p[0]);parsed_date=datetime.date.fromisoformat(date)
    if parsed_date>today_hk():raise ValueError('ECB reference date is in the future')
    if old and old.get('date','')>date:raise ValueError('ECB source older than last-good reference date')
    if not all(finite_positive(v) for v in rates.values()):raise ValueError('ECB rate must be finite and positive')
    result=copy.deepcopy(old or {})
    result.update({'base':'HKD','quote':'KRW','hkdToKrw':rates['KRW']/rates['HKD'],'date':date,'retrievedAt':checked or now_iso(),'sourceName':'ECB reference rate','source':FX_URL,'referencePage':'https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html','method':'Cross rate = ECB KRW per EUR / ECB HKD per EUR from the same published day. Full ratio retained; display rounds to 2 decimals.','eurHkd':rates['HKD'],'eurKrw':rates['KRW'],'isIndicative':True})
    result.setdefault('notes',['Reference rate, not a bank or remittance quote; excludes spreads and fees.','Currency conversions do not change the underlying HKD property prices or yields.','An unchanged HKD price can have a different KRW equivalent when FX moves.','Reference dates may precede retrieval on weekends and public holidays.'])
    return result

def parse_rvd_csv(raw,kind):
    rows=list(csv.reader(io.StringIO(raw.decode('utf-8-sig'))));header_index=next((i for i,r in enumerate(rows) if r and r[0].strip()=='Month' and 'All Classes' in r),None)
    if header_index is None:raise ValueError('RVD CSV Month/All Classes header absent')
    header=[x.strip() for x in rows[header_index]];output=[]
    def value(row,column):
        index=header.index(column)
        try:v=float(row[index].strip())
        except (IndexError,ValueError):raise ValueError('Missing/non-numeric RVD '+column)
        if not finite_positive(v):raise ValueError('Invalid RVD '+column)
        remark_index=header.index(column+' - Remarks') if column+' - Remarks' in header else None
        remark=row[remark_index].strip() if remark_index is not None and remark_index<len(row) else ''
        return v,remark
    for row in rows[header_index+1:]:
        if not row or not re.fullmatch(r'\d{2}-\d{4}',row[0].strip()):continue
        month,year=map(int,row[0].strip().split('-'))
        if year<2020:continue
        date=datetime.date(year,month,1)
        if date>today_hk():raise ValueError('RVD observation month is in the future')
        all_value,all_remark=value(row,'All Classes');a,a_remark=value(row,'Class A');b,b_remark=value(row,'Class B')
        output.append({'date':date.strftime('%Y-%m'),kind:all_value,kind+'A':a,kind+'B':b,'provisional':any([all_remark,a_remark,b_remark])})
    output.sort(key=lambda r:r['date'])
    if len({r['date'] for r in output})!=len(output):raise ValueError('Duplicate RVD monthly observations')
    if not output:raise ValueError('RVD recent monthly series empty')
    return output

def source_rows_from_combined(indices,kind):
    saved=indices.get('sourceMonthly',{}).get(kind)
    if saved:return copy.deepcopy(saved)
    return [{'date':r['date'],**{k:r[k] for k in RVD_KEYS[kind] if k in r},'provisional':bool(r.get(kind+'Provisional',r.get('provisional',False)))} for r in indices.get('monthly',[]) if all(finite_positive(r.get(k)) for k in RVD_KEYS[kind])]

def merge_rvd(indices,sources,checked,success_kinds):
    result=copy.deepcopy(indices);maps={kind:{r['date']:r for r in rows} for kind,rows in sources.items()};common=sorted(set(maps['price'])&set(maps['rent']));combined=[]
    for date in common:
        p,r=maps['price'][date],maps['rent'][date]
        combined.append({'date':date,**{k:p[k] for k in RVD_KEYS['price']},**{k:r[k] for k in RVD_KEYS['rent']},'provisional':bool(p.get('provisional') or r.get('provisional')),'priceProvisional':bool(p.get('provisional')),'rentProvisional':bool(r.get('provisional'))})
    if not combined:raise ValueError('No common RVD price/rent months after merge')
    result['monthly']=combined;result['sourceMonthly']=sources;result['latestIndexPeriod']=combined[-1]['date'];result.setdefault('retrievalBySource',{})
    for kind in success_kinds:result['retrievalBySource'][kind+'Monthly']={'retrievedAt':checked,'source':RVD_URLS[kind],'latestPeriod':sources[kind][-1]['date']}
    if set(success_kinds)=={'price','rent'}:result['retrievedAt']=checked
    # An HTTP fetch date is not a publication date. Preserve sourceUpdatedAt until known.
    metrics={}
    if len(combined)>=13:
        latest,prior,yoy=combined[-1],combined[-2],combined[-13]
        december=next((r for r in combined if r['date']==str(int(latest['date'][:4])-1)+'-12'),None)
        for key in RVD_KEYS['price']+RVD_KEYS['rent']:
            metric={'latest':latest[key],'mom':round((latest[key]/prior[key]-1)*100,3),'yoy':round((latest[key]/yoy[key]-1)*100,3)}
            if december:metric['ytd']=round((latest[key]/december[key]-1)*100,3)
            metrics[key]=metric
        result['metrics']=metrics
    return result

def merge_listings(previous,candidate,checked):
    """Accept complete region refreshes; retain dated baselines after incomplete ones."""
    previous=copy.deepcopy(previous or {});candidate=copy.deepcopy(candidate or {})
    old_regions={r['id']:r for r in previous.get('regions',[])};new_regions={r['id']:r for r in candidate.get('regions',[])}
    order=list(old_regions)+[key for key in new_regions if key not in old_regions]
    result={k:v for k,v in candidate.items() if k not in {'regions','listings','errors'}}
    result.setdefault('provider',previous.get('provider','28Hse'));result.setdefault('coverage',previous.get('coverage','One provider; defined search districts, not all Hong Kong properties.'))
    result['regions']=[];result['listings']=[];result['errors']=[];result['attemptedAt']=checked;accepted=[];retained=[]
    for region_id in order:
        old=old_regions.get(region_id);new=new_regions.get(region_id)
        old_rows=[r for r in previous.get('listings',[]) if r.get('focusRegion')==region_id]
        new_rows=[r for r in candidate.get('listings',[]) if r.get('focusRegion')==region_id]
        complete=bool(new and new.get('allExpectedPagesFetched') and not new.get('error') and new_rows)
        if complete:
            selected=new;rows=new_rows;accepted.append(region_id);selected['refreshStatus']='complete-source-pagination';selected['lastSuccessfulCheckAt']=new.get('checkedAt',checked)
        elif old_rows:
            selected=copy.deepcopy(old);rows=old_rows;retained.append(region_id);selected['refreshStatus']='retained_after_incomplete_refresh';selected['lastAttemptAt']=checked;selected['lastAttemptError']=(new or {}).get('error') or 'Source pagination incomplete or no valid advertised rows; last-known region retained.'
            selected['allExpectedPagesFetched']=False;result['errors'].append({'region':region_id,'error':selected['lastAttemptError'],'retainedCheckedAt':selected.get('checkedAt')})
        else:
            selected=new or old or {'id':region_id};rows=new_rows;selected['refreshStatus']='partial_initial_capture';selected['lastAttemptAt']=checked
            selected['allExpectedPagesFetched']=False;result['errors'].append({'region':region_id,'error':selected.get('error') or 'No complete baseline; only observed subset retained.'})
        selected['capturedAds']=len(rows);selected['targetFitCount']=sum(bool(r.get('targetFit')) for r in rows)
        result['regions'].append(selected);result['listings'].extend(rows)
    if not order:raise ValueError('No listing-region metadata in candidate or baseline')
    if not result['listings']:raise ValueError('No observed advertisements or last-good baseline; refusing to publish a false empty inventory')
    # A partial attempt is not a new successful inventory check.
    all_good=len(accepted)==len(order)
    result['refreshStatus']='complete-source-pagination' if all_good else 'partial-previous-data-retained'
    result['checkedAt']=candidate.get('checkedAt',checked) if all_good or not previous.get('checkedAt') else previous['checkedAt']
    result['lastFullSuccessfulAt']=result['checkedAt'] if all_good else previous.get('lastFullSuccessfulAt',previous.get('checkedAt') if previous.get('regions') and all(r.get('allExpectedPagesFetched') for r in previous['regions']) else None)
    return result,accepted,retained

def inventory_summary(current):
    rows=current.get('listings',[])
    known=bool(rows) or bool(current.get('regions')) and all(r.get('allExpectedPagesFetched') for r in current.get('regions',[]))
    return {'totalAdvertisedRows':len(rows) if known else None,'observedRows':len(rows),'inventoryKnown':known,'targetFitCount':sum(bool(r.get('targetFit')) for r in rows) if known else None,'provider':'28Hse','deduplication':'Provider advertisement id, not necessarily unique physical flats.','byRegion':[{'id':r['id'],'label':r.get('label',r['id']),'count':sum(x.get('focusRegion')==r['id'] for x in rows) if any(x.get('focusRegion')==r['id'] for x in rows) or r.get('allExpectedPagesFetched') else None,'targetFitCount':sum(x.get('focusRegion')==r['id'] and bool(x.get('targetFit')) for x in rows),'checkedAt':r.get('checkedAt'),'lastSuccessfulCheckAt':r.get('lastSuccessfulCheckAt'),'refreshStatus':r.get('refreshStatus'),'allExpectedPagesFetched':bool(r.get('allExpectedPagesFetched')),'reportedAdvertCount':r.get('reportedAdvertCount')} for r in current.get('regions',[])]}

def listing_changes(previous,current,accepted):
    result={'baselineAvailable':bool(previous and previous.get('listings')),'comparedRegions':[],'newIdsCount':0,'removedIdsCount':0,'priceChangedIdsCount':0,'new':[],'removed':[],'priceChanges':[],'interpretation':'Changes compare provider advertisement ids only after complete source pagination. Removed means no longer observed on this provider, not proof sold, withdrawn, or unavailable. Duplicate agent ads may represent the same physical flat.'}
    old_regions={r.get('id') for r in (previous or {}).get('regions',[])}
    for region_id in accepted:
        if region_id not in old_regions:continue
        old={r['id']:r for r in (previous or {}).get('listings',[]) if r.get('focusRegion')==region_id};new={r['id']:r for r in current.get('listings',[]) if r.get('focusRegion')==region_id}
        if not old:continue
        result['comparedRegions'].append(region_id)
        for key in sorted(set(new)-set(old)):result['new'].append({k:new[key].get(k) for k in ['id','focusRegion','estate','location','askingHkd','saleableSqft','bedrooms','url']})
        for key in sorted(set(old)-set(new)):result['removed'].append({k:old[key].get(k) for k in ['id','focusRegion','estate','location','askingHkd','url']})
        for key in sorted(set(old)&set(new)):
            a,b=old[key].get('askingHkd'),new[key].get('askingHkd')
            if finite_positive(a) and finite_positive(b) and a!=b:result['priceChanges'].append({'id':key,'focusRegion':region_id,'estate':new[key].get('estate'),'url':new[key].get('url'),'oldAskingHkd':a,'newAskingHkd':b,'changeHkd':b-a,'changePct':round((b/a-1)*100,4)})
    result.update({'newIdsCount':len(result['new']),'removedIdsCount':len(result['removed']),'priceChangedIdsCount':len(result['priceChanges'])})
    return result

def import_helper(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    if not spec or not spec.loader:raise ValueError('Unable to load helper '+str(path))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def offline_check():
    checked='2026-11-02T00:00:00+00:00';old_fx={'date':'2026-10-29','retrievedAt':'old'}
    xml=b'<Envelope><Cube><Cube time="2026-10-30"><Cube currency="HKD" rate="8"/><Cube currency="KRW" rate="1400"/></Cube></Cube></Envelope>'
    fx=parse_ecb(xml,old_fx,checked);assert fx['hkdToKrw']==175 and fx['date']=='2026-10-30'
    try:parse_ecb(b'<error/>',old_fx,checked)
    except ValueError:pass
    else:raise AssertionError('Malformed FX accepted')
    header='Month,Class A,Class A - Remarks,Class B,Class B - Remarks,All Classes,All Classes - Remarks\n'
    raw=('title,,,,,,\n'+header+'09-2026,321,P,301,,310,P\n').encode();p=parse_rvd_csv(raw,'price');assert p[0]['price']==310 and p[0]['provisional']
    raw2=('title,,,,,,\n'+header+'09-2026,220,,210,,215,\n10-2026,225,,215,,220,\n').encode();r=parse_rvd_csv(raw2,'rent')
    combined=merge_rvd({'monthly':[]},{'price':p,'rent':r},checked,['price','rent']);assert len(combined['monthly'])==1 and combined['latestIndexPeriod']=='2026-09';assert combined['sourceMonthly']['rent'][-1]['date']=='2026-10'
    old={'checkedAt':'old','regions':[{'id':'a','checkedAt':'old','allExpectedPagesFetched':True}],'listings':[{'id':'a1','focusRegion':'a','askingHkd':100,'checkedAt':'old'}]}
    failed={'checkedAt':checked,'regions':[{'id':'a','checkedAt':checked,'allExpectedPagesFetched':False,'error':'simulated source failure'}],'listings':[]}
    kept,accepted,retained=merge_listings(old,failed,checked);assert kept['listings']==old['listings'] and kept['checkedAt']=='old' and accepted==[] and retained==['a'];assert listing_changes(old,kept,accepted)['removedIdsCount']==0
    fresh={'checkedAt':checked,'regions':[{'id':'a','checkedAt':checked,'allExpectedPagesFetched':True}],'listings':[{'id':'a1','focusRegion':'a','askingHkd':90},{'id':'a2','focusRegion':'a','askingHkd':200}]}
    updated,accepted,_=merge_listings(old,fresh,checked);diff=listing_changes(old,updated,accepted);assert diff['newIdsCount']==1 and diff['priceChangedIdsCount']==1 and diff['priceChanges'][0]['changePct']==-10
    with tempfile.TemporaryDirectory() as temp:
        path=pathlib.Path(temp)/'status.json';atomic_json(path,{'ok':True});assert load_json(path)['ok'];assert len(list(path.parent.iterdir()))==1
    assert inventory_summary({})['totalAdvertisedRows'] is None
    print('Offline checks passed: FX cross/date; CSV remarks; asynchronous RVD periods; no false empty/removed inventory; changes; atomic writes.',flush=True)

def main():
    script=pathlib.Path(__file__).resolve();repo=script.parent.parent if script.parent.name=='scripts' else script.parent
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--site-dir',type=pathlib.Path,default=repo/'hong-kong-property');ap.add_argument('--helper-dir',type=pathlib.Path,default=repo/'scripts');ap.add_argument('--skip-listings',action='store_true');ap.add_argument('--skip-trends',action='store_true');ap.add_argument('--offline-check',action='store_true');args=ap.parse_args()
    if args.offline_check:offline_check();return 0
    site=args.site_dir.resolve();data_path=site/'data.json';data=load_json(data_path)
    if not isinstance(data,dict) or not data.get('estates'):raise SystemExit('Missing or invalid site data.json: '+str(data_path))
    checked=now_iso();prior_status=load_json(site/'refresh-status.json',{});status={'attemptedAt':checked,'timezone':'Asia/Hong_Kong','successes':[],'errors':[],'components':{},'runStatus':'running'}
    def success(name,**details):status['components'][name]={'status':'updated','lastSuccessfulAt':checked,**details};status['successes'].append({'component':name,**details})
    def failure(name,error,old_date=None,**details):status['components'][name]={'status':'retained_after_error','lastSuccessfulAt':prior_status.get('components',{}).get(name,{}).get('lastSuccessfulAt',old_date),'error':str(error),**details};status['errors'].append({'component':name,'error':str(error)})
    # FX: no conversion fallback is guessed if the reference service fails.
    try:
        data['fx']=parse_ecb(download(FX_URL),data.get('fx'),checked);success('fx',referenceDate=data['fx']['date'],source=FX_URL)
    except Exception as err:failure('fx',err,(data.get('fx') or {}).get('retrievedAt'),referenceDate=(data.get('fx') or {}).get('date'))
    # Refresh each official source independently, retaining last-good arrays/dates.
    indices=data.setdefault('indices',{});sources={kind:source_rows_from_combined(indices,kind) for kind in ['price','rent']};rvd_ok=[]
    for kind,url in RVD_URLS.items():
        try:
            rows=parse_rvd_csv(download(url),kind)
            if len(rows)<60:raise ValueError('RVD response has fewer than 60 monthly observations since 2020')
            if sources[kind] and rows[-1]['date']<sources[kind][-1]['date']:raise ValueError('RVD response is older than last-good series')
            sources[kind]=rows;rvd_ok.append(kind);success('rvd_'+kind,latestPeriod=rows[-1]['date'],observations=len(rows),source=url)
        except Exception as err:failure('rvd_'+kind,err,indices.get('retrievalBySource',{}).get(kind+'Monthly',{}).get('retrievedAt',indices.get('retrievedAt')),latestPeriod=sources[kind][-1]['date'] if sources[kind] else None,source=url)
    if rvd_ok:
        try:data['indices']=merge_rvd(indices,sources,checked,rvd_ok)
        except Exception as err:status['errors'].append({'component':'rvd_merge','error':str(err)})
    # Quarterly histories: helper keeps per-estate old observations after failure.
    if args.skip_trends:status['components']['trends']={'status':'skipped','lastSuccessfulAt':prior_status.get('components',{}).get('trends',{}).get('lastSuccessfulAt')}
    else:
        previous=load_json(site/'trends.json',{})
        try:
            helper=import_helper(args.helper_dir/'property_trends.py','home_lens_property_trends');trends=helper.refresh_trends(data,previous)
            if not trends.get('estates'):raise ValueError('No valid quarterly estate histories returned')
            atomic_json(site/'trends.json',trends)
            if trends.get('errors'):
                status['components']['trends']={'status':'partial','lastSuccessfulAt':prior_status.get('components',{}).get('trends',{}).get('lastSuccessfulAt',previous.get('retrievedAt')),'estates':len(trends['estates']),'perEstateErrors':trends['errors']};status['errors'].extend({'component':'trends','error':e} for e in trends['errors'])
            else:success('trends',estates=len(trends['estates']))
        except Exception as err:failure('trends',err,previous.get('retrievedAt'))
    # Sale ads: stage in a temporary baseline-seeded file; only publish validated output.
    old_listings=load_json(site/'listings.json',{});listings=old_listings;accepted=[]
    if args.skip_listings:status['components']['listings']={'status':'skipped','lastSuccessfulAt':old_listings.get('lastFullSuccessfulAt',old_listings.get('checkedAt'))}
    else:
        stage=None
        try:
            with tempfile.NamedTemporaryFile('w',encoding='utf-8',suffix='.json',delete=False) as temp:stage=pathlib.Path(temp.name);json.dump(old_listings,temp,ensure_ascii=False)
            command=[sys.executable,str(args.helper_dir/'property_listings.py'),'--output',str(stage),'--delay','0.6','--max-pages','200']
            collected=subprocess.run(command,text=True,capture_output=True,timeout=1800)
            candidate=load_json(stage)
            if candidate==old_listings:raise ValueError('Listing collector did not replace its baseline; no successful check can be recorded')
            if not isinstance(candidate,dict) or not candidate.get('regions'):raise ValueError('Listing collector produced no region metadata: '+collected.stderr[-400:])
            listings,accepted,retained=merge_listings(old_listings,candidate,checked)
            atomic_json(site/'listings.json',listings)
            if listings.get('errors'):
                status['components']['listings']={'status':'partial','lastSuccessfulAt':listings.get('lastFullSuccessfulAt'),'acceptedRegions':accepted,'retainedRegions':retained,'perRegionErrors':listings['errors']};status['errors'].extend({'component':'listings','error':e} for e in listings['errors'])
            else:success('listings',regions=accepted,advertisements=len(listings.get('listings',[])))
            if collected.returncode:status['errors'].append({'component':'listing_collector_process','error':'Collector exited '+str(collected.returncode)+'; validated output used with region-level guards.'})
        except Exception as err:failure('listings',err,old_listings.get('lastFullSuccessfulAt',old_listings.get('checkedAt')))
        finally:
            if stage:
                try:stage.unlink()
                except FileNotFoundError:pass
    status['inventory']=inventory_summary(listings);status['listingChanges']=listing_changes(old_listings,listings,accepted)
    estate_dates=sorted({e.get('date') for e in data['estates'] if e.get('date')})
    status['components']['estateSnapshots']={'status':'retained_original_observations','oldestObservationDate':estate_dates[0] if estate_dates else None,'latestObservationDate':estate_dates[-1] if estate_dates else None,'estates':len(data['estates']),'note':'Estate-wide 90-day sale/rent snapshots and illustrative unit examples are not silently refreshed. Their original observation/source dates remain authoritative. Quarterly history, advertised sale inventory, FX and official monthly indices have separate refresh status.'}
    status['runStatus']='partial' if status['errors'] and status['successes'] else 'failed' if status['errors'] else 'success';status['finishedAt']=now_iso()
    if status['runStatus']=='success' and not args.skip_listings and not args.skip_trends:status['lastFullSuccessfulAt']=status['finishedAt']
    else:status['lastFullSuccessfulAt']=prior_status.get('lastFullSuccessfulAt')
    data['refreshMetadata']={'attemptedAt':checked,'statusFile':'refresh-status.json','runStatus':status['runStatus'],'note':'Read per-component and per-region dates; an attempted run is not proof every dataset refreshed.'}
    atomic_json(data_path,data);atomic_json(site/'refresh-status.json',status)
    print(json.dumps({'runStatus':status['runStatus'],'successes':[x['component'] for x in status['successes']],'errors':len(status['errors']),'advertisements':status['inventory']['totalAdvertisedRows'],'changes':{k:status['listingChanges'][k] for k in ['newIdsCount','removedIdsCount','priceChangedIdsCount']}},ensure_ascii=False),flush=True)
    # Partial data remains deployable with explicit status; workflow can notify from JSON.
    return 0 if status['runStatus']!='failed' else 1
if __name__=='__main__':raise SystemExit(main())
