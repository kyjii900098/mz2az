#!/usr/bin/env python3
"""Validate the B deliverable and write compact, reproducible audit artifacts."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = Path(__file__).resolve().parent
INPUT = ROOT / "조합작업/TOP120완성/장면설명대상_B.csv"
OUTPUT = ROOT / "조합작업/TOP120완성/장면설명결과_B.csv"
EVIDENCE = RESEARCH / "evidence.json"
BANNED = ("ys-dl.tistory.com", "hanlyu-map.com", "seasonings.tistory.com")


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def main() -> None:
    _, source_rows = read_csv(INPUT)
    output_fields, output_rows = read_csv(OUTPUT)
    evidence_rows = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    source_by_id = {row["id"]: row for row in source_rows}
    errors: list[str] = []

    if output_fields != [
        "id",
        "place_name",
        "scene_description",
        "desc_source_url",
    ]:
        errors.append(f"incorrect header: {output_fields}")
    if len(source_rows) != len(output_rows):
        errors.append("input/output row-count mismatch")

    filled: list[dict[str, str]] = []
    for line_number, (source, result) in enumerate(
        zip(source_rows, output_rows), start=2
    ):
        if source["id"] != result["id"]:
            errors.append(f"line {line_number}: id/order mismatch")
        if source["place_name"] != result["place_name"]:
            errors.append(f"line {line_number}: place_name mismatch")
        description = result["scene_description"]
        urls = result["desc_source_url"]
        if bool(description) != bool(urls):
            errors.append(f"{result['id']}: description/source pairing mismatch")
        if not description:
            continue
        filled.append(result)
        if not 25 <= len(description) <= 90:
            errors.append(f"{result['id']}: description length is {len(description)}")
        if "장면" not in description:
            errors.append(f"{result['id']}: missing 장면 format")
        if any(domain in urls for domain in BANNED):
            errors.append(f"{result['id']}: banned source")
        if "realscene.site" in urls and ";" not in urls:
            errors.append(f"{result['id']}: realscene.site used alone")
        for url in urls.split(";"):
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                errors.append(f"{result['id']}: malformed URL {url}")

    if len({row["id"] for row in output_rows}) != len(output_rows):
        errors.append("duplicate output id")
    if Counter(row["id"] for row in evidence_rows) != Counter(
        row["id"] for row in filled
    ):
        errors.append("evidence/output id-set mismatch")

    title_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "filled": 0, "blank": 0}
    )
    for row in source_rows:
        title_counts[row["title"]]["total"] += 1
    for row in filled:
        title_counts[source_by_id[row["id"]]["title"]]["filled"] += 1
    for counts in title_counts.values():
        counts["blank"] = counts["total"] - counts["filled"]

    unique_urls = sorted(
        {
            url
            for row in filled
            for url in row["desc_source_url"].split(";")
            if url
        }
    )

    with (RESEARCH / "claim_source_map.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "id",
                "title",
                "place_name",
                "scene_description",
                "desc_source_url",
            ],
        )
        writer.writeheader()
        for row in filled:
            source = source_by_id[row["id"]]
            writer.writerow(
                {
                    "id": row["id"],
                    "title": source["title"],
                    "place_name": row["place_name"],
                    "scene_description": row["scene_description"],
                    "desc_source_url": row["desc_source_url"],
                }
            )

    with (RESEARCH / "sources.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=["url", "domain", "claim_count"])
        writer.writeheader()
        for url in unique_urls:
            writer.writerow(
                {
                    "url": url,
                    "domain": urlparse(url).netloc,
                    "claim_count": sum(
                        url in row["desc_source_url"].split(";") for row in filled
                    ),
                }
            )

    summary = {
        "generated_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
        "status": "pass" if not errors else "fail",
        "input_rows": len(source_rows),
        "output_rows": len(output_rows),
        "filled_rows": len(filled),
        "blank_rows": len(output_rows) - len(filled),
        "unique_source_urls": len(unique_urls),
        "description_length_min": min(map(lambda row: len(row["scene_description"]), filled)),
        "description_length_max": max(map(lambda row: len(row["scene_description"]), filled)),
        "duplicate_descriptions": sum(
            count - 1
            for count in Counter(row["scene_description"] for row in filled).values()
            if count > 1
        ),
        "title_counts": title_counts,
        "errors": errors,
    }
    (RESEARCH / "qa_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
