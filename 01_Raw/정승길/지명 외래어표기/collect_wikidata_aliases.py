"""
Wikidata 한국 장소 영문 별칭(alias) 수집 스크립트

무엇을 만드는가
  GeoNames 가 못 잡는 두 가지를 메운다.
  1. 개칭 이력 — 경원대역 → 가천대역 (Kyungwon University Station / Gachon University Station)
  2. 옛 이름   — 서울 ← Hanyang, Gyeongseong
  3. POI 별칭  — Gyeongbokgung / Gyeongbok Palace 처럼 궁·사찰·역의 영어식 의역

출처
  Wikidata Query Service (SPARQL) — https://query.wikidata.org/sparql
  라이선스: CC0 (제약 없음)

수집일: 2026-08-08
실행:   python3 collect_wikidata_aliases.py
결과:   data/wikidata_aliases.csv
"""

import csv
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).parent
RAW = BASE / "data"
RAW.mkdir(exist_ok=True)

ENDPOINT = "https://query.wikidata.org/sparql"
# Wikidata 는 연락처가 없는 요청을 막는다. 반드시 식별 가능한 UA 를 보낸다.
UA = "SceneTrip-research/1.0 (https://github.com/mz2az; kikongdosa@gmail.com)"

# P17=국가, Q884=대한민국, P625=좌표. 좌표가 있는 항목만 받아 인물·작품을 걸러낸다.
QUERY = """
SELECT ?item ?rr ?alias ?coord ?typeLabel WHERE {
  ?item wdt:P17 wd:Q884 ;
        wdt:P625 ?coord ;
        skos:altLabel ?alias .
  FILTER(lang(?alias) = "en")
  ?item rdfs:label ?rr . FILTER(lang(?rr) = "en")
  OPTIONAL { ?item wdt:P31 ?type . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"""


def run_query(query: str, retries: int = 3) -> list:
    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": query})
    req = urllib.request.Request(url, headers={"Accept": "text/csv", "User-Agent": UA})
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                text = resp.read().decode("utf-8")
            return list(csv.DictReader(text.splitlines()))
        except Exception as e:
            if attempt == retries:
                raise
            wait = 5 * attempt
            print(f"  실패 ({e}). {wait}초 뒤 재시도 {attempt}/{retries - 1}")
            time.sleep(wait)
    return []


def main():
    print("[1/2] Wikidata 질의")
    rows = run_query(QUERY)
    print(f"  {len(rows):,}행 받음")

    print("[2/2] 정리")
    out = RAW / "wikidata_aliases.csv"
    seen = set()
    n = 0
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["qid", "official_en", "alias", "type", "lat", "lon", "wikidata_url"])
        for r in rows:
            qid = r["item"].rsplit("/", 1)[-1]
            official, alias = r["rr"].strip(), r["alias"].strip()
            if not alias or alias == official:
                continue
            key = (qid, alias)
            if key in seen:      # OPTIONAL P31 때문에 같은 별칭이 여러 번 나온다
                continue
            seen.add(key)
            # coord 는 "Point(126.97 37.56)" 꼴이다
            lon = lat = ""
            c = r.get("coord", "")
            if c.startswith("Point("):
                parts = c[6:-1].split()
                if len(parts) == 2:
                    lon, lat = parts
            w.writerow([qid, official, alias, r.get("typeLabel", ""), lat, lon, r["item"]])
            n += 1

    print(f"\n완료: {out}")
    print(f"  장소 {len({k[0] for k in seen}):,}곳 / 별칭 {n:,}건")


if __name__ == "__main__":
    sys.exit(main())
