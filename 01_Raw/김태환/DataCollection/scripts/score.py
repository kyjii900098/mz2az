#!/usr/bin/env python
"""MZ2AZ-141 — 2단계: 인기도 채점 · 성지 필터링 · scene_description 보완.

작품별 블로그 코퍼스에서 v4 의 place_name 이 몇 개의 글에 등장하는지 세고,
작품 내 상대빈도로 인기도를 매긴 뒤 상위 성지만 남긴다.
같은 패스에서 비어 있던 scene_description 을 글 본문 문장으로 채운다.
"""
import csv, json, os, re, sys
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
VAULT = "/Users/setgee/orca/workspaces/mz2az/141_성지장소필터링-인기도에따라"
V4 = f"{VAULT}/01_Raw/정승길/data/result/촬영지_TOP_v4_MVP1.csv"
CORPUS = f"{BASE}/corpus"
OUT = f"{VAULT}/01_Raw/김태환/DataCollection"
STAMP = "2026-08-01"

PUNCT = re.compile(r"[\s,·:\-–—!?'\"“”‘’()\[\]]+")
NORM = re.compile(r"[^0-9a-z가-힣]+")

# 이름만으로는 특정 장소를 가리키지 않는 말 — 오탐 방지용
STOP = {
    "서울", "부산", "인천", "대구", "광주", "대전", "울산", "제주", "경기", "강원", "세종",
    "충북", "충남", "전북", "전남", "경북", "경남", "제주도", "한국", "대한민국",
    "카페", "식당", "공원", "학교", "병원", "회사", "아파트", "호텔", "해변", "해수욕장",
    "바다", "도로", "거리", "광장", "마을", "시장", "골목", "다리", "터널", "빌딩", "건물",
    "세트장", "스튜디오", "촬영지", "기타", "미확인", "미상", "없음",
    "mbc", "sbs", "kbs", "jtbc", "tvn", "ocn", "ebs", "cgv", "메가박스", "롯데시네마",
}
# 장면 서술로 보이는 문장 가점 키워드
SCENE_KW = ["촬영", "장면", "씬", "나온", "나오는", "등장", "배경", "찍은", "찍었", "그곳",
            "주인공", "명장면", "에피소드", "회차", "대사", "고백", "첫만남", "재회"]
BAD_KW = ["구독", "이웃추가", "협찬", "체험단", "원고료", "제공받", "공동구매", "링크",
          "http", "www.", "예약금", "문의", "카카오톡", "댓글", "좋아요", "포스팅"]


def title_key(t):
    return PUNCT.sub("", t)


def norm(s):
    return NORM.sub("", s.lower())


def place_keys(place_name):
    """place_name → 본문에서 찾을 매칭 키 목록."""
    keys = []
    base = re.sub(r"\([^)]*\)", "", place_name).strip()  # 마곡중앙로(1) → 마곡중앙로
    for cand in (base, place_name):
        n = norm(cand)
        if n and n not in keys:
            keys.append(n)
    # 스타벅스 성수점 → 스타벅스성수
    m = re.sub(r"(본점|지점|점)$", "", base).strip()
    if m and norm(m) not in keys:
        keys.append(norm(m))
    # 윤치과(청진3리어민복지회관) → 괄호 안 별칭도 블로그에서 쓰인다
    for alias in re.findall(r"\(([^)]*)\)", place_name):
        n = norm(alias)
        if n and not n.isdigit() and n not in keys:
            keys.append(n)
    out = [k for k in keys if len(k) >= 3 and k not in STOP]
    return out


SIDO = ("서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원",
        "충북", "충남", "전북", "전남", "경북", "경남", "제주", "충청", "전라", "경상")


def in_korea(la, lo):
    return 33.0 <= la <= 38.7 and 124.5 <= lo <= 132.0


def fix_coords(r):
    """v4 에 위도·경도가 뒤바뀐 행이 있다(마더 10 · 지옥 8). 되돌리고 표시한다."""
    lat, lon = r["place_latitude"].strip(), r["place_longitude"].strip()
    if not (lat and lon):
        return ""
    try:
        la, lo = float(lat), float(lon)
    except ValueError:
        return "좌표파싱불가"
    if not in_korea(la, lo) and in_korea(lo, la):
        r["place_latitude"], r["place_longitude"] = lon, lat
        return "위경도뒤바뀜_교정"
    return ""


def is_overseas(r):
    """국내 여행 앱이므로 해외 로케이션은 기본 제외 — 7/31 회의 안건 3."""
    lat, lon = r["place_latitude"].strip(), r["place_longitude"].strip()
    if lat and lon:
        try:
            return not in_korea(float(lat), float(lon))
        except ValueError:
            pass
    a = r["place_address"].strip()
    return bool(a) and not a.startswith(SIDO)


def load_corpus(key):
    safe = re.sub(r"[^\w가-힣]", "_", key)[:60] or "untitled"
    path = f"{CORPUS}/{safe}.jsonl"
    if not os.path.exists(path):
        return []
    docs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            d["norm"] = norm(d["text"])
            docs.append(d)
    return docs


def split_segments(text):
    segs = []
    for line in text.split("\n"):
        for s in re.split(r"(?<=[.!?。])\s+|(?<=다\.)\s*", line):
            s = s.strip()
            if 15 <= len(s) <= 300:
                segs.append(s)
    return segs


ENDING = re.compile(r"(다|요|죠|네|음|임|함|것|곳|중|짱)[.!?]?$|[.!?]$")


def clean_seg(seg):
    out = re.sub(r"\s+", " ", seg).strip(" ·-–—…")
    out = re.sub(r"^[^가-힣0-9A-Za-z<(]+", "", out)
    if len(out) > 180:
        out = out[:180].rsplit(" ", 1)[0] + "…"
    return out


def describe_candidates(docs, keys):
    """장소가 언급된 문장을 장면 서술다움 순으로 돌려준다."""
    cands = []
    for d in docs:
        if d["url"] == "__search_snippets__":
            continue
        if not any(k in d["norm"] for k in keys):
            continue
        for seg in split_segments(d["text"]):
            ns = norm(seg)
            pos = min((ns.find(k) for k in keys if k in ns), default=-1)
            if pos < 0:
                continue
            sc = 0
            for kw in SCENE_KW:
                if kw in seg:
                    sc += 3
            if sc == 0:      # 장면 서술 단서가 하나도 없으면 설명이 아니라 잡문이다
                continue
            if any(b in seg for b in BAD_KW):
                sc -= 10
            if re.search(r"[#@]|\d{2,4}-\d{3,4}-\d{4}", seg):
                sc -= 4
            if ENDING.search(seg):          # 문장이 끊기지 않고 끝나야 읽힌다
                sc += 4
            else:
                sc -= 3
            if pos < len(ns) / 2:           # 그 장소가 주어일 때 가점
                sc += 2
            if seg.count(",") >= 3:         # 장소 나열 문장은 개별 설명이 못 된다
                sc -= 5
            L = len(seg)
            if 30 <= L <= 160:
                sc += 3
            elif L > 220:
                sc -= 2
            if sc >= 6:
                cands.append((sc, clean_seg(seg), d["url"]))
    cands.sort(key=lambda x: -x[0])
    return cands


def main():
    rows = list(csv.DictReader(open(V4, encoding="utf-8-sig")))
    base_cols = list(rows[0].keys())

    by_key = defaultdict(list)
    for r in rows:
        by_key[title_key(r["title"])].append(r)

    new_cols = ["title_key", "mention_doc_count", "mention_total_count", "corpus_doc_count",
                "popularity_score", "popularity_rank_in_title", "is_overseas", "dup_of", "coord_issue",
                "is_popular", "filter_reason", "scene_description_source", "evidence_url"]
    for r in rows:
        for c in new_cols:
            r[c] = ""
        r["coord_issue"] = fix_coords(r)

    work_summary = []
    evidence = []
    filled = 0

    for i, (key, group) in enumerate(sorted(by_key.items()), 1):
        docs = load_corpus(key)
        ndocs = len([d for d in docs if d["url"] != "__search_snippets__"])
        snip = next((d for d in docs if d["url"] == "__search_snippets__"), None)

        # 같은 장소가 표기만 다른 행으로 갈라져 있을 수 있어 이름 기준으로 묶어 센다
        counts = {}
        for r in group:
            keys = place_keys(r["place_name"])
            r["_keys"] = keys
            if not keys:
                r["mention_doc_count"] = 0
                r["mention_total_count"] = 0
                continue
            kk = tuple(keys)
            if kk not in counts:
                dc = tot = 0
                for d in docs:
                    hit = sum(d["norm"].count(k) for k in keys)
                    if hit:
                        dc += 1
                        tot += hit
                # 검색결과 제목에 이름이 뜨면 대표 성지일 확률이 높다 → 가중
                if snip and any(k in snip["norm"] for k in keys):
                    dc += 1
                counts[kk] = (dc, tot)
            r["mention_doc_count"], r["mention_total_count"] = counts[kk]

        mx = max((r["mention_doc_count"] for r in group), default=0) or 1
        ordered = sorted(group, key=lambda r: (-r["mention_doc_count"], -r["mention_total_count"],
                                               r["place_name"]))
        for rank, r in enumerate(ordered, 1):
            r["title_key"] = key
            r["corpus_doc_count"] = ndocs
            r["popularity_rank_in_title"] = rank
            r["popularity_score"] = round(r["mention_doc_count"] / mx * 100, 1)

        # --- 근접 중복 정리: 용연리(1)/(2)/(2-2) 처럼 같은 곳이 여러 행으로 갈린 경우 ---
        def dq(r):
            return (bool(r["scene_description"].strip()), bool(r["place_naver_url"].strip()),
                    bool(r["place_image_url"].strip()), bool(r["place_latitude"].strip()),
                    -int(r["popularity_rank_in_title"]))

        keep_of = {}
        for r in ordered:
            kk = r.get("_keys") and r["_keys"][0]
            if not kk:
                continue
            if kk not in keep_of or dq(r) > dq(keep_of[kk]):
                keep_of[kk] = r
        # 용연리 / 용연리마을 처럼 한쪽이 다른 쪽의 접두면 같은 곳으로 본다
        canon = {}
        for kk in sorted(keep_of, key=len):
            canon[kk] = next((canon[p] for p in canon if kk.startswith(p)), kk)
        for r in ordered:
            kk = r.get("_keys") and r["_keys"][0]
            if not kk:
                r["dup_of"] = ""
                continue
            head = keep_of[canon[kk]]
            if dq(r) > dq(head):
                head = r
                keep_of[canon[kk]] = r
            r["dup_of"] = "" if head is r else head["id"]
        for r in ordered:  # 대표행이 바뀌었을 수 있어 한 번 더 맞춘다
            kk = r.get("_keys") and r["_keys"][0]
            r["dup_of"] = "" if not kk or keep_of[canon[kk]] is r else keep_of[canon[kk]]["id"]

        # --- 필터 ---
        for r in ordered:
            dc = r["mention_doc_count"]
            share = dc / ndocs if ndocs else 0
            r["is_overseas"] = "Y" if is_overseas(r) else "N"
            if r["is_overseas"] == "Y":
                r["is_popular"], r["filter_reason"] = "N", "해외로케이션_국내앱기본제외"
            elif r["dup_of"]:
                r["is_popular"], r["filter_reason"] = "N", f"근접중복_{r['dup_of']}로통합"
            elif dc >= 2 and r["popularity_rank_in_title"] <= 15:
                r["is_popular"], r["filter_reason"] = "Y", "언급2회이상_작품내상위15"
            elif share >= 0.15 and dc >= 2:
                r["is_popular"], r["filter_reason"] = "Y", "작품내언급비율15%이상"
            else:
                r["is_popular"], r["filter_reason"] = "N", ""

        # 신호가 약한 작품은 데이터 품질 좋은 순으로 최소 3곳 보존
        if sum(1 for r in ordered if r["is_popular"] == "Y") < 3:
            def quality(r):
                return (r["mention_doc_count"],
                        bool(r["scene_description"].strip()),
                        bool(r["place_naver_url"].strip()),
                        bool(r["place_image_url"].strip()),
                        bool(r["place_latitude"].strip()))
            for r in sorted(ordered, key=quality, reverse=True):
                if sum(1 for x in ordered if x["is_popular"] == "Y") >= 3:
                    break
                if r["is_overseas"] == "Y" or r["dup_of"]:
                    continue
                if r["is_popular"] != "Y":
                    r["is_popular"] = "Y"
                    r["filter_reason"] = "언급부족_데이터품질기준보존"

        # --- 장면 설명 보완 (같은 문장을 여러 장소에 돌려쓰지 않는다) ---
        used = set()
        for r in ordered:
            if r["scene_description"].strip():
                r["scene_description_source"] = "정승길_v4"
                continue
            if r["mention_doc_count"] >= 1 and r.get("_keys"):
                for _, desc, url in describe_candidates(docs, r["_keys"]):
                    if desc in used:
                        continue
                    r["scene_description"] = desc
                    r["scene_description_source"] = f"블로그크롤링_{STAMP}"
                    r["evidence_url"] = url
                    used.add(desc)
                    filled += 1
                    break

        # --- 검증용 근거: 통과 성지가 어느 글에서 언급됐는지 ---
        for r in ordered:
            if r["is_popular"] != "Y" or not r.get("_keys"):
                continue
            srcs = [d["url"] for d in docs
                    if d["url"] != "__search_snippets__" and any(k in d["norm"] for k in r["_keys"])]
            evidence.append({
                "id": r["id"], "title": r["title"], "place_name": r["place_name"],
                "mention_doc_count": r["mention_doc_count"],
                "popularity_score": r["popularity_score"],
                "근거_URL_상위3": " | ".join(srcs[:3]),
            })

        pop = [r for r in ordered if r["is_popular"] == "Y"]
        work_summary.append({
            "title_key": key,
            "title_표기": " / ".join(sorted({r["title"] for r in group})),
            "category": group[0]["title_category"],
            "수집_글수": ndocs,
            "전체_성지수": len(group),
            "언급된_성지수": sum(1 for r in group if r["mention_doc_count"] > 0),
            "필터통과_성지수": len(pop),
            "대표성지_TOP5": " / ".join(f"{r['place_name']}({r['mention_doc_count']})" for r in ordered[:5]),
        })
        if i % 20 == 0:
            print(f"  채점 {i}/{len(by_key)}", flush=True)

    for r in rows:
        r.pop("_keys", None)

    os.makedirs(OUT, exist_ok=True)
    all_cols = base_cols + new_cols

    f1 = f"{OUT}/촬영지_v4_인기도점수_전체_{STAMP}.csv"
    with open(f1, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=all_cols)
        w.writeheader()
        w.writerows(rows)

    pop_rows = [r for r in rows if r["is_popular"] == "Y"]
    pop_rows.sort(key=lambda r: (r["title_key"], r["popularity_rank_in_title"]))
    f2 = f"{OUT}/촬영지_v4_인기성지_필터링_{STAMP}.csv"
    with open(f2, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=all_cols)
        w.writeheader()
        w.writerows(pop_rows)

    f4 = f"{OUT}/인기성지_언급근거_{STAMP}.csv"
    with open(f4, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(evidence[0].keys()))
        w.writeheader()
        w.writerows(evidence)

    f3 = f"{OUT}/작품별_크롤링_인기도_요약_{STAMP}.csv"
    with open(f3, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(work_summary[0].keys()))
        w.writeheader()
        w.writerows(sorted(work_summary, key=lambda x: -x["수집_글수"]))

    stats = {
        "작품수_정규화": len(by_key),
        "전체행": len(rows),
        "코퍼스_총글수": sum(s["수집_글수"] for s in work_summary),
        "언급된_행": sum(1 for r in rows if r["mention_doc_count"] and int(r["mention_doc_count"]) > 0),
        "필터통과_행": len(pop_rows),
        "좌표교정_행": sum(1 for r in rows if r["coord_issue"] == "위경도뒤바뀜_교정"),
        "해외제외_행": sum(1 for r in rows if r["is_overseas"] == "Y"),
        "근접중복_행": sum(1 for r in rows if r["dup_of"]),
        "장면설명_보완": filled,
        "장면설명_최종채움": sum(1 for r in pop_rows if r["scene_description"].strip()),
    }
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    json.dump(stats, open(f"{BASE}/stats.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("wrote:", f1, f2, f3, f4, sep="\n  ")


if __name__ == "__main__":
    main()
