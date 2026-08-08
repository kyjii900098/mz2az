#!/usr/bin/env python3
"""merge_recollect.py의 픽스처·안전장치 테스트."""

from __future__ import annotations

import csv
import hashlib
import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import merge_recollect as merge


SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parents[1]
MOTHER_FIXTURE = DATA_DIR / "조합작업" / "신규수집" / "신규수집_마더.csv"


def write_csv(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    """테스트용 UTF-8-SIG CSV를 쓴다."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    """파일 해시를 반환한다."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(64 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class DuplicateDetectionTest(unittest.TestCase):
    """실제 마더 픽스처를 활용한 장소 중복 판정 테스트."""

    @classmethod
    def setUpClass(cls) -> None:
        headers, rows = merge.read_csv(MOTHER_FIXTURE)
        if not rows:
            raise unittest.SkipTest(f"픽스처 행이 없습니다: {MOTHER_FIXTURE}")
        cls.headers = headers
        cls.mother = rows[0]

    def test_title_and_place_normalization_remove_spacing_and_punctuation(self) -> None:
        self.assertEqual(
            merge.normalize_text("사랑의 불시착!"),
            merge.normalize_text("사랑의불시착"),
        )
        self.assertEqual(
            merge.normalize_title("약한영웅 Class 2"),
            merge.normalize_title("약한영웅2"),
        )
        self.assertEqual(
            merge.normalize_title("모범택시"),
            merge.normalize_title("모범택시1"),
        )
        self.assertEqual(
            merge.normalize_title("월간남친"),
            merge.normalize_title("월간 남자친구"),
        )
        existing = dict(self.mother)
        existing["place_name"] = "오정동 선교사촌 - (한남대학교 선교사촌)"
        self.assertEqual(
            merge.find_duplicate_index([existing], [0], self.mother),
            0,
        )

    def test_swapped_fixture_coordinates_support_near_partial_name_match(self) -> None:
        existing = dict(self.mother)
        existing["place_name"] = "오정동 선교사촌"
        self.assertEqual(
            merge.find_duplicate_index([existing], [0], self.mother),
            0,
        )

    def test_partial_name_requires_distance_within_300_meters(self) -> None:
        existing = dict(self.mother)
        existing["place_name"] = "오정동 선교사촌"
        # 마더 픽스처는 위도/경도 열이 뒤바뀌어 있으므로 실제 위도에 해당하는
        # place_longitude를 약 1km 이동시킨다.
        existing["place_longitude"] = str(
            float(existing["place_longitude"]) + 0.01
        )
        self.assertIsNone(
            merge.find_duplicate_index([existing], [0], self.mother)
        )

    def test_near_coordinates_still_require_partial_name(self) -> None:
        existing = dict(self.mother)
        existing["place_name"] = "전혀다른장소"
        self.assertIsNone(
            merge.find_duplicate_index([existing], [0], self.mother)
        )

    def test_duplicate_supplements_blanks_and_merges_sources(self) -> None:
        existing = dict(self.mother)
        existing["place_address"] = ""
        existing["scene_description"] = ""
        existing["source_url"] = "https://example.com/existing"
        recollected = dict(self.mother)
        recollected["source_url"] = (
            "https://example.com/existing;https://example.com/recollected"
        )

        filled, changed = merge.supplement_duplicate(existing, recollected)

        self.assertTrue(changed)
        self.assertEqual(filled, 2)
        self.assertEqual(existing["place_address"], self.mother["place_address"])
        self.assertEqual(
            existing["scene_description"], self.mother["scene_description"]
        )
        self.assertEqual(
            existing["source_url"],
            "https://example.com/existing;https://example.com/recollected",
        )


class TemporaryPipelineTest(unittest.TestCase):
    """실데이터를 수정하지 않고 임시 본체 사본에 병합하는 통합 테스트."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.recollect_dir = self.root / "조합작업" / "전수재수집"
        self.recollect_dir.mkdir(parents=True)
        self.fixture_copy = self.recollect_dir / "재수집_마더.csv"
        shutil.copy2(MOTHER_FIXTURE, self.fixture_copy)
        self.fixture_hash = sha256(self.fixture_copy)

        fixture_headers, fixture_rows = merge.read_csv(self.fixture_copy)
        self.fixture_rows = fixture_rows
        first = fixture_rows[0]

        self.drama_headers = list(merge.DRAMA_REQUIRED_FIELDS)
        existing = {field_name: "" for field_name in self.drama_headers}
        for field_name in fixture_headers:
            existing[field_name] = first[field_name]
        existing["id"] = "st_00007"
        existing["famous_rank"] = "42"
        existing["source_url"] = "https://example.com/existing"
        existing["scene_description"] = ""
        self.drama_path = self.root / "드라마_kdramamap_스키마.csv"
        write_csv(self.drama_path, self.drama_headers, [existing])

        self.location_headers = self.drama_headers + ["audience_acc", "award"]
        location_existing = {
            field_name: existing.get(field_name, "")
            for field_name in self.location_headers
        }
        movie_existing = {field_name: "" for field_name in self.location_headers}
        movie_existing.update(
            {
                "id": "mv_00001",
                "title": "테스트 영화",
                "title_category": "movie",
                "place_name": "기존 영화 촬영지",
            }
        )
        self.location_path = self.root / "촬영지_마스터.csv"
        write_csv(
            self.location_path,
            self.location_headers,
            [location_existing, movie_existing],
        )

        self.target_path = self.recollect_dir / "_대상목록.csv"
        write_csv(
            self.target_path,
            ["priority", "title"],
            [{"priority": "T100-001", "title": "마더"}],
        )
        self.backup_root = self.root / "codex"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def pipeline(self, *, apply: bool) -> merge.PipelineResult:
        return merge.run_pipeline(
            drama_master_path=self.drama_path,
            location_master_path=self.location_path,
            recollect_dir=self.recollect_dir,
            target_list_path=self.target_path,
            backup_root=self.backup_root,
            apply=apply,
            now=datetime(2026, 7, 30, 12, 34, 56),
        )

    def test_default_dry_run_changes_nothing_and_creates_no_backup(self) -> None:
        before = (sha256(self.drama_path), sha256(self.location_path))

        result = self.pipeline(apply=False)

        after = (sha256(self.drama_path), sha256(self.location_path))
        self.assertEqual(before, after)
        self.assertFalse(result.applied)
        self.assertFalse(self.backup_root.exists())
        self.assertEqual(result.totals.duplicate, 1)
        self.assertEqual(result.totals.added, len(self.fixture_rows) - 1)

    def test_apply_updates_only_temp_copies_and_creates_backups(self) -> None:
        result = self.pipeline(apply=True)

        self.assertTrue(result.applied)
        self.assertEqual(len(result.backup_paths), 2)
        self.assertTrue(all(path.exists() for path in result.backup_paths))
        self.assertEqual(sha256(self.fixture_copy), self.fixture_hash)

        drama_headers, drama_rows = merge.read_csv(self.drama_path)
        location_headers, location_rows = merge.read_csv(self.location_path)
        self.assertEqual(drama_headers, self.drama_headers)
        self.assertEqual(location_headers, self.location_headers)
        self.assertEqual(len(drama_rows), len(self.fixture_rows))
        self.assertEqual(len(location_rows), len(self.fixture_rows) + 1)
        self.assertEqual(drama_rows[0]["id"], "st_00007")
        self.assertEqual(drama_rows[1]["id"], "st_00008")
        self.assertEqual(drama_rows[-1]["id"], f"st_{6 + len(drama_rows):05d}")
        self.assertTrue(
            all(row["famous_rank"] == "42" for row in drama_rows[1:])
        )
        self.assertTrue(
            all(row["recent_rank"] == "" for row in drama_rows[1:])
        )
        self.assertIn(
            self.fixture_rows[0]["source_url"], drama_rows[0]["source_url"]
        )
        self.assertEqual(location_rows[0]["id"], "st_00007")
        self.assertEqual(location_rows[1]["id"], "mv_00001")
        self.assertEqual(
            [row["id"] for row in drama_rows],
            [location_rows[0]["id"]]
            + [row["id"] for row in location_rows[2:]],
        )
        self.assertEqual(self.drama_path.read_bytes()[:3], b"\xef\xbb\xbf")
        self.assertEqual(self.location_path.read_bytes()[:3], b"\xef\xbb\xbf")

    def test_new_work_rank_is_derived_from_target_priority(self) -> None:
        write_csv(self.drama_path, self.drama_headers, [])
        write_csv(self.location_path, self.location_headers, [])
        write_csv(
            self.target_path,
            ["priority", "title"],
            [{"priority": "T20-06", "title": "마더"}],
        )

        result = self.pipeline(apply=True)
        _, rows = merge.read_csv(self.drama_path)

        self.assertEqual(result.totals.added, len(self.fixture_rows))
        self.assertTrue(all(row["famous_rank"] == "" for row in rows))
        self.assertTrue(all(row["recent_rank"] == "6" for row in rows))

    def test_same_day_repeated_backups_never_overwrite(self) -> None:
        fixed_time = datetime(2026, 7, 30, 12, 34, 56)
        sources = [self.drama_path, self.location_path]

        first = merge.make_backups(sources, self.backup_root, now=fixed_time)
        second = merge.make_backups(sources, self.backup_root, now=fixed_time)
        third = merge.make_backups(sources, self.backup_root, now=fixed_time)

        all_paths = first + second + third
        self.assertEqual(len(all_paths), len(set(all_paths)))
        self.assertTrue(all(path.exists() for path in all_paths))


if __name__ == "__main__":
    unittest.main(verbosity=2)
