#!/usr/bin/env python
"""Apply incremental verified research results to the Codex-only worklist."""

import json
from pathlib import Path

import pandas as pd


CODEX_DIR = Path(__file__).resolve().parents[1]
WORKLIST = CODEX_DIR / "영화_장면설명_62곳_codex.csv"
RESULTS = (
    CODEX_DIR
    / "RESEARCH"
    / "영화_촬영지_장면정보_codex_20260730_030302"
    / "artifacts"
    / "영화_장면설명_검증결과_codex.json"
)


def main() -> None:
    worklist = pd.read_csv(
        WORKLIST,
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )
    with RESULTS.open(encoding="utf-8") as handle:
        results = json.load(handle)

    by_id = {item["id"]: item for item in results}
    unknown = sorted(set(by_id) - set(worklist["id"]))
    if unknown:
        raise ValueError(f"Unknown IDs in research results: {unknown}")

    update_columns = [
        "proposed_scene_description",
        "evidence_url_1",
        "evidence_url_2",
        "evidence_summary",
        "source_quality",
        "codex_status",
        "codex_notes",
    ]
    for row_index, row_id in worklist["id"].items():
        result = by_id.get(row_id)
        if not result:
            continue
        for column in update_columns:
            worklist.at[row_index, column] = result.get(column, "")

    worklist.to_csv(WORKLIST, index=False, encoding="utf-8-sig")
    counts = worklist["codex_status"].value_counts().to_dict()
    print(f"applied {len(results)} result rows")
    print(f"status counts: {counts}")


if __name__ == "__main__":
    main()
