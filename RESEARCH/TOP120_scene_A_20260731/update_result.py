from __future__ import annotations

import csv
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "01_Raw/정승길/data/조합작업/TOP120완성/장면설명대상_A.csv"
OUTPUT = ROOT / "01_Raw/정승길/data/조합작업/TOP120완성/장면설명결과_A.csv"
FILLS = Path(__file__).resolve().parent / "artifacts/fills.jsonl"


def main() -> None:
    with INPUT.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    fills: dict[str, dict[str, str]] = {}
    for line in FILLS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        fills[record["id"]] = record

    known_ids = {row["id"] for row in rows}
    unknown = sorted(set(fills) - known_ids)
    if unknown:
        raise ValueError(f"Unknown fill ids: {unknown}")

    for row in rows:
        fill = fills.get(row["id"])
        if not fill:
            continue
        if fill["title"] != row["title"] or fill["place_name"] != row["place_name"]:
            raise ValueError(f"Input mismatch for {row['id']}")
        length = len(fill["scene_description"])
        if not 25 <= length <= 90:
            raise ValueError(f"Description length {length} for {row['id']}")

    temporary = OUTPUT.with_suffix(".csv.tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["id", "place_name", "scene_description", "desc_source_url"],
        )
        writer.writeheader()
        for row in rows:
            fill = fills.get(row["id"], {})
            writer.writerow(
                {
                    "id": row["id"],
                    "place_name": row["place_name"],
                    "scene_description": fill.get("scene_description", ""),
                    "desc_source_url": fill.get("desc_source_url", ""),
                }
            )
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, OUTPUT)
    directory_fd = os.open(OUTPUT.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    print(f"updated {OUTPUT}: {len(rows)} rows, {len(fills)} filled")


if __name__ == "__main__":
    main()
