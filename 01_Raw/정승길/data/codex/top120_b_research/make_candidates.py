#!/usr/bin/env python3
"""Create compact, human-reviewable source contexts for each target row."""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "조합작업/TOP120완성/장면설명대상_B.csv"
HERE = Path(__file__).resolve().parent
INDEX = HERE / "source_index.json"
OUT = HERE / "candidate_contexts"


def key(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", (value or "").lower())


def canonical(value: str) -> str:
    aliases = {
        "다이루어질지니": "다 이루어질지니",
        "유미의세포들3": "유미의 세포들 3",
        "판사이한영": "판사 이한영",
        "반짝이는워터멜론": "반짝이는 워터멜론",
        "당신이잠든사이에": "당신이 잠든 사이에",
    }
    return aliases.get(key(value), value)


def place_keys(row: dict) -> list[str]:
    raw_name = re.sub(r"\([^)]*\)", "", row["place_name"])
    raw_name = re.sub(r"\[[^]]*\]", "", raw_name)
    values = [key(raw_name)]

    # Road-name + building number is a useful address confirmation but is
    # never enough on its own to assign a scene.
    address = row.get("place_address", "")
    road_match = re.search(r"([가-힣0-9]+(?:로|길))\s*([0-9]+(?:-[0-9]+)?)", address)
    if road_match:
        values.append(key("".join(road_match.groups())))

    # Drop suffix qualifiers only as a discovery aid; a reviewer must still
    # confirm the exact facility and address before accepting the candidate.
    trimmed = re.sub(
        r"(정류장|버스정류장|버정|촬영지점|촬영지점|앞|옆|인근|일대|골목|내부|외부)$",
        "",
        raw_name,
    )
    if len(key(trimmed)) >= 4:
        values.append(key(trimmed))
    return list(dict.fromkeys(item for item in values if len(item) >= 4))


def main() -> None:
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    with INPUT.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[canonical(row["title"])].append(row)

    OUT.mkdir(parents=True, exist_ok=True)
    selected = sys.argv[1:] or list(index)
    for raw_title in selected:
        title = canonical(raw_title)
        if title not in index or title not in grouped:
            continue
        blocks: list[str] = [f"# {title}"]
        matched_rows = 0
        for row in grouped[title]:
            row_blocks: list[str] = []
            needles = place_keys(row)
            for source in index[title]["sources"]:
                strings = source.get("strings") or []
                hits: list[int] = []
                for position, text in enumerate(strings):
                    text_key = key(text)
                    if any(needle in text_key for needle in needles):
                        hits.append(position)
                if not hits:
                    continue
                # Merge close hits into one context window.
                windows: list[tuple[int, int]] = []
                for position in hits:
                    start, end = max(0, position - 9), min(len(strings), position + 12)
                    if windows and start <= windows[-1][1]:
                        windows[-1] = (windows[-1][0], max(windows[-1][1], end))
                    else:
                        windows.append((start, end))
                row_blocks.append(
                    f"\nSOURCE {source['url']}\n"
                    f"TITLE {source.get('page_title', '')}\n"
                )
                for start, end in windows:
                    row_blocks.append(f"WINDOW {start}:{end}\n")
                    row_blocks.extend(
                        f"{position:04d} {strings[position]}\n"
                        for position in range(start, end)
                    )
            if row_blocks:
                matched_rows += 1
                blocks.append(
                    f"\n## {row['id']} | {row['place_name']} | {row['place_address']}\n"
                )
                blocks.extend(row_blocks)
        path = OUT / f"{key(title)}.txt"
        path.write_text("".join(blocks), encoding="utf-8")
        print(f"{title}: matched_rows={matched_rows}/{len(grouped[title])} -> {path}")


if __name__ == "__main__":
    main()
