#!/usr/bin/env python3
"""Refresh advertised-sale inventory from public 28Hse HTML, not a whole-market feed.
Stdlib only; plain URLs permitted by source robots.txt checked 2026-11-02.
Polite sequential requests; stop region on blocking/error; preserve prior rows on failure.
"""
import argparse,datetime,html,json,math,re,time,urllib.request,urllib.error,pathlib,sys
REGIONS=[
 {'id':'taikoo','label':'Tai Koo / Taikoo Shing','estateId':'taikoo-quarry-bay','district':'Eastern','region':'Hong Kong Island','url':'https://www.28hse.com/en/buy/a1/dg9','scope':'28Hse Taikoo Shing search district'},
 {'id':'olympic','label':'Olympic','estateId':'olympic','district':'Yau Tsim Mong','region':'Kowloon','url':'https://www.28hse.com/en/buy/a2/dg28/di28-68','scope':'28Hse Olympic search district'},
 {'id':'tko','label':'Tseung Kwan O','estateId':'tseung-kwan-o','district':'Sai Kung','region':'New Territories','url':'https://www.28hse.com/en/buy/a3/dg41/di41-125','scope':'28Hse Tseung Kwan O central search district; excludes separate Lohas, Hang Hau, Po Lam and Tiu Keng Leng search districts'}]
HEADERS={'User-Agent':'HomeLensHK/1.0 (+public research; single sequential HTML request)','Accept-Language':'en-HK,en;q=0.8'}
def text(s):return re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>',' ',s))).strip()
def fetch(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers=HEADERS),timeout=25) as response:
  if response.status!=200:raise RuntimeError('HTTP '+str(response.status))
  data=response.read().decode('utf-8')
 if 'property_item' not in data:raise RuntimeError('Listing cards unavailable; parser/source may have changed')
 return data

def parse_cards(s,region,page_url,checked):
 starts=list(re.finditer(r'<div class="item property_item[^\"]*"',s));rows=[]
 for i,start in enumerate(starts):
  block=s[start.start():starts[i+1].start() if i+1<len(starts) else s.find('<div class="pagination',start.start()) if s.find('<div class="pagination',start.start())>0 else len(s)]
  id_match=re.search(r'property-(\d+)',block)
  if not id_match:continue
  listing_id=id_match.group(1)
  detail='https://www.28hse.com/en/buy/apartment/property-'+listing_id
  area_match=re.search(r'Saleable Area:\s*([\d,]+)\s*ft',block,re.I)
  price_label=re.search(r'<div class="ui right floated red large label">(.*?)</div>',block,re.S)
  price_match=re.search(r'(?:Sale|Sell)\s+(?:HK\$|HKD\$)\s*([\d,.]+)\s*(million|millions|billion|thousand)?',text(price_label.group(1) if price_label else ''),re.I)
  asking=None
  if price_match:
   asking=float(price_match.group(1).replace(',',''))*({'million':1e6,'millions':1e6,'billion':1e9,'thousand':1e3}.get((price_match.group(2) or '').lower(),1))
   asking=round(asking)
  district_area=re.search(r'<div class="district_area[^\"]*">(.*?)</div>',block,re.S)
  places=re.findall(r'<a\b[^>]*href="([^\"]+)"[^>]*>(.*?)</a>',district_area.group(1),re.S) if district_area else []
  neighborhood=text(places[0][1]) if places else region['label']
  estate=text(places[1][1]) if len(places)>1 else None
  if not estate and len(places)>1 and '/c1140' in places[1][0]:estate='Taikoo Shing'
  estate_search_url=html.unescape(places[1][0]) if len(places)>1 else None
  unit_match=re.search(r'<span class="unit_desc">(.*?)</span>',block,re.S)
  bed_match=re.search(r'>(\d+) Bedrooms?(?:\s*,|\s*<)',block,re.I)
  bedroom=int(bed_match.group(1)) if bed_match else 0 if re.search(r'>\s*Studio\s*<',block,re.I) else None
  agent_match=re.search(r'<div class="companyName"[^>]*>(.*?)</div>',block,re.S)
  posted_match=re.search(r'((?:\d+|a|an)\s+(?:minutes?|hours?|days?|months?|years?)\s+ago posted)',text(block),re.I)
  area=int(area_match.group(1).replace(',','')) if area_match else None
  tags=[tag for tag in ['Balcony','MTR nearby','Sea view','Open view','Good school zone','Shopping Mall nearby','Home Ownership','Premium Unpaid','Premium Paid','Garden','Ensuite','Maid bedroom','Penthouse','Apartment'] if re.search(r'>\s*'+re.escape(tag)+r'\s*<',block,re.I)]
  row={'id':'28hse-'+listing_id,'sourceId':listing_id,'focusRegion':region['id'],'location':neighborhood,'district':region['district'],'region':region['region'],'estate':estate,'estateId':region['estateId'] if estate in {'Taikoo Shing','Park Avenue','Park Central'} else None,'street':({'Taikoo Shing':'Taikoo Wan Road / Taikoo Shing Road','Park Avenue':'18 Hoi Ting Road','Park Central':'Tong Tak Street / Tong Chun Street','Harbour Green':'8 Sham Mong Road','One Silversea':'18 Hoi Fai Road','Island Harbourview':'11 Hoi Fai Road','Imperial Cullinan':'10 Hoi Fai Road'}.get(estate)),'unit':text(unit_match.group(1)) if unit_match else None,'bedrooms':bedroom,'saleableSqft':area,'askingHkd':asking,'askingPsf':round(asking/area,2) if asking and area else None,'source':'28Hse','url':detail,'sourceSearchUrl':page_url,'estateSearchUrl':estate_search_url,'postedLabel':posted_match.group(1) if posted_match else None,'createdAt':None,'updatedAt':None,'checkedAt':checked,'availability':'advertised-at-last-check','availabilityConfirmed':False,'status':'asking','agent':text(agent_match.group(1)) if agent_match else None,'features':tags,'targetFit':bedroom==2 and area is not None and 400<=area<=600,'dedupKey':'28hse:'+listing_id}
  row['title']=' · '.join(x for x in [estate or neighborhood,str(bedroom)+' bedrooms' if bedroom is not None else None,str(area)+' saleable sq ft' if area else None] if x)
  rows.append(row)
 return rows

def total_count(s):
 m=re.search(r'"numberOfItems"\s*:\s*"?(\d+)',s)
 if m:return int(m.group(1))
 m=re.search(r'([\d,]+) results of property for sale',s)
 return int(m.group(1).replace(',','')) if m else None

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',default='/workspace/focus-listings.json');ap.add_argument('--max-pages',type=int,default=100);ap.add_argument('--delay',type=float,default=.55);ap.add_argument('--regions',default='taikoo,olympic,tko');args=ap.parse_args()
 checked=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds');baseline={}
 try:baseline=json.loads(pathlib.Path(args.output).read_text())
 except (FileNotFoundError,json.JSONDecodeError):pass
 out={'checkedAt':checked,'provider':'28Hse','methodology':'Public search-result sale advertisements. Asking prices are not transactions; availability must be reconfirmed with the agent. Deduplicated by provider listing id, not by physical flat: multiple agent ads for one flat may remain. Source claims/cached counts can change during pagination. No photos or marketing descriptions copied. All unit areas are source-reported saleable square feet, not gross area. Fields absent in source search cards remain null.','coverage':'One provider; three defined search districts, not all Hong Kong properties or full market coverage.','regions':[],'listings':[],'errors':[]}
 def save():pathlib.Path(args.output).write_text(json.dumps(out,ensure_ascii=False,indent=2))
 for region in [r for r in REGIONS if r['id'] in args.regions.split(',')]:
  rows={};pages=[];first_count=None;end=False;error=None
  try:
   s=fetch(region['url']);first_count=total_count(s);first_rows=parse_cards(s,region,region['url'],checked);per_page=len(first_rows)
   if not per_page:raise RuntimeError('No parsed sale ads')
   # Page may contain ads with missing values; count ItemList entries, not parsed subset.
   item_starts=len(list(re.finditer(r'<div class="item property_item[^\"]*"',s)))
   desired=math.ceil(first_count/item_starts) if first_count else 1
   desired=min(desired,args.max_pages)
   for page in range(1,desired+1):
    url=region['url'] if page==1 else region['url']+'/page-'+str(page)
    if page>1:
     time.sleep(args.delay);s=fetch(url)
    parsed=parse_cards(s,region,url,checked)
    added=0
    for row in parsed:
     if row['id'] not in rows:rows[row['id']]=row;added+=1
    pages.append(url)
    print(region['id'],'page',page,'parsed',len(parsed),'unique',len(rows),flush=True)
    if page>1 and not added:
     error='Pagination returned only repeated listing ids; completeness not established';out['errors'].append({'region':region['id'],'error':error});end=False;break
   else:end=first_count is not None and len(pages)>=math.ceil(first_count/item_starts)
  except Exception as e:
   error=str(e);out['errors'].append({'region':region['id'],'error':error});print(region['id'],'ERROR',error,flush=True)
  attempted_count=len(rows);retained=0;old_region=next((r for r in baseline.get('regions',[]) if r.get('id')==region['id']),{})
  if not end:
   for old_row in baseline.get('listings',[]):
    if old_row.get('focusRegion')==region['id'] and old_row['id'] not in rows:
     rows[old_row['id']]=old_row;retained+=1
  out['regions'].append({**region,'reportedAdvertCount':first_count if first_count is not None else old_region.get('reportedAdvertCount'),'capturedAds':len(rows),'attemptedCapturedAds':attempted_count,'previousRowsRetained':retained,'pagesFetched':len(pages),'searchPages':pages,'allExpectedPagesFetched':end,'completeMarketCoverage':False,'checkedAt':checked if end else old_region.get('checkedAt'),'attemptedAt':checked,'lastSuccessfulCheckAt':checked if end else old_region.get('lastSuccessfulCheckAt',old_region.get('checkedAt')),'refreshStatus':'complete-source-pagination' if end else 'partial-previous-data-retained' if rows else 'failed-no-data','error':error,'targetFitCount':sum(r.get('targetFit',False) for r in rows.values()),'unknownAskingCount':sum(r.get('askingHkd') is None for r in rows.values()),'unknownAreaCount':sum(r.get('saleableSqft') is None for r in rows.values()),'unknownBedroomCount':sum(r.get('bedrooms') is None for r in rows.values()),'omissionNote':'All identifiable source ads retained. Missing source numeric fields remain null. Provider counts may include duplicate agent ads or change during pagination.'})
  out['listings'].extend(rows.values());save()
 selected_ids=set(args.regions.split(','))
 for old_region in baseline.get('regions',[]):
  if old_region.get('id') not in selected_ids:
   out['regions'].append(old_region)
   out['listings'].extend(r for r in baseline.get('listings',[]) if r.get('focusRegion')==old_region.get('id'))
 save()
 print('Saved',len(out['listings']),'ads to',args.output,flush=True)
 if any(not r.get('allExpectedPagesFetched') for r in out['regions'] if r['id'] in selected_ids):sys.exit(2)
if __name__=='__main__':main()
