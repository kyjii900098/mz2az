#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""(1) 축별 격차가 표본오차를 넘는지 검정  (2) 데이터 주도 군집화"""
import analyze as A
import collections, math, itertools

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

def z2p(z):
    """양측 p-value (정규근사)"""
    return math.erfc(abs(z) / math.sqrt(2))

def ztest(k1, n1, k2, n2):
    if n1 == 0 or n2 == 0: return 0.0, 1.0
    p1, p2 = k1/n1, k2/n2
    p = (k1+k2)/(n1+n2)
    se = math.sqrt(p*(1-p)*(1/n1+1/n2))
    if se == 0: return 0.0, 1.0
    z = (p1-p2)/se
    return z, z2p(z)

STYLE = {
    'A customized baseline: I want a pre-made route, but I need the flexibility to tweak and adjust it easily.': '커스터마이즈',
    '100% DIY: I prefer researching and building my own route from scratch.': 'DIY',
    'Spontaneous: I just pin places on a map and go without a fixed plan.': '즉흥',
    "A pre-made itinerary: I'd rather follow a fully planned route made by experts or fans.": '완성형',
}

AXES = {
    '여행 단계': lambda r: A.stage(r) if A.stage(r) in ('noplan', 'visited') else None,
    '여행 스타일': lambda r: STYLE.get(r[A.C_STYLE].strip()),
    '거주 지역': lambda r: r[A.C_LIVE].strip() or None,
    '나이': lambda r: r[A.C_AGE].strip() or None,
    '성별': lambda r: r[A.C_GENDER].strip() or None,
    '페인 경험': lambda r: (None if not A.merged(r, A.C_HAPPEN_A, A.C_HAPPEN_B).strip()
                        else ('페인없음' if A.multi(A.merged(r, A.C_HAPPEN_A, A.C_HAPPEN_B)) == ['None of these'] else '페인있음')),
}

print('=' * 96)
print('## 1. 어떤 격차가 표본오차를 넘는가 (n>=15 그룹끼리, 양측 z검정)')
print('=' * 96)
print(f'{"축":<12}{"그룹 A":<18}{"그룹 B":<18}{"항목":<10}{"A":>8}{"B":>8}{"격차":>7}{"p":>8}  판정')
sig_rows = []
for axname, keyfn in AXES.items():
    g = collections.defaultdict(list)
    for r in VALID:
        k = keyfn(r)
        if k: g[k].append(r)
    g = {k: v for k, v in g.items() if len(v) >= 15}
    for a, b in itertools.combinations(sorted(g, key=lambda x: -len(g[x])), 2):
        for fname, fstr in list(FEATS.items()) + [('$11+', None)]:
            def cnt(rows):
                k = n = 0
                for r in rows:
                    if fstr is None:
                        v = r[A.C_PRICE].strip()
                        if v: n += 1; k += v in HIGH
                    else:
                        v = A.multi(r[A.C_FEAT])
                        if v: n += 1; k += fstr in v
                return k, n
            k1, n1 = cnt(g[a]); k2, n2 = cnt(g[b])
            z, p = ztest(k1, n1, k2, n2)
            gap = abs(k1/n1 - k2/n2) * 100 if n1 and n2 else 0
            mark = '★ 유의' if p < 0.05 else ('· 경계' if p < 0.10 else '')
            if p < 0.10:
                sig_rows.append((axname, a, b, fname, k1/n1*100, k2/n2*100, gap, p, mark))
for row in sorted(sig_rows, key=lambda x: x[7]):
    axname, a, b, fname, p1, p2, gap, p, mark = row
    print(f'{axname:<12}{a[:16]:<18}{b[:16]:<18}{fname:<10}{p1:>7.0f}%{p2:>7.0f}%{gap:>6.0f}p{p:>8.3f}  {mark}')
if not sig_rows:
    print('  → p<0.10을 넘는 조합이 하나도 없다.')
print(f'\n검정한 조합 수 대비 p<0.05 = {sum(1 for r in sig_rows if r[7]<0.05)}건')

print('\n' + '=' * 96)
print('## 2. 데이터 주도 군집화 — 기능 선택 6개 이진벡터, 자카드 거리 + 평균연결 계층군집')
print('=' * 96)

pts = []
for r in VALID:
    v = A.multi(r[A.C_FEAT])
    if not v: continue
    vec = tuple(1 if FEATS[k] in v else 0 for k in FEATS)
    if sum(vec) == 0: continue
    pts.append((vec, r))

def jac(a, b):
    inter = sum(x and y for x, y in zip(a, b))
    uni = sum(x or y for x, y in zip(a, b))
    return 1 - inter/uni if uni else 1.0

clusters = [[i] for i in range(len(pts))]
D = {(i, j): jac(pts[i][0], pts[j][0]) for i in range(len(pts)) for j in range(i+1, len(pts))}
def cdist(c1, c2):
    return sum(D[(min(i, j), max(i, j))] for i in c1 for j in c2) / (len(c1)*len(c2))

while len(clusters) > 4:
    best = None
    for i, j in itertools.combinations(range(len(clusters)), 2):
        d = cdist(clusters[i], clusters[j])
        if best is None or d < best[0]: best = (d, i, j)
    _, i, j = best
    clusters[i] = clusters[i] + clusters[j]
    del clusters[j]

clusters.sort(key=len, reverse=True)
print(f'\n{"군집":<6}{"n":>4}  ' + ''.join(f'{k:>9}' for k in FEATS) + f'{"$11+":>8}{"방문%":>7}{"커스텀%":>8}')
for ci, c in enumerate(clusters, 1):
    rows = [pts[i][1] for i in c]
    fv = [pts[i][0] for i in c]
    feats = [sum(v[k] for v in fv)/len(fv)*100 for k in range(len(FEATS))]
    pn = hi = 0
    for r in rows:
        v = r[A.C_PRICE].strip()
        if v: pn += 1; hi += v in HIGH
    vis = sum(1 for r in rows if A.stage(r) == 'visited')/len(rows)*100
    cus = sum(1 for r in rows if STYLE.get(r[A.C_STYLE].strip()) == '커스터마이즈')/len(rows)*100
    print(f'C{ci:<5}{len(c):>4}  ' + ''.join(f'{x:>8.0f}%' for x in feats)
          + f'{hi/pn*100 if pn else 0:>7.0f}%{vis:>6.0f}%{cus:>7.0f}%')

print('\n--- 군집이 기존 축과 겹치는가 (카이제곱 대신 분포로 확인)')
for ci, c in enumerate(clusters, 1):
    rows = [pts[i][1] for i in c]
    st = collections.Counter(A.stage(r) for r in rows)
    sy = collections.Counter(STYLE.get(r[A.C_STYLE].strip(), '무응답') for r in rows)
    print(f'  C{ci} (n={len(c)}) 단계 {dict(st)} | 스타일 {dict(sy)}')
