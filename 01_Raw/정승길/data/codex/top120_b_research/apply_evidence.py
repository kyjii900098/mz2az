#!/usr/bin/env python3
"""Atomically apply reviewed evidence to the required deliverable CSV."""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "조합작업/TOP120완성/장면설명대상_B.csv"
OUTPUT = ROOT / "조합작업/TOP120완성/장면설명결과_B.csv"
EVIDENCE = Path(__file__).resolve().parent / "evidence.json"
FIELDS = ["id", "place_name", "scene_description", "desc_source_url"]
BANNED = ("ys-dl.tistory.com", "hanlyu-map.com", "seasonings.tistory.com")


def main() -> None:
    selected = set(sys.argv[1:])
    with INPUT.open(encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    evidence_rows = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in source_rows}
    existing: dict[str, dict] = {}
    if OUTPUT.exists():
        with OUTPUT.open(encoding="utf-8-sig", newline="") as handle:
            existing = {row["id"]: row for row in csv.DictReader(handle)}

    applied = 0
    for record in evidence_rows:
        row_id = record["id"]
        if row_id not in by_id:
            raise SystemExit(f"unknown id in evidence: {row_id}")
        title = by_id[row_id]["title"]
        if selected and title not in selected:
            continue
        description = record["scene_description"].strip()
        urls = record["desc_source_url"].strip()
        if not 25 <= len(description) <= 90:
            raise SystemExit(
                f"{row_id}: description length {len(description)} outside 25..90: {description}"
            )
        if not (description.endswith("장면") or "장면" in description):
            raise SystemExit(f"{row_id}: description does not use scene format")
        if any(domain in urls for domain in BANNED):
            raise SystemExit(f"{row_id}: banned source URL")
        if "realscene.site" in urls and ";" not in urls:
            raise SystemExit(f"{row_id}: realscene.site cannot be the sole source")
        existing[row_id] = {
            "id": row_id,
            "place_name": by_id[row_id]["place_name"],
            "scene_description": description,
            "desc_source_url": urls,
        }
        applied += 1

    temp = OUTPUT.with_suffix(OUTPUT.suffix + ".tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in source_rows:
            old = existing.get(row["id"], {})
            writer.writerow(
                {
                    "id": row["id"],
                    "place_name": row["place_name"],
                    "scene_description": old.get("scene_description", ""),
                    "desc_source_url": old.get("desc_source_url", ""),
                }
            )
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, OUTPUT)
    print(f"atomically applied {applied} reviewed rows -> {OUTPUT}")


if __name__ == "__main__":
    main()
