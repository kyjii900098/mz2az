#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""사전 지정 가설 5개만 검정한다 (다중비교 낚시를 피하려고 항목을 미리 고정)."""
import analyze as A
import math

V = [r for r in A.ROWS_NEW if A.stage(r) != 'uninterested']

def z2p(z): return math.erfc(abs(z) / math.sqrt(2))
def zt(k1, n1, k2, n2):
    p1, p2 = k1/n1, k2/n2
    p = (k1+k2)/(n1+n2)
    se = math.sqrt(p*(1-p)*(1/n1+1/n2))
    if se == 0: return 0.0, 1.0
    return (p1-p2)/se, z2p((p1-p2)/se)

AI = 'An AI that builds my day route around the spots I pick'
MAP = 'A map with verified visit info (open now? how to get there?)'
STY = {
    'A customized baseline: I want a pre-made route, but I need the flexibility to tweak and adjust it easily.': '커스터마이즈',
    '100% DIY: I prefer researching and building my own route from scratch.': 'DIY',
    'Spontaneous: I just pin places on a map and go without a fixed plan.': '즉흥',
    "A pre-made itinerary: I'd rather follow a fully planned route made by experts or fans.": '완성형',
}
HI = ('$11-15', '$16-20')
vis = lambda r: A.stage(r) == 'visited'
pain_v = lambda r: A.merged(r, A.C_HAPPEN_A, A.C_HAPPEN_B)

print('=== H1. 완성형 코스 선호 × 방한 경험 ===')
full = [r for r in V if STY.get(r[A.C_STYLE].strip()) == '완성형']
oth = [r for r in V if STY.get(r[A.C_STYLE].strip()) in ('커스터마이즈', 'DIY', '즉흥')]
a, b = sum(map(vis, full)), sum(map(vis, oth))
_, p = zt(a, len(full), b, len(oth))
print(f'  완성형 방문 {a}/{len(full)} ({a/len(full)*100:.0f}%) vs 나머지 {b}/{len(oth)} ({b/len(oth)*100:.0f}%)   p={p:.4f}')

print('=== H2. AI 동선 선택 × 방한 경험 ===')
ai = [r for r in V if AI in A.multi(r[A.C_FEAT])]
nai = [r for r in V if r[A.C_FEAT].strip() and AI not in A.multi(r[A.C_FEAT])]
a, b = sum(map(vis, ai)), sum(map(vis, nai))
_, p = zt(a, len(ai), b, len(nai))
print(f'  AI 고름 방문 {a}/{len(ai)} ({a/len(ai)*100:.0f}%) vs 안 고름 {b}/{len(nai)} ({b/len(nai)*100:.0f}%)   p={p:.4f}')

print('=== H3. $11+ 지불 의사 × 방한 경험 ===')
def hi(rows):
    n = k = 0
    for r in rows:
        v = r[A.C_PRICE].strip()
        if v: n += 1; k += v in HI
    return k, n
vv = [r for r in V if vis(r)]
nn = [r for r in V if A.stage(r) == 'noplan']
k1, n1 = hi(vv); k2, n2 = hi(nn)
_, p = zt(k1, n1, k2, n2)
print(f'  방문자 {k1}/{n1} ({k1/n1*100:.0f}%) vs 계획없음 {k2}/{n2} ({k2/n2*100:.0f}%)   p={p:.4f}')

print('=== H4. 언어장벽 × 정보분산 독립성 ===')
L = 'Language barrier blocked me (Korean-only info)'
S = 'Hard to find—information was too scattered.'
n = l = s = both = 0
for r in V:
    v = pain_v(r)
    if not v: continue
    n += 1
    x = A.multi(v); a1, b1 = L in x, S in x
    l += a1; s += b1; both += a1 and b1
exp = l*s/n
print(f'  n={n}  언어={l}  분산={s}  실제 겹침={both}  독립가정 기대 겹침={exp:.1f}')
print(f'  → 겹침이 기대보다 {both-exp:+.1f}명.  둘 중 하나라도={l+s-both} ({(l+s-both)/n*100:.0f}%)')

print('=== H5. 페인 겪은 적 없음 × 지도 선호 ===')
def has(rows, f):
    n = k = 0
    for r in rows:
        v = A.multi(r[A.C_FEAT])
        if v: n += 1; k += f in v
    return k, n
pn = [r for r in V if A.multi(pain_v(r)) == ['None of these']]
py = [r for r in V if pain_v(r).strip() and A.multi(pain_v(r)) != ['None of these']]
k1, n1 = has(pn, MAP); k2, n2 = has(py, MAP)
_, p = zt(k1, n1, k2, n2)
print(f'  페인 없음 지도 {k1}/{n1} ({k1/n1*100:.0f}%) vs 페인 있음 {k2}/{n2} ({k2/n2*100:.0f}%)   p={p:.4f}')

print('\n--- 사전 지정 5건 기준 본페로니 임계 = 0.010')
