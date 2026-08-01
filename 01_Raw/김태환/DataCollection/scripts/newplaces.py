#!/usr/bin/env python
"""MZ2AZ-141 보강 — v4 에 없는 신규 성지 후보 역추출.

v1·v2 필터는 v4 를 모집단으로 고정해서, 블로그에 자주 나오지만 v4 에 없는
장소는 통째로 빠졌다(예: 선재 업고 튀어 '행리단길' 30글). 그 구멍을 메운다.

읽기: 정승길 v4 (수정하지 않음).  쓰기: 01_Raw/김태환/DataCollection/ 만.
"""
import csv, json, os, re
from collections import defaultdict, Counter

BASE = os.path.dirname(os.path.abspath(__file__))
V4 = "/Users/setgee/Desktop/github/mz2az/01_Raw/정승길/data/result/촬영지_TOP_v4_MVP1.csv"
CORPUS = f"{BASE}/corpus"
OUTS = ["/Users/setgee/Desktop/github/mz2az/01_Raw/김태환/DataCollection",
        "/Users/setgee/orca/workspaces/mz2az/141_성지장소필터링-인기도에따라/01_Raw/김태환/DataCollection"]
STAMP = "2026-08-01"

PUNCT = re.compile(r"[\s,·:\-–—!?'\"“”‘’()\[\]]+")
NORM = re.compile(r"[^0-9a-z가-힣]+")

# 장소임이 비교적 분명한 접미사만 쓴다 (리·사·동 처럼 일반어와 겹치는 건 제외)
SUFFIX = ["해수욕장", "해변", "전망대", "수목원", "미술관", "박물관", "도서관", "체육관",
          "저수지", "휴게소", "폭포", "계곡", "터널", "대교", "공원", "시장", "카페",
          "대학교", "초등학교", "중학교", "고등학교", "병원", "성당", "교회", "타워",
          "호수", "산성", "서원", "향교", "고택", "한옥마을", "벽화마을", "출렁다리",
          "전망공원", "생태공원", "유원지", "방파제", "등대", "항구", "포구", "스튜디오",
          "테마파크", "랜드", "리조트", "펜션", "온천", "약수터", "계단", "육교", "광장",
          "정류장", "터미널", "공항", "산성", "궁", "탑", "항", "역", "길"]
SUF_RE = re.compile(r"[가-힣A-Za-z0-9]{2,7}(?:" + "|".join(SUFFIX) + r")")

CUE = ["촬영", "성지", "나온", "나오는", "등장", "배경", "찍은", "찍었", "명장면", "무대탐방"]
WINDOW = 100

# 접미사 규칙에 걸리지만 장소가 아닌 말
NOISE = {
    "볼거리", "먹거리", "즐길거리", "이야기", "카테고리", "인테리어", "베이커리", "아메리카노",
    "고속도로", "지하철역", "전철역", "버스정류장", "고속터미널", "종합터미널", "국제공항",
    "우리집", "이곳", "그곳", "저곳", "여기", "거기", "요즘", "오늘", "내일", "어제",
    "블로그", "인스타그램", "유튜브", "네이버", "카카오", "구글", "포스팅", "리뷰",
    "주차장", "화장실", "편의점", "매표소", "안내소", "입구", "출구", "정문", "후문",
    "드라마", "영화", "촬영지", "성지순례", "여행코스", "가볼만한곳", "데이트코스",
    "간이역", "루프탑", "이스타항", "폐역", "종착역", "환승역", "출발역", "도착역",
}
NOISE_SUB = ["광역", "거리", "이야기", "리어", "리카", "니다", "습니", "해요", "어요", "구독", "이웃",
             "감사", "안녕", "포스", "사진", "정보", "추천", "후기", "방문", "위치", "예약"]


def norm(s):
    return NORM.sub("", s.lower())


def title_key(t):
    return PUNCT.sub("", t)


def author_of(url):
    m = re.match(r"https?://blog\.naver\.com/([^/?]+)/", url)
    if m:
        return "naver:" + m.group(1)
    m = re.match(r"https?://([a-z0-9-]+)\.tistory\.com/", url)
    return "tistory:" + m.group(1) if m else url


def v4_keys(place_name):
    keys = []
    base = re.sub(r"\([^)]*\)", "", place_name).strip()
    for c in (base, place_name):
        n = norm(c)
        if n and len(n) >= 2:
            keys.append(n)
    for a in re.findall(r"\(([^)]*)\)", place_name):
        n = norm(a)
        if n and len(n) >= 2:
            keys.append(n)
    return keys


ROADFRAG = re.compile(r"(\d+번길$|로\d+길$|길\d+$)")


def looks_bad(n, raw):
    if n in NOISE or len(n) < 3 or len(n) > 14:
        return True
    if ROADFRAG.search(n):          # 화서문로48번길 같은 주소 조각
        return True
    if any(b in n for b in NOISE_SUB):
        return True
    if n.isdigit() or re.fullmatch(r"[0-9]+.*", n):
        return True
    return False


def main():
    rows = list(csv.DictReader(open(V4, encoding="utf-8-sig")))
    by = defaultdict(list)
    for r in rows:
        by[title_key(r["title"])].append(r)

    out = []
    for ti, (key, group) in enumerate(sorted(by.items()), 1):
        safe = re.sub(r"[^\w가-힣]", "_", key)[:60] or "untitled"
        path = f"{CORPUS}/{safe}.jsonl"
        if not os.path.exists(path):
            continue
        docs = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                if d["url"] == "__search_snippets__":
                    continue
                d["norm"] = norm(d["text"])
                d["author"] = author_of(d["url"])
                docs.append(d)
        if not docs:
            continue

        known = set()
        for r in group:
            known.update(v4_keys(r["place_name"]))
        nkey = norm(key)

        df, authors, cue_df, title_df, ex = Counter(), defaultdict(set), Counter(), Counter(), {}
        for d in docs:
            seen, seen_cue = set(), set()
            for m in SUF_RE.findall(d["text"]):
                n = norm(m)
                if looks_bad(n, m):
                    continue
                if nkey and (n in nkey or nkey in n):   # 작품명 조각 제외
                    continue
                if any(k in n or n in k for k in known):  # v4 에 이미 있음
                    continue
                seen.add(n)
                ex.setdefault(n, m)
                i = d["norm"].find(n)
                if i >= 0:
                    win = d["norm"][max(0, i - WINDOW): i + len(n) + WINDOW]
                    if any(c in win for c in CUE):
                        seen_cue.add(n)
            for n in seen:
                df[n] += 1
                authors[n].add(d["author"])
            for n in seen_cue:
                cue_df[n] += 1
            nt = norm(d.get("title", ""))
            for n in seen:
                if n in nt:              # 글 제목에 뜨면 그 글의 목적지다
                    title_df[n] += 1

        for n, c in df.most_common():
            if cue_df[n] >= 3 and len(authors[n]) >= 3 and title_df[n] >= 1:
                out.append({
                    "title_key": key,
                    "title_표기": group[0]["title"],
                    "category": group[0]["title_category"],
                    "후보_장소명": ex[n],
                    "정규화": n,
                    "언급_글수": c,
                    "촬영단서_글수": cue_df[n],
                    "제목등장_글수": title_df[n],
                    "저자수": len(authors[n]),
                    "corpus_글수": len(docs),
                })
        if ti % 40 == 0:
            print(f"  {ti}/{len(by)}", flush=True)

    out.sort(key=lambda x: (-x["촬영단서_글수"], -x["저자수"], x["title_key"]))
    for o in OUTS:
        os.makedirs(o, exist_ok=True)
        with open(f"{o}/신규성지후보_v4미등재_{STAMP}.csv", "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
            w.writeheader()
            w.writerows(out)
    print(json.dumps({"후보수": len(out), "작품수": len({x['title_key'] for x in out})},
                     ensure_ascii=False, indent=2))
    print("\n=== 상위 25 ===")
    for x in out[:25]:
        print(f"  {x['촬영단서_글수']:>3}글/{x['저자수']:>2}명  [{x['title_표기']}] {x['후보_장소명']}")


if __name__ == "__main__":
    main()
