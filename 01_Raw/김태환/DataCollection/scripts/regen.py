#!/usr/bin/env python
"""최종 채택본(991행) 기준으로 근거 파일과 작품별 요약을 다시 만든다."""
import csv, json, os, re
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
CORPUS = f"{BASE}/corpus"
OUTS = ["/Users/setgee/Desktop/github/mz2az/01_Raw/김태환/DataCollection",
        "/Users/setgee/orca/workspaces/mz2az/141_성지장소필터링-인기도에따라/01_Raw/김태환/DataCollection"]
FINAL = f"{OUTS[0]}/촬영지_인기성지_최종_2026-08-01.csv"
ALL = f"{OUTS[0]}/촬영지_인기성지_최종_전체등급_2026-08-01.csv"
STAMP = "2026-08-01"
NORM = re.compile(r"[^0-9a-z가-힣]+")


def norm(s):
    return NORM.sub("", s.lower())


def keys(place_name):
    ks = []
    base = re.sub(r"\([^)]*\)", "", place_name).strip()
    for c in (base, place_name):
        n = norm(c)
        if n and n not in ks:
            ks.append(n)
    for a in re.findall(r"\(([^)]*)\)", place_name):
        n = norm(a)
        if n and not n.isdigit() and n not in ks:
            ks.append(n)
    return [k for k in ks if len(k) >= 3]


def load(key):
    safe = re.sub(r"[^\w가-힣]", "_", key)[:60] or "untitled"
    p = f"{CORPUS}/{safe}.jsonl"
    if not os.path.exists(p):
        return []
    out = []
    for line in open(p, encoding="utf-8"):
        d = json.loads(line)
        if d["url"] == "__search_snippets__":
            continue
        d["norm"] = norm(d["text"])
        out.append(d)
    return out


sel = list(csv.DictReader(open(FINAL, encoding="utf-8-sig")))
allr = list(csv.DictReader(open(ALL, encoding="utf-8-sig")))
by_sel = defaultdict(list)
for r in sel:
    by_sel[r["title_key"]].append(r)
by_all = defaultdict(list)
for r in allr:
    by_all[r["title_key"]].append(r)

evidence, summary = [], []
for key in sorted(by_all):
    docs = load(key)
    grp = by_all[key]
    picked = by_sel.get(key, [])
    for r in picked:
        ks = keys(r["place_name"])
        srcs = [d["url"] for d in docs if ks and any(k in d["norm"] for k in ks)]
        evidence.append({
            "id": r["id"], "title": r["title"], "place_name": r["place_name"],
            "tier": r["tier"], "유효언급_글수": r["cue_docs"], "저자수": r["author_count"],
            "popularity_score": r["popularity_score"],
            "근거_URL_상위3": " | ".join(srcs[:3]),
        })
    summary.append({
        "title_key": key,
        "표기": " / ".join(sorted({r["title"] for r in grp})),
        "category": grp[0]["title_category"],
        "수집_글수": grp[0]["corpus_doc_count"],
        "v4_성지수": len(grp),
        "S": sum(1 for r in grp if r["tier"] == "S"),
        "A": sum(1 for r in grp if r["tier"] == "A"),
        "최종채택": len(picked),
        "LLM제외": sum(1 for r in grp if r["llm_review"] == "제외"),
        "채택성지": " / ".join(f"{r['place_name']}({r['cue_docs']})" for r in picked[:5]),
    })

for out in OUTS:
    with open(f"{out}/인기성지_언급근거_{STAMP}.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(evidence[0].keys())); w.writeheader(); w.writerows(evidence)
    with open(f"{out}/작품별_요약_{STAMP}.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys())); w.writeheader()
        w.writerows(sorted(summary, key=lambda x: -int(x["최종채택"])))
print(f"근거 {len(evidence)}행 · 요약 {len(summary)}행 재생성")
