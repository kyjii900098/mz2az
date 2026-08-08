"""
GeoNames 한국 지명 로마자 이표기(variant) 수집 스크립트

무엇을 만드는가
  한국 지명 하나에 대해 실제로 통용되는 로마자 표기를 모두 모은 표.
  예: 설악산 → Seoraksan(현행) / Sŏraksan, Sŏrak-san(매큔-라이샤워) /
      Setsugaku-zan(일제강점기 일본어 표기) …

출처
  - https://download.geonames.org/export/dump/KR.zip                 (지명 본체)
  - https://download.geonames.org/export/dump/alternatenames/KR.zip  (이표기)
  라이선스: CC BY 4.0 (출처 표시하면 상업적 이용 가능)

수집일: 2026-08-08
실행:   python3 collect_geonames_variants.py
결과:   data/geonames_kr_raw.tsv          — 지명 본체 원본
        data/geonames_kr_altnames_raw.tsv — 이표기 원본
        data/romanization_variants.csv    — 이표기가 2개 이상인 지명만 정리한 표
"""

import csv
import io
import re
import sys
import time
import unicodedata
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).parent
RAW = BASE / "data"
RAW.mkdir(exist_ok=True)

SOURCES = {
    "geonames_kr_raw.tsv": "https://download.geonames.org/export/dump/KR.zip",
    "geonames_kr_altnames_raw.tsv": "https://download.geonames.org/export/dump/alternatenames/KR.zip",
}

# GeoNames 본체(KR.txt) 컬럼 — readme.txt 기준
MAIN_COLS = [
    "geonameid", "name", "asciiname", "alternatenames", "latitude", "longitude",
    "feature_class", "feature_code", "country_code", "cc2", "admin1_code",
    "admin2_code", "admin3_code", "admin4_code", "population", "elevation",
    "dem", "timezone", "modification_date",
]
# 이표기(alternatenames/KR.txt) 컬럼
ALT_COLS = [
    "alternateNameId", "geonameid", "isolanguage", "alternate_name",
    "isPreferredName", "isShortName", "isColloquial", "isHistoric",
    "from", "to",
]

# 언어 코드가 아니라 링크·코드 체계인 값들. 지명 표기가 아니므로 버린다.
NON_NAME_LANGS = {
    "link", "wkdt", "iata", "icao", "faac", "tcid", "unlc", "post", "phone",
    "fr_1793", "abbr", "nat",
}

# 매큔-라이샤워(MR) 표기에서만 나타나는 글자. RR(2000년 현행)에는 없다.
MR_MARKERS = re.compile(r"[ŏŭŎŬ]|[’'`ʼ]")


def download(dest_name: str, url: str) -> Path:
    """zip 을 받아 안의 KR.txt 를 dest_name 으로 푼다. 이미 있으면 건너뛴다."""
    dest = RAW / dest_name
    if dest.exists():
        print(f"  건너뜀 (이미 있음): {dest.name}")
        return dest
    print(f"  받는 중: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "SceneTrip-research/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        blob = resp.read()
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        with z.open("KR.txt") as f:
            dest.write_bytes(f.read())
    print(f"  저장: {dest.name} ({dest.stat().st_size:,} bytes)")
    time.sleep(1)  # 서버 배려
    return dest


def read_tsv(path: Path, cols: list) -> list:
    rows = []
    with path.open(encoding="utf-8", newline="") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            parts += [""] * (len(cols) - len(parts))
            rows.append(dict(zip(cols, parts)))
    return rows


def is_latin(s: str) -> bool:
    """로마자(발음기호 포함) 표기인가. 한글·한자·키릴 등은 제외한다."""
    if not s or not s[0].isalpha():
        return False
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return False
    return all("LATIN" in unicodedata.name(c, "") for c in letters)


def norm(s: str) -> str:
    """비교용 정규화 — 반달표·어깻점·하이픈·공백·대소문자를 지운다.
    이걸로 같아지면 '같은 이름의 표기 차이', 달라지면 '다른 이름'이다."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")  # 결합 발음기호 제거
    s = re.sub(r"[’'`ʼ\-\s.]", "", s)
    return s.lower()


def classify(name: str, official: str) -> str:
    """표기 하나를 어느 계통으로 볼지 판정한다. 어림짐작이므로 참고용이다."""
    if name == official:
        return "RR_official"
    if MR_MARKERS.search(name):
        return "MR"
    if norm(name) == norm(official):
        return "spacing_hyphen"  # 같은 표기인데 하이픈·띄어쓰기만 다름
    return "other_variant"


def main():
    print("[1/4] 원본 내려받기")
    for dest_name, url in SOURCES.items():
        download(dest_name, url)

    print("[2/4] 읽기")
    main_rows = read_tsv(RAW / "geonames_kr_raw.tsv", MAIN_COLS)
    alt_rows = read_tsv(RAW / "geonames_kr_altnames_raw.tsv", ALT_COLS)
    print(f"  지명 {len(main_rows):,}건 / 이표기 {len(alt_rows):,}건")

    info = {r["geonameid"]: r for r in main_rows}

    print("[3/4] 로마자 이표기 모으기")
    variants = defaultdict(dict)   # geonameid -> {표기: 플래그들}
    hangul = defaultdict(set)      # geonameid -> 한글 표기
    for r in alt_rows:
        gid, lang, nm = r["geonameid"], r["isolanguage"], r["alternate_name"]
        if lang in NON_NAME_LANGS or not nm:
            continue
        if lang == "ko":
            hangul[gid].add(nm)
        elif lang in ("", "en") and is_latin(nm):
            prev = variants[gid].get(nm, {"hist": False})
            variants[gid][nm] = {"hist": prev["hist"] or r["isHistoric"] == "1"}

    print("[4/4] 표 만들기")
    out = RAW / "romanization_variants.csv"
    n_place = n_row = 0
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "geonameid", "official_rr", "hangul", "feature_class", "feature_code",
            "latitude", "longitude", "variant", "variant_type", "is_historic",
            "same_name_diff_spelling",
        ])
        for gid, names in variants.items():
            if gid not in info:
                continue
            official = info[gid]["name"]
            # 정규화해서 겹치는 걸 걷어낸 뒤 2개 이상 남는 지명만 대상으로 삼는다
            if len({norm(n) for n in names} | {norm(official)}) < 2:
                continue
            n_place += 1
            m = info[gid]
            ko = " / ".join(sorted(hangul.get(gid, [])))
            for nm, flag in sorted(names.items()):
                if nm == official:
                    continue
                w.writerow([
                    gid, official, ko, m["feature_class"], m["feature_code"],
                    m["latitude"], m["longitude"], nm, classify(nm, official),
                    "Y" if flag["hist"] else "",
                    "Y" if norm(nm) == norm(official) else "",
                ])
                n_row += 1

    print(f"\n완료: {out}")
    print(f"  이표기를 가진 지명 {n_place:,}곳 / 이표기 행 {n_row:,}건")


if __name__ == "__main__":
    sys.exit(main())
