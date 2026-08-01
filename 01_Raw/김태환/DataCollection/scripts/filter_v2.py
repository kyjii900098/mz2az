#!/usr/bin/env python
"""MZ2AZ-141 재작업 — 성지 필터링 v2.

v1 의 약점 셋을 고친다.
  1. 스쳐가는 언급과 성지 서술을 구분하지 못했다
     → 장소명 주변 ±120자에 촬영/성지/드라마 단서가 있는 '유효 언급'만 센다.
  2. 한 블로거가 여러 글로 도배하면 점수가 부풀었다
     → 서로 다른 블로그 저자 수를 따로 세고 등급 조건에 넣는다.
  3. Y/N 이분법이라 앱에서 조절할 여지가 없었다
     → S/A/B/C 등급으로 내보내고 컷은 앱이 정하게 한다.

읽기: 정승길 v4 (수정하지 않음).  쓰기: 01_Raw/김태환/DataCollection/ 만.
"""
import csv, json, os, re, statistics
from collections import defaultdict, Counter

BASE = os.path.dirname(os.path.abspath(__file__))
V4 = "/Users/setgee/Desktop/github/mz2az/01_Raw/정승길/data/result/촬영지_TOP_v4_MVP1.csv"
CORPUS = f"{BASE}/corpus"
OUTS = ["/Users/setgee/Desktop/github/mz2az/01_Raw/김태환/DataCollection",
        "/Users/setgee/orca/workspaces/mz2az/141_성지장소필터링-인기도에따라/01_Raw/김태환/DataCollection"]
STAMP = "2026-08-01"

PUNCT = re.compile(r"[\s,·:\-–—!?'\"“”‘’()\[\]]+")
NORM = re.compile(r"[^0-9a-z가-힣]+")
WINDOW = 120  # 장소명 주변 이만큼 안에 단서가 있어야 '유효 언급'

# 정규화 후 기준이라 공백이 없다
CUE = ["촬영", "성지", "드라마", "영화", "장면", "나온", "나오는", "등장", "배경",
       "찍은", "찍었", "명장면", "주인공", "무대탐방", "순례"]

STOP = {
    "서울", "부산", "인천", "대구", "광주", "대전", "울산", "제주", "경기", "강원", "세종",
    "충북", "충남", "전북", "전남", "경북", "경남", "제주도", "한국", "대한민국",
    "카페", "식당", "공원", "학교", "병원", "회사", "아파트", "호텔", "해변", "해수욕장",
    "바다", "도로", "거리", "광장", "마을", "시장", "골목", "다리", "터널", "빌딩", "건물",
    "세트장", "스튜디오", "촬영지", "기타", "미확인", "미상", "없음",
    "mbc", "sbs", "kbs", "jtbc", "tvn", "ocn", "ebs", "cgv", "메가박스", "롯데시네마",
}
SIDO = ("서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원",
        "충북", "충남", "전북", "전남", "경북", "경남", "제주", "충청", "전라", "경상")


def title_key(t):
    return PUNCT.sub("", t)


def norm(s):
    return NORM.sub("", s.lower())


def place_keys(place_name):
    keys = []
    base = re.sub(r"\([^)]*\)", "", place_name).strip()
    for cand in (base, place_name):
        n = norm(cand)
        if n and n not in keys:
            keys.append(n)
    m = re.sub(r"(본점|지점|점)$", "", base).strip()
    if m and norm(m) not in keys:
        keys.append(norm(m))
    for alias in re.findall(r"\(([^)]*)\)", place_name):
        n = norm(alias)
        if n and not n.isdigit() and n not in keys:
            keys.append(n)
    return [k for k in keys if len(k) >= 3 and k not in STOP]


def in_korea(la, lo):
    return 33.0 <= la <= 38.7 and 124.5 <= lo <= 132.0


def fix_coords(r):
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
    lat, lon = r["place_latitude"].strip(), r["place_longitude"].strip()
    if lat and lon:
        try:
            return not in_korea(float(lat), float(lon))
        except ValueError:
            pass
    a = r["place_address"].strip()
    return bool(a) and not a.startswith(SIDO)


def author_of(url):
    m = re.match(r"https?://blog\.naver\.com/([^/?]+)/", url)
    if m:
        return "naver:" + m.group(1)
    m = re.match(r"https?://([a-z0-9-]+)\.tistory\.com/", url)
    return "tistory:" + m.group(1) if m else url


def load_corpus(key):
    safe = re.sub(r"[^\w가-힣]", "_", key)[:60] or "untitled"
    path = f"{CORPUS}/{safe}.jsonl"
    if not os.path.exists(path):
        return [], None
    docs, snip = [], None
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d["url"] == "__search_snippets__":
                d["norm"] = norm(d["text"])
                snip = d
                continue
            d["norm"] = norm(d["text"])
            d["ntitle"] = norm(d.get("title", ""))
            d["author"] = author_of(d["url"])
            docs.append(d)
    return docs, snip


def measure(docs, snip, keys):
    """장소 하나에 대한 신호 묶음."""
    hit_docs, cue_docs, title_docs, authors, total = 0, 0, 0, set(), 0
    for d in docs:
        pos, cnt = [], 0
        for k in keys:
            start = 0
            while True:
                i = d["norm"].find(k, start)
                if i < 0:
                    break
                pos.append((i, len(k)))
                cnt += 1
                start = i + 1
        if not pos:
            continue
        hit_docs += 1
        total += cnt
        authors.add(d["author"])
        if any(k in d["ntitle"] for k in keys):   # 글 제목에 있으면 그 글의 주인공이다
            title_docs += 1
            cue_docs += 1
            continue
        for i, L in pos:                          # 주변에 촬영/성지 단서가 있나
            win = d["norm"][max(0, i - WINDOW): i + L + WINDOW]
            if any(c in win for c in CUE):
                cue_docs += 1
                break
    in_snip = bool(snip and any(k in snip["norm"] for k in keys))
    return {"hit_docs": hit_docs, "cue_docs": cue_docs, "title_docs": title_docs,
            "authors": len(authors), "total": total, "in_snip": in_snip}


def grade(m, top_cue, ndocs):
    """유효 언급 수 · 저자 다양성 · 작품 내 비중으로 등급."""
    cue, au = m["cue_docs"], m["authors"]
    share = cue / top_cue if top_cue else 0
    if cue >= 3 and au >= 3 and share >= 0.30:
        return "S"
    if cue >= 2 and au >= 2:
        return "A"
    if cue >= 1 or m["title_docs"] >= 1:
        return "B"
    return "C"


def main():
    rows = list(csv.DictReader(open(V4, encoding="utf-8-sig")))
    base_cols = list(rows[0].keys())
    by_key = defaultdict(list)
    for r in rows:
        by_key[title_key(r["title"])].append(r)

    new_cols = ["title_key", "corpus_doc_count", "hit_docs", "cue_docs", "title_docs",
                "author_count", "mention_total", "popularity_score", "rank_in_title",
                "tier", "is_overseas", "dup_of", "coord_issue", "is_selected", "decision_note"]
    for r in rows:
        for c in new_cols:
            r[c] = ""
        r["coord_issue"] = fix_coords(r)

    summary = []
    for i, (key, group) in enumerate(sorted(by_key.items()), 1):
        docs, snip = load_corpus(key)
        ndocs = len(docs)

        cache = {}
        for r in group:
            ks = place_keys(r["place_name"])
            r["_keys"] = ks
            if not ks:
                r["_m"] = {"hit_docs": 0, "cue_docs": 0, "title_docs": 0, "authors": 0,
                           "total": 0, "in_snip": False}
                continue
            kk = tuple(ks)
            if kk not in cache:
                cache[kk] = measure(docs, snip, ks)
            r["_m"] = cache[kk]

        top_cue = max((r["_m"]["cue_docs"] for r in group), default=0)
        ordered = sorted(group, key=lambda r: (-r["_m"]["cue_docs"], -r["_m"]["authors"],
                                               -r["_m"]["hit_docs"], r["place_name"]))

        # --- 근접 중복: 정규화 키가 같거나 접두 관계면 같은 곳 ---
        def dq(r):
            return (r["_m"]["cue_docs"], bool(r["scene_description"].strip()),
                    bool(r["place_naver_url"].strip()), bool(r["place_image_url"].strip()),
                    bool(r["place_latitude"].strip()))

        best = {}
        for r in ordered:
            kk = r["_keys"][0] if r["_keys"] else None
            if kk and (kk not in best or dq(r) > dq(best[kk])):
                best[kk] = r
        canon = {}
        for kk in sorted(best, key=len):
            canon[kk] = next((canon[p] for p in canon if kk.startswith(p)), kk)
        head = {}
        for r in ordered:
            kk = r["_keys"][0] if r["_keys"] else None
            if not kk:
                continue
            c = canon[kk]
            if c not in head or dq(r) > dq(head[c]):
                head[c] = r

        for rank, r in enumerate(ordered, 1):
            m = r["_m"]
            r.update({
                "title_key": key, "corpus_doc_count": ndocs,
                "hit_docs": m["hit_docs"], "cue_docs": m["cue_docs"],
                "title_docs": m["title_docs"], "author_count": m["authors"],
                "mention_total": m["total"], "rank_in_title": rank,
                "popularity_score": round(m["cue_docs"] / top_cue * 100, 1) if top_cue else 0.0,
                "is_overseas": "Y" if is_overseas(r) else "N",
            })
            kk = r["_keys"][0] if r["_keys"] else None
            r["dup_of"] = "" if not kk or head[canon[kk]] is r else head[canon[kk]]["id"]
            r["tier"] = grade(m, top_cue, ndocs)

        # --- 채택 ---
        for r in ordered:
            if r["is_overseas"] == "Y":
                r["is_selected"], r["decision_note"] = "N", "해외로케이션_국내앱기본제외"
            elif r["dup_of"]:
                r["is_selected"], r["decision_note"] = "N", f"근접중복_{r['dup_of']}로통합"
            elif r["tier"] in ("S", "A"):
                r["is_selected"], r["decision_note"] = "Y", f"tier{r['tier']}_유효언급{r['cue_docs']}글_저자{r['author_count']}명"
            else:
                r["is_selected"], r["decision_note"] = "N", ""

        # 채택 0곳인 작품만 B등급 상위 3곳 구제 — v1 처럼 언급 0곳까지 넣지는 않는다
        if not any(r["is_selected"] == "Y" for r in ordered):
            for r in ordered:
                if sum(1 for x in ordered if x["is_selected"] == "Y") >= 3:
                    break
                if r["is_overseas"] == "Y" or r["dup_of"] or r["tier"] == "C":
                    continue
                r["is_selected"] = "Y"
                r["decision_note"] = f"작품구제_tierB_유효언급{r['cue_docs']}글"

        sel = [r for r in ordered if r["is_selected"] == "Y"]
        summary.append({
            "title_key": key, "표기": " / ".join(sorted({r["title"] for r in group})),
            "category": group[0]["title_category"], "수집_글수": ndocs,
            "전체_성지수": len(group),
            "S": sum(1 for r in ordered if r["tier"] == "S"),
            "A": sum(1 for r in ordered if r["tier"] == "A"),
            "B": sum(1 for r in ordered if r["tier"] == "B"),
            "C": sum(1 for r in ordered if r["tier"] == "C"),
            "채택수": len(sel),
            "대표성지_TOP5": " / ".join(f"{r['place_name']}({r['cue_docs']})" for r in ordered[:5]),
        })
        if i % 40 == 0:
            print(f"  {i}/{len(by_key)}", flush=True)

    for r in rows:
        r.pop("_keys", None)
        r.pop("_m", None)

    cols = base_cols + new_cols
    sel_rows = [r for r in rows if r["is_selected"] == "Y"]
    sel_rows.sort(key=lambda r: (r["title_key"], int(r["rank_in_title"])))

    for out in OUTS:
        os.makedirs(out, exist_ok=True)
        with open(f"{out}/촬영지_인기성지_v2_채택_{STAMP}.csv", "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(sel_rows)
        with open(f"{out}/촬영지_인기성지_v2_전체등급_{STAMP}.csv", "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
        with open(f"{out}/작품별_등급요약_v2_{STAMP}.csv", "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(summary[0].keys())); w.writeheader()
            w.writerows(sorted(summary, key=lambda x: -x["채택수"]))

    tiers = Counter(r["tier"] for r in rows)
    stats = {
        "작품수": len(by_key), "전체행": len(rows),
        "등급분포": dict(tiers),
        "채택": len(sel_rows),
        "채택작품수": len({r["title_key"] for r in sel_rows}),
        "작품당평균": round(len(sel_rows) / len(by_key), 1),
        "해외제외": sum(1 for r in rows if r["is_overseas"] == "Y"),
        "근접중복": sum(1 for r in rows if r["dup_of"]),
        "구제": sum(1 for r in sel_rows if r["decision_note"].startswith("작품구제")),
    }
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    json.dump(stats, open(f"{BASE}/stats_v2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
