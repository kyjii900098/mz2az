#!/usr/bin/env python3
"""v5 정예4작품 — scene_image_url 빈칸을 TMDB 스틸로 보충.
장면설명의 "N화/N회/EP.N"을 파싱해 해당 에피소드 스틸을, 없으면 작품 백드롭을
행 순번으로 순환 배정(같은 이미지 반복 최소화).
출력: 조합작업/v5정예/TMDB스틸_결과.csv (id,image_url,source)
"""
import csv, json, re, time, urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parents[2]
V5 = DATA/'result'/'촬영지_TOP_v5_정예4작품.csv'
OUT = DATA/'조합작업'/'v5정예'/'TMDB스틸_결과.csv'
IMG = 'https://image.tmdb.org/t/p/w780'

def load_token():
    for line in open(Path.home()/'.secrets'):
        line = line.strip()
        if line.startswith('TMDB_API_KEY='):
            return line.split('=',1)[1].strip().strip('"\'')
    raise SystemExit('TMDB_API_KEY not found')
TOK = load_token()

def api(path, **params):
    import urllib.parse
    url = f'https://api.themoviedb.org/3{path}'
    if params: url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {TOK}', 'accept': 'application/json'})
    for a in range(3):
        try:
            return json.load(urllib.request.urlopen(req, timeout=20))
        except Exception:
            if a < 2: time.sleep(2*(a+1)); continue
            raise

WORKS = {
    '도깨비':          ('tv',    '도깨비', 2016),
    '눈물의 여왕':      ('tv',    '눈물의 여왕', 2024),
    '이태원 클라쓰':    ('tv',    '이태원 클라쓰', 2020),
    '케이팝 데몬 헌터스': ('movie', '케이팝 데몬 헌터스', 2025),
}
ids = {}
for title, (kind, q, yr) in WORKS.items():
    if kind == 'tv':
        res = api('/search/tv', query=q, language='ko-KR', first_air_date_year=yr)
    else:
        res = api('/search/movie', query=q, language='ko-KR', year=yr)
    hits = res.get('results') or []
    if not hits: raise SystemExit(f'TMDB 미발견: {title}')
    ids[title] = (kind, hits[0]['id'], hits[0].get('name') or hits[0].get('title'))
    print(title, '->', ids[title], flush=True)

backdrops = {}
for title, (kind, tid, mn) in ids.items():
    res = api(f'/{"tv" if kind=="tv" else "movie"}/{tid}/images')
    bl = sorted(res.get('backdrops') or [], key=lambda b: -(b.get('vote_count') or 0))
    backdrops[title] = [b['file_path'] for b in bl if b.get('file_path')][:40]
    print(title, '백드롭', len(backdrops[title]), flush=True)

ep_cache = {}
def episode_stills(title, ep):
    kind, tid, _ = ids[title]
    if kind != 'tv': return []
    key = (tid, ep)
    if key not in ep_cache:
        try:
            res = api(f'/tv/{tid}/season/1/episode/{ep}/images')
            st = sorted(res.get('stills') or [], key=lambda b: -(b.get('vote_count') or 0))
            ep_cache[key] = [s['file_path'] for s in st if s.get('file_path')]
        except Exception:
            ep_cache[key] = []
        time.sleep(0.2)
    return ep_cache[key]

EP_RE = re.compile(r'(?:EP\.?\s*|\b)(\d{1,2})\s*[화회]|EP\.?\s*(\d{1,2})', re.I)
rows = list(csv.reader(open(V5, encoding='utf-8-sig')))
h = rows[0]; ix = {c:h.index(c) for c in h}
targets = [r for r in rows[1:] if not r[ix['scene_image_url']].strip()]
print(f'대상 {len(targets)}행', flush=True)

out = [['id','image_url','source']]
counters = {}
filled = 0
for r in targets:
    title = r[ix['title']]
    if title not in ids:
        out.append([r[ix['id']], '', 'no-work']); continue
    desc = r[ix['scene_description']]
    ep = None
    m = EP_RE.search(desc or '')
    if m:
        try:
            ep = int(m.group(1) or m.group(2))
        except Exception: ep = None
    pool, src = [], ''
    if ep:
        pool = episode_stills(title, ep)
        src = f'ep{ep}-still'
    if not pool:
        pool = backdrops.get(title) or []
        src = 'backdrop'
    if not pool:
        out.append([r[ix['id']], '', 'none']); continue
    k = (title, src)
    idx = counters.get(k, 0); counters[k] = idx + 1
    out.append([r[ix['id']], IMG + pool[idx % len(pool)], src])
    filled += 1
with open(OUT,'w',encoding='utf-8-sig',newline='') as f: csv.writer(f).writerows(out)
print(f'완료 {len(targets)} | 배정 {filled}', flush=True)
