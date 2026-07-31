#!/usr/bin/env python
"""Build Codex-only movie research worklists from the frozen master copy."""

from pathlib import Path

import pandas as pd


CODEX_DIR = Path(__file__).resolve().parents[1]
MASTER = CODEX_DIR / "촬영지_마스터_codex.csv"
SCENE_WORKLIST = CODEX_DIR / "영화_장면설명_62곳_codex.csv"
NO_LOCATION_QUEUE = CODEX_DIR / "영화_무촬영지_우선순위_codex.csv"


def first_nonempty(values: pd.Series) -> str:
    for value in values:
        value = str(value).strip()
        if value:
            return value
    return ""


def main() -> None:
    data = pd.read_csv(
        MASTER,
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )
    movies = data[data["title_category"].eq("movie")].copy()
    has_place = movies["place_name"].str.strip().ne("")
    has_scene = movies["scene_description"].str.strip().ne("")

    scene_rows = movies.loc[
        has_place & ~has_scene,
        [
            "id",
            "title",
            "place_name",
            "place_address",
            "place_latitude",
            "place_longitude",
            "source_url",
            "scene_description",
        ],
    ].copy()
    scene_rows = scene_rows.rename(columns={"source_url": "original_source_url"})
    scene_rows["proposed_scene_description"] = ""
    scene_rows["evidence_url_1"] = ""
    scene_rows["evidence_url_2"] = ""
    scene_rows["evidence_summary"] = ""
    scene_rows["source_quality"] = ""
    scene_rows["codex_status"] = "pending"
    scene_rows["codex_notes"] = ""
    scene_rows.to_csv(SCENE_WORKLIST, index=False, encoding="utf-8-sig")

    by_title = movies.groupby("title", as_index=False).agg(
        place_rows=("place_name", lambda values: values.str.strip().ne("").sum()),
        audience_acc=("audience_acc", first_nonempty),
        award=("award", first_nonempty),
        source_url=("source_url", first_nonempty),
    )
    queue = by_title[by_title["place_rows"].eq(0)].copy()
    queue["audience_numeric"] = pd.to_numeric(
        queue["audience_acc"].str.replace(",", "", regex=False),
        errors="coerce",
    ).fillna(-1).astype("int64")
    queue["has_award"] = queue["award"].str.strip().ne("")
    queue["priority_tier"] = "C"
    queue.loc[queue["audience_numeric"].ge(5_000_000), "priority_tier"] = "B"
    queue.loc[
        queue["audience_numeric"].ge(10_000_000) | queue["has_award"],
        "priority_tier",
    ] = "A"
    queue = queue.sort_values(
        ["priority_tier", "audience_numeric", "has_award", "title"],
        ascending=[True, False, False, True],
    ).reset_index(drop=True)
    queue.insert(0, "priority_rank", queue.index + 1)
    queue["codex_status"] = "pending"
    queue["codex_notes"] = ""
    queue.to_csv(NO_LOCATION_QUEUE, index=False, encoding="utf-8-sig")

    print(f"scene worklist: {len(scene_rows)} rows -> {SCENE_WORKLIST.name}")
    print(f"no-location queue: {len(queue)} titles -> {NO_LOCATION_QUEUE.name}")


if __name__ == "__main__":
    main()
