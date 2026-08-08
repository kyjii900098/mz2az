#!/usr/bin/env python3
"""v5 정예4작품 — place_image_url 빈칸을 구글 Places(New)로 채우는 배치.
정정명칭_목록.csv의 교정 명칭을 우선 검색어로 쓰고, 좌표 150m 이내면 표기차여도 채택.
출력: 조합작업/v5정예/구글사진_결과.csv (id,image_url,matched_name,confidence)
"""
import csv, json, time, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib.util
spec = importlib.util.spec_from_file_location('gpb', Path(__file__).resolve().parent/'google_places_batch.py')
gpb = importlib.util.module_from_spec(spec)
import builtins
_real_main = None
gpb.__dict__['__name__'] = 'gpb'
spec.loader.exec_module(gpb)  # main() 실행 안 됨(__main__ 아님)

DATA = Path(__file__).resolve().parents[2]
V5 = DATA/'result'/'촬영지_TOP_v5_정예4작품.csv'
WD = DATA/'조합작업'/'v5정예'
OUT = WD/'구글사진_결과.csv'

canon = {}
cp = WD/'정정명칭_목록.csv'
if cp.exists():
    for r in list(csv.reader(open(cp, encoding='utf-8-sig')))[1:]:
        canon[r[0]] = r[2]

rows = list(csv.reader(open(V5, encoding='utf-8-sig')))
h = rows[0]; ix = {c:h.index(c) for c in h}
targets = [r for r in rows[1:] if not r[ix['place_image_url']].strip()]
print(f'대상 {len(targets)}행', flush=True)

out = [['id','image_url','matched_name','confidence']]
found = 0
for i, r in enumerate(targets, 1):
    rid = r[ix['id']]
    name = canon.get(rid) or r[ix['place_name']].strip()
    addr = r[ix['place_address']].strip()
    lat, lng = r[ix['place_latitude']].strip(), r[ix['place_longitude']].strip()
    q = f'{name} {addr.split()[0]}' if addr else name
    body = {'textQuery': q, 'languageCode': 'ko'}
    if lat and lng:
        try:
            body['locationBias'] = {'circle':{'center':{'latitude':float(lat),'longitude':float(lng)},'radius':2000.0}}
        except Exception: pass
    url = ''; mn = ''; conf = 'failed'
    try:
        res = gpb.gapi('https://places.googleapis.com/v1/places:searchText', body,
                       'places.id,places.displayName,places.location,places.photos')
        places = res.get('places', [])
        if places:
            p = places[0]
            mn = p.get('displayName',{}).get('text','')
            glat = p.get('location',{}).get('latitude',''); glng = p.get('location',{}).get('longitude','')
            sim = gpb.name_sim(name, mn)
            d = gpb.dist_m(lat, lng, glat, glng) if lat else None
            if sim >= 0.8 and (d is None or d <= 500): conf = 'high'
            elif d is not None and d <= 150: conf = 'coord'
            elif sim >= 0.5: conf = 'mid'
            photos = p.get('photos', [])
            if photos and conf in ('high','mid','coord'):
                pm = gpb.gapi(f"https://places.googleapis.com/v1/{photos[0]['name']}/media?maxWidthPx=800&skipHttpRedirect=true")
                url = pm.get('photoUri','')
                if url: found += 1
    except Exception as e:
        mn = f'ERR:{type(e).__name__}'
    out.append([rid, url, mn, conf])
    if i % 10 == 0:
        with open(OUT,'w',encoding='utf-8-sig',newline='') as f: csv.writer(f).writerows(out)
        print(f'{i}/{len(targets)} 사진 {found}', flush=True)
    time.sleep(0.3)
with open(OUT,'w',encoding='utf-8-sig',newline='') as f: csv.writer(f).writerows(out)
print(f'완료 {len(targets)} | 사진 {found}', flush=True)
