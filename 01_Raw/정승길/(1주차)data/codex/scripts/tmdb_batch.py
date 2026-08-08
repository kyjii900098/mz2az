#!/usr/bin/env python3
"""v4의 고유 작품별 TMDB 감독·포스터 URL 수집.
- 드라마: /search/tv → /tv/{id}/aggregate_credits에서 job=Director (없으면 created_by 폴백, 표기 'FALLBACK:크리에이터')
- 영화: /search/movie → /movie/{id}/credits에서 job=Director
출력: 조합작업/TOP120완성/TMDB결과.csv (title, category, matched_title, year, director, poster_url, status)
"""
import csv, json, time, re
from pathlib import Path
import urllib.request, urllib.parse

DATA = Path(__file__).resolve().parents[2]
V4 = DATA/'result'/'촬영지_TOP_v4_MVP1.csv'
OUT = DATA/'조합작업'/'TOP120완성'/'TMDB결과.csv'

def load_key():
    for line in open(Path.home()/'.secrets'):
        if line.strip().startswith('TMDB_API_KEY='):
            return line.split('=',1)[1].strip().strip('"\'')
    raise SystemExit('no key')
KEY=load_key()
HDR={'Authorization':f'Bearer {KEY}'} if KEY.startswith('eyJ') else None

def tmdb(path, **params):
    if HDR is None: params['api_key']=KEY
    url=f'https://api.themoviedb.org/3{path}?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url, headers=HDR or {})
    for a in range(3):
        try: return json.load(urllib.request.urlopen(req, timeout=15))
        except Exception:
            if a<2: time.sleep(1.5*(a+1)); continue
            raise

def spaced(t):
    # 붙여쓴 제목 검색 실패 대비 원제 그대로 + 공백 변형 둘 다 시도
    return t

rows=list(csv.reader(open(V4, encoding='utf-8-sig')))
h=rows[0]; ix={c:h.index(c) for c in h}
works={}
for r in rows[1:]:
    t=r[ix['title']].strip()
    if t and t not in works:
        works[t]=r[ix['title_category']].strip() or 'drama'
print(f'고유 작품: {len(works)}', flush=True)

out=[['title','category','matched_title','year','director','poster_url','status']]
ok=0
for i,(title,cat) in enumerate(works.items(),1):
    is_movie = cat=='movie'
    ep='/search/movie' if is_movie else '/search/tv'
    rec=[title,cat,'','','','','not_found']
    try:
        res=tmdb(ep, query=title, language='ko-KR')
        results=res.get('results',[])
        if not results:
            # 별칭(영문)으로 재시도
            alias=next((r2[ix['title_aliases']].split(';')[0].strip() for r2 in rows[1:] if r2[ix['title']].strip()==title and r2[ix['title_aliases']].strip()), None)
            if alias:
                res=tmdb(ep, query=alias, language='ko-KR'); results=res.get('results',[])
        if results:
            m=results[0]
            mid=m['id']
            name=m.get('title') or m.get('name','')
            year=(m.get('release_date') or m.get('first_air_date') or '')[:4]
            poster='https://image.tmdb.org/t/p/w500'+m['poster_path'] if m.get('poster_path') else ''
            directors=[]
            if is_movie:
                cr=tmdb(f'/movie/{mid}/credits', language='ko-KR')
                directors=[c['name'] for c in cr.get('crew',[]) if c.get('job')=='Director']
            else:
                cr=tmdb(f'/tv/{mid}/aggregate_credits', language='ko-KR')
                for c in cr.get('crew',[]):
                    for j in c.get('jobs',[]):
                        if j.get('job')=='Director': directors.append(c['name']); break
                if not directors:
                    det=tmdb(f'/tv/{mid}', language='ko-KR')
                    directors=[p['name'] for p in det.get('created_by',[])]
            rec=[title,cat,name,year,';'.join(dict.fromkeys(directors)),poster,'ok']
            ok+=1
    except Exception as e:
        rec[6]=f'err:{type(e).__name__}'
    out.append(rec)
    if i%25==0:
        with open(OUT,'w',encoding='utf-8-sig',newline='') as f: csv.writer(f).writerows(out)
        print(f'{i}/{len(works)} ok={ok}', flush=True)
    time.sleep(0.15)
with open(OUT,'w',encoding='utf-8-sig',newline='') as f: csv.writer(f).writerows(out)
print(f'완료: {len(works)}작품 | 매칭 {ok}', flush=True)
