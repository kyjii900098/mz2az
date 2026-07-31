#!/usr/bin/env python3
"""Discover and cache source text for TOP120 scene-description research.

The script is deliberately read-only with respect to the source CSV and does
not touch the deliverable CSV.  It stores resumable research artifacts beside
this file.
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "조합작업/TOP120완성/장면설명대상_B.csv"
RECRAWL = ROOT / "조합작업/전수재수집"
HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
INDEX = HERE / "source_index.json"
PREFERRED = {"redmee2", "tammara", "hsc_one1", "dalkomi84", "location_info", "ryu71s"}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138 Safari/537.36"
    )
}


def compact(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def title_key(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", (value or "").lower())


def canonical_title(value: str) -> str:
    key = title_key(value)
    aliases = {
        "다이루어질지니": "다 이루어질지니",
        "유미의세포들3": "유미의 세포들 3",
        "판사이한영": "판사 이한영",
        "반짝이는워터멜론": "반짝이는 워터멜론",
        "당신이잠든사이에": "당신이 잠든 사이에",
    }
    return aliases.get(key, value)


def get(url: str) -> str:
    digest = hashlib.sha256(url.encode()).hexdigest()
    cache_path = CACHE / f"{digest}.html"
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8", errors="replace")
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    text = response.text
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(text, encoding="utf-8")
    time.sleep(0.12)
    return text


def naver_urls(search_html: str) -> list[str]:
    pattern = r"https?://(?:m\.)?blog\.naver\.com/[A-Za-z0-9_-]+/[0-9]+"
    found: list[str] = []
    for raw in re.findall(pattern, search_html):
        url = html.unescape(raw).replace("https://m.blog.naver.com/", "https://blog.naver.com/")
        if url not in found:
            found.append(url)
    return found


def naver_author(url: str) -> str:
    match = re.search(r"blog\.naver\.com/([A-Za-z0-9_-]+)/", url)
    return match.group(1) if match else ""


def seed_urls(title: str) -> list[str]:
    wanted = title_key(title)
    urls: list[str] = []
    for path in RECRAWL.glob("재수집_*.csv"):
        try:
            with path.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
        except (OSError, UnicodeError):
            continue
        if not rows:
            continue
        found_title = title_key(rows[0].get("title", ""))
        if found_title != wanted:
            continue
        for row in rows:
            for url in (row.get("source_url") or "").split(";"):
                url = url.strip()
                if url and url not in urls:
                    urls.append(url)
    return urls


def parse_naver(url: str) -> dict:
    author = naver_author(url)
    mobile = url.replace("https://blog.naver.com/", "https://m.blog.naver.com/")
    soup = BeautifulSoup(get(mobile), "html.parser")
    node = soup.select_one(".se-main-container") or soup.select_one("#postViewArea") or soup
    strings = [compact(item) for item in node.stripped_strings]
    strings = [item for item in strings if item]
    page_title = compact((soup.title.string if soup.title else "") or "")
    return {
        "url": url,
        "kind": "naver_blog",
        "author": author,
        "preferred": author in PREFERRED,
        "page_title": page_title,
        "strings": strings,
    }


def parse_generic(url: str) -> dict:
    soup = BeautifulSoup(get(url), "html.parser")
    for tag in soup.select("script, style, noscript, svg"):
        tag.decompose()
    page_title = compact((soup.title.string if soup.title else "") or "")
    strings = [compact(item) for item in soup.stripped_strings]
    strings = [item for item in strings if item]
    return {
        "url": url,
        "kind": "web",
        "author": "",
        "preferred": False,
        "page_title": page_title,
        "strings": strings,
    }


def discover(title: str) -> list[str]:
    if os.environ.get("TOP120_SEED_ONLY") == "1":
        return []
    # Current-year context is retained in every query per the research protocol.
    patterns = [
        f'"{title}" 촬영지 장면 회차 2026',
        f'"{title}" 촬영지 1화 2화 2026',
        f'"{title}" 촬영지 3화 4화 2026',
        f'"{title}" 촬영지 5화 6화 2026',
        f'"{title}" 촬영지 7화 8화 2026',
        f'"{title}" 촬영지 9화 10화 2026',
        f'"{title}" 촬영지 11화 12화 2026',
        f'"{title}" 촬영지 13화 14화 16화 2026',
    ]
    found: list[str] = []
    for query in patterns:
        url = "https://search.naver.com/search.naver?where=view&query=" + quote(query)
        try:
            urls = naver_urls(get(url))
        except Exception as exc:  # keep the crawl resumable
            print(f"search failed: {query}: {exc}", file=sys.stderr)
            continue
        for item in urls:
            if item not in found:
                found.append(item)
    return found


def main() -> None:
    with INPUT.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[canonical_title(row["title"])].append(row)

    if INDEX.exists():
        index = json.loads(INDEX.read_text(encoding="utf-8"))
    else:
        index = {}

    selected = sys.argv[1:] or list(grouped)
    for raw_title in selected:
        title = canonical_title(raw_title)
        if title not in grouped:
            print(f"skip unknown title: {raw_title}", file=sys.stderr)
            continue
        discovered = discover(title)
        seeded = seed_urls(title)
        urls: list[str] = []
        for url in seeded + discovered:
            if url not in urls:
                urls.append(url)

        # Fetch preferred Naver sources, all seeded Naver sources, and user-
        # preferred generic domains.  Other discovered personal blogs remain
        # recorded as leads but are not treated as evidence.
        seeded_set = set(seeded)
        accepted: list[dict] = []
        leads: list[str] = []
        for url in urls:
            try:
                if "blog.naver.com/" in url:
                    author = naver_author(url)
                    if author in PREFERRED or url in seeded_set:
                        accepted.append(parse_naver(url))
                    else:
                        leads.append(url)
                elif url in seeded_set and any(
                    domain in url
                    for domain in (
                        "traveltodrama.com",
                        "koreandramalocation.com",
                        "korean.visitkorea.or.kr",
                        "english.visitkorea.or.kr",
                        "mediahub.seoul.go.kr",
                        "opengov.seoul.go.kr",
                        "yna.co.kr",
                        "mk.co.kr",
                    )
                ):
                    accepted.append(parse_generic(url))
                else:
                    leads.append(url)
            except Exception as exc:
                accepted.append({"url": url, "error": str(exc)})
        index[title] = {
            "row_count": len(grouped[title]),
            "queries": 0 if os.environ.get("TOP120_SEED_ONLY") == "1" else 8,
            "sources": accepted,
            "leads": leads,
        }
        INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            f"{title}: rows={len(grouped[title])} "
            f"sources={len(accepted)} leads={len(leads)}"
        )


if __name__ == "__main__":
    main()
