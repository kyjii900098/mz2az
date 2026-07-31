#!/usr/bin/env python3
"""TOP120 드라마 + 영화 촬영지의 구글맵 URL·대표사진 CDN URL 수집 배치.

- 입력: 본체 2개 CSV에서 (famous_rank/recent_rank 있는 드라마 행) + (영화 장소 행)
- 장소당: Text Search 1콜 → 이름유사+거리로 등급 → 사진 있으면 media 1콜(skipHttpRedirect)로 CDN URL 확보
- 출력: 조합작업/TOP120완성/구글결과.csv, 캐시 구글결과_cache.jsonl (재개 가능), 100행마다 flush
"""
import csv, json, time, sys, re, math
from pathlib import Path
import urllib.request, urllib.error

DATA = Path(__file__).resolve().parents[2]
OUT = DATA/'조합작업'/'TOP120완성'/'구글결과.csv'
CACHE = DATA/'조합작업'/'TOP120완성'/'구글결과_cache.jsonl'
HEADER = ['id','place_name','google_place_id','google_url','photo_url','google_lat','google_lng','match_confidence','matched_name','matched_address']

def load_key():
    for line in open(Path.home()/'.secrets'):
        line=line.strip()
        if '=' in line and ('GOOGLE' in line.upper() or 'PLACE' in line.upper()):
            return line.split('=',1)[1].strip().strip('"\'')
    raise SystemExit('GOOGLE key not found in ~/.secrets')

KEY = load_key()

def gapi(url, body=None, mask=None):
    headers={'X-Goog-Api-Key':KEY}
    data=None
    if body is not None:
        headers['Content-Type']='application/json'; data=json.dumps(body).encode()
    if mask: headers['X-Goog-FieldMask']=mask
    req=urllib.request.Request(url, data=data, headers=headers)
    for attempt in range(3):
        try:
            return json.load(urllib.request.urlopen(req, timeout=20))
        except urllib.error.HTTPError as e:
            if e.code in (403,429,500,503) and attempt<2:
                time.sleep(2*(attempt+1)); continue
            raise
        except Exception:
            if attempt<2: time.sleep(2*(attempt+1)); continue
            raise

def norm(s): return re.sub(r'[\s\(\)\[\]·,\.\-]','',s or '').lower()

def name_sim(a,b):
    na,nb=norm(a),norm(b)
    if not na or not nb: return 0
    if na==nb: return 1.0
    if na in nb or nb in na: return 0.8
    common=len(set(na)&set(nb))/max(len(set(na)),len(set(nb)))
    return common*0.6

def dist_m(lat1,lng1,lat2,lng2):
    try:
        lat1,lng1,lat2,lng2=map(float,(lat1,lng1,lat2,lng2))
    except Exception: return None
    dx=(lng2-lng1)*88800*math.cos(math.radians(lat1)); dy=(lat2-lat1)*111000
    return (dx*dx+dy*dy)**0.5

def main():
    # 대상 수집
    combos={}
    for body in ['드라마_kdramamap_스키마.csv','촬영지_마스터.csv']:
        rows=list(csv.reader(open(DATA/body,encoding='utf-8-sig')))
        h=rows[0]; ix={c:h.index(c) for c in h}
        for r in rows[1:]:
            is_top = r[ix['famous_rank']].strip() or r[ix['recent_rank']].strip() if 'famous_rank' in ix else False
            is_mov = ix.get('title_category') is not None and r[ix['title_category']]=='movie'
            if not (is_top or is_mov): continue
            name=r[ix['place_name']].strip()
            if not name: continue
            k=(name, r[ix['place_address']].strip())
            if k not in combos:
                combos[k]={'id':r[ix['id']],'lat':r[ix['place_latitude']].strip(),'lng':r[ix['place_longitude']].strip()}
    print(f'대상 고유 콤보: {len(combos)}', flush=True)

    cache={}
    if CACHE.exists():
        for line in open(CACHE,encoding='utf-8'):
            try:
                j=json.loads(line); cache[(j['place_name'],j['place_address'])]=j
            except Exception: pass
    print(f'캐시: {len(cache)}', flush=True)

    limit=None
    for i,a in enumerate(sys.argv):
        if a=='--limit' and i+1<len(sys.argv): limit=int(sys.argv[i+1])
    results=[]
    cf=open(CACHE,'a',encoding='utf-8')
    n=0; new_calls=0
    for (name,addr),meta in combos.items():
        n+=1
        ck=(name,addr)
        if ck in cache:
            results.append(cache[ck]); continue
        if limit is not None and new_calls>=limit:
            print(f'--limit {limit} 도달, 중단 (처리 {n-1}/{len(combos)})', flush=True)
            break
        new_calls+=1
        # 검색
        q=f'{name} {addr.split()[0]}' if addr else name
        body={'textQuery':q,'languageCode':'ko'}
        if meta['lat'] and meta['lng']:
            try:
                body['locationBias']={'circle':{'center':{'latitude':float(meta['lat']),'longitude':float(meta['lng'])},'radius':2000.0}}
            except Exception: pass
        rec={'place_name':name,'place_address':addr,'id':meta['id'],'google_place_id':'','google_url':'','photo_url':'','google_lat':'','google_lng':'','match_confidence':'failed','matched_name':'','matched_address':''}
        try:
            res=gapi('https://places.googleapis.com/v1/places:searchText', body,
                     'places.id,places.displayName,places.formattedAddress,places.location,places.googleMapsUri,places.photos')
            places=res.get('places',[])
            if places:
                p=places[0]
                mn=p.get('displayName',{}).get('text','')
                ma=p.get('formattedAddress','')
                glat=p.get('location',{}).get('latitude',''); glng=p.get('location',{}).get('longitude','')
                sim=name_sim(name,mn)
                d=dist_m(meta['lat'],meta['lng'],glat,glng) if meta['lat'] else None
                if sim>=0.8 and (d is None or d<=500): conf='high'
                elif sim>=0.5: conf='mid'
                elif sim>0: conf='low'
                else: conf='failed'
                rec.update({'google_place_id':p.get('id',''),'google_url':p.get('googleMapsUri',''),
                            'google_lat':str(glat),'google_lng':str(glng),'match_confidence':conf,
                            'matched_name':mn,'matched_address':ma})
                # 사진 (high/mid만 — 콜 절약)
                photos=p.get('photos',[])
                if photos and conf in ('high','mid'):
                    try:
                        pm=gapi(f"https://places.googleapis.com/v1/{photos[0]['name']}/media?maxWidthPx=800&skipHttpRedirect=true")
                        rec['photo_url']=pm.get('photoUri','')
                    except Exception: pass
        except Exception as e:
            rec['matched_name']=f'ERR:{type(e).__name__}'
        results.append(rec)
        cf.write(json.dumps(rec,ensure_ascii=False)+'\n'); cf.flush()
        if n%100==0:
            write_out(results); print(f'{n}/{len(combos)}', flush=True)
        time.sleep(0.25)
    write_out(results)
    from collections import Counter
    print('완료:', dict(Counter(r['match_confidence'] for r in results)), flush=True)

def write_out(results):
    with open(OUT,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f); w.writerow(HEADER)
        for r in results: w.writerow([r.get(c,'') for c in HEADER])

if __name__=='__main__':
    main()
