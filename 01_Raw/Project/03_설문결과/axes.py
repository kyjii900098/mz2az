#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""축 후보 검증: 어떤 분할 변수가 기능 니즈/지불 의사를 실제로 가르는가."""
import analyze as A
import collections

VALID = [r for r in A.ROWS_NEW if A.stage(r) != 'uninterested']

FEATS = {
    '지도': 'A map with verified visit info (open now? how to get there?)',
    '검색': 'Search every filming location by show, artist, or scene',
    'AI동선': 'An AI that builds my day route around the spots I pick',
    '커뮤니티': 'Community: fan tips, visit proof, route sharing',
    '포토': 'Photo-spot guides (exact angle from the scene)',
    '기성코스': 'Ready-made fan courses I can just follow (e.g. "Queen of Tears 1-day course")',
}
HIGH = ('$11-15', '$16-20')
PAIN = {
    '언어': 'Language barrier blocked me (Korean-only info)',
    '분산': 'Hard to find—information was too scattered.',
    '주소': 'Couldn’t find the exact address',
    '오래됨': 'Info was outdated (place closed or changed)',
    '교통': 'Couldn’t figure out transport to get there',
    '헛걸음': 'Got there, but nothing else to do nearby — wasted trip',
    '없음': 'None of these',
}

def profile(rows):
    n = len(rows)
    if n == 0: return None
    f = collections.Counter()
    fn = 0
    for r in rows:
        v = A.multi(r[A.C_FEAT])
        if v:
            fn += 1
            for k, s in FEATS.items():
                if s in v: f[k] += 1
    pn = hi = 0
    for r in rows:
        p = r[A.C_PRICE].strip()
        if p:
            pn += 1
            hi += p in HIGH
    pain = collections.Counter(); pnn = 0
    for r in rows:
        v = A.multi(A.merged(r, A.C_HAPPEN_A, A.C_HAPPEN_B))
        if v:
            pnn += 1
            for k, s in PAIN.items():
                if s in v: pain[k] += 1
    return dict(n=n, fn=fn, feat={k: f[k]/fn*100 if fn else 0 for k in FEATS},
                pay=hi/pn*100 if pn else 0, pn=pn,
                pain={k: pain[k]/pnn*100 if pnn else 0 for k in PAIN})

def split(name, keyfn, minn=15):
    groups = collections.defaultdict(list)
    for r in VALID:
        k = keyfn(r)
        if k: groups[k].append(r)
    groups = {k: v for k, v in groups.items() if len(v) >= minn}
    if len(groups) < 2: return
    print(f'\n{"="*100}\n## 축 후보: {name}')
    hdr = f'{"그룹":<26}{"n":>4}' + ''.join(f'{k:>9}' for k in FEATS) + f'{"$11+":>8}'
    print(hdr)
    prof = {}
    for k, v in sorted(groups.items(), key=lambda x: -len(x[1])):
        p = profile(v); prof[k] = p
        line = f'{k[:24]:<26}{p["n"]:>4}' + ''.join(f'{p["feat"][x]:>8.0f}%' for x in FEATS) + f'{p["pay"]:>7.0f}%'
        print(line)
    # 최대-최소 스프레드 = 이 축이 얼마나 가르는가
    spread = {}
    for x in list(FEATS) + ['$11+']:
        vals = [prof[k]['feat'][x] if x in FEATS else prof[k]['pay'] for k in prof]
        spread[x] = max(vals) - min(vals)
    print(f'{"→ 최대-최소 격차(%p)":<26}{"":>4}' + ''.join(f'{spread[x]:>8.0f}p' for x in FEATS) + f'{spread["$11+"]:>7.0f}p')
    print(f'   평균 격차: {sum(spread.values())/len(spread):.1f}%p')

STYLE = {
    'A customized baseline: I want a pre-made route, but I need the flexibility to tweak and adjust it easily.': '커스터마이즈',
    '100% DIY: I prefer researching and building my own route from scratch.': 'DIY',
    'Spontaneous: I just pin places on a map and go without a fixed plan.': '즉흥',
    "A pre-made itinerary: I'd rather follow a fully planned route made by experts or fans.": '완성형',
}

def follow_key(r):
    v = A.multi(r[A.C_FOLLOW])
    d = 'K-dramas' in v; k = 'K-pop (artists, MVs)' in v
    if d and k: return '드라마+K-pop'
    if d: return '드라마만'
    if k: return 'K-pop만'
    return None

split('나이', lambda r: r[A.C_AGE].strip() or None)
split('거주 지역', lambda r: r[A.C_LIVE].strip() or None)
split('콘텐츠 종류', follow_key)
split('성별', lambda r: r[A.C_GENDER].strip() or None)
split('여행 단계', lambda r: A.stage(r))
split('여행 스타일', lambda r: STYLE.get(r[A.C_STYLE].strip()))
split('페인 경험 유무', lambda r: (
    None if not A.merged(r, A.C_HAPPEN_A, A.C_HAPPEN_B).strip()
    else ('페인 없음' if A.multi(A.merged(r, A.C_HAPPEN_A, A.C_HAPPEN_B)) == ['None of these'] else '페인 있음')))
split('탐색 소요시간', lambda r: A.merged(r, A.C_TIME_A, A.C_TIME_B).strip() or None)
