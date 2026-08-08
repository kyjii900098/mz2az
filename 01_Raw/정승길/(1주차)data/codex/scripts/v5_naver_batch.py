#!/usr/bin/env python3
"""v5 정예4작품 — place_naver_url 빈칸 재검 배치 (정정명칭 우선, coord≤150m 완화).
해외(경도 124~132 밖) 행은 네이버 미등록 지역이므로 제외.
출력: 조합작업/v5정예/네이버재검_결과.csv (id,search_key,naver_url,confidence,matched_name)
"""
import csv, json, sys, time, importlib.util
from pathlib import Path

DATA = Path(__file__).resolve().parents[2]
V5 = DATA/'result'/'촬영지_TOP_v5_정예4작품.csv'
WD = DATA/'조합작업'/'v5정예'
OUT = WD/'네이버재검_결과.csv'

spec = importlib.util.spec_from_file_location('npb', DATA/'codex'/'scripts'/'naver_place_batch.py')
npb = importlib.util.module_from_spec(spec)
sys.modules['npb'] = npb
sys.argv = ['npb']
spec.loader.exec_module(npb)

canon = {}
cp = WD/'정정명칭_목록.csv'
if cp.exists():
    for r in list(csv.reader(open(cp, encoding='utf-8-sig')))[1:]:
        canon[r[0]] = r[2]

rows = list(csv.reader(open(V5, encoding='utf-8-sig')))
h = rows[0]; ix = {c:h.index(c) for c in h}
targets = []
skipped_overseas = 0
for r in rows[1:]:
    if r[ix['place_naver_url']].strip(): continue
    lng = r[ix['place_longitude']].strip()
    try:
        if not (124.0 <= float(lng) <= 132.0):
            skipped_overseas += 1; continue
    except Exception: pass
    targets.append(r)
print(f'대상 {len(targets)}행 (해외 제외 {skipped_overseas})', flush=True)

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

out = [['id','search_key','naver_url','confidence','matched_name']]
adopted = 0
for i, r in enumerate(targets, 1):
    rid = r[ix['id']]
    name = canon.get(rid) or r[ix['place_name']].strip()
    addr = r[ix['place_address']].strip()
    combo = npb.PlaceCombo(place_name=name, place_address=addr,
                           orig_lat=r[ix['place_latitude']].strip(), orig_lng=r[ix['place_longitude']].strip(),
                           key=rid)
    url = ''; conf = 'failed'; mn = ''
    try:
        items = []
        for q in npb.make_queries(combo, 3):
            items = session.search(q)
            if items: break
        best = npb.choose_candidate(combo, items) if items else None
        conf = npb.classify_match(combo, best)
        if best and conf not in ('high','mid'):
            d = best.get('distance_m')
            if d is not None and d <= 150:
                conf = 'coord'
        if best and conf in ('high','mid','coord'):
            item = best.get('item') or {}
            pid = npb.clean_text(item.get('id'))
            if pid:
                url = f'https://map.naver.com/p/entry/place/{pid}'
                mn = npb.clean_text(item.get('name'))
                adopted += 1
    except npb.BlockedError:
        print('차단 — 60s 대기', flush=True); time.sleep(60)
    except Exception as e:
        mn = f'ERR:{type(e).__name__}'
    out.append([rid, name, url, conf, mn])
    if i % 10 == 0:
        with open(OUT,'w',encoding='utf-8-sig',newline='') as f: csv.writer(f).writerows(out)
        print(f'{i}/{len(targets)} 채택 {adopted}', flush=True)
    time.sleep(1.5)
with open(OUT,'w',encoding='utf-8-sig',newline='') as f: csv.writer(f).writerows(out)
print(f'완료 {len(targets)} | 채택 {adopted}', flush=True)
