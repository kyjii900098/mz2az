from __future__ import annotations

import csv
import json
import re
import sys
import time
from collections import OrderedDict
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from lxml import html


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "01_Raw/정승길/data/조합작업/TOP120완성/장면설명대상_A.csv"
SESSION = Path(__file__).resolve().parent
RAW = SESSION / "sources/raw"
SEARCH_RESULTS = SESSION / "sources/search_results.jsonl"
FAILED = SESSION / "sources/failed_urls.txt"

PREFERRED = {
    "redmee2",
    "tammara",
    "hsc_one1",
    "dalkomi84",
    "location_info",
    "ryu71s",
}


def input_titles() -> list[str]:
    with INPUT.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return list(OrderedDict.fromkeys(r["title"] for r in rows))


def normalize_post_url(url: str) -> tuple[str, str, str] | None:
    parsed = urlparse(url)
    if parsed.netloc not in {"blog.naver.com", "m.blog.naver.com"}:
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2 and parts[1].isdigit():
        return parts[0], parts[1], f"https://blog.naver.com/{parts[0]}/{parts[1]}"
    if parsed.path.endswith("PostView.naver"):
        q = parse_qs(parsed.query)
        blog_id = q.get("blogId", [""])[0]
        log_no = q.get("logNo", [""])[0]
        if blog_id and log_no.isdigit():
            return blog_id, log_no, f"https://blog.naver.com/{blog_id}/{log_no}"
    return None


def naver_search(session: requests.Session, query: str) -> list[dict[str, str]]:
    response = session.get(
        "https://search.naver.com/search.naver",
        params={"where": "view", "query": query},
        timeout=25,
    )
    response.raise_for_status()
    doc = html.fromstring(response.text)
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in doc.xpath("//a[@href]"):
        normalized = normalize_post_url(anchor.get("href", ""))
        if not normalized:
            continue
        blog_id, log_no, url = normalized
        if url in seen:
            continue
        seen.add(url)
        title = " ".join(anchor.text_content().split())
        results.append(
            {
                "query": query,
                "blog_id": blog_id,
                "log_no": log_no,
                "url": url,
                "result_text": title,
                "preferred": str(blog_id in PREFERRED).lower(),
            }
        )
    return results


def fetch_post(session: requests.Session, result: dict[str, str], show: str) -> dict[str, str]:
    blog_id = result["blog_id"]
    log_no = result["log_no"]
    url = f"https://blog.naver.com/PostView.naver?blogId={blog_id}&logNo={log_no}"
    response = session.get(url, timeout=25)
    response.raise_for_status()
    doc = html.fromstring(response.text)
    title = " ".join(doc.xpath("//title/text()")).strip()
    containers = doc.xpath(
        '//*[contains(concat(" ", normalize-space(@class), " "), " se-main-container ")]'
    )
    if not containers:
        containers = doc.xpath('//*[@id="postViewArea"]')
    text = "\n".join(
        line
        for container in containers
        for line in (" ".join(x.split()) for x in container.text_content().splitlines())
        if line
    )
    text = re.sub(r"\n{3,}", "\n\n", text)
    safe = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", show).strip("_")
    path = RAW / safe / f"{blog_id}_{log_no}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"TITLE: {title}\nURL: {result['url']}\nBLOG_ID: {blog_id}\n\n{text}\n",
        encoding="utf-8",
    )
    return {
        **result,
        "show": show,
        "post_title": title,
        "raw_path": str(path.relative_to(ROOT)),
        "text_chars": str(len(text)),
    }


def main() -> None:
    requested = sys.argv[1:]
    titles = requested or input_titles()
    RAW.mkdir(parents=True, exist_ok=True)
    SEARCH_RESULTS.parent.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0 Safari/537.36"
            )
        }
    )
    all_records: list[dict[str, str]] = []
    failures: list[str] = []
    for index, show in enumerate(titles, 1):
        by_url: OrderedDict[str, dict[str, str]] = OrderedDict()
        queries = [f'"{show}" 촬영지', f'"{show}" 드라마 촬영지 회차']
        for query in queries:
            try:
                for result in naver_search(session, query):
                    by_url.setdefault(result["url"], result)
            except Exception as exc:
                failures.append(f"SEARCH\t{query}\t{type(exc).__name__}: {exc}")
            time.sleep(0.15)

        ranked = sorted(
            by_url.values(),
            key=lambda r: (r["blog_id"] not in PREFERRED, list(by_url).index(r["url"])),
        )[:20]
        collected = 0
        for result in ranked:
            try:
                record = fetch_post(session, result, show)
                all_records.append(record)
                collected += 1
            except Exception as exc:
                failures.append(f"FETCH\t{result['url']}\t{type(exc).__name__}: {exc}")
            time.sleep(0.08)
        print(f"[{index:02d}/{len(titles):02d}] {show}: {len(by_url)} results, {collected} fetched")

    with SEARCH_RESULTS.open("w", encoding="utf-8") as f:
        for record in all_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    FAILED.write_text("\n".join(failures) + ("\n" if failures else ""), encoding="utf-8")
    print(f"saved {len(all_records)} posts; failures={len(failures)}")


if __name__ == "__main__":
    main()
