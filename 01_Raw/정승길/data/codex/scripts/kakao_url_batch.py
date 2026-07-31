#!/usr/bin/env python3
"""TOP120 촬영지의 카카오 장소 URL·좌표를 수집한다.

원본 CSV는 읽기만 한다. 각 행의 처리 결과를 JSONL 캐시에 즉시 기록하고,
검수용 CSV는 100건마다 원자적으로 다시 써서 중단 후에도 재개할 수 있다.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import signal
import sys
import tempfile
import time
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

import requests


DATA_DIR = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = DATA_DIR / "조합작업" / "TOP120완성" / "카카오대상.csv"
DEFAULT_OUTPUT = DATA_DIR / "조합작업" / "TOP120완성" / "카카오결과.csv"
DEFAULT_CACHE = (
    DATA_DIR / "조합작업" / "TOP120완성" / "카카오결과_cache.jsonl"
)

ENDPOINT = "https://k-skill-proxy.nomadamas.org/v1/kakao-map/search/keyword"
POLICY_VERSION = 1
MIN_PACING_SECONDS = 1.2

OUTPUT_FIELDS = [
    "id",
    "place_name",
    "kakao_place_id",
    "kakao_url",
    "kakao_lat",
    "kakao_lng",
    "match_confidence",
    "matched_name",
    "matched_address",
]

ENUM_OR_STATUS_RE = re.compile(
    r"\s*\((?:\d+|폐업|철거|이전|구\s*[^)]*|옛\s*[^)]*)\)\s*$"
)
CLOSED_RE = re.compile(r"\(\s*폐업\s*\)")
DESCRIPTIVE_RE = re.compile(
    r"(?:"
    r"앞|뒤|옆|건너편|인근|일대|주변|진입로|구간|방면|"
    r"골목|도로변|횡단보도"
    r")\s*\)?\s*$"
)
FACILITY_SUFFIX_RE = re.compile(
    r"(?:신사옥|사옥|본관|별관|신관|구관|청사|캠퍼스|건물)$"
)
BRANCH_SUFFIXES = ("직영점", "본점", "지점", "몰점", "센터점", "점")
BRANCH_END_RE = re.compile(r"(?:직영점|본점|지점|몰점|센터점|점)$")


@dataclass(frozen=True)
class InputRow:
    id: str
    title: str
    place_name: str
    place_address: str
    place_latitude: str
    place_longitude: str
    row_key: str


class RequestError(RuntimeError):
    """한 행의 카카오 검색이 재시도 후에도 실패한 경우."""


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\ufeff", "").split())


def parse_float(value: Any) -> float | None:
    try:
        number = float(clean_text(value))
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def format_coord(value: Any) -> str:
    number = parse_float(value)
    if number is None:
        return ""
    return f"{number:.10f}".rstrip("0").rstrip(".")


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKC", clean_text(value)).casefold()
    return re.sub(r"[^0-9a-z가-힣]+", "", text)


def search_name(value: str) -> str:
    return clean_text(ENUM_OR_STATUS_RE.sub("", clean_text(value)))


def precheck_failure_reason(value: str) -> str:
    name = clean_text(value)
    if CLOSED_RE.search(name):
        return "closed_place_name"
    if DESCRIPTIVE_RE.search(search_name(name)):
        return "descriptive_place_name"
    return ""


def make_row_key(row: dict[str, str]) -> str:
    canonical = [
        clean_text(row.get("id")),
        clean_text(row.get("title")),
        clean_text(row.get("place_name")),
        clean_text(row.get("place_address")),
        format_coord(row.get("place_latitude")),
        format_coord(row.get("place_longitude")),
    ]
    body = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def row_from_dict(row: dict[str, str]) -> InputRow:
    return InputRow(
        id=clean_text(row.get("id")),
        title=clean_text(row.get("title")),
        place_name=clean_text(row.get("place_name")),
        place_address=clean_text(row.get("place_address")),
        place_latitude=clean_text(row.get("place_latitude")),
        place_longitude=clean_text(row.get("place_longitude")),
        row_key=make_row_key(row),
    )


def load_input(path: Path) -> list[InputRow]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = {
            field
            for field in (
                "id",
                "title",
                "place_name",
                "place_address",
                "place_latitude",
                "place_longitude",
            )
            if field not in (reader.fieldnames or [])
        }
        if missing:
            raise ValueError(f"입력 CSV 필수 컬럼 누락: {sorted(missing)}")
        rows = [row_from_dict(row) for row in reader]

    if any(not row.id for row in rows):
        raise ValueError("입력 CSV에 id가 빈 행이 있습니다.")
    ids = [row.id for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("입력 CSV의 id가 중복됩니다.")
    return rows


def address_tokens(value: str) -> set[str]:
    tokens = re.findall(
        r"[0-9a-zA-Z가-힣]+",
        unicodedata.normalize("NFKC", clean_text(value)),
    )
    return {token.casefold() for token in tokens if len(token) > 1}


def sigungu_tokens(value: str) -> set[str]:
    return {
        token
        for token in address_tokens(value)
        if re.search(r"(?:시|군|구)$", token)
        and not re.search(r"(?:특별시|광역시|특별자치시)$", token)
    }


def neighborhood_tokens(value: str) -> set[str]:
    return {
        token
        for token in address_tokens(value)
        if re.search(r"(?:읍|면|동|리|[0-9]가)$", token)
    }


def address_requirements(original: str, matched: str) -> tuple[bool, bool]:
    original_sigungu = sigungu_tokens(original)
    matched_sigungu = sigungu_tokens(matched)
    same_sigungu = bool(
        original_sigungu
        and matched_sigungu
        and original_sigungu.issubset(matched_sigungu)
    )
    original_neighborhood = neighborhood_tokens(original)
    matched_neighborhood = neighborhood_tokens(matched)
    same_neighborhood = bool(
        original_neighborhood
        and matched_neighborhood
        and original_neighborhood.issubset(matched_neighborhood)
    )
    return same_sigungu, same_neighborhood


def address_similarity(original: str, matched: str) -> float:
    left = address_tokens(original)
    right = address_tokens(matched)
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def terminal_branch(value: str) -> tuple[bool, str]:
    tokens = re.findall(
        r"[0-9a-zA-Z가-힣]+",
        unicodedata.normalize("NFKC", clean_text(value)).casefold(),
    )
    if not tokens:
        return False, ""
    last = tokens[-1]
    for suffix in BRANCH_SUFFIXES:
        if not last.endswith(suffix):
            continue
        branch = last[: -len(suffix)]
        if not branch and len(tokens) >= 2:
            branch = tokens[-2]
        return True, normalize_name(branch)
    return False, ""


def branch_tokens_match(original: str, matched: str) -> bool:
    if normalize_name(original) == normalize_name(matched):
        return True
    original_has_branch, original_branch = terminal_branch(original)
    matched_has_branch, matched_branch = terminal_branch(matched)
    if original_has_branch != matched_has_branch:
        return False
    if not original_has_branch:
        return True
    return bool(
        original_branch
        and matched_branch
        and original_branch == matched_branch
    )


def address_localities(address: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[0-9a-zA-Z가-힣]+", address)
        if re.search(
            r"(?:특별시|광역시|특별자치시|특별자치도|도|시|군|구|읍|면|동|리)$",
            token,
        )
    ]


def name_variants(
    value: str,
    localities: Iterable[str],
    *,
    candidate: bool,
) -> set[str]:
    base = normalize_name(ENUM_OR_STATUS_RE.sub("", clean_text(value)))
    variants = {base} if base else set()
    if not candidate or not base:
        return variants

    for locality in localities:
        prefix = normalize_name(locality)
        if prefix and base.startswith(prefix) and len(base) > len(prefix) + 1:
            variants.add(base[len(prefix) :])

    for variant in list(variants):
        stripped = FACILITY_SUFFIX_RE.sub("", variant)
        if stripped and len(stripped) >= 2:
            variants.add(stripped)
    return variants


def pair_similarity(original: str, matched: str) -> float:
    if not original or not matched:
        return 0.0
    if original == matched:
        return 1.0
    ratio = SequenceMatcher(None, original, matched).ratio()
    shorter, longer = sorted((original, matched), key=len)
    if shorter in longer:
        containment = 0.72 + 0.28 * (len(shorter) / len(longer))
        ratio = max(ratio, containment)
        if len(original) <= 4 and len(matched) >= len(original) * 2:
            if BRANCH_END_RE.search(matched):
                ratio = min(ratio, 0.56)
    return min(1.0, ratio)


def name_similarity(original: str, matched: str, address: str) -> float:
    localities = address_localities(address)
    originals = name_variants(original, localities, candidate=False)
    matches = name_variants(matched, localities, candidate=True)
    return max(
        (pair_similarity(left, right) for left in originals for right in matches),
        default=0.0,
    )


def haversine_m(
    lat1: float | None,
    lng1: float | None,
    lat2: float | None,
    lng2: float | None,
) -> float | None:
    if None in (lat1, lng1, lat2, lng2):
        return None
    radius = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def candidate_match_address(item: dict[str, Any]) -> str:
    return clean_text(
        f"{item.get('road_address_name') or ''} "
        f"{item.get('address_name') or ''}"
    )


def candidate_output_address(item: dict[str, Any]) -> str:
    return clean_text(
        item.get("road_address_name") or item.get("address_name") or ""
    )


def score_candidate(row: InputRow, item: dict[str, Any]) -> dict[str, Any]:
    matched_name = clean_text(item.get("place_name"))
    match_address = candidate_match_address(item)
    kakao_lat = parse_float(item.get("y"))
    kakao_lng = parse_float(item.get("x"))
    original_lat = parse_float(row.place_latitude)
    original_lng = parse_float(row.place_longitude)
    distance = haversine_m(
        original_lat,
        original_lng,
        kakao_lat,
        kakao_lng,
    )
    name_score = name_similarity(
        search_name(row.place_name),
        matched_name,
        row.place_address,
    )
    address_score = address_similarity(row.place_address, match_address)
    same_sigungu, same_neighborhood = address_requirements(
        row.place_address,
        match_address,
    )
    branches_match = branch_tokens_match(
        search_name(row.place_name),
        matched_name,
    )
    has_original_coords = original_lat is not None and original_lng is not None
    has_kakao_coords = kakao_lat is not None and kakao_lng is not None

    high = (
        name_score >= 0.86
        and branches_match
        and has_kakao_coords
        and (
            (
                has_original_coords
                and distance is not None
                and distance <= 300
            )
            or (
                not has_original_coords
                and same_sigungu
                and same_neighborhood
            )
        )
    )
    if high:
        confidence = "high"
    elif name_score >= 0.70:
        confidence = "mid"
    else:
        confidence = "low"

    distance_score = 0.0
    if distance is not None:
        if distance <= 100:
            distance_score = 1.0
        elif distance <= 300:
            distance_score = 0.85
        elif distance <= 1_000:
            distance_score = 0.35
    selection_score = (
        name_score * 0.82
        + address_score * 0.08
        + distance_score * 0.10
    )
    return {
        "item": item,
        "confidence": confidence,
        "name_score": name_score,
        "address_score": address_score,
        "same_sigungu": same_sigungu,
        "same_neighborhood": same_neighborhood,
        "branches_match": branches_match,
        "distance_m": distance,
        "selection_score": selection_score,
        "kakao_lat": kakao_lat,
        "kakao_lng": kakao_lng,
    }


def choose_candidate(
    row: InputRow,
    documents: Iterable[dict[str, Any]],
) -> dict[str, Any] | None:
    scored = [
        score_candidate(row, item)
        for item in documents
        if clean_text(item.get("id")) and clean_text(item.get("place_name"))
    ]
    if not scored:
        return None
    confidence_rank = {"high": 2, "mid": 1, "low": 0}
    return max(
        scored,
        key=lambda value: (
            confidence_rank[value["confidence"]],
            value["selection_score"],
            value["name_score"],
            value["address_score"],
            -(value["distance_m"] or 10**12),
        ),
    )


def address_prefix(value: str) -> str:
    tokens = re.findall(
        r"[0-9a-zA-Z가-힣-]+",
        unicodedata.normalize("NFKC", clean_text(value)),
    )
    return " ".join(tokens[:3])


def query_for_row(row: InputRow) -> tuple[str, dict[str, str]]:
    name = search_name(row.place_name)
    lat = parse_float(row.place_latitude)
    lng = parse_float(row.place_longitude)
    if lat is not None and lng is not None:
        return name, {
            "q": name,
            "x": format_coord(lng),
            "y": format_coord(lat),
            "radius": "1000",
            "sort": "accuracy",
        }
    query = clean_text(f"{name} {address_prefix(row.place_address)}")
    return query, {"q": query}


def empty_result(row: InputRow, confidence: str) -> dict[str, str]:
    return {
        "id": row.id,
        "place_name": row.place_name,
        "kakao_place_id": "",
        "kakao_url": "",
        "kakao_lat": "",
        "kakao_lng": "",
        "match_confidence": confidence,
        "matched_name": "",
        "matched_address": "",
    }


def output_from_candidate(
    row: InputRow,
    best: dict[str, Any] | None,
) -> dict[str, str]:
    if best is None:
        return empty_result(row, "failed")
    confidence = best["confidence"]
    if confidence == "low":
        return empty_result(row, "low")
    item = best["item"]
    result = empty_result(row, confidence)
    result.update(
        {
            "kakao_place_id": clean_text(item.get("id")),
            "kakao_url": clean_text(item.get("place_url")),
            "kakao_lat": format_coord(best["kakao_lat"]),
            "kakao_lng": format_coord(best["kakao_lng"]),
            "matched_name": clean_text(item.get("place_name")),
            "matched_address": candidate_output_address(item),
        }
    )
    return result


def snapshot_document(item: dict[str, Any]) -> dict[str, str]:
    return {
        "id": clean_text(item.get("id")),
        "place_name": clean_text(item.get("place_name")),
        "road_address_name": clean_text(item.get("road_address_name")),
        "address_name": clean_text(item.get("address_name")),
        "x": format_coord(item.get("x")),
        "y": format_coord(item.get("y")),
        "place_url": clean_text(item.get("place_url")),
    }


class KakaoProxyClient:
    def __init__(
        self,
        *,
        delay: float,
        timeout: float,
        backoff_base: float,
    ) -> None:
        if delay < MIN_PACING_SECONDS:
            raise ValueError(
                f"호출 간격은 최소 {MIN_PACING_SECONDS:.1f}초여야 합니다."
            )
        self.delay = delay
        self.timeout = timeout
        self.backoff_base = backoff_base
        self.last_request_at = 0.0
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "TOP120-Kakao-URL-Batch/1.0",
            }
        )

    def _pace(self) -> None:
        elapsed = time.monotonic() - self.last_request_at
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

    @staticmethod
    def _retry_after_seconds(
        response: requests.Response | None,
        data: Any,
    ) -> float:
        candidates: list[float] = []
        if isinstance(data, dict):
            value = parse_float(data.get("retry_after_ms"))
            if value is not None:
                candidates.append(value / 1000.0)
        if response is not None:
            value = parse_float(response.headers.get("Retry-After"))
            if value is not None:
                candidates.append(value)
        return max(candidates, default=0.0)

    def search(self, params: dict[str, str]) -> list[dict[str, Any]]:
        last_error = ""
        for attempt in range(2):
            self._pace()
            response: requests.Response | None = None
            data: Any = None
            try:
                response = self.session.get(
                    ENDPOINT,
                    params=params,
                    timeout=self.timeout,
                )
                self.last_request_at = time.monotonic()
                try:
                    data = response.json()
                except ValueError:
                    data = None

                api_error = (
                    isinstance(data, dict)
                    and clean_text(data.get("error"))
                )
                if response.status_code >= 400 or api_error:
                    detail = (
                        json.dumps(data, ensure_ascii=False)[:500]
                        if data is not None
                        else response.text[:500]
                    )
                    last_error = f"HTTP {response.status_code}: {detail}"
                    raise RequestError(last_error)
                if not isinstance(data, dict):
                    last_error = (
                        f"JSON object가 아닌 응답: {response.text[:500]}"
                    )
                    raise RequestError(last_error)
                documents = data.get("documents")
                if not isinstance(documents, list):
                    last_error = "응답에 documents[]가 없습니다."
                    raise RequestError(last_error)
                return [
                    item for item in documents if isinstance(item, dict)
                ]
            except requests.RequestException as exc:
                self.last_request_at = time.monotonic()
                last_error = f"{type(exc).__name__}: {exc}"
            except RequestError:
                pass

            if attempt == 0:
                retry_after = self._retry_after_seconds(response, data)
                backoff = max(self.backoff_base * (2**attempt), retry_after)
                time.sleep(backoff)

        raise RequestError(last_error or "알 수 없는 카카오 API 오류")


def process_row(
    row: InputRow,
    client: KakaoProxyClient,
) -> tuple[dict[str, str], dict[str, Any]]:
    precheck_reason = precheck_failure_reason(row.place_name)
    if precheck_reason:
        return (
            empty_result(row, "failed"),
            {
                "status": "precheck_failed",
                "precheck_reason": precheck_reason,
                "query": "",
                "candidate_count": 0,
                "error": "",
            },
        )

    query, params = query_for_row(row)
    try:
        documents = client.search(params)
    except RequestError as exc:
        return (
            empty_result(row, "failed"),
            {
                "status": "request_error",
                "precheck_reason": "",
                "query": query,
                "params": params,
                "candidate_count": 0,
                "error": str(exc),
            },
        )

    best = choose_candidate(row, documents)
    result = output_from_candidate(row, best)
    meta: dict[str, Any] = {
        "status": "ok",
        "precheck_reason": "",
        "query": query,
        "params": params,
        "candidate_count": len(documents),
        "error": "",
    }
    if best is not None:
        meta.update(
            {
                "name_score": round(best["name_score"], 6),
                "address_score": round(best["address_score"], 6),
                "same_sigungu": best["same_sigungu"],
                "same_neighborhood": best["same_neighborhood"],
                "branches_match": best["branches_match"],
                "distance_m": (
                    round(best["distance_m"], 2)
                    if best["distance_m"] is not None
                    else None
                ),
                "selected": snapshot_document(best["item"]),
            }
        )
    return result, meta


def load_cache(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                print(
                    f"[cache] 손상된 행 무시: {path}:{line_number}",
                    file=sys.stderr,
                    flush=True,
                )
                continue
            if record.get("policy_version") != POLICY_VERSION:
                continue
            row_key = clean_text(record.get("row_key"))
            result = record.get("result")
            if row_key and isinstance(result, dict):
                records[row_key] = record
    return records


def append_cache(
    handle: Any,
    row: InputRow,
    result: dict[str, str],
    meta: dict[str, Any],
) -> None:
    record = {
        "policy_version": POLICY_VERSION,
        "row_key": row.row_key,
        "input": asdict(row),
        "result": result,
        "meta": meta,
        "processed_at": now_iso(),
    }
    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    handle.flush()
    os.fsync(handle.fileno())


def atomic_write_csv(
    path: Path,
    rows: Iterable[dict[str, str]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(
            fd,
            "w",
            encoding="utf-8-sig",
            newline="",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=OUTPUT_FIELDS,
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def completed_output_rows(
    input_rows: Iterable[InputRow],
    results: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    return [
        results[row.row_key]
        for row in input_rows
        if row.row_key in results
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--delay", type=float, default=MIN_PACING_SECONDS)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--backoff-base", type=float, default=2.4)
    parser.add_argument("--flush-every", type=int, default=100)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument(
        "--limit",
        type=int,
        help="테스트용: 입력 앞부분 N행만 처리",
    )
    parser.add_argument(
        "--only-id",
        help="테스트/재검사용: 지정한 id 한 행만 처리",
    )
    parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="캐시된 request_error 행만 다시 API 호출",
    )
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if args.delay < MIN_PACING_SECONDS:
        raise ValueError(
            f"--delay는 {MIN_PACING_SECONDS:.1f} 이상이어야 합니다."
        )
    if args.timeout <= 0 or args.backoff_base < 0:
        raise ValueError("timeout은 양수, backoff-base는 0 이상이어야 합니다.")
    if args.flush_every <= 0 or args.progress_every <= 0:
        raise ValueError("flush/progress 간격은 양수여야 합니다.")
    if args.limit is not None and args.limit <= 0:
        raise ValueError("--limit는 양수여야 합니다.")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    validate_args(args)
    input_rows = load_input(args.input)
    if args.only_id:
        input_rows = [row for row in input_rows if row.id == args.only_id]
        if not input_rows:
            raise ValueError(f"입력에서 id를 찾지 못했습니다: {args.only_id}")
    if args.limit is not None:
        input_rows = input_rows[: args.limit]

    cached_records = load_cache(args.cache)
    results: dict[str, dict[str, str]] = {}
    metas: dict[str, dict[str, Any]] = {}
    for row in input_rows:
        record = cached_records.get(row.row_key)
        if record is None:
            continue
        if (
            args.retry_errors
            and (record.get("meta") or {}).get("status") == "request_error"
        ):
            continue
        results[row.row_key] = record["result"]
        metas[row.row_key] = record.get("meta") or {}

    atomic_write_csv(
        args.output,
        completed_output_rows(input_rows, results),
    )
    pending = [row for row in input_rows if row.row_key not in results]
    print(
        f"[start] total={len(input_rows)} cached={len(results)} "
        f"pending={len(pending)} delay={args.delay:.1f}s",
        flush=True,
    )

    stop_requested = False

    def request_stop(signum: int, frame: Any) -> None:
        del signum, frame
        nonlocal stop_requested
        stop_requested = True
        print(
            "[signal] 현재 행 처리 후 캐시와 CSV를 저장하고 종료합니다.",
            flush=True,
        )

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    client = KakaoProxyClient(
        delay=args.delay,
        timeout=args.timeout,
        backoff_base=args.backoff_base,
    )
    args.cache.parent.mkdir(parents=True, exist_ok=True)
    processed_new = 0
    since_flush = 0
    with args.cache.open("a", encoding="utf-8") as cache_handle:
        for row in pending:
            if stop_requested:
                break
            result, meta = process_row(row, client)
            append_cache(cache_handle, row, result, meta)
            results[row.row_key] = result
            metas[row.row_key] = meta
            processed_new += 1
            since_flush += 1

            completed = len(results)
            if (
                processed_new % args.progress_every == 0
                or completed == len(input_rows)
            ):
                distribution = Counter(
                    value["match_confidence"] for value in results.values()
                )
                print(
                    f"[progress] completed={completed}/{len(input_rows)} "
                    f"new={processed_new} grades={dict(distribution)} "
                    f"last_id={row.id}",
                    flush=True,
                )
            if since_flush >= args.flush_every:
                atomic_write_csv(
                    args.output,
                    completed_output_rows(input_rows, results),
                )
                since_flush = 0
                print(
                    f"[flush] rows={completed} output={args.output}",
                    flush=True,
                )

    atomic_write_csv(
        args.output,
        completed_output_rows(input_rows, results),
    )
    distribution = Counter(
        value["match_confidence"] for value in results.values()
    )
    request_errors = sum(
        meta.get("status") == "request_error" for meta in metas.values()
    )
    precheck_failures = sum(
        meta.get("status") == "precheck_failed" for meta in metas.values()
    )
    recovered_coordinates = sum(
        parse_float(row.place_latitude) is None
        and parse_float(row.place_longitude) is None
        and bool(results.get(row.row_key, {}).get("kakao_lat"))
        and bool(results.get(row.row_key, {}).get("kakao_lng"))
        for row in input_rows
    )
    print(
        f"[done] completed={len(results)}/{len(input_rows)} "
        f"new={processed_new} grades={dict(distribution)} "
        f"recovered_coords={recovered_coordinates} "
        f"precheck_failed={precheck_failures} "
        f"request_errors={request_errors} output={args.output}",
        flush=True,
    )
    return 130 if stop_requested else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"[fatal] {exc}", file=sys.stderr, flush=True)
        raise SystemExit(2)
