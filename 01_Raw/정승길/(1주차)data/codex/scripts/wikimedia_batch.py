#!/usr/bin/env python3
"""위키미디어 커먼즈 사진 배치 — v4_정승길의 place_image_url 빈칸을
좌표 근접(geosearch, 150m) CC 이미지로 채울 재료 수집. 키 불필요.
출력: 조합작업/TOP120완성/위키미디어_결과.csv
      (id,place_name,image_url,commons_page,license,author,distance_m)
"""
import csv, json, time, urllib.request, urllib.parse, urllib.error
from pathlib import Path

DATA = Path(__file__).resolve().parents[2]
SRC = DATA/'result'/'촬영지_TOP_v4_정승길.csv'
import os
_sh = os.environ.get('SHARD','0/1')
SH_I, SH_N = int(_sh.split('/')[0]), int(_sh.split('/')[1])
OUT = DATA/'조합작업'/'TOP120완성'/f'위키미디어_결과_{SH_I}.csv'
CACHE = DATA/'조합작업'/'TOP120완성'/f'위키미디어_cache_{SH_I}.jsonl'
API = 'https://commons.wikimedia.org/w/api.php'
UA = {'User-Agent': 'SceneTripDataBot/0.1 (contact: team mz2az; non-commercial MVP research)'}

def api(**params):
    params.update(format='json')
    url = API+'?'+urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    for a in range(3):
        try:
            return json.load(urllib.request.urlopen(req, timeout=20))
        except urllib.error.HTTPError as e:
            if e.code == 429 and a < 2: time.sleep(15*(a+1)); continue
            if a < 2: time.sleep(3*(a+1)); continue
            raise
        except Exception:
            if a < 2: time.sleep(3*(a+1)); continue
            raise

rows = list(csv.reader(open(SRC, encoding='utf-8-sig')))
h = rows[0]; ix = {c: h.index(c) for c in h}
targets = {}
for r in rows[1:]:
    if r[ix['place_image_url']].strip(): continue
    lat, lng = r[ix['place_latitude']].strip(), r[ix['place_longitude']].strip()
    if not lat or not lng: continue
    key = (r[ix['place_name']].strip(), lat, lng)
    targets.setdefault(key, []).append(r[ix['id']])
print(f'대상: {len(targets)} 고유 장소', flush=True)

done = set()
if CACHE.exists():
    for line in open(CACHE, encoding='utf-8'):
        try: done.add(tuple(json.loads(line)['key']))
        except Exception: pass

out = [['id','place_name','image_url','commons_page','license','author','distance_m']]
cf = open(CACHE, 'a', encoding='utf-8')
n = 0; found = 0
for si,(key, ids) in enumerate(targets.items()):
    if si % SH_N != SH_I: continue
    n += 1
    if key in done: continue
    name, lat, lng = key
    rec = {'key': list(key), 'ids': ids, 'url': '', 'page': '', 'lic': '', 'auth': '', 'd': ''}
    try:
        gs = api(action='query', list='geosearch', gscoord=f'{lat}|{lng}',
                 gsradius=150, gsnamespace=6, gslimit=5)
        hits = (gs.get('query') or {}).get('geosearch') or []
        for hit in hits:
            title = hit.get('title','')
            if not title.lower().endswith(('.jpg','.jpeg','.png','.webp')): continue
            ii = api(action='query', titles=title, prop='imageinfo',
                     iiprop='url|extmetadata', iiurlwidth=800)
            pages = (ii.get('query') or {}).get('pages') or {}
            for p in pages.values():
                info = (p.get('imageinfo') or [{}])[0]
                meta = info.get('extmetadata') or {}
                lic = (meta.get('LicenseShortName') or {}).get('value','')
                auth = (meta.get('Artist') or {}).get('value','')
                import re
                auth = re.sub(r'<[^>]+>','',auth)[:80]
                url = info.get('thumburl') or info.get('url','')
                if url and lic:
                    rec.update({'url': url, 'page': f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(title)}",
                                'lic': lic, 'auth': auth, 'd': str(hit.get('dist',''))})
                    found += 1
                    break
            if rec['url']: break
    except Exception as e:
        rec['lic'] = f'ERR:{type(e).__name__}'
    if not str(rec['lic']).startswith('ERR'):
        cf.write(json.dumps(rec, ensure_ascii=False)+'\n'); cf.flush()
    for i in ids:
        out.append([i, name, rec['url'], rec['page'], rec['lic'], rec['auth'], rec['d']])
    if n % 100 == 0:
        with open(OUT,'w',encoding='utf-8-sig',newline='') as f: csv.writer(f).writerows(out)
        print(f'{n}/{len(targets)} 발견 {found}', flush=True)
    time.sleep(0.9)
with open(OUT,'w',encoding='utf-8-sig',newline='') as f: csv.writer(f).writerows(out)
print(f'완료 {n} | 발견 {found}', flush=True)
