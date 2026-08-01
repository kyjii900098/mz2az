#!/usr/bin/env python
"""MZ2AZ-141 v3 — 규칙 필터 결과에 LLM(Claude) 판정을 덮어 최종본을 만든다.

decisions/*.jsonl 은 규칙과 다른 건만 기록돼 있다.
  {"id":..., "sel":"N", "why":...}          → 채택 취소
  {"id":..., "sel":"Y", "desc":"..."}       → 채택 유지 + 빈 장면설명 생성
"""
import csv, json, os, glob
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
OUTS = ["/Users/setgee/Desktop/github/mz2az/01_Raw/김태환/DataCollection",
        "/Users/setgee/orca/workspaces/mz2az/141_성지장소필터링-인기도에따라/01_Raw/김태환/DataCollection"]
SRC = f"{OUTS[0]}/촬영지_인기성지_v2_전체등급_2026-08-01.csv"
STAMP = "2026-08-01"

dec = {}
for f in sorted(glob.glob(f"{BASE}/decisions/*.jsonl")):
    for line in open(f, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        dec[d["id"]] = d

rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig")))
cols = list(rows[0].keys()) + ["scene_description_source", "llm_review", "llm_note"]

n_rej = n_desc = 0
for r in rows:
    r["llm_review"] = ""
    r["llm_note"] = ""
    r["scene_description_source"] = "정승길_v4" if r["scene_description"].strip() else ""
    d = dec.get(r["id"])
    if not d:
        if r["is_selected"] == "Y":
            r["llm_review"] = "유지"
        continue
    if d.get("sel") == "N":
        if r["is_selected"] == "Y":
            n_rej += 1
        r["is_selected"] = "N"
        r["llm_review"] = "제외"
        r["llm_note"] = d.get("why", "")
        r["decision_note"] = "LLM검수제외_" + d.get("why", "")
    else:
        r["is_selected"] = "Y"
        r["llm_review"] = "유지"
        if d.get("desc") and not r["scene_description"].strip():
            r["scene_description"] = d["desc"]
            r["scene_description_source"] = f"LLM생성_{STAMP}"
            n_desc += 1
            r["llm_note"] = "장면설명생성"

sel = [r for r in rows if r["is_selected"] == "Y"]
sel.sort(key=lambda r: (r["title_key"], int(r["rank_in_title"])))

for out in OUTS:
    with open(f"{out}/촬영지_인기성지_최종_{STAMP}.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(sel)
    with open(f"{out}/촬영지_인기성지_최종_전체등급_{STAMP}.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)

stats = {
    "판정기록": len(dec),
    "LLM제외": n_rej,
    "LLM장면설명생성": n_desc,
    "최종채택": len(sel),
    "최종작품수": len({r["title_key"] for r in sel}),
    "제외사유": Counter(r["llm_note"] for r in rows if r["llm_review"] == "제외").most_common(),
    "장면설명채움률": round(sum(1 for r in sel if r["scene_description"].strip()) / len(sel) * 100, 1),
}
print(json.dumps(stats, ensure_ascii=False, indent=2))
