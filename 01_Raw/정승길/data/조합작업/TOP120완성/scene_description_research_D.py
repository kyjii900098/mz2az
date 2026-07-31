#!/usr/bin/env python3
"""Incrementally update and validate scene-description result D."""

from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "장면설명대상_D.csv"
OUTPUT = ROOT / "장면설명결과_D.csv"
LOG = ROOT / "장면설명리서치로그_D.json"
OUTPUT_FIELDS = ["id", "place_name", "scene_description", "desc_source_url"]
FORBIDDEN_SOURCES = (
    "ys-dl.tistory.com",
    "hanlyu-map.com",
    "seasonings.tistory.com",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_write_csv(rows: list[dict[str, str]]) -> None:
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8-sig",
        newline="",
        dir=ROOT,
        delete=False,
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
        temporary_path = Path(handle.name)
    temporary_path.replace(OUTPUT)


def apply_updates(updates_path: Path, title: str, note: str) -> None:
    input_rows = read_csv(INPUT)
    result_rows = read_csv(OUTPUT)
    if len(input_rows) != len(result_rows):
        raise ValueError("input/result row counts differ")

    updates = json.loads(updates_path.read_text(encoding="utf-8"))
    if not isinstance(updates, list):
        raise ValueError("updates JSON must be a list")

    by_id: dict[str, dict[str, str]] = {}
    for item in updates:
        if set(item) != {"id", "scene_description", "desc_source_url"}:
            raise ValueError(f"invalid update keys: {item}")
        item_id = str(item["id"])
        if item_id in by_id:
            raise ValueError(f"duplicate update id: {item_id}")
        by_id[item_id] = item

    title_ids = {row["id"] for row in input_rows if row["title"] == title}
    unexpected = set(by_id) - title_ids
    if unexpected:
        raise ValueError(
            f"updates contain IDs outside title {title!r}: {sorted(unexpected)}"
        )

    changed = 0
    for result in result_rows:
        item = by_id.get(result["id"])
        if not item:
            continue
        description = item["scene_description"].strip()
        source_url = item["desc_source_url"].strip()
        if bool(description) != bool(source_url):
            raise ValueError(
                f"description/source mismatch for id={result['id']}"
            )
        result["scene_description"] = description
        result["desc_source_url"] = source_url
        changed += 1

    atomic_write_csv(result_rows)
    log = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {}
    title_rows = [row for row in input_rows if row["title"] == title]
    log[title] = {
        "rows": len(title_rows),
        "filled": len(by_id),
        "blank": len(title_rows) - len(by_id),
        "note": note,
    }
    LOG.write_text(
        json.dumps(log, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"flushed title={title!r}: {changed} filled updates")


def validate() -> None:
    input_rows = read_csv(INPUT)
    result_rows = read_csv(OUTPUT)
    errors: list[str] = []
    if len(input_rows) != len(result_rows):
        errors.append(
            f"row count: input={len(input_rows)} result={len(result_rows)}"
        )

    seen_ids: set[str] = set()
    for row_number, (source, result) in enumerate(
        zip(input_rows, result_rows), start=2
    ):
        if source["id"] != result["id"]:
            errors.append(f"row {row_number}: id order mismatch")
        if source["place_name"] != result["place_name"]:
            errors.append(f"row {row_number}: place_name mismatch")
        if result["id"] in seen_ids:
            errors.append(f"row {row_number}: duplicate id")
        seen_ids.add(result["id"])

        description = result["scene_description"]
        source_url = result["desc_source_url"]
        if bool(description) != bool(source_url):
            errors.append(f"row {row_number}: description/source mismatch")
        if description and not 25 <= len(description) <= 90:
            errors.append(
                f"row {row_number}: description length={len(description)}"
            )
        if description and not (
            ("화에서" in description and description.endswith("장면"))
            or (description.startswith("극 중 ") and description.endswith("장면"))
        ):
            errors.append(f"row {row_number}: description format")
        for forbidden in FORBIDDEN_SOURCES:
            if forbidden in source_url:
                errors.append(
                    f"row {row_number}: forbidden source {forbidden}"
                )
        if "realscene.site" in source_url and ";" not in source_url:
            errors.append(
                f"row {row_number}: realscene.site used as sole source"
            )

    title_stats: dict[str, Counter[str]] = defaultdict(Counter)
    for source, result in zip(input_rows, result_rows):
        status = "filled" if result["scene_description"] else "blank"
        title_stats[source["title"]][status] += 1

    print(
        json.dumps(
            {
                "input_rows": len(input_rows),
                "result_rows": len(result_rows),
                "filled": sum(
                    bool(row["scene_description"]) for row in result_rows
                ),
                "blank": sum(
                    not row["scene_description"] for row in result_rows
                ),
                "errors": errors[:100],
                "title_stats": title_stats,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if errors:
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--updates", type=Path, required=True)
    apply_parser.add_argument("--title", required=True)
    apply_parser.add_argument("--note", default="")
    subparsers.add_parser("validate")
    args = parser.parse_args()

    if args.command == "apply":
        apply_updates(args.updates, args.title, args.note)
    else:
        validate()


if __name__ == "__main__":
    main()
