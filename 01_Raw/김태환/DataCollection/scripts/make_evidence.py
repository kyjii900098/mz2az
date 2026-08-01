#!/usr/bin/env python
"""MZ2AZ-141 v3 — LLM 판정용 근거 묶음 생성.

규칙 필터로 후보를 좁힌 뒤(S/A/B 등급), 각 장소마다 블로그 근거 문장을 모아
작품 단위 JSON 으로 떨군다. 이걸 사람/LLM 이 읽고 채택 여부와 설명을 정한다.
"""
import csv, json, os, re
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
GRADED = ("/Users/setgee/Desktop/github/mz2az/01_Raw/김태환/DataCollection/"
          "촬영지_인기성지_v2_전체등급_2026-08-01.csv")
CORPUS = f"{BASE}/corpus"
EV = f"{BASE}/evidence"
os.makedirs(EV, exist_ok=True)

NORM = re.compile(r"[^0-9a-z가-힣]+")
PUNCT = re.compile(r"[\s,·:\-–—!?'\"“”‘’()\[\]]+")
CUE = ["촬영", "성지", "나온", "나오는", "등장", "배경", "찍은", "찍었", "명장면", "무대탐방"]
MAX_PLACES = 30      # 작품당 판정 대상 상한 (cue_docs 상위)
MAX_SNIP = 4         # 장소당 근거 문장 수


def norm(s):
    return NORM.sub("", s.lower())


def place_keys(place_name):
    keys = []
    base = re.sub(r"\([^)]*\)", "", place_name).strip()
    for c in (base, place_name):
        n = norm(c)
        if n and n not in keys:
            keys.append(n)
    for a in re.findall(r"\(([^)]*)\)", place_name):
        n = norm(a)
        if n and not n.isdigit() and n not in keys:
            keys.append(n)
    return [k for k in keys if len(k) >= 3]


def load(key):
    safe = re.sub(r"[^\w가-힣]", "_", key)[:60] or "untitled"
    p = f"{CORPUS}/{safe}.jsonl"
    if not os.path.exists(p):
        return []
    docs = []
    for line in open(p, encoding="utf-8"):
        d = json.loads(line)
        if d["url"] == "__search_snippets__":
            continue
        d["norm"] = norm(d["text"])
        docs.append(d)
    return docs


def snippets(docs, keys):
    out, seen = [], set()
    for d in docs:
        if not any(k in d["norm"] for k in keys):
            continue
        for seg in re.split(r"(?<=[.!?])\s+|\n", d["text"]):
            seg = re.sub(r"\s+", " ", seg).strip()
            if not (12 <= len(seg) <= 200):
                continue
            ns = norm(seg)
            if not any(k in ns for k in keys):
                continue
            if not any(c in seg for c in CUE):
                continue
            if seg.count("/") >= 4 or seg.count("#") >= 2:   # 해시태그·태그나열
                continue
            k = seg[:40]
            if k in seen:
                continue
            seen.add(k)
            out.append(seg[:200])
            break
        if len(out) >= MAX_SNIP:
            break
    return out


def main():
    rows = list(csv.DictReader(open(GRADED, encoding="utf-8-sig")))
    by = defaultdict(list)
    for r in rows:
        by[r["title_key"]].append(r)

    made = 0
    for key, group in sorted(by.items()):
        cand = [r for r in group if r["tier"] in ("S", "A", "B")]
        if not cand:
            continue
        cand.sort(key=lambda r: (-int(r["cue_docs"]), -int(r["author_count"])))
        cand = cand[:MAX_PLACES]
        docs = load(key)

        places = []
        for r in cand:
            ks = place_keys(r["place_name"])
            places.append({
                "id": r["id"],
                "name": r["place_name"],
                "addr": r["place_address"][:40],
                "tier": r["tier"],
                "cue": int(r["cue_docs"]),
                "authors": int(r["author_count"]),
                "hits": int(r["hit_docs"]),
                "overseas": r["is_overseas"],
                "dup_of": r["dup_of"],
                "has_desc": bool(r["scene_description"].strip()),
                "desc": r["scene_description"][:90],
                "ev": snippets(docs, ks) if ks else [],
            })
        pack = {
            "title_key": key,
            "title": group[0]["title"],
            "category": group[0]["title_category"],
            "corpus_docs": int(group[0]["corpus_doc_count"]),
            "total_places_in_v4": len(group),
            "places": places,
        }
        safe = re.sub(r"[^\w가-힣]", "_", key)[:60]
        json.dump(pack, open(f"{EV}/{safe}.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        made += 1
    print(f"근거 묶음 {made}편 생성 → {EV}")
    tot = sum(len(json.load(open(f"{EV}/{f}", encoding="utf-8"))["places"])
              for f in os.listdir(EV))
    print(f"판정 대상 장소 {tot}곳")


if __name__ == "__main__":
    main()
