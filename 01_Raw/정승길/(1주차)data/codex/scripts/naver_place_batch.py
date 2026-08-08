#!/usr/bin/env python3
"""네이버 플레이스 실제 장소 URL·좌표 수집 배치.

원본 CSV는 읽기만 한다. 진행 결과는 JSONL 캐시에 한 건씩 추가하고,
검수용 CSV는 일정 건수마다 원자적으로 다시 쓴다.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
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
from typing import Any, Callable, Iterable
from urllib.parse import quote

import requests


DATA_DIR = Path(__file__).resolve().parents[2]
DRAMA_CSV = DATA_DIR / "드라마_kdramamap_스키마.csv"
MOVIE_DIR = DATA_DIR / "조합작업" / "영화신규수집"
DEFAULT_OUTPUT = DATA_DIR / "조합작업" / "place_url_네이버.csv"
DEFAULT_CACHE = DATA_DIR / "조합작업" / "place_url_네이버_cache.jsonl"
DEFAULT_STATE = DATA_DIR / "조합작업" / "place_url_네이버_state.json"

ENDPOINT = "https://bff-gateway.place.naver.com/graphql"
DETAIL_ENDPOINT = "https://map.naver.com/p/api/place/summary/{place_id}"
MATCH_POLICY_VERSION = 4
GRAPHQL_QUERY = """
query getPlacesList($input: PlaceExternalListInput) {
  placeList(input: $input) {
    businesses {
      total
      items {
        id
        name
        address {
          roadAddress
          address
        }
        coordinate {
          latitude
          longitude
        }
      }
    }
  }
}
""".strip()

OUTPUT_FIELDS = [
    "place_name",
    "place_address",
    "orig_lat",
    "orig_lng",
    "naver_place_id",
    "naver_url",
    "naver_lat",
    "naver_lng",
    "match_confidence",
    "matched_name",
    "matched_address",
    "verification_status",
    "mismatch_flag",
    "mismatch_reason",
]

DESCRIPTIVE_RE = re.compile(
    r"(?:"
    r"앞|뒤|옆|건너편|인근|일대|주변|입구|출구|진입로|구간|방면|"
    r"골목|도로|거리|사거리|오거리|교차로|로터리|램프|"
    r"정류장|횡단보도|육교|고가|지하도|터널|"
    r"(?:대로|로|길)(?:\(\d[^)]*\)|\(\d*단지앞\)|\(\d+\)|\d*)?"
    r")$"
)
ENUM_OR_STATUS_RE = re.compile(
    r"\s*\((?:\d+|폐업|철거|이전|구\s*[^)]*|옛\s*[^)]*)\)\s*$"
)
CLOSED_RE = re.compile(r"\(\s*폐업\s*\)")
ENUMERATED_AREA_RE = re.compile(
    r"^\s*[0-9a-zA-Z가-힣]+(?:리|동)\s*"
    r"\(\s*\d+(?:\s*-\s*\d+)?\s*\)\s*$"
)
FACILITY_SUFFIX_RE = re.compile(
    r"(?:신사옥|사옥|본관|별관|신관|구관|청사|캠퍼스|건물)$"
)
BRANCH_END_RE = re.compile(r"(?:몰점|본점|지점|직영점|점)$")
BRANCH_SUFFIXES = ("직영점", "본점", "지점", "몰점", "점")
BLOCK_MESSAGE_RE = re.compile(
    r"captcha|wtm|too many|rate.?limit|blocked|forbidden|temporar",
    re.I,
)


@dataclass(frozen=True)
class PlaceCombo:
    place_name: str
    place_address: str
    orig_lat: str
    orig_lng: str
    key: str


class BlockedError(RuntimeError):
    """백오프 후에도 네이버가 요청을 차단한 경우."""


class RequestError(RuntimeError):
    """개별 검색 요청이 네트워크/API 오류로 끝난 경우."""


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


def canonical_coord(value: str) -> str:
    number = parse_float(value)
    if number is None:
        return ""
    return f"{number:.8f}".rstrip("0").rstrip(".")


def format_coord(value: Any) -> str:
    number = parse_float(value)
    if number is None:
        return ""
    return f"{number:.10f}".rstrip("0").rstrip(".")


def combo_key(name: str, address: str, lat: str, lng: str) -> str:
    canonical = [
        clean_text(name),
        clean_text(address),
        canonical_coord(lat),
        canonical_coord(lng),
    ]
    body = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def combo_from_row(row: dict[str, str]) -> PlaceCombo | None:
    name = clean_text(row.get("place_name"))
    if not name:
        return None
    address = clean_text(row.get("place_address"))
    lat = clean_text(row.get("place_latitude"))
    lng = clean_text(row.get("place_longitude"))
    return PlaceCombo(name, address, lat, lng, combo_key(name, address, lat, lng))


def load_combos() -> tuple[list[PlaceCombo], dict[str, int]]:
    combos: dict[str, PlaceCombo] = {}
    stats = {
        "ranked_drama_rows": 0,
        "movie_rows": 0,
        "missing_name_rows": 0,
    }

    with DRAMA_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if not (
                clean_text(row.get("famous_rank"))
                or clean_text(row.get("recent_rank"))
            ):
                continue
            stats["ranked_drama_rows"] += 1
            combo = combo_from_row(row)
            if combo is None:
                stats["missing_name_rows"] += 1
            else:
                combos.setdefault(combo.key, combo)

    for path in sorted(MOVIE_DIR.glob("*.csv")):
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                stats["movie_rows"] += 1
                combo = combo_from_row(row)
                if combo is None:
                    stats["missing_name_rows"] += 1
                else:
                    combos.setdefault(combo.key, combo)

    stats["unique_combos"] = len(combos)
    stats["missing_both_coordinates"] = sum(
        not combo.orig_lat and not combo.orig_lng for combo in combos.values()
    )
    return list(combos.values()), stats


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKC", clean_text(value)).casefold()
    return re.sub(r"[^0-9a-z가-힣]+", "", text)


def search_name(value: str) -> str:
    return clean_text(ENUM_OR_STATUS_RE.sub("", clean_text(value)))


def precheck_failure_reason(value: str) -> str:
    name = clean_text(value)
    if CLOSED_RE.search(name):
        return "closed_place_name"
    if ENUMERATED_AREA_RE.fullmatch(name):
        return "enumerated_area_name"
    return ""


def terminal_branch(value: str) -> tuple[bool, str]:
    """Return whether the name has a branch suffix and its branch token."""
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
    """Conservatively reject high confidence when branch tokens differ."""
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
    tokens = re.findall(r"[0-9a-zA-Z가-힣]+", address)
    return [
        token
        for token in tokens
        if re.search(r"(?:특별시|광역시|특별자치시|특별자치도|도|시|군|구|읍|면|동|리)$", token)
    ]


def region_hint(address: str) -> str:
    tokens = re.findall(r"[0-9a-zA-Z가-힣-]+", address)
    if not tokens:
        return ""
    chosen: list[str] = []
    for token in tokens:
        chosen.append(token)
        if len(chosen) >= 3 or (
            len(chosen) >= 2
            and re.search(r"(?:구|군|읍|면|동|리)$", token)
        ):
            break
    return " ".join(chosen)


def name_variants(value: str, localities: Iterable[str], *, candidate: bool) -> set[str]:
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


def address_tokens(value: str) -> set[str]:
    tokens = re.findall(r"[0-9a-zA-Z가-힣]+", unicodedata.normalize("NFKC", value))
    return {
        token.casefold()
        for token in tokens
        if len(token) > 1 or token.isdigit()
    }


def sigungu_tokens(value: str) -> set[str]:
    tokens = address_tokens(value)
    return {
        token
        for token in tokens
        if re.search(r"(?:시|군|구)$", token)
        and not re.search(r"(?:특별시|광역시|특별자치시)$", token)
    }


def neighborhood_tokens(value: str) -> set[str]:
    return {
        token
        for token in address_tokens(value)
        if re.search(r"(?:읍|면|동|리)$", token)
    }


def road_tokens(value: str) -> set[str]:
    return {
        token
        for token in address_tokens(value)
        if re.search(r"(?:대로|로|길)$", token)
    }


def address_requirements(
    original: str,
    matched: str,
) -> tuple[bool, bool]:
    """Return (same 시군구, same 읍면동 or road-name level)."""
    original_sigungu = sigungu_tokens(original)
    matched_sigungu = sigungu_tokens(matched)
    same_sigungu = bool(
        original_sigungu
        and matched_sigungu
        and original_sigungu.issubset(matched_sigungu)
    )

    original_neighborhood = neighborhood_tokens(original)
    matched_neighborhood = neighborhood_tokens(matched)
    original_roads = road_tokens(original)
    matched_roads = road_tokens(matched)
    same_detail = bool(
        (original_neighborhood & matched_neighborhood)
        or (original_roads & matched_roads)
    )
    return same_sigungu, same_detail


def address_similarity(original: str, matched: str) -> float:
    left = address_tokens(original)
    right = address_tokens(matched)
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


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


def candidate_address(item: dict[str, Any]) -> str:
    address = item.get("address") or {}
    return clean_text(
        f"{address.get('roadAddress') or ''} {address.get('address') or ''}"
    )


def score_candidate(combo: PlaceCombo, item: dict[str, Any]) -> dict[str, Any]:
    coordinate = item.get("coordinate") or {}
    naver_lat = parse_float(coordinate.get("latitude"))
    naver_lng = parse_float(coordinate.get("longitude"))
    distance = haversine_m(
        parse_float(combo.orig_lat),
        parse_float(combo.orig_lng),
        naver_lat,
        naver_lng,
    )
    matched_name = clean_text(item.get("name"))
    matched_address = candidate_address(item)
    name_score = name_similarity(combo.place_name, matched_name, combo.place_address)
    addr_score = address_similarity(
        combo.place_address,
        matched_address,
    )
    same_sigungu, same_address_detail = address_requirements(
        combo.place_address,
        matched_address,
    )
    branches_match = branch_tokens_match(combo.place_name, matched_name)

    coordinate_score = 0.0
    if distance is not None:
        if distance <= 100:
            coordinate_score = 1.0
        elif distance <= 300:
            coordinate_score = 0.85
        elif distance <= 1_000:
            coordinate_score = 0.35
    selection_score = name_score * 0.82 + addr_score * 0.08 + coordinate_score * 0.10
    return {
        "item": item,
        "name_score": name_score,
        "address_score": addr_score,
        "same_sigungu": same_sigungu,
        "same_address_detail": same_address_detail,
        "branches_match": branches_match,
        "distance_m": distance,
        "selection_score": selection_score,
        "naver_lat": naver_lat,
        "naver_lng": naver_lng,
    }


def choose_candidate(
    combo: PlaceCombo, items: Iterable[dict[str, Any]]
) -> dict[str, Any] | None:
    scored = [
        score_candidate(combo, item)
        for item in items
        if clean_text(item.get("id")) and clean_text(item.get("name"))
    ]
    if not scored:
        return None
    return max(
        scored,
        key=lambda value: (
            value["selection_score"],
            value["name_score"],
            value["address_score"],
            -(value["distance_m"] or 10**12),
        ),
    )


def classify_match(combo: PlaceCombo, best: dict[str, Any] | None) -> str:
    if precheck_failure_reason(combo.place_name):
        return "failed"
    if best is None:
        return "failed"

    score = best["name_score"]
    distance = best["distance_m"]
    has_orig_coords = (
        parse_float(combo.orig_lat) is not None
        and parse_float(combo.orig_lng) is not None
    )
    has_naver_coords = (
        best["naver_lat"] is not None and best["naver_lng"] is not None
    )

    high_requirements = (
        score >= 0.86
        and best["branches_match"]
        and best["same_sigungu"]
        and best["same_address_detail"]
        and has_orig_coords
        and has_naver_coords
        and distance is not None
        and distance <= 300
    )
    if high_requirements:
        return "high"

    if score >= 0.70:
        gross_location_mismatch = (
            (has_orig_coords and distance is not None and distance > 3_000)
            or (
                bool(sigungu_tokens(combo.place_address))
                and not best["same_sigungu"]
            )
        )
        return "low" if gross_location_mismatch else "mid"

    descriptive = bool(DESCRIPTIVE_RE.search(search_name(combo.place_name)))
    if score >= 0.52 and not descriptive:
        return "low"
    return "failed"


def make_queries(combo: PlaceCombo, max_attempts: int) -> list[str]:
    name = search_name(combo.place_name)
    possibilities = [
        clean_text(f"{name} {combo.place_address}"),
        clean_text(f"{name} {region_hint(combo.place_address)}"),
        name,
    ]
    result: list[str] = []
    for query in possibilities:
        if query and query not in result:
            result.append(query)
    return result[:max_attempts]


def snapshot_item(item: dict[str, Any]) -> dict[str, Any]:
    coordinate = item.get("coordinate") or {}
    address = item.get("address") or {}
    return {
        "id": clean_text(item.get("id")),
        "name": clean_text(item.get("name")),
        "address": {
            "roadAddress": clean_text(address.get("roadAddress")),
            "address": clean_text(address.get("address")),
        },
        "coordinate": {
            "latitude": parse_float(coordinate.get("latitude")),
            "longitude": parse_float(coordinate.get("longitude")),
        },
    }


def item_from_result(result: dict[str, Any]) -> dict[str, Any]:
    """Rebuild a single bound candidate from a legacy cached result."""
    return {
        "id": clean_text(result.get("naver_place_id")),
        "name": clean_text(result.get("matched_name")),
        "address": {
            "roadAddress": clean_text(result.get("matched_address")),
            "address": "",
        },
        "coordinate": {
            "latitude": parse_float(result.get("naver_lat")),
            "longitude": parse_float(result.get("naver_lng")),
        },
    }


def verification_result(
    requested_id: str,
    search_item: dict[str, Any],
    detail_item: dict[str, Any],
) -> dict[str, Any]:
    """Compare the ID-bound detail response with the selected search item."""
    reasons: list[str] = []
    search_id = clean_text(search_item.get("id"))
    detail_id = clean_text(detail_item.get("id"))
    if search_id != requested_id:
        reasons.append("search_id_not_bound")
    if detail_id != requested_id:
        reasons.append("detail_id_mismatch")

    search_name_value = clean_text(search_item.get("name"))
    detail_name_value = clean_text(detail_item.get("name"))
    if (
        search_name_value
        and detail_name_value
        and normalize_name(search_name_value) != normalize_name(detail_name_value)
    ):
        reasons.append("name_mismatch")

    search_address_value = candidate_address(search_item)
    detail_address_value = candidate_address(detail_item)
    if search_address_value and detail_address_value:
        same_sigungu, same_detail = address_requirements(
            search_address_value,
            detail_address_value,
        )
        search_sigungu = sigungu_tokens(search_address_value)
        detail_sigungu = sigungu_tokens(detail_address_value)
        explicit_sigungu_conflict = bool(
            search_sigungu
            and detail_sigungu
            and not same_sigungu
        )
        search_address_tokens = address_tokens(search_address_value)
        detail_address_tokens = address_tokens(detail_address_value)
        subset_compatible = bool(
            search_address_tokens
            and detail_address_tokens
            and (
                search_address_tokens.issubset(detail_address_tokens)
                or detail_address_tokens.issubset(search_address_tokens)
            )
        )
        # The list API normally omits 시·군·구 while the ID detail API adds
        # them. A shared 읍면동 or road name proves these are compatible
        # representations; explicit conflicting 시·군·구 still fails.
        if (
            explicit_sigungu_conflict
            or not (same_detail or subset_compatible)
        ):
            reasons.append("address_mismatch")

    search_coordinate = search_item.get("coordinate") or {}
    detail_coordinate = detail_item.get("coordinate") or {}
    detail_distance = haversine_m(
        parse_float(search_coordinate.get("latitude")),
        parse_float(search_coordinate.get("longitude")),
        parse_float(detail_coordinate.get("latitude")),
        parse_float(detail_coordinate.get("longitude")),
    )
    if detail_distance is not None and detail_distance > 30:
        reasons.append("coordinate_mismatch")

    return {
        "status": "mismatch" if reasons else "verified",
        "mismatch": bool(reasons),
        "reasons": reasons,
        "detail_distance_m": round(detail_distance, 2)
        if detail_distance is not None
        else None,
    }


def downgrade_confidence(confidence: str) -> str:
    return {
        "high": "mid",
        "mid": "low",
        "low": "failed",
        "failed": "failed",
    }.get(confidence, "failed")


def empty_result(
    combo: PlaceCombo,
    confidence: str = "failed",
    *,
    verification_status: str = "not_applicable",
    mismatch: bool = False,
    mismatch_reason: str = "",
) -> dict[str, str]:
    return {
        "place_name": combo.place_name,
        "place_address": combo.place_address,
        "orig_lat": combo.orig_lat,
        "orig_lng": combo.orig_lng,
        "naver_place_id": "",
        "naver_url": "",
        "naver_lat": "",
        "naver_lng": "",
        "match_confidence": confidence,
        "matched_name": "",
        "matched_address": "",
        "verification_status": verification_status,
        "mismatch_flag": "true" if mismatch else "false",
        "mismatch_reason": mismatch_reason,
    }


def output_from_match(
    combo: PlaceCombo,
    best: dict[str, Any] | None,
    confidence: str,
    verification: dict[str, Any] | None = None,
) -> dict[str, str]:
    verification = verification or {
        "status": "not_applicable",
        "mismatch": False,
        "reasons": [],
    }
    mismatch = bool(verification.get("mismatch"))
    mismatch_reason = "|".join(verification.get("reasons") or [])
    if best is None or confidence == "failed":
        return empty_result(
            combo,
            verification_status=clean_text(verification.get("status"))
            or "not_applicable",
            mismatch=mismatch,
            mismatch_reason=mismatch_reason,
        )
    item = best["item"]
    place_id = clean_text(item.get("id"))
    result = empty_result(
        combo,
        confidence,
        verification_status=clean_text(verification.get("status"))
        or "not_applicable",
        mismatch=mismatch,
        mismatch_reason=mismatch_reason,
    )
    result.update(
        {
            "naver_place_id": place_id,
            "naver_url": f"https://map.naver.com/p/entry/place/{place_id}",
            "naver_lat": format_coord(best["naver_lat"]),
            "naver_lng": format_coord(best["naver_lng"]),
            "matched_name": clean_text(item.get("name")),
            "matched_address": candidate_address(item),
        }
    )
    return result


class NaverPlaceClient:
    def __init__(
        self,
        *,
        min_delay: float,
        max_delay: float,
        timeout: float,
        max_retries: int,
        block_backoff: float,
        on_block: Callable[[dict[str, Any]], None],
    ) -> None:
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.block_backoff = block_backoff
        self.on_block = on_block
        self.last_request_at = 0.0
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Linux; Android 14; SM-S918N) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/138.0.0.0 Mobile Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.7,en;q=0.6",
                "Content-Type": "application/json",
                "Origin": "https://m.place.naver.com",
                "Referer": "https://m.place.naver.com/place/list",
                "apollographql-client-name": "place-search-service",
            }
        )

    def _pace(self) -> None:
        target_delay = random.uniform(self.min_delay, self.max_delay)
        elapsed = time.monotonic() - self.last_request_at
        if elapsed < target_delay:
            time.sleep(target_delay - elapsed)

    def _block_event(
        self,
        *,
        query: str,
        attempt: int,
        status: int | None,
        detail: str,
    ) -> None:
        self.on_block(
            {
                "at": now_iso(),
                "query": query,
                "attempt": attempt,
                "status": status,
                "detail": detail[:300],
            }
        )

    def search(self, query: str) -> list[dict[str, Any]]:
        payload = {
            "operationName": "getPlacesList",
            "variables": {
                "input": {
                    "query": query,
                    "businessType": "place",
                    "start": 1,
                    "display": 20,
                    "deviceType": "MOBILE",
                }
            },
            "query": GRAPHQL_QUERY,
        }
        last_error = ""

        for attempt in range(1, self.max_retries + 1):
            self._pace()
            try:
                response = self.session.post(
                    ENDPOINT,
                    json=payload,
                    timeout=self.timeout,
                )
                self.last_request_at = time.monotonic()
            except requests.RequestException as exc:
                self.last_request_at = time.monotonic()
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt < self.max_retries:
                    time.sleep(min(20.0, 5.0 * (2 ** (attempt - 1))))
                    continue
                raise RequestError(last_error) from exc

            content_type = response.headers.get("content-type", "")
            body_preview = response.text[:500]
            blocked = response.status_code in {403, 405, 429, 503}
            blocked = blocked or (
                "json" not in content_type.casefold()
                and BLOCK_MESSAGE_RE.search(body_preview) is not None
            )
            if blocked:
                last_error = f"HTTP {response.status_code}: {body_preview}"
                self._block_event(
                    query=query,
                    attempt=attempt,
                    status=response.status_code,
                    detail=body_preview,
                )
                if attempt < self.max_retries:
                    time.sleep(
                        min(60.0, self.block_backoff * (2 ** (attempt - 1)))
                    )
                    continue
                raise BlockedError(last_error)

            if response.status_code >= 500:
                last_error = f"HTTP {response.status_code}: {body_preview}"
                if attempt < self.max_retries:
                    time.sleep(min(30.0, 5.0 * (2 ** (attempt - 1))))
                    continue
                raise RequestError(last_error)

            try:
                data = response.json()
            except ValueError as exc:
                raise RequestError(
                    f"JSON decode error (HTTP {response.status_code}): {body_preview}"
                ) from exc

            errors = data.get("errors") or []
            if errors:
                detail = " | ".join(
                    clean_text(error.get("message")) for error in errors
                )
                if BLOCK_MESSAGE_RE.search(detail):
                    self._block_event(
                        query=query,
                        attempt=attempt,
                        status=response.status_code,
                        detail=detail,
                    )
                    if attempt < self.max_retries:
                        time.sleep(
                            min(60.0, self.block_backoff * (2 ** (attempt - 1)))
                        )
                        continue
                    raise BlockedError(detail)
                raise RequestError(f"GraphQL error: {detail}")

            businesses = (
                (data.get("data") or {})
                .get("placeList", {})
                .get("businesses", {})
            )
            items = businesses.get("items") or []
            return [item for item in items if isinstance(item, dict)]

        raise RequestError(last_error or "unknown request error")

    def detail(self, place_id: str) -> dict[str, Any]:
        """Fetch an ID-addressed place summary and bind all fields to that ID."""
        place_id = clean_text(place_id)
        if not place_id:
            raise RequestError("empty place_id")
        request_label = f"detail:{place_id}"
        url = DETAIL_ENDPOINT.format(place_id=quote(place_id, safe=""))
        headers = {
            "Referer": f"https://map.naver.com/p/entry/place/{place_id}",
            "x-ntm": "1",
        }
        last_error = ""

        for attempt in range(1, self.max_retries + 1):
            self._pace()
            try:
                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=self.timeout,
                )
                self.last_request_at = time.monotonic()
            except requests.RequestException as exc:
                self.last_request_at = time.monotonic()
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt < self.max_retries:
                    time.sleep(min(20.0, 5.0 * (2 ** (attempt - 1))))
                    continue
                raise RequestError(last_error) from exc

            content_type = response.headers.get("content-type", "")
            body_preview = response.text[:500]
            blocked = response.status_code in {403, 405, 429, 503}
            blocked = blocked or (
                "json" not in content_type.casefold()
                and BLOCK_MESSAGE_RE.search(body_preview) is not None
            )
            if blocked:
                last_error = f"HTTP {response.status_code}: {body_preview}"
                self._block_event(
                    query=request_label,
                    attempt=attempt,
                    status=response.status_code,
                    detail=body_preview,
                )
                if attempt < self.max_retries:
                    time.sleep(
                        min(60.0, self.block_backoff * (2 ** (attempt - 1)))
                    )
                    continue
                raise BlockedError(last_error)

            if response.status_code >= 400:
                last_error = f"HTTP {response.status_code}: {body_preview}"
                if response.status_code >= 500 and attempt < self.max_retries:
                    time.sleep(min(30.0, 5.0 * (2 ** (attempt - 1))))
                    continue
                raise RequestError(last_error)

            try:
                data = response.json()
            except ValueError as exc:
                raise RequestError(
                    f"JSON decode error (HTTP {response.status_code}): "
                    f"{body_preview}"
                ) from exc

            errors = data.get("errors") or []
            if errors:
                detail = " | ".join(
                    clean_text(error.get("message")) for error in errors
                )
                raise RequestError(f"detail API error: {detail}")

            item = (data.get("data") or {}).get("placeDetail")
            if not isinstance(item, dict):
                raise RequestError("detail API response has no placeDetail")
            bound = snapshot_item(item)
            if clean_text(bound.get("id")) != place_id:
                # Preserve the response for mismatch reporting, but never borrow
                # any field from another item or a neighboring search result.
                return bound
            return bound

        raise RequestError(last_error or "unknown detail request error")


def process_combo(
    combo: PlaceCombo,
    client: NaverPlaceClient,
    max_query_attempts: int,
    get_detail: Callable[[str], dict[str, Any]],
) -> tuple[dict[str, str], dict[str, Any]]:
    all_items: dict[str, dict[str, Any]] = {}
    queries_used: list[str] = []
    errors: list[str] = []
    precheck_reason = precheck_failure_reason(combo.place_name)
    if precheck_reason:
        return (
            empty_result(
                combo,
                verification_status=f"precheck:{precheck_reason}",
            ),
            {
                "policy_version": MATCH_POLICY_VERSION,
                "precheck_reason": precheck_reason,
                "queries": [],
                "candidate_count": 0,
                "errors": [],
            },
        )

    descriptive = bool(DESCRIPTIVE_RE.search(search_name(combo.place_name)))
    best: dict[str, Any] | None = None

    for query in make_queries(combo, max_query_attempts):
        queries_used.append(query)
        try:
            items = client.search(query)
        except RequestError as exc:
            errors.append(str(exc))
            continue
        for item in items:
            place_id = clean_text(item.get("id"))
            if place_id:
                all_items.setdefault(place_id, item)
        best = choose_candidate(combo, all_items.values())
        confidence = classify_match(combo, best)

        if confidence == "high":
            break
        if confidence == "mid" and best and best["name_score"] >= 0.78:
            break
        if descriptive and confidence == "failed":
            break

    best = choose_candidate(combo, all_items.values())
    confidence = classify_match(combo, best)
    selected_search_item = snapshot_item(best["item"]) if best else None
    verification: dict[str, Any] = {
        "status": "not_matched",
        "mismatch": False,
        "reasons": [],
    }
    authoritative_best = best
    detail_item: dict[str, Any] | None = None

    if best is not None and confidence != "failed":
        place_id = clean_text(best["item"].get("id"))
        try:
            detail_item = get_detail(place_id)
        except RequestError as exc:
            errors.append(f"detail: {exc}")
            verification = {
                "status": "error",
                "mismatch": False,
                "reasons": [],
                "error": str(exc),
            }
            confidence = downgrade_confidence(confidence)
        else:
            verification = verification_result(
                place_id,
                selected_search_item or {},
                detail_item,
            )
            if clean_text(detail_item.get("id")) == place_id:
                authoritative_best = score_candidate(combo, detail_item)
                confidence = classify_match(combo, authoritative_best)
            else:
                confidence = "failed"
            if verification["mismatch"]:
                confidence = downgrade_confidence(confidence)

    output = output_from_match(
        combo,
        authoritative_best,
        confidence,
        verification,
    )
    score_source = authoritative_best
    meta = {
        "policy_version": MATCH_POLICY_VERSION,
        "precheck_reason": "",
        "queries": queries_used,
        "candidate_count": len(all_items),
        "name_score": round(score_source["name_score"], 6)
        if score_source
        else None,
        "address_score": round(score_source["address_score"], 6)
        if score_source
        else None,
        "same_sigungu": score_source["same_sigungu"]
        if score_source
        else None,
        "same_address_detail": score_source["same_address_detail"]
        if score_source
        else None,
        "branches_match": score_source["branches_match"]
        if score_source
        else None,
        "distance_m": round(score_source["distance_m"], 2)
        if score_source and score_source["distance_m"] is not None
        else None,
        "selected_search_item": selected_search_item,
        "detail_item": detail_item,
        "verification": verification,
        "errors": errors,
    }
    return output, meta


def reevaluate_cached_combo(
    combo: PlaceCombo,
    old_record: dict[str, Any],
    get_detail: Callable[[str], dict[str, Any]],
) -> tuple[dict[str, str], dict[str, Any]]:
    old_result = old_record.get("result") or {}
    previous_confidence = (
        clean_text(old_result.get("match_confidence")) or "failed"
    )
    precheck_reason = precheck_failure_reason(combo.place_name)
    if precheck_reason:
        return (
            empty_result(
                combo,
                verification_status=f"precheck:{precheck_reason}",
            ),
            {
                "policy_version": MATCH_POLICY_VERSION,
                "reevaluated_from_cache": True,
                "previous_confidence": previous_confidence,
                "precheck_reason": precheck_reason,
                "queries": list((old_record.get("meta") or {}).get("queries") or []),
                "candidate_count": int(
                    (old_record.get("meta") or {}).get("candidate_count") or 0
                ),
                "errors": [],
            },
        )

    place_id = clean_text(old_result.get("naver_place_id"))
    if not place_id:
        return (
            empty_result(combo, verification_status="not_matched"),
            {
                "policy_version": MATCH_POLICY_VERSION,
                "reevaluated_from_cache": True,
                "previous_confidence": previous_confidence,
                "precheck_reason": "",
                "queries": list((old_record.get("meta") or {}).get("queries") or []),
                "candidate_count": int(
                    (old_record.get("meta") or {}).get("candidate_count") or 0
                ),
                "errors": list(
                    (old_record.get("meta") or {}).get("errors") or []
                ),
            },
        )

    old_meta = old_record.get("meta") or {}
    selected_search_item = old_meta.get("selected_search_item")
    if not isinstance(selected_search_item, dict):
        selected_search_item = item_from_result(old_result)
    selected_search_item = snapshot_item(selected_search_item)
    errors = list(old_meta.get("errors") or [])
    detail_item: dict[str, Any] | None = None
    verification: dict[str, Any]

    try:
        detail_item = get_detail(place_id)
    except RequestError as exc:
        errors.append(f"detail: {exc}")
        verification = {
            "status": "error",
            "mismatch": False,
            "reasons": [],
            "error": str(exc),
        }
        best = score_candidate(combo, selected_search_item)
        confidence = downgrade_confidence(classify_match(combo, best))
    else:
        verification = verification_result(
            place_id,
            selected_search_item,
            detail_item,
        )
        if clean_text(detail_item.get("id")) == place_id:
            best = score_candidate(combo, detail_item)
            confidence = classify_match(combo, best)
        else:
            best = score_candidate(combo, selected_search_item)
            confidence = "failed"
        if verification["mismatch"]:
            confidence = downgrade_confidence(confidence)

    output = output_from_match(combo, best, confidence, verification)
    meta = {
        "policy_version": MATCH_POLICY_VERSION,
        "reevaluated_from_cache": True,
        "previous_confidence": previous_confidence,
        "precheck_reason": "",
        "queries": list(old_meta.get("queries") or []),
        "candidate_count": int(old_meta.get("candidate_count") or 0),
        "name_score": round(best["name_score"], 6),
        "address_score": round(best["address_score"], 6),
        "same_sigungu": best["same_sigungu"],
        "same_address_detail": best["same_address_detail"],
        "branches_match": best["branches_match"],
        "distance_m": round(best["distance_m"], 2)
        if best["distance_m"] is not None
        else None,
        "selected_search_item": selected_search_item,
        "detail_item": detail_item,
        "verification": verification,
        "errors": errors,
    }
    return output, meta


def load_cache(
    path: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    records: dict[str, dict[str, Any]] = {}
    details: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return records, details
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                print(
                    f"[cache] 손상된 마지막/중간 행 무시: {path}:{line_number}",
                    file=sys.stderr,
                )
                continue
            if clean_text(record.get("kind")) == "place_detail":
                place_id = clean_text(record.get("place_id"))
                item = record.get("item")
                if place_id and isinstance(item, dict):
                    details[place_id] = record
                continue
            key = clean_text(record.get("key"))
            result = record.get("result")
            if key and isinstance(result, dict):
                records[key] = record
    return records, details


def atomic_json_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def write_output(
    path: Path,
    combos: list[PlaceCombo],
    records: dict[str, dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
            writer.writeheader()
            for combo in combos:
                record = records.get(combo.key)
                if record:
                    writer.writerow(
                        {
                            field: clean_text(record["result"].get(field))
                            for field in OUTPUT_FIELDS
                        }
                    )
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def confidence_counts(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(
        clean_text(record.get("result", {}).get("match_confidence")) or "unknown"
        for record in records
    )
    return {
        confidence: counts.get(confidence, 0)
        for confidence in ("high", "mid", "low", "failed")
    }


def verification_counts(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(
        clean_text(record.get("result", {}).get("verification_status"))
        or "unknown"
        for record in records
    )
    return dict(sorted(counts.items()))


def build_state(
    *,
    prior: dict[str, Any],
    stats: dict[str, int],
    records: dict[str, dict[str, Any]],
    target_keys: set[str],
    status: str,
    blocked_events: list[dict[str, Any]],
    started_at: str,
    last_error: str = "",
    reevaluation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target_records = [
        record for key, record in records.items() if key in target_keys
    ]
    return {
        "status": status,
        "started_at": started_at,
        "updated_at": now_iso(),
        "completed_at": now_iso() if status == "completed" else "",
        "input_stats": stats,
        "processed_combos": len(target_records),
        "remaining_combos": max(0, len(target_keys) - len(target_records)),
        "confidence": confidence_counts(target_records),
        "verification": verification_counts(target_records),
        "verification_error_count": sum(
            clean_text(
                record.get("result", {}).get("verification_status")
            )
            == "error"
            for record in target_records
        ),
        "mismatch_count": sum(
            clean_text(record.get("result", {}).get("mismatch_flag"))
            == "true"
            for record in target_records
        ),
        "match_policy_version": MATCH_POLICY_VERSION,
        "reevaluation": reevaluation or prior.get("reevaluation") or {},
        "blocked_occurred": bool(
            blocked_events or prior.get("blocked_occurred")
        ),
        "blocked_event_count": int(prior.get("blocked_event_count") or 0)
        + len(blocked_events),
        "blocked_events": (
            list(prior.get("blocked_events") or []) + blocked_events
        )[-50:],
        "last_error": last_error,
    }


def read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="TOP120/영화 촬영지의 실제 네이버 플레이스 URL·좌표 수집"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="이번 실행 대상 수 제한(0=전체, 샘플 검증용)",
    )
    parser.add_argument("--min-delay", type=float, default=1.5)
    parser.add_argument("--max-delay", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--max-retries", type=int, default=4)
    parser.add_argument("--block-backoff", type=float, default=30.0)
    parser.add_argument("--max-query-attempts", type=int, default=3)
    parser.add_argument("--flush-every", type=int, default=10)
    parser.add_argument(
        "--retry-failures",
        action="store_true",
        help="캐시의 failed 건도 다시 조회",
    )
    parser.add_argument(
        "--print-input-stats",
        action="store_true",
        help="입력 통계만 출력하고 종료",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.limit < 0:
        raise SystemExit("--limit은 0 이상이어야 합니다.")
    if args.min_delay < 0 or args.max_delay < args.min_delay:
        raise SystemExit("지연 범위가 잘못되었습니다.")
    if args.max_retries < 1:
        raise SystemExit("--max-retries는 1 이상이어야 합니다.")
    if args.max_query_attempts < 1 or args.max_query_attempts > 3:
        raise SystemExit("--max-query-attempts는 1~3이어야 합니다.")
    if args.flush_every < 1:
        raise SystemExit("--flush-every는 1 이상이어야 합니다.")


def main() -> int:
    args = parse_args()
    validate_args(args)
    combos, stats = load_combos()
    if args.limit:
        combos = combos[: args.limit]
        stats = {**stats, "run_limit": args.limit}
    print(json.dumps(stats, ensure_ascii=False), flush=True)
    if args.print_input_stats:
        return 0

    args.cache.parent.mkdir(parents=True, exist_ok=True)
    records, detail_records = load_cache(args.cache)
    target_keys = {combo.key for combo in combos}
    prior_state = read_state(args.state)
    started_at = now_iso()
    new_block_events: list[dict[str, Any]] = []
    reevaluation_state: dict[str, Any] = {}
    stop_requested = False

    def request_stop(signum: int, _frame: Any) -> None:
        nonlocal stop_requested
        stop_requested = True
        print(f"[signal] {signum} 수신: 현재 건 저장 후 종료", flush=True)

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    def on_block(event: dict[str, Any]) -> None:
        new_block_events.append(event)
        print(
            f"[block] status={event['status']} attempt={event['attempt']} "
            f"query={event['query']!r}",
            flush=True,
        )
        state = build_state(
            prior=prior_state,
            stats=stats,
            records=records,
            target_keys=target_keys,
            status="running_with_backoff",
            blocked_events=new_block_events,
            started_at=started_at,
            reevaluation=reevaluation_state,
        )
        atomic_json_write(args.state, state)

    client = NaverPlaceClient(
        min_delay=args.min_delay,
        max_delay=args.max_delay,
        timeout=args.timeout,
        max_retries=args.max_retries,
        block_backoff=args.block_backoff,
        on_block=on_block,
    )

    write_output(args.output, combos, records)

    processed_this_run = 0
    detail_requests_this_run = 0
    last_error = ""
    exit_status = "completed"
    exit_code = 0

    with args.cache.open("a", encoding="utf-8") as cache_handle:
        def append_cache_record(record: dict[str, Any]) -> None:
            cache_handle.write(
                json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                + "\n"
            )
            cache_handle.flush()

        def get_detail(place_id: str) -> dict[str, Any]:
            nonlocal detail_requests_this_run
            place_id = clean_text(place_id)
            cached = detail_records.get(place_id)
            if cached and isinstance(cached.get("item"), dict):
                return snapshot_item(cached["item"])
            item = client.detail(place_id)
            detail_record = {
                "kind": "place_detail",
                "place_id": place_id,
                "item": snapshot_item(item),
                "fetched_at": now_iso(),
            }
            append_cache_record(detail_record)
            detail_records[place_id] = detail_record
            detail_requests_this_run += 1
            return detail_record["item"]

        def flush_progress(phase: str) -> None:
            os.fsync(cache_handle.fileno())
            write_output(args.output, combos, records)
            state = build_state(
                prior=prior_state,
                stats=stats,
                records=records,
                target_keys=target_keys,
                status=phase,
                blocked_events=new_block_events,
                started_at=started_at,
                reevaluation=reevaluation_state,
            )
            atomic_json_write(args.state, state)
            counts = state["confidence"]
            print(
                f"[progress:{phase}] "
                f"{state['processed_combos']}/{len(combos)} "
                f"high={counts['high']} mid={counts['mid']} "
                f"low={counts['low']} failed={counts['failed']} "
                f"details={len(detail_records)}",
                flush=True,
            )

        try:
            refresh: list[tuple[PlaceCombo, dict[str, Any]]] = []
            for combo in combos:
                record = records.get(combo.key)
                if record is None:
                    continue
                policy_version = int(
                    (record.get("meta") or {}).get("policy_version") or 0
                )
                verification_status = clean_text(
                    (record.get("result") or {}).get("verification_status")
                )
                if (
                    policy_version != MATCH_POLICY_VERSION
                    or verification_status == "error"
                ):
                    refresh.append((combo, record))

            if refresh:
                refresh_keys = [combo.key for combo, _record in refresh]
                before_records = [record for _combo, record in refresh]
                reevaluation_state = {
                    "status": "running",
                    "policy_version": MATCH_POLICY_VERSION,
                    "target_records": len(refresh),
                    "processed_records": 0,
                    "before": confidence_counts(before_records),
                    "after": {},
                    "old_high_downgraded": 0,
                    "detail_cache_before": len(detail_records),
                    "detail_cache_after": len(detail_records),
                }
                print(
                    f"[reevaluate] target={len(refresh)} "
                    f"details_cached={len(detail_records)}",
                    flush=True,
                )

                for combo, old_record in refresh:
                    if stop_requested:
                        exit_status = "interrupted"
                        exit_code = 130
                        break
                    result, meta = reevaluate_cached_combo(
                        combo,
                        old_record,
                        get_detail,
                    )
                    record = {
                        "key": combo.key,
                        "combo": asdict(combo),
                        "result": result,
                        "meta": meta,
                        "processed_at": now_iso(),
                    }
                    append_cache_record(record)
                    records[combo.key] = record
                    processed_this_run += 1
                    reevaluation_state["processed_records"] += 1
                    if (
                        clean_text(
                            old_record.get("result", {}).get(
                                "match_confidence"
                            )
                        )
                        == "high"
                        and clean_text(result.get("match_confidence"))
                        != "high"
                    ):
                        reevaluation_state["old_high_downgraded"] += 1
                    if processed_this_run % args.flush_every == 0:
                        reevaluation_state["after"] = confidence_counts(
                            records[key]
                            for key in refresh_keys
                            if key in records
                        )
                        reevaluation_state["detail_cache_after"] = len(
                            detail_records
                        )
                        flush_progress("reevaluating")

                reevaluation_state["after"] = confidence_counts(
                    records[key] for key in refresh_keys if key in records
                )
                reevaluation_state["detail_cache_after"] = len(detail_records)
                reevaluation_state["status"] = (
                    "completed"
                    if reevaluation_state["processed_records"] == len(refresh)
                    else "interrupted"
                )
                flush_progress("running")
                print(
                    "[reevaluate-done] "
                    + json.dumps(reevaluation_state, ensure_ascii=False),
                    flush=True,
                )

            pending: list[PlaceCombo] = []
            if exit_status == "completed":
                for combo in combos:
                    record = records.get(combo.key)
                    if record is None:
                        pending.append(combo)
                    elif (
                        args.retry_failures
                        and clean_text(
                            record["result"].get("match_confidence")
                        )
                        == "failed"
                    ):
                        pending.append(combo)

            print(
                f"[start] target={len(combos)} "
                f"cached={len(combos) - len(pending)} "
                f"pending={len(pending)} output={args.output}",
                flush=True,
            )

            for combo in pending:
                if stop_requested:
                    exit_status = "interrupted"
                    exit_code = 130
                    break

                result, meta = process_combo(
                    combo,
                    client,
                    args.max_query_attempts,
                    get_detail,
                )
                record = {
                    "key": combo.key,
                    "combo": asdict(combo),
                    "result": result,
                    "meta": meta,
                    "processed_at": now_iso(),
                }
                append_cache_record(record)
                records[combo.key] = record
                processed_this_run += 1

                if processed_this_run % args.flush_every == 0:
                    flush_progress("running")
        except BlockedError as exc:
            exit_status = "blocked"
            exit_code = 75
            last_error = str(exc)
            print(f"[blocked-stop] {last_error}", file=sys.stderr, flush=True)
        except KeyboardInterrupt:
            exit_status = "interrupted"
            exit_code = 130
            last_error = "KeyboardInterrupt"
        finally:
            cache_handle.flush()
            os.fsync(cache_handle.fileno())
            write_output(args.output, combos, records)
            if len([key for key in target_keys if key in records]) < len(target_keys):
                if exit_status == "completed":
                    exit_status = "interrupted"
                    exit_code = 130
            verification_errors = sum(
                clean_text(
                    records[key].get("result", {}).get(
                        "verification_status"
                    )
                )
                == "error"
                for key in target_keys
                if key in records
            )
            if exit_status == "completed" and verification_errors:
                exit_status = "verification_incomplete"
                exit_code = 74
                last_error = (
                    f"{verification_errors} detail verification request(s) "
                    "remain unresolved"
                )
            final_state = build_state(
                prior=prior_state,
                stats=stats,
                records=records,
                target_keys=target_keys,
                status=exit_status,
                blocked_events=new_block_events,
                started_at=started_at,
                last_error=last_error,
                reevaluation=reevaluation_state,
            )
            final_state["detail_cache_records"] = len(detail_records)
            final_state["detail_requests_this_run"] = (
                detail_requests_this_run
            )
            atomic_json_write(args.state, final_state)

    print(json.dumps(final_state, ensure_ascii=False), flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
