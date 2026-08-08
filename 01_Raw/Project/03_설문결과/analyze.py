#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SceneTrip survey re-analysis: 88 responses (was 69).
Replicates 정권호's 2026-08-01 methodology so numbers are comparable."""
import csv, collections, sys

def load(p):
    r = list(csv.reader(open(p, encoding='utf-8-sig')))
    return r[0], r[1:]

H, ROWS_NEW = load('new.csv')
_, ROWS_OLD = load('old.csv')
OLDKEYS = set(tuple(x) for x in ROWS_OLD)
ROWS_DELTA = [x for x in ROWS_NEW if tuple(x) not in OLDKEYS]

# column indices
C_TS=0; C_FOLLOW=1; C_STAGE=2
C_STORY_T=3; C_MAPAPP=4; C_FRUST=5; C_WISH=6; C_STORY_P=7
C_BLOCK=8; C_UNAPPEAL=9
C_WHERE_A=10; C_TIME_A=11; C_RECENT_A=12; C_HAPPEN_A=13
C_ROUTE=14
C_WHERE_B=15; C_TIME_B=16; C_RECENT_B=17; C_HAPPEN_B=18
C_FEAT=19; C_PAID=20; C_STYLE=21; C_PRICE=22
C_AGE=23; C_GENDER=24; C_LIVE=25; C_EMAIL=26

def multi(v):
    return [x.strip() for x in v.split(';') if x.strip()]

def merged(r, a, b):
    """branch-merged column"""
    return r[a].strip() or r[b].strip()

def counts(rows, idx, multivalue=True, merge=None):
    c = collections.Counter(); n = 0
    for r in rows:
        v = merged(r, *merge) if merge else r[idx].strip()
        if not v: continue
        n += 1
        c.update(multi(v) if multivalue else [v])
    return c, n

def show(title, c, n, top=20):
    print(f'\n--- {title}  (n={n})')
    for k, v in c.most_common(top):
        print(f'  {v:3d}  {v/n*100:5.1f}%  {k[:95]}')

STAGE_VISIT = ['I’ve been to Korea in the past 5 years', 'I’ve been to Korea in the past 3 years']
STAGE_NOPLAN = 'I want to go but have no concrete plan yet'
STAGE_BOOKED = 'I have a trip booked or actively planned'
STAGE_NONE = 'Not interested in visiting'

def stage(r):
    s = r[C_STAGE].strip()
    if s in STAGE_VISIT: return 'visited'
    if s == STAGE_NOPLAN: return 'noplan'
    if s == STAGE_BOOKED: return 'booked'
    return 'uninterested'

def region(v):
    v = v.strip()
    return v

def analyze(rows, label):
    print('\n' + '=' * 78)
    print(f'### {label}  (N={len(rows)})')
    print('=' * 78)

    st = collections.Counter(stage(r) for r in rows)
    print('\n--- 여행 단계')
    for k, v in st.most_common():
        print(f'  {v:3d}  {v/len(rows)*100:5.1f}%  {k}')

    valid = [r for r in rows if stage(r) != 'uninterested']
    print(f'\n유효 응답(관심없음 제외) = {len(valid)}')

    for t, idx, mv, mg in [
        ('팔로우 콘텐츠', C_FOLLOW, True, None),
        ('나이', C_AGE, False, None),
        ('성별', C_GENDER, False, None),
        ('거주', C_LIVE, False, None),
        ('겪은 문제 (페인포인트)', None, True, (C_HAPPEN_A, C_HAPPEN_B)),
        ('어디서 찾나', None, True, (C_WHERE_A, C_WHERE_B)),
        ('한 곳 찾는 데 걸린 시간', None, False, (C_TIME_A, C_TIME_B)),
        ('원하는 기능 (최대 3)', C_FEAT, True, None),
        ('여행 스타일', C_STYLE, False, None),
        ('1일 코스 지불 의사', C_PRICE, False, None),
        ('지불 경험', C_PAID, True, None),
        ('하루 동선 짜는 법', C_ROUTE, False, None),
        ('여행 중 쓴 지도앱', C_MAPAPP, True, None),
        ('현장에서 답답했던 것', C_FRUST, True, None),
    ]:
        c, n = counts(valid, idx, mv, mg)
        show(t, c, n)

    # 언어장벽 x 정보분산 교차
    LANG = 'Language barrier blocked me (Korean-only info)'
    SCAT = 'Hard to find—information was too scattered.'
    both = lang = scat = either = 0
    hp = 0
    for r in valid:
        v = merged(r, C_HAPPEN_A, C_HAPPEN_B)
        if not v: continue
        hp += 1
        s = multi(v)
        l, sc = LANG in s, SCAT in s
        lang += l; scat += sc; both += (l and sc); either += (l or sc)
    print(f'\n--- 언어장벽 x 정보분산 (문항 응답 n={hp})')
    print(f'  언어장벽 {lang} · 정보분산 {scat} · 동시 {both} · 둘 중 하나라도 {either} ({either/hp*100:.0f}%)')

    # 스타일 x 단계 교차
    print('\n--- 여행 스타일 × 여행 단계')
    tab = collections.defaultdict(collections.Counter)
    for r in valid:
        s = r[C_STYLE].strip()
        if s: tab[s][stage(r)] += 1
    print(f'  {"스타일":<58} {"방문":>4}{"계획없음":>7}{"예약":>5}')
    for s, c in sorted(tab.items(), key=lambda x: -sum(x[1].values())):
        print(f'  {s[:56]:<58} {c["visited"]:>4}{c["noplan"]:>7}{c["booked"]:>5}')

    # 루트 관련 3기능 중 하나라도
    ROUTE_FEATS = ['An AI that builds my day route around the spots I pick',
                   'Community: fan tips, visit proof, route sharing',
                   'Ready-made fan courses I can just follow (e.g. "Queen of Tears 1-Day Course")']
    fn = any_route = 0
    for r in valid:
        v = r[C_FEAT].strip()
        if not v: continue
        fn += 1
        s = multi(v)
        if any(f in s for f in ROUTE_FEATS): any_route += 1
    print(f'\n--- 루트 관련 기능 3개 중 하나라도: {any_route}/{fn} ({any_route/fn*100:.0f}%)')

    # 지불의사 $11+
    HIGH = ['$11-15', '$16-20']
    pn = high = 0
    for r in valid:
        v = r[C_PRICE].strip()
        if not v: continue
        pn += 1
        if v in HIGH: high += 1
    print(f'--- $11 이상 지불 의사: {high}/{pn} ({high/pn*100:.0f}%)')

    return valid

def personas(valid):
    print('\n' + '=' * 78)
    print('### 페르소나 재계산 (여행 단계 × 여행 스타일)')
    print('=' * 78)
    CUSTOM = 'A customized baseline: I want a pre-made route, but I need the flexibility to tweak and adjust it easily.'
    DIY = '100% DIY: I prefer researching and building my own route from scratch.'
    SPON = 'Spontaneous: I just pin places on a map and go without a fixed plan.'
    FULL = "A pre-made itinerary: I'd rather follow a fully planned route made by experts or fans."
    NONE_HAPPENED = 'None of these'

    # 정권호 원본과 동일하게 상호배타적이지 않은 정의를 쓴다 (P4는 P1~P3와 겹칠 수 있다)
    P = {'P1': [], 'P2': [], 'P3': [], 'P4': []}
    unclassified = []
    for r in valid:
        s = stage(r); sty = r[C_STYLE].strip()
        hv = multi(merged(r, C_HAPPEN_A, C_HAPPEN_B))
        no_pain = (hv == [NONE_HAPPENED])
        planning = s == 'noplan'  # 정권호 원본 §2.2 표와 동일하게 '예약'은 제외한다
        hit = False
        if planning and sty == CUSTOM: P['P1'].append(r); hit = True
        if s == 'visited' and sty in (SPON, DIY): P['P2'].append(r); hit = True
        if planning and sty == FULL: P['P3'].append(r); hit = True
        if planning and no_pain: P['P4'].append(r); hit = True
        if not hit: unclassified.append(r)

    for k in ['P1', 'P2', 'P3', 'P4']:
        print(f'  {k}: {len(P[k])}  ({len(P[k])/len(valid)*100:.0f}%)')
    print(f'  어디에도 안 걸림: {len(unclassified)}  ({len(unclassified)/len(valid)*100:.0f}%)')
    print(f'  P4 ∩ (P1/P2/P3): {sum(1 for r in P["P4"] if any(r in P[k] for k in ["P1","P2","P3"]))}')

    for k in ['P1', 'P2', 'P3', 'P4']:
        rows = P[k]
        print(f'\n===== {k}  n={len(rows)}')
        for t, idx, mv, mg in [
            ('원하는 기능', C_FEAT, True, None),
            ('겪은 문제', None, True, (C_HAPPEN_A, C_HAPPEN_B)),
            ('어디서 찾나', None, True, (C_WHERE_A, C_WHERE_B)),
            ('지불 의사', C_PRICE, False, None),
            ('거주', C_LIVE, False, None),
            ('나이', C_AGE, False, None),
        ]:
            c, n = counts(rows, idx, mv, mg)
            if n: show(t, c, n, 8)
    return P

if __name__ == '__main__':
    v_new = analyze(ROWS_NEW, '전체 88건 (갱신본)')
    personas(v_new)
    analyze(ROWS_DELTA, '신규 19건만 (7/25~8/02)')
