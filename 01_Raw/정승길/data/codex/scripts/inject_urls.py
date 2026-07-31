#!/usr/bin/env python3
"""네이버/카카오 URL 배치 결과를 본체 2개 CSV에 주입한다.

규칙:
- 네이버: match_confidence=high(사후검증 통과분)만 place_naver_url을 진짜 링크로 교체.
  high가 아닌 행의 기존 '검색형' URL(map.naver.com/p/search/…)은 삭제(빈칸) — 가짜 링크를 남기지 않는다.
  좌표가 빈 행은 naver_lat/lng로 보충.
- 카카오: high만 place_kakao_url 주입(kakao_url). 좌표 빈 행은 kakao_lat/lng로 보충(네이버 보충이 먼저면 유지).
- 기본 드라이런. --apply 시 백업(codex/backup_url_YYYYMMDD/) 후 저장.
"""
import csv, sys, shutil, datetime
from pathlib import Path

DATA = Path(__file__).resolve().parents[2]
BODIES = [DATA/'드라마_kdramamap_스키마.csv', DATA/'촬영지_마스터.csv']
NAVER = DATA/'조합작업'/'place_url_네이버.csv'
KAKAO = DATA/'조합작업'/'TOP120완성'/'카카오결과.csv'

def load(p): return list(csv.reader(open(p, encoding='utf-8-sig')))
def key(name, addr): return (name.strip(), addr.strip())

def main():
    apply = '--apply' in sys.argv
    # 네이버 결과: (name,addr) -> (url, lat, lng) high만
    nv = {}
    if NAVER.exists():
        rows = load(NAVER)
        for r in rows[1:]:
            if len(r) > 8 and r[8] == 'high' and r[5].strip():
                nv[key(r[0], r[1])] = (r[5].strip(), r[6].strip(), r[7].strip())
    # 카카오 결과: id -> (url, lat, lng) high만
    kk = {}
    if KAKAO.exists():
        rows = load(KAKAO)
        for r in rows[1:]:
            if len(r) > 6 and r[6] == 'high' and r[3].strip():
                kk[r[0]] = (r[3].strip(), r[4].strip(), r[5].strip())
    print(f'네이버 high(url 有): {len(nv)} 콤보 / 카카오 high: {len(kk)} 행')

    stamp = datetime.datetime.now().strftime('%Y%m%d')
    for body in BODIES:
        rows = load(body)
        h = rows[0]; ix = {c: h.index(c) for c in h}
        stats = dict(nv_replaced=0, nv_cleared=0, kk_injected=0, coord_filled=0)
        for r in rows[1:]:
            k = key(r[ix['place_name']], r[ix['place_address']])
            cur_nv = r[ix['place_naver_url']]
            hit = nv.get(k)
            if hit:
                if cur_nv != hit[0]:
                    r[ix['place_naver_url']] = hit[0]; stats['nv_replaced'] += 1
                if not r[ix['place_latitude']].strip() and hit[1]:
                    r[ix['place_latitude']], r[ix['place_longitude']] = hit[1], hit[2]
                    stats['coord_filled'] += 1
            elif '/p/search/' in cur_nv:
                # 배치 대상(TOP120·영화)만 가짜 링크 삭제 — 미시도 행은 회의 결정까지 보존
                is_target = (r[ix.get('famous_rank', 0)].strip() or r[ix.get('recent_rank', 0)].strip()
                             or r[ix['title_category']] == 'movie') if 'famous_rank' in ix else False
                if is_target:
                    r[ix['place_naver_url']] = ''; stats['nv_cleared'] += 1
            kh = kk.get(r[ix['id']])
            if kh and not r[ix['place_kakao_url']].strip():
                r[ix['place_kakao_url']] = kh[0]; stats['kk_injected'] += 1
                if not r[ix['place_latitude']].strip() and kh[1]:
                    r[ix['place_latitude']], r[ix['place_longitude']] = kh[1], kh[2]
                    stats['coord_filled'] += 1
        print(body.name, stats, '(드라이런)' if not apply else '')
        if apply:
            bdir = DATA/'codex'/f'backup_url_{stamp}'; bdir.mkdir(exist_ok=True)
            shutil.copy2(body, bdir/body.name)
            with open(body, 'w', encoding='utf-8-sig', newline='') as f:
                csv.writer(f).writerows(rows)
    if apply: print('적용 완료. 백업:', f'codex/backup_url_{stamp}/')

if __name__ == '__main__':
    main()
