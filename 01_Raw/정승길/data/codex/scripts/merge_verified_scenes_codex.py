#!/usr/bin/env python
"""Merge verified movie scene descriptions into the Codex-only master copy."""

from datetime import date
from pathlib import Path

import pandas as pd


CODEX_DIR = Path(__file__).resolve().parents[1]
MASTER = CODEX_DIR / "촬영지_마스터_codex.csv"
WORKLIST = CODEX_DIR / "영화_장면설명_62곳_codex.csv"
MERGE_LOG = CODEX_DIR / "영화_장면설명_병합로그_codex.csv"


def main() -> None:
    master = pd.read_csv(
        MASTER,
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )
    worklist = pd.read_csv(
        WORKLIST,
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )

    verified = worklist.loc[worklist["codex_status"].eq("verified")].copy()
    if verified["id"].duplicated().any():
        raise ValueError("Verified worklist contains duplicate IDs.")
    if verified["proposed_scene_description"].eq("").any():
        raise ValueError("A verified row has a blank proposed scene description.")

    master_by_id = master.set_index("id", drop=False)
    missing_ids = sorted(set(verified["id"]) - set(master_by_id.index))
    if missing_ids:
        raise ValueError(f"Verified IDs missing from master: {missing_ids}")

    log_rows: list[dict[str, str]] = []
    changed = 0
    unchanged = 0
    for _, research_row in verified.iterrows():
        row_id = research_row["id"]
        master_index = master.index[master["id"].eq(row_id)]
        if len(master_index) != 1:
            raise ValueError(f"Expected one master row for {row_id}, found {len(master_index)}.")
        index = master_index[0]

        for column in ("title", "place_name", "place_address"):
            if master.at[index, column] != research_row[column]:
                raise ValueError(
                    f"{row_id} mismatch in {column}: "
                    f"{master.at[index, column]!r} != {research_row[column]!r}"
                )

        old_description = master.at[index, "scene_description"]
        new_description = research_row["proposed_scene_description"]
        if old_description and old_description != new_description:
            raise ValueError(
                f"Refusing to overwrite nonblank scene_description for {row_id}."
            )

        action = "unchanged"
        if not old_description:
            master.at[index, "scene_description"] = new_description
            master.at[index, "last_updated"] = date.today().isoformat()
            action = "filled"
            changed += 1
        else:
            unchanged += 1

        log_rows.append(
            {
                "id": row_id,
                "title": research_row["title"],
                "place_name": research_row["place_name"],
                "old_scene_description": old_description,
                "new_scene_description": new_description,
                "action": action,
                "evidence_url_1": research_row["evidence_url_1"],
                "evidence_url_2": research_row["evidence_url_2"],
                "source_quality": research_row["source_quality"],
            }
        )

    master.to_csv(MASTER, index=False, encoding="utf-8-sig")
    pd.DataFrame(log_rows).to_csv(MERGE_LOG, index=False, encoding="utf-8-sig")
    print(f"verified rows: {len(verified)}")
    print(f"filled blank descriptions: {changed}")
    print(f"already identical/nonblank: {unchanged}")
    print(f"master rows preserved: {len(master)}")
    print(f"merge log: {MERGE_LOG}")


if __name__ == "__main__":
    main()
