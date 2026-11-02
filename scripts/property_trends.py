#!/usr/bin/env python3
"""Fetch public 28Hse estate quarterly Sold Price Trend chart arrays.
No browser execution, authentication, hidden APIs, interpolation, or guessed prices.
Usage: python fetch-estate-trends.py [data.json] [output.json]
Output stores observed source chart labels and quarter interpretation separately.
"""
import concurrent.futures,datetime,hashlib,json,re,sys,urllib.request
from zoneinfo import ZoneInfo
SOURCE_DATA=sys.argv[1] if len(sys.argv)>1 else '/workspace/sites/hong-kong-home-lens/dist/data.json'
OUTPUT=sys.argv[2] if len(sys.argv)>2 else '/workspace/focus-trends.json'
NOW=datetime.datetime.now(ZoneInfo('Asia/Hong_Kong'))
TODAY=NOW.date();CURRENT_Q=(TODAY.month-1)//3+1

def extract_series(html):
    m=re.search(r"labels_estate_deal_q_(\d+)\.push\('([0-9]{4}-[0-9]{2})'\)",html)
    if not m:raise ValueError('No estate quarterly chart labels found')
    chart_id=m.group(1)
    labels=re.findall(r"labels_estate_deal_q_"+chart_id+r"\.push\('([0-9]{4}-[0-9]{2})'\)",html)
    start=html.find('const data_estate_deal_q_'+chart_id)
    end=html.find('const marketEvents_estate_deal_q_'+chart_id,start)
    body=html[start:end]
    def dataset(label):
        found=re.search(r"label:\s*['\"]"+re.escape(label)+r"['\"]\s*,[\s\S]*?data:\s*\[([^\]]*)\]",body)
        if not found:raise ValueError('Missing chart dataset '+label)
        raw=re.sub(r'//[^\n]*','',found.group(1)).strip()
        raw=re.sub(r',\s*$','',raw)
        if re.search(r'[^0-9.,\snull\-]',raw):raise ValueError('Unexpected chart array syntax')
        values=json.loads('['+raw+']')
        if len(values)!=len(labels):raise ValueError('Mismatched chart labels and '+label)
        return values
    prices=dataset('AVG Price');volumes=dataset('Volume');hk=dataset('All HK')
    rows=[]
    for date,price,n,allhk in zip(labels,prices,volumes,hk):
        year,month=map(int,date.split('-'));quarter=(month-1)//3+1
        if year<2020 or (year,quarter)>(TODAY.year,CURRENT_Q):continue
        if price is not None and (not isinstance(price,(int,float)) or not 0<=price<=200000):raise ValueError('Out-of-range price')
        if n is not None and (not isinstance(n,(int,float)) or n<0):raise ValueError('Invalid volume')
        start=datetime.date(year,3*(quarter-1)+1,1)
        next_start=datetime.date(year+1,1,1) if quarter==4 else datetime.date(year,3*quarter+1,1)
        end=next_start-datetime.timedelta(days=1)
        partial=end>=TODAY
        rows.append({'period':f'{year}-Q{quarter}','year':year,'quarter':quarter,'sourceLabel':date,'periodStart':str(start),'periodEnd':str(end),'salePsf':price,'transactions':n,'providerHongKongSalePsf':allhk,'partial':partial,'sampleCaution':n is None or n<10})
    if not rows:raise ValueError('No recent chart observations')
    return rows

def get_estate(e):
    url=e['source'];request=urllib.request.Request(url,headers={'User-Agent':'HomeLensResearch/1.0 (+public estate price chart comparison)'})
    with urllib.request.urlopen(request,timeout=35) as response:
        raw=response.read();meta={'httpDate':response.headers.get('Date'),'lastModified':response.headers.get('Last-Modified')}
    html=raw.decode('utf-8','replace');rows=extract_series(html)
    completed=[r for r in rows if not r['partial']]
    latest=completed[-1] if completed else None
    baseline=next((r for r in rows if latest and r['year']==latest['year']-5 and r['quarter']==latest['quarter']),None)
    change=(latest['salePsf']/baseline['salePsf']-1)*100 if latest and baseline and latest['salePsf'] and baseline['salePsf'] else None
    comparable=bool(latest and baseline and not latest['sampleCaution'] and not baseline['sampleCaution'])
    return {'id':e['id'],'neighborhood':e['neighborhood'],'estate':e['estate'],'source':url,'provider':'28Hse','retrievedAt':NOW.isoformat(timespec='seconds'),'sourceChartTitle':e['estate']+' Sold Price Trend','frequency':'quarterly','unit':'HKD per saleable square foot','scope':'Estate-wide all unit sizes; provider chart series, not a neighbourhood or official RVD index. Not filtered to two-bedroom 400–600 sq ft flats.','rows':rows,'rentalHistory':{'available':False,'reason':'The public estate chart exposes sale-price and transaction-volume arrays; no comparable estate rental history was found. Do not substitute Hong Kong rental indices as a local rental trend.'},'latestCompletedPeriod':latest['period'] if latest else None,'fiveYearChangePct':round(change,4) if change is not None and comparable else None,'fiveYearChangeRawPct':round(change,4) if change is not None else None,'fiveYearComparisonReliable':comparable,'fiveYearComparisonCaution':None if comparable else 'Insufficient source transaction sample in the baseline or latest completed quarter; comparison withheld.','fiveYearChangeStart':baseline['period'] if baseline else None,'fiveYearChangeEnd':latest['period'] if latest else None,'sourceHtmlSha256':hashlib.sha256(raw).hexdigest(),'http':meta}

def refresh_trends(data,previous=None):
    """Return current series, retaining dated last-good rows on individual failures.

    `data` is either the tracker data object or its estates list. `previous` is
    this function's prior output, if available. No failure is marked refreshed.
    """
    estates=data['estates'] if isinstance(data,dict) else data
    old={e['id']:e for e in (previous or {}).get('estates',[])}
    out=[];errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(get_estate,e):e for e in estates}
        for future in concurrent.futures.as_completed(futures):
            e=futures[future]
            try:
                result=future.result();prior=old.get(e['id']);
                if prior and max((r['period'] for r in result['rows']),default='')<max((r['period'] for r in prior.get('rows',[])),default=''):raise ValueError('Historical source rolled back to an older period; retaining last-good series')
                result['fetchStatus']='ok';result['lastSuccessfulAt']=result['retrievedAt'];out.append(result)
                print(e['id'],len(result['rows']),result['latestCompletedPeriod'],result['fiveYearChangePct'],flush=True)
            except Exception as err:
                errors.append({'id':e['id'],'source':e['source'],'error':str(err),'attemptedAt':NOW.isoformat(timespec='seconds')})
                if e['id'] in old:
                    retained=dict(old[e['id']]);retained['fetchStatus']='retained_after_fetch_failure';retained['refreshError']=str(err);retained['lastAttemptAt']=NOW.isoformat(timespec='seconds');out.append(retained)
                print('ERROR',e['id'],str(err),flush=True)
    order={e['id']:i for i,e in enumerate(estates)};out.sort(key=lambda e:order[e['id']])
    return {'retrievedAt':NOW.isoformat(timespec='seconds'),'provider':'28Hse','frequency':'quarterly','methodology':['Values are parsed from public estate-page JavaScript arrays labelled AVG Price, All HK and Volume. Source labels are retained verbatim.','The source chart slices years as four observations. Quarterly labels may use a middle/end month (for example August or September for Q3). We map the literal source month to its containing quarter; November is not a completed monthly observation.','The current quarter is explicitly partial. Five-year change compares the latest completed quarter with the same quarter five years earlier, when both source observations exist.','No interpolation, annual-to-monthly expansion, or neighbourhood index synthesis. Points with zero or fewer than ten source transactions carry a sample caution. Five-year changes are withheld if either endpoint has fewer than ten source observations.','The chart uses estate-wide all-size provider aggregates; it is neither target-unit-only nor an official quality-adjusted district index. Provider model details are not fully disclosed.','Latest estate snapshot psf may differ from the chart because data windows, cache dates and provider revisions differ. Preserve these scopes rather than overwrite one with the other.','Estate rental histories were not available from the sale-price chart; missing history remains unavailable.','Failed per-estate fetches retain the previous dated series with fetchStatus and refreshError; they never acquire a new successful retrieval date.'],'estates':out,'errors':errors}

def main():
    data=json.load(open(SOURCE_DATA))
    try:previous=json.load(open(OUTPUT))
    except (FileNotFoundError,json.JSONDecodeError):previous=None
    result=refresh_trends(data,previous)
    json.dump(result,open(OUTPUT,'w'),ensure_ascii=False,indent=2)
    print('Saved',OUTPUT,'estates',len(result['estates']),'errors',len(result['errors']),flush=True)
if __name__=='__main__':main()
