#!/usr/bin/env python3
"""TOP120 전수재수집 CSV를 드라마 본체 두 파일에 안전하게 병합한다.

기본 동작은 드라이런이다. 실제 파일 변경은 ``--apply``를 명시했을 때만
수행하며, 변경 직전에 두 본체를 날짜별 백업 디렉터리에 복사한다.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import re
import shutil
import sys
import tempfile
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Sequence


RECOLLECT_FIELDS = [
    "id",
    "title",
    "title_aliases",
    "title_category",
    "title_cast",
    "place_name",
    "place_type",
    "place_address",
    "place_latitude",
    "place_longitude",
    "place_image_url",
    "place_naver_url",
    "scene_description",
    "source_url",
    "last_updated",
]

DRAMA_REQUIRED_FIELDS = RECOLLECT_FIELDS + [
    "famous_rank",
    "recent_rank",
    "place_kakao_url",
]

SUPPLEMENT_FIELDS = [
    "title_aliases",
    "title_category",
    "title_cast",
    "place_name",
    "place_type",
    "place_address",
    "place_latitude",
    "place_longitude",
    "place_image_url",
    "place_naver_url",
    "scene_description",
    "last_updated",
]

ST_ID_RE = re.compile(r"^st_(\d+)$")
PRIORITY_RE = re.compile(r"^(T100|T20)-(\d+)$")
EARTH_RADIUS_M = 6_371_008.8

# 현재 대상목록의 표준 표기와 재수집 title이 의미상 같지만 단순 문장부호
# 정규화로는 이어지지 않는 유일한 확인 사례다. 목록/본체/재수집 모두 같은
# canonical key를 사용해 이 한 쌍만 명시적으로 동등하게 취급한다.
TITLE_EQUIVALENTS = {
    "모범택시": "모범택시1",
    "약한영웅class2": "약한영웅2",
    "월간남친": "월간남자친구",
}


class MergeError(RuntimeError):
    """입력 데이터 또는 병합 안전 조건이 충족되지 않았을 때 발생한다."""


@dataclass
class WorkSummary:
    """작품 하나의 병합 결과."""

    duplicate: int = 0
    supplemented: int = 0
    added: int = 0
    supplemented_fields: int = 0


@dataclass(frozen=True)
class SourceRow:
    """출처 파일 및 원본 행 번호를 포함한 재수집 행."""

    path: Path
    line_number: int
    row: dict[str, str]


@dataclass
class PipelineResult:
    """드라이런 또는 적용 결과와 출력용 통계."""

    summaries: "OrderedDict[str, WorkSummary]"
    source_files: int
    source_rows: int
    original_drama_rows: int
    final_drama_rows: int
    first_new_id: str | None
    last_new_id: str | None
    applied: bool = False
    backup_paths: list[Path] = field(default_factory=list)

    @property
    def totals(self) -> WorkSummary:
        total = WorkSummary()
        for summary in self.summaries.values():
            total.duplicate += summary.duplicate
            total.supplemented += summary.supplemented
            total.added += summary.added
            total.supplemented_fields += summary.supplemented_fields
        return total


def normalize_text(value: str) -> str:
    """공백과 문장부호를 제거하고 대소문자를 접어 비교용 문자열을 만든다."""

    return "".join(char.casefold() for char in (value or "") if char.isalnum())


def normalize_title(value: str) -> str:
    """작품명 기본 정규화 후 확인된 표기 동등어를 canonical key로 바꾼다."""

    normalized = normalize_text(value)
    return TITLE_EQUIVALENTS.get(normalized, normalized)


def names_partially_match(left: str, right: str) -> bool:
    """정규화된 두 장소명 중 하나가 다른 하나를 포함하는지 확인한다."""

    left_norm = normalize_text(left)
    right_norm = normalize_text(right)
    return bool(
        left_norm
        and right_norm
        and (left_norm in right_norm or right_norm in left_norm)
    )


def coordinate_pair(row: Mapping[str, str]) -> tuple[float, float] | None:
    """행의 좌표를 (위도, 경도)로 반환한다.

    두 값이 모두 있어야 하며 숫자와 범위가 유효해야 한다. 일부 기존 수집
    파일처럼 위도/경도 열이 명백히 뒤바뀐 경우에는 거리 계산에 한해 순서를
    바로잡는다. 원본 셀 값 자체는 변경하지 않는다.
    """

    raw_latitude = (row.get("place_latitude") or "").strip()
    raw_longitude = (row.get("place_longitude") or "").strip()
    if not raw_latitude or not raw_longitude:
        return None

    try:
        latitude = float(raw_latitude)
        longitude = float(raw_longitude)
    except ValueError:
        return None

    if -90 <= latitude <= 90 and -180 <= longitude <= 180:
        return latitude, longitude
    if -90 <= longitude <= 90 and -180 <= latitude <= 180:
        return longitude, latitude
    return None


def haversine_distance_m(
    left: tuple[float, float], right: tuple[float, float]
) -> float:
    """두 위경도 좌표 사이의 대권거리를 미터로 계산한다."""

    left_lat, left_lon = map(math.radians, left)
    right_lat, right_lon = map(math.radians, right)
    delta_lat = right_lat - left_lat
    delta_lon = right_lon - left_lon
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(left_lat)
        * math.cos(right_lat)
        * math.sin(delta_lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(haversine)))


def find_duplicate_index(
    rows: Sequence[Mapping[str, str]],
    candidate_indices: Sequence[int],
    recollect_row: Mapping[str, str],
    *,
    max_distance_m: float = 300.0,
) -> int | None:
    """같은 작품 후보 중 중복 장소의 행 인덱스를 반환한다.

    우선 장소명 정규화 완전일치를 찾는다. 완전일치가 없으면 좌표가 300m
    이내이고 장소명 한쪽이 다른 쪽을 포함하는 후보 중 가장 가까운 행을
    선택한다.
    """

    recollect_name = normalize_text(recollect_row.get("place_name", ""))
    if recollect_name:
        for index in candidate_indices:
            if normalize_text(rows[index].get("place_name", "")) == recollect_name:
                return index

    recollect_coordinate = coordinate_pair(recollect_row)
    if recollect_coordinate is None:
        return None

    distance_candidates: list[tuple[float, int]] = []
    for index in candidate_indices:
        existing = rows[index]
        if not names_partially_match(
            existing.get("place_name", ""), recollect_row.get("place_name", "")
        ):
            continue
        existing_coordinate = coordinate_pair(existing)
        if existing_coordinate is None:
            continue
        distance = haversine_distance_m(existing_coordinate, recollect_coordinate)
        if distance <= max_distance_m:
            distance_candidates.append((distance, index))

    if not distance_candidates:
        return None
    distance_candidates.sort(key=lambda item: (item[0], item[1]))
    return distance_candidates[0][1]


def merge_source_urls(existing: str, recollected: str) -> str:
    """세미콜론 URL 목록을 기존 값 우선 순서로 합치고 중복을 제거한다."""

    merged: list[str] = []
    seen: set[str] = set()
    for value in (existing, recollected):
        for url in value.split(";"):
            clean_url = url.strip()
            if clean_url and clean_url not in seen:
                seen.add(clean_url)
                merged.append(clean_url)
    return ";".join(merged)


def supplement_duplicate(
    existing: MutableMapping[str, str], recollected: Mapping[str, str]
) -> tuple[int, bool]:
    """기존 중복 행의 빈 필드를 채우고 URL을 합친다.

    반환값은 ``(채운 빈 필드 수, 행 변경 여부)``다. 기존 비어 있던
    ``source_url``을 채운 경우도 빈 필드 보충으로 센다.
    """

    filled = 0
    changed = False
    for field_name in SUPPLEMENT_FIELDS:
        old_value = (existing.get(field_name) or "").strip()
        new_value = (recollected.get(field_name) or "").strip()
        if not old_value and new_value:
            existing[field_name] = recollected.get(field_name, "")
            filled += 1
            changed = True

    old_source = existing.get("source_url", "")
    new_source = recollected.get("source_url", "")
    merged_source = merge_source_urls(old_source, new_source)
    if merged_source != old_source:
        if not old_source.strip() and merged_source:
            filled += 1
        existing["source_url"] = merged_source
        changed = True

    return filled, changed


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """UTF-8-SIG CSV를 엄격하게 읽어 헤더와 행을 반환한다."""

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            headers = list(reader.fieldnames or [])
            if not headers:
                raise MergeError(f"CSV 헤더가 없습니다: {path}")
            rows: list[dict[str, str]] = []
            for line_number, row in enumerate(reader, start=2):
                if None in row:
                    raise MergeError(
                        f"헤더보다 값이 많은 행이 있습니다: {path}:{line_number}"
                    )
                missing_cells = [
                    field_name for field_name, value in row.items() if value is None
                ]
                if missing_cells:
                    raise MergeError(
                        f"값이 누락된 열이 있습니다: {path}:{line_number} "
                        f"({', '.join(missing_cells)})"
                    )
                rows.append({key: value or "" for key, value in row.items()})
    except FileNotFoundError as exc:
        raise MergeError(f"필수 파일을 찾을 수 없습니다: {path}") from exc
    except UnicodeDecodeError as exc:
        raise MergeError(f"UTF-8 CSV로 읽을 수 없습니다: {path}") from exc
    except csv.Error as exc:
        raise MergeError(f"CSV 형식 오류: {path}: {exc}") from exc
    return headers, rows


def require_fields(path: Path, headers: Sequence[str], required: Iterable[str]) -> None:
    """필수 열이 모두 있는지 검사한다."""

    missing = [field_name for field_name in required if field_name not in headers]
    if missing:
        raise MergeError(f"필수 열 누락: {path} ({', '.join(missing)})")


def load_recollect_rows(recollect_dir: Path) -> list[SourceRow]:
    """재수집 디렉터리의 ``재수집_*.csv``를 파일명 순으로 읽는다."""

    paths = sorted(recollect_dir.glob("재수집_*.csv"))
    if not paths:
        raise MergeError(f"재수집 CSV가 없습니다: {recollect_dir}")

    source_rows: list[SourceRow] = []
    for path in paths:
        headers, rows = read_csv(path)
        if headers != RECOLLECT_FIELDS:
            raise MergeError(
                f"재수집 CSV는 지정된 15개 열과 순서가 같아야 합니다: {path}\n"
                f"예상: {RECOLLECT_FIELDS}\n실제: {headers}"
            )
        if not rows:
            raise MergeError(f"재수집 CSV에 데이터 행이 없습니다: {path}")
        normalized_titles: set[str] = set()
        for offset, row in enumerate(rows, start=2):
            title_key = normalize_title(row.get("title", ""))
            if not title_key:
                raise MergeError(f"title이 비어 있습니다: {path}:{offset}")
            if not normalize_text(row.get("place_name", "")):
                raise MergeError(f"place_name이 비어 있습니다: {path}:{offset}")
            normalized_titles.add(title_key)
            source_rows.append(SourceRow(path=path, line_number=offset, row=row))
        if len(normalized_titles) > 1:
            raise MergeError(f"한 재수집 파일에 여러 작품이 섞여 있습니다: {path}")

    return source_rows


def load_target_ranks(target_list_path: Path) -> dict[str, tuple[str, str]]:
    """대상목록 priority를 ``(famous_rank, recent_rank)``로 변환한다."""

    headers, rows = read_csv(target_list_path)
    require_fields(target_list_path, headers, ("priority", "title"))
    target_ranks: dict[str, tuple[str, str]] = {}
    for line_number, row in enumerate(rows, start=2):
        title_key = normalize_title(row.get("title", ""))
        if not title_key:
            raise MergeError(f"대상목록 title이 비어 있습니다: {target_list_path}:{line_number}")
        match = PRIORITY_RE.fullmatch((row.get("priority") or "").strip())
        if not match:
            raise MergeError(
                f"알 수 없는 priority 형식: {target_list_path}:{line_number} "
                f"({row.get('priority', '')!r})"
            )
        rank_kind, rank_number = match.groups()
        normalized_rank = str(int(rank_number))
        ranks = (
            (normalized_rank, "") if rank_kind == "T100" else ("", normalized_rank)
        )
        if title_key in target_ranks:
            raise MergeError(
                f"정규화 후 중복되는 대상 작품이 있습니다: "
                f"{target_list_path}:{line_number} ({row.get('title', '')})"
            )
        target_ranks[title_key] = ranks
    return target_ranks


def max_st_number(rows: Sequence[Mapping[str, str]]) -> int:
    """행 목록에서 가장 큰 ``st_번호``를 반환한다."""

    maximum = 0
    for row in rows:
        match = ST_ID_RE.fullmatch((row.get("id") or "").strip())
        if match:
            maximum = max(maximum, int(match.group(1)))
    return maximum


def ranks_for_existing_work(
    rows: Sequence[Mapping[str, str]], indices: Sequence[int], title: str
) -> tuple[str, str]:
    """같은 작품 기존 행에서 일관된 랭크 값을 가져온다."""

    values: list[str] = []
    for field_name in ("famous_rank", "recent_rank"):
        distinct = {
            (rows[index].get(field_name) or "").strip()
            for index in indices
            if (rows[index].get(field_name) or "").strip()
        }
        if len(distinct) > 1:
            raise MergeError(
                f"같은 작품의 {field_name} 값이 서로 다릅니다: {title} "
                f"({', '.join(sorted(distinct))})"
            )
        values.append(next(iter(distinct), ""))
    return values[0], values[1]


def build_new_row(
    recollected: Mapping[str, str],
    headers: Sequence[str],
    new_id: str,
    ranks: tuple[str, str],
) -> dict[str, str]:
    """재수집 행을 본체 스키마에 맞춘 신규 행으로 변환한다."""

    new_row = {field_name: "" for field_name in headers}
    for field_name in RECOLLECT_FIELDS:
        if field_name != "id" and field_name in new_row:
            new_row[field_name] = recollected.get(field_name, "")
    new_row["id"] = new_id
    new_row["famous_rank"], new_row["recent_rank"] = ranks
    return new_row


def merge_drama_rows(
    headers: Sequence[str],
    master_rows: Sequence[Mapping[str, str]],
    recollect_rows: Sequence[SourceRow],
    target_ranks: Mapping[str, tuple[str, str]],
) -> tuple[list[dict[str, str]], "OrderedDict[str, WorkSummary]", str | None, str | None]:
    """드라마 본체 복사본에 모든 재수집 행을 병합한다."""

    rows = [dict(row) for row in master_rows]
    title_indices: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        title_indices[normalize_title(row.get("title", ""))].append(index)

    grouped_sources: "OrderedDict[str, list[SourceRow]]" = OrderedDict()
    display_titles: dict[str, str] = {}
    for source in recollect_rows:
        title = (source.row.get("title") or "").strip()
        title_key = normalize_title(title)
        grouped_sources.setdefault(title_key, []).append(source)
        display_titles.setdefault(title_key, title)

    summaries: "OrderedDict[str, WorkSummary]" = OrderedDict()
    next_st_number = max_st_number(rows) + 1
    first_new_id: str | None = None
    last_new_id: str | None = None

    for title_key, work_sources in grouped_sources.items():
        display_title = display_titles[title_key]
        summary = WorkSummary()
        summaries[display_title] = summary
        existing_indices = title_indices.get(title_key, [])
        if existing_indices:
            ranks = ranks_for_existing_work(rows, existing_indices, display_title)
        else:
            try:
                ranks = target_ranks[title_key]
            except KeyError as exc:
                first_source = work_sources[0]
                raise MergeError(
                    f"본체에 없는 작품이 대상목록에도 없습니다: {display_title} "
                    f"({first_source.path}:{first_source.line_number})"
                ) from exc

        for source in work_sources:
            candidate_indices = title_indices.setdefault(title_key, [])
            duplicate_index = find_duplicate_index(
                rows, candidate_indices, source.row
            )
            if duplicate_index is not None:
                summary.duplicate += 1
                filled_fields, _ = supplement_duplicate(
                    rows[duplicate_index], source.row
                )
                if filled_fields:
                    summary.supplemented += 1
                    summary.supplemented_fields += filled_fields
                continue

            new_id = f"st_{next_st_number:05d}"
            next_st_number += 1
            new_row = build_new_row(source.row, headers, new_id, ranks)
            rows.append(new_row)
            title_indices[title_key].append(len(rows) - 1)
            summary.added += 1
            first_new_id = first_new_id or new_id
            last_new_id = new_id

    return rows, summaries, first_new_id, last_new_id


def unique_rows_by_id(
    rows: Sequence[Mapping[str, str]], *, label: str
) -> dict[str, Mapping[str, str]]:
    """ID가 비어 있지 않고 유일한지 확인한 뒤 ID 인덱스를 만든다."""

    indexed: dict[str, Mapping[str, str]] = {}
    for row_number, row in enumerate(rows, start=2):
        row_id = (row.get("id") or "").strip()
        if not row_id:
            raise MergeError(f"{label}에 빈 id가 있습니다: CSV {row_number}행")
        if row_id in indexed:
            raise MergeError(f"{label}에 중복 id가 있습니다: {row_id}")
        indexed[row_id] = row
    return indexed


def validate_master_alignment(
    drama_headers: Sequence[str],
    drama_rows: Sequence[Mapping[str, str]],
    location_headers: Sequence[str],
    location_rows: Sequence[Mapping[str, str]],
) -> None:
    """촬영지 마스터가 드라마 본체의 모든 원본 행을 동일하게 포함하는지 검사한다."""

    missing_headers = [
        field_name for field_name in drama_headers if field_name not in location_headers
    ]
    if missing_headers:
        raise MergeError(
            "촬영지 마스터에 드라마 본체 열이 없습니다: "
            + ", ".join(missing_headers)
        )

    drama_by_id = unique_rows_by_id(drama_rows, label="드라마 본체")
    location_by_id = unique_rows_by_id(location_rows, label="촬영지 마스터")
    for row_id, drama_row in drama_by_id.items():
        location_row = location_by_id.get(row_id)
        if location_row is None:
            raise MergeError(f"촬영지 마스터에 드라마 행이 없습니다: {row_id}")
        differing = [
            field_name
            for field_name in drama_headers
            if drama_row.get(field_name, "") != location_row.get(field_name, "")
        ]
        if differing:
            raise MergeError(
                f"두 본체의 공통 드라마 행이 다릅니다: {row_id} "
                f"({', '.join(differing)})"
            )


def synchronize_location_master(
    drama_headers: Sequence[str],
    original_drama_rows: Sequence[Mapping[str, str]],
    merged_drama_rows: Sequence[Mapping[str, str]],
    location_headers: Sequence[str],
    location_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, str]]:
    """드라마 본체에서 바뀐 공통 행과 신규 행을 촬영지 마스터에 반영한다."""

    original_count = len(original_drama_rows)
    merged_location_rows = [dict(row) for row in location_rows]
    location_indices: dict[str, int] = {}
    for index, row in enumerate(merged_location_rows):
        row_id = row.get("id", "")
        if row_id in location_indices:
            raise MergeError(f"촬영지 마스터에 중복 id가 있습니다: {row_id}")
        location_indices[row_id] = index

    for original_row, merged_row in zip(
        original_drama_rows, merged_drama_rows[:original_count]
    ):
        changed_fields = [
            field_name
            for field_name in drama_headers
            if original_row.get(field_name, "") != merged_row.get(field_name, "")
        ]
        if not changed_fields:
            continue
        location_index = location_indices[merged_row["id"]]
        for field_name in changed_fields:
            merged_location_rows[location_index][field_name] = merged_row[field_name]

    for merged_row in merged_drama_rows[original_count:]:
        row_id = merged_row["id"]
        if row_id in location_indices:
            raise MergeError(f"신규 id가 촬영지 마스터와 충돌합니다: {row_id}")
        location_row = {field_name: "" for field_name in location_headers}
        for field_name in drama_headers:
            location_row[field_name] = merged_row.get(field_name, "")
        merged_location_rows.append(location_row)
        location_indices[row_id] = len(merged_location_rows) - 1

    return merged_location_rows


def write_csv_temp(
    destination: Path, headers: Sequence[str], rows: Sequence[Mapping[str, str]]
) -> Path:
    """목적지와 같은 디렉터리에 UTF-8-SIG 임시 CSV를 완성해 둔다."""

    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(
            file_descriptor, "w", encoding="utf-8-sig", newline=""
        ) as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=list(headers),
                extrasaction="raise",
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(rows)
            stream.flush()
            os.fsync(stream.fileno())
        shutil.copymode(destination, temporary_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return temporary_path


def make_backups(
    source_paths: Sequence[Path],
    backup_root: Path,
    *,
    now: datetime | None = None,
) -> list[Path]:
    """두 본체를 ``backup_YYYYMMDD`` 디렉터리에 충돌 없이 복사한다."""

    timestamp = now or datetime.now()
    backup_dir = backup_root / f"backup_{timestamp:%Y%m%d}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_paths: list[Path] = []
    for source_path in source_paths:
        backup_path = backup_dir / source_path.name
        if backup_path.exists():
            suffix = f"{timestamp:%H%M%S_%f}"
            backup_path = backup_dir / (
                f"{source_path.stem}_{suffix}{source_path.suffix}"
            )
            collision_number = 2
            while backup_path.exists():
                backup_path = backup_dir / (
                    f"{source_path.stem}_{suffix}_{collision_number}"
                    f"{source_path.suffix}"
                )
                collision_number += 1
        shutil.copy2(source_path, backup_path)
        backup_paths.append(backup_path)
    return backup_paths


def replace_both_with_rollback(
    destinations: Sequence[Path],
    temporary_paths: Sequence[Path],
    backup_paths: Sequence[Path],
) -> None:
    """두 임시 파일을 교체하고 두 번째 실패 시 첫 번째를 백업으로 복원한다."""

    if not (len(destinations) == len(temporary_paths) == len(backup_paths) == 2):
        raise ValueError("두 본체 파일을 정확히 지정해야 합니다.")

    first_replaced = False
    try:
        os.replace(temporary_paths[0], destinations[0])
        first_replaced = True
        os.replace(temporary_paths[1], destinations[1])
    except Exception:
        if first_replaced:
            shutil.copy2(backup_paths[0], destinations[0])
        raise
    finally:
        for temporary_path in temporary_paths:
            temporary_path.unlink(missing_ok=True)


def run_pipeline(
    *,
    drama_master_path: Path,
    location_master_path: Path,
    recollect_dir: Path,
    target_list_path: Path,
    backup_root: Path,
    apply: bool = False,
    now: datetime | None = None,
) -> PipelineResult:
    """입력 파일을 검증하고 병합한다. ``apply=False``이면 메모리에서만 수행한다."""

    drama_headers, original_drama_rows = read_csv(drama_master_path)
    require_fields(drama_master_path, drama_headers, DRAMA_REQUIRED_FIELDS)
    location_headers, location_rows = read_csv(location_master_path)
    validate_master_alignment(
        drama_headers,
        original_drama_rows,
        location_headers,
        location_rows,
    )

    target_ranks = load_target_ranks(target_list_path)
    recollect_rows = load_recollect_rows(recollect_dir)
    source_file_count = len({source.path for source in recollect_rows})
    merged_drama_rows, summaries, first_new_id, last_new_id = merge_drama_rows(
        drama_headers,
        original_drama_rows,
        recollect_rows,
        target_ranks,
    )
    merged_location_rows = synchronize_location_master(
        drama_headers,
        original_drama_rows,
        merged_drama_rows,
        location_headers,
        location_rows,
    )

    result = PipelineResult(
        summaries=summaries,
        source_files=source_file_count,
        source_rows=len(recollect_rows),
        original_drama_rows=len(original_drama_rows),
        final_drama_rows=len(merged_drama_rows),
        first_new_id=first_new_id,
        last_new_id=last_new_id,
    )
    if not apply:
        return result

    destinations = [drama_master_path, location_master_path]
    temporary_paths: list[Path] = []
    try:
        temporary_paths.append(
            write_csv_temp(drama_master_path, drama_headers, merged_drama_rows)
        )
        temporary_paths.append(
            write_csv_temp(location_master_path, location_headers, merged_location_rows)
        )
        backup_paths = make_backups(destinations, backup_root, now=now)
        replace_both_with_rollback(destinations, temporary_paths, backup_paths)
    except Exception:
        for temporary_path in temporary_paths:
            temporary_path.unlink(missing_ok=True)
        raise

    result.applied = True
    result.backup_paths = backup_paths
    return result


def print_summary(result: PipelineResult) -> None:
    """사람이 확인하기 쉬운 작품별 병합 요약을 출력한다."""

    mode = "APPLY 완료" if result.applied else "DRY-RUN (파일 변경 없음)"
    print(mode)
    print(
        f"재수집: {result.source_files}개 파일, {result.source_rows}행 | "
        f"드라마 본체: {result.original_drama_rows}행 → {result.final_drama_rows}행"
    )
    print()
    print(f"{'작품':<30} {'중복':>6} {'보충':>6} {'신규':>6}")
    print("-" * 54)
    for title, summary in result.summaries.items():
        print(
            f"{title:<30} {summary.duplicate:>6} "
            f"{summary.supplemented:>6} {summary.added:>6}"
        )
    totals = result.totals
    print("-" * 54)
    print(
        f"{'합계':<30} {totals.duplicate:>6} "
        f"{totals.supplemented:>6} {totals.added:>6}"
    )
    print(f"보충된 빈 필드 수: {totals.supplemented_fields}")
    if result.first_new_id and result.last_new_id:
        print(f"신규 ID 범위: {result.first_new_id} ~ {result.last_new_id}")
    else:
        print("신규 ID: 없음")
    if result.backup_paths:
        print("백업:")
        for backup_path in result.backup_paths:
            print(f"  - {backup_path}")


def default_data_dir() -> Path:
    """스크립트 위치를 기준으로 data 디렉터리를 찾는다."""

    return Path(__file__).resolve().parents[2]


def build_argument_parser() -> argparse.ArgumentParser:
    """명령행 파서를 만든다."""

    parser = argparse.ArgumentParser(
        description=(
            "전수재수집 CSV를 두 본체에 병합합니다. 기본은 드라이런이며 "
            "--apply를 지정해야 파일을 변경합니다."
        )
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=default_data_dir(),
        help="데이터 루트 디렉터리 (기본: 스크립트 기준 자동 탐색)",
    )
    parser.add_argument(
        "--drama-master",
        type=Path,
        help="드라마 본체 CSV (기본: <data-dir>/드라마_kdramamap_스키마.csv)",
    )
    parser.add_argument(
        "--location-master",
        type=Path,
        help="촬영지 마스터 CSV (기본: <data-dir>/촬영지_마스터.csv)",
    )
    parser.add_argument(
        "--recollect-dir",
        type=Path,
        help="재수집 CSV 디렉터리 (기본: <data-dir>/조합작업/전수재수집)",
    )
    parser.add_argument(
        "--target-list",
        type=Path,
        help="대상목록 CSV (기본: <recollect-dir>/_대상목록.csv)",
    )
    parser.add_argument(
        "--backup-root",
        type=Path,
        help="날짜별 백업 디렉터리의 부모 (기본: <data-dir>/codex)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="검증·요약 후 백업을 만들고 두 본체 파일을 실제 갱신",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI 진입점."""

    parser = build_argument_parser()
    arguments = parser.parse_args(argv)
    data_dir = arguments.data_dir.resolve()
    recollect_dir = (
        arguments.recollect_dir or data_dir / "조합작업" / "전수재수집"
    ).resolve()
    drama_master_path = (
        arguments.drama_master or data_dir / "드라마_kdramamap_스키마.csv"
    ).resolve()
    location_master_path = (
        arguments.location_master or data_dir / "촬영지_마스터.csv"
    ).resolve()
    target_list_path = (
        arguments.target_list or recollect_dir / "_대상목록.csv"
    ).resolve()
    backup_root = (arguments.backup_root or data_dir / "codex").resolve()

    try:
        result = run_pipeline(
            drama_master_path=drama_master_path,
            location_master_path=location_master_path,
            recollect_dir=recollect_dir,
            target_list_path=target_list_path,
            backup_root=backup_root,
            apply=arguments.apply,
        )
    except (MergeError, OSError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1

    print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
