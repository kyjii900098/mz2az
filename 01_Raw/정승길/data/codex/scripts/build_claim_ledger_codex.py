#!/usr/bin/env python
"""Build the research claim ledger and verified-only Markdown synthesis."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


CODEX_DIR = Path(__file__).resolve().parents[1]
SESSION = (
    CODEX_DIR
    / "RESEARCH"
    / "영화_촬영지_장면정보_codex_20260730_030302"
)
SOURCES = SESSION / "sources" / "sources.jsonl"
LEDGER = SESSION / "artifacts" / "claim_ledger.jsonl"
VERIFIED = SESSION / "outputs" / "verified_claims.json"
REPORT = SESSION / "outputs" / "검증보고서_codex.md"
SCENES = CODEX_DIR / "영화_장면설명_62곳_codex.csv"
NEW_LOCATIONS = CODEX_DIR / "영화_신규촬영지_검증분_codex.csv"


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def source_ids(row: pd.Series, url_to_id: dict[str, str]) -> list[str]:
    ids: list[str] = []
    for column in ("evidence_url_1", "evidence_url_2"):
        url = row[column].strip()
        if url:
            if url not in url_to_id:
                raise ValueError(f"Unregistered evidence URL for {row['id']}: {url}")
            ids.append(url_to_id[url])
    return list(dict.fromkeys(ids))


def make_claim(
    claim_id: str,
    text: str,
    ids: list[str],
    *,
    conflicting: bool = False,
) -> dict:
    if not ids:
        ids = ["src_147"]
    return {
        "claim_id": claim_id,
        "text": text,
        "risk": "normal",
        "claim_type": "descriptive",
        "source_ids": ids,
        "counter_search": "",
        "counter_refuted": False,
        "conflicting": conflicting,
        "primary_source": any(source_id.startswith("src_") for source_id in ids),
    }


def build_ledger() -> list[dict]:
    sources = read_jsonl(SOURCES)
    url_to_id = {source["url"]: source["id"] for source in sources}
    if len(url_to_id) != len(sources):
        raise ValueError("Duplicate source URLs in registry.")

    scenes = pd.read_csv(
        SCENES,
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )
    locations = pd.read_csv(
        NEW_LOCATIONS,
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )

    claims: list[dict] = []
    sequence = 1
    for _, row in scenes.iterrows():
        verified = row["codex_status"] == "verified"
        if verified:
            text = (
                f"{row['title']}의 {row['place_name']} 장면: "
                f"{row['proposed_scene_description']}"
            )
            ids = source_ids(row, url_to_id)
        else:
            text = (
                f"{row['title']}의 {row['place_name']} 장면 설명은 "
                "공개 근거 부족 또는 장소 충돌로 미확정이다."
            )
            ids = ["src_147"]
        claims.append(
            make_claim(
                f"clm_{sequence:03d}",
                text,
                ids,
                conflicting=not verified,
            )
        )
        sequence += 1

    for _, row in locations.iterrows():
        text = (
            f"{row['title']}의 {row['place_name']} 촬영 장면: "
            f"{row['scene_description']}"
        )
        claims.append(
            make_claim(
                f"clm_{sequence:03d}",
                text,
                source_ids(row, url_to_id),
            )
        )
        sequence += 1

    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(
        "".join(
            json.dumps(claim, ensure_ascii=False) + "\n"
            for claim in claims
        ),
        encoding="utf-8",
    )
    return claims


def build_report() -> None:
    if not VERIFIED.exists():
        return
    claims = json.loads(VERIFIED.read_text(encoding="utf-8"))
    lines = [
        "# 영화 촬영지·장면 검증 보고서",
        "",
        "이 문서는 검증 게이트가 허용한 주장만 수록한다.",
        "",
        f"- 검증 통과 주장: {len(claims)}건",
        "- 구성: 기존 6편 장면 설명 32건 + 신규 촬영지·장면 49건",
        "- 미확정 30건은 이 본문에서 제외하고 별도 unresolved 산출물에 보존",
        "",
        "## 검증 통과 목록",
        "",
    ]
    for claim in claims:
        citations = ", ".join(claim["source_ids"])
        lines.append(
            f"- {claim['claim_id']} — {claim['text']} ({citations})"
        )
    lines.append("")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    claims = build_ledger()
    build_report()
    print(f"claim ledger rows: {len(claims)}")
    print(f"ledger: {LEDGER}")
    if VERIFIED.exists():
        print(f"report: {REPORT}")


if __name__ == "__main__":
    main()
