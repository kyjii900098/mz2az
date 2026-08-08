#!/usr/bin/env python3
"""네이버 구조(rescue) 배치 — "네이버 ✗ 이면서 구글 or 카카오 ○"인 장소를
구글/카카오가 검증한 정식 명칭·좌표를 검색 키로 네이버 재조회.

naver_place_batch.py의 세션·스코어링·판정 로직을 그대로 재사용한다.
출력: 조합작업/TOP120완성/네이버구조_결과.csv (id,place_name,search_key,naver_url,naver_lat,naver_lng,confidence,matched_name)
"""
import csv, json, sys, time, importlib.util
from pathlib import Path

DATA = Path(__file__).resolve().parents[2]
OUT = DATA/'조합작업'/'TOP120완성'/'네이버구조_결과.csv'
CACHE = DATA/'조합작업'/'TOP120완성'/'네이버구조_cache.jsonl'

spec = importlib.util.spec_from_file_location('npb', DATA/'codex'/'scripts'/'naver_place_batch.py')
npb = importlib.util.module_from_spec(spec)
sys.modules['npb'] = npb
sys.argv = ['npb']
spec.loader.exec_module(npb)

# 대상 수집: v3 기준 네이버∅ & (구글○ or 카카오○)
rows = list(csv.reader(open(DATA/'result'/'촬영지_TOP_v3_MVP1.csv', encoding='utf-8-sig')))
h = rows[0]; ix = {c: h.index(c) for c in h}
gcache = {}
for line in open(DATA/'조합작업'/'TOP120완성'/'구글결과_cache.jsonl', encoding='utf-8'):
    try:
        j = json.loads(line)
        gcache[(j['place_name'], j['place_address'])] = j
    except Exception:
        pass
kk = {}
for r in list(csv.reader(open(DATA/'조합작업'/'TOP120완성'/'카카오결과.csv', encoding='utf-8-sig')))[1:]:
    if len(r) > 7 and r[6] in ('high','mid'):
        kk[r[0]] = r[7]  # id -> matched_name

targets = {}
for r in rows[1:]:
    if r[ix['place_naver_url']].strip():
        continue
    if not (r[ix['place_google_url']].strip() or r[ix['place_kakao_url']].strip()):
        continue
    key = (r[ix['place_name']].strip(), r[ix['place_address']].strip())
    if key in targets:
        targets[key]['ids'].append(r[ix['id']])
        continue
    g = gcache.get(key)
    canon = (g or {}).get('matched_name') or kk.get(r[ix['id']]) or key[0]
    addr = (g or {}).get('matched_address') or key[1]
    lat = r[ix['place_latitude']].strip() or (g or {}).get('google_lat','')
    lng = r[ix['place_longitude']].strip() or (g or {}).get('google_lng','')
    targets[key] = {'ids':[r[ix['id']]], 'canon':canon, 'addr':addr, 'lat':str(lat), 'lng':str(lng)}
print(f'구조 대상: {len(targets)} 콤보', flush=True)

done = set()
if CACHE.exists():
    for line in open(CACHE, encoding='utf-8'):
        try: done.add(tuple(json.loads(line)['key']))
        except Exception: pass

def _mk_client():
    C = npb.NaverPlaceClient
    import inspect
    params = set(inspect.signature(C.__init__).parameters)
    kwargs = dict(min_delay=1.2, max_delay=2.5, timeout=20, max_retries=3, block_backoff=15)
    if 'on_block' in params:
        kwargs['on_block'] = lambda e: print('[block]', str(e)[:80], flush=True)
    kwargs = {k: v for k, v in kwargs.items() if k in params}
    return C(**kwargs)
session = _mk_client()

out_rows = [['id','place_name','search_key','naver_url','naver_lat','naver_lng','confidence','matched_name']]
cf = open(CACHE,'a',encoding='utf-8')
n=0; adopted=0
for key, t in targets.items():
    n+=1
    if key in done:
        continue
    combo = npb.PlaceCombo(place_name=t['canon'], place_address=t['addr'], orig_lat=t['lat'], orig_lng=t['lng'], key=f'{key[0]}|{key[1]}')
    rec = {'key': list(key), 'ids': t['ids'], 'url':'', 'conf':'failed', 'mn':'', 'lat':'', 'lng':''}
    try:
        items=[]
        for q in npb.make_queries(combo, 3):
            items = session.search(q)
            if items: break
        best = npb.choose_candidate(combo, items) if items else None
        conf = npb.classify_match(combo, best)
        # 구조 전용 완화: 정식명칭 검색 결과가 기존 좌표 150m 이내면 표기 차이(한/영)여도 채택
        if best and conf not in ('high','mid'):
            d = best.get('distance_m')
            if d is not None and d <= 150:
                conf = 'coord'
        if best and conf in ('high','mid','coord'):
            item = best.get('item') or {}
            pid = npb.clean_text(item.get('id'))
            if pid:
                rec.update({'url': f'https://map.naver.com/p/entry/place/{pid}', 'conf': conf,
                            'mn': npb.clean_text(item.get('name')),
                            'lat': str(best.get('naver_lat') or ''), 'lng': str(best.get('naver_lng') or '')})
                adopted+=1
    except npb.BlockedError:
        print('차단 — 60s 대기', flush=True); time.sleep(60)
    except Exception as e:
        rec['mn']=f'ERR:{type(e).__name__}'
    cf.write(json.dumps(rec, ensure_ascii=False)+'\n'); cf.flush()
    for i in t['ids']:
        out_rows.append([i, key[0], t['canon'], rec['url'], rec['lat'], rec['lng'], rec['conf'], rec['mn']])
    if n % 50 == 0:
        with open(OUT,'w',encoding='utf-8-sig',newline='') as f: csv.writer(f).writerows(out_rows)
        print(f'{n}/{len(targets)} 채택 {adopted}', flush=True)
    time.sleep(1.5)
with open(OUT,'w',encoding='utf-8-sig',newline='') as f: csv.writer(f).writerows(out_rows)
print(f'완료 {n} 콤보 | 채택 {adopted}', flush=True)
